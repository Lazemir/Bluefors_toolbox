import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional, Unpack

import requests
from qcodes.instrument import (
    Instrument,
    InstrumentBaseKWArgs,
)
from requests import Response

from scr.exceptions import APIError, OutdatedError
from scr.instrument_drivers.bluefors.cryomech import CPA
from scr.instrument_drivers.bluefors.edwards_nXDS import EdwardsNXDS
from scr.instrument_drivers.bluefors.lakeshore_model_372 import Lakeshore
from scr.instrument_drivers.bluefors.maxigauge import Maxigauge
from scr.instrument_drivers.bluefors.pfeiffer_TC400 import PfeifferTC400
from scr.instrument_drivers.bluefors.control_unit import ControlUnit
from scr.instrument_drivers.bluefors.vc import VC


def _get_value_from_response(data, target: str) -> Any:
    try:
        latest_value = data["data"][f"{target}"]["content"]["latest_value"]
        value: float = latest_value["value"]
        is_outdated: bool = latest_value["outdated"]
        synchronization_status: str = latest_value["status"]
        if is_outdated:
            timestamp_ms: int = latest_value["date"]
            raise OutdatedError(datetime.fromtimestamp(timestamp_ms / 1_000))
        if synchronization_status != "SYNCHRONIZED":
            raise APIError("Data not synchronized", status_code=500)
        return value
    except KeyError as e:
        raise APIError(f"Data not found: {e}", status_code=404)


def _get_notifications_from_response(data) -> list[dict[str, Any]]:
    try:
        notifications = data["data"]["notifications"]
    except KeyError as e:
        raise APIError(f"Data not found: {e}", status_code=404)

    if not isinstance(notifications, list):
        raise APIError("Invalid notifications payload", status_code=500)

    return notifications


class BlueforsLD400(Instrument):
    N_TRY = 5

    def __init__(self,
                 name: str,
                 api_key: str,
                 certificate_path: Optional[str] = None,
                 ip: Optional[str] = "localhost",
                 port: Optional[int] = 49098,
                 expected_api_version: Optional[str] = "v2.0",
                 **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(name, **kwargs)
        self.__base_url = f"https://{ip}:{port}"
        self.__query_string = f'prettyprint=1&key={api_key}'
        self._certificate_path = certificate_path or False

        self.__data: Optional[Response] = None
        self.__system_info: Optional[dict[str, Any]] = None
        self.__api_version: Optional[str] = None
        self.__system_version: Optional[str] = None
        self.__system_name: Optional[str] = None

        self.add_submodule('cpa', CPA(self, 'cpa'))
        self.add_submodule('lakeshore', Lakeshore(self, 'lakeshore'))
        self.add_submodule('maxigauge', Maxigauge(self, 'maxigauge'))
        self.add_submodule('vc', VC(self, 'vc'))
        self.add_submodule('tc400', PfeifferTC400(self, 'tc400'))
        self.add_submodule('nxds', EdwardsNXDS(self, 'nxds'))
        self.add_submodule('control_unit', ControlUnit(self, 'control_unit'))

        self._verify_api_version(expected_api_version)

    def _build_endpoint_url(self, endpoint: str) -> str:
        endpoint = endpoint.strip('/')
        return f"{self.__base_url}/{endpoint}" if endpoint else self.__base_url

    def _build_request_uri(self, base_url: str, target: str = '') -> str:
        endpoint = f'{target}'.replace('.', '/').strip('/')
        url = f'{base_url}/{endpoint}' if endpoint else base_url
        return f"{url}?{self.__query_string}"

    def _get_value_request(self, target: str) -> Response:
        value_url = self._build_endpoint_url('values')
        return self._get_request(value_url, target)

    def _get_request(self, base_url: str, target: str = '') -> Response:
        request_uri = self._build_request_uri(base_url, target)
        response = requests.get(request_uri,
                                headers={"Content-Type": "application/json"},
                                verify=self._certificate_path)
        response.raise_for_status()
        return response

    def _post_request(self, target: str, **content) -> Response:
        value_url = self._build_endpoint_url('values')
        request_uri = self._build_request_uri(value_url)
        body = {
            "data": {
                f'{target}': {
                    "content": content
                }
            }
        }

        response = requests.post(request_uri,
                                 data=json.dumps(body),
                                 headers={"Content-Type": "application/json"},
                                 verify=self._certificate_path)
        response.raise_for_status()
        return response

    def _get_notifications_request(self) -> Response:
        notifications_url = self._build_endpoint_url('notifications')
        return self._get_request(notifications_url)

    def _get_system_request(self) -> Response:
        system_url = self._build_endpoint_url('system')
        return self._get_request(system_url)

    def _verify_api_version(self, expected_version: Optional[str]) -> None:
        response = self._get_system_request()
        try:
            system_info = response.json()["data"]
        except (KeyError, ValueError) as error:
            raise APIError(f"Unable to read system information: {error}", status_code=500)

        if not isinstance(system_info, dict):
            raise APIError("Invalid system information payload", status_code=500)

        api_version = system_info.get("api_version")
        if api_version is None:
            raise APIError("API version is not reported by the system", status_code=500)

        self.__system_info = system_info
        self.__api_version = api_version
        self.__system_version = system_info.get("system_version")
        self.__system_name = system_info.get("system_name")

        if expected_version is None:
            return

        if api_version != expected_version:
            raise APIError(
                f"API version mismatch. Expected {expected_version} but got {api_version}",
                status_code=500,
            )

    def call_method(self, target: str) -> None:
        self._post_request(target, call=1)

    def get_value(self, target: str) -> Any:
        data = self.__data or self._get_value_request(target)
        try:
            return _get_value_from_response(data.json(), target)
        except OutdatedError as e:
            for i in range(self.N_TRY):
                try:
                    data = self._get_value_request(target)
                    return _get_value_from_response(data.json(), target)
                except OutdatedError:
                    continue
            raise e

    def set_value(self, target: str, value: Any) -> None:
        self._post_request(target, value=value)

    def get_notifications(self, *, seen: Optional[bool] = None) -> list[dict[str, Any]]:
        response = self._get_notifications_request()
        notifications = _get_notifications_from_response(response.json())
        if seen is None:
            return notifications
        return [notification for notification in notifications if notification.get('seen') is seen]

    @contextmanager
    def read_session(self):
        self.__data = self._get_value_request('')
        try:
            yield
        finally:
            self.__data = None

    @property
    def api_version(self) -> Optional[str]:
        return self.__api_version

    @property
    def system_version(self) -> Optional[str]:
        return self.__system_version

    @property
    def system_name(self) -> Optional[str]:
        return self.__system_name

    @property
    def system_info(self) -> Optional[dict[str, Any]]:
        return self.__system_info

