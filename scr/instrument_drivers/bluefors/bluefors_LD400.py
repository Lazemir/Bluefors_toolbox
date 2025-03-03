import json
from typing import Any, Optional, Unpack

import requests
from qcodes.instrument import (
    Instrument,
    InstrumentBaseKWArgs,
)
from requests import Response

from scr.exceptions import APIError
from scr.instrument_drivers.bluefors.cryomech import CPA
from scr.instrument_drivers.bluefors.edwards_nXDS import EdwardsNXDS
from scr.instrument_drivers.bluefors.lakeshore_model_372 import Lakeshore
from scr.instrument_drivers.bluefors.maxigauge import Maxigauge
from scr.instrument_drivers.bluefors.pfeiffer_TC400 import PfeifferTC400
from scr.instrument_drivers.bluefors.control_unit import ControlUnit
from scr.instrument_drivers.bluefors.vc import VC


def _get_value_from_response(data, target: str) -> Any:
    try:
        latest_valid_value = data["data"][f"{target}"]["content"]["latest_valid_value"]
        value = latest_valid_value["value"]
        synchronization_status = latest_valid_value["status"]
        if synchronization_status != "SYNCHRONIZED":
            raise APIError("Data not synchronized", status_code=500)
        return value
    except KeyError as e:
        raise APIError(f"Data not found: {e}", status_code=404)


class BlueforsLD400(Instrument):
    def __init__(self,
                 name: str,
                 api_key: str,
                 certificate_path: Optional[str] = None,
                 ip: Optional[str] = "localhost",
                 port: Optional[int] = 49098,
                 **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(name, **kwargs)
        self.__url = f'https://{ip}:{port}/values'
        self.__uri_vars = f'?prettyprint=1&key={api_key}'
        self._certificate_path = certificate_path or False

        self.add_submodule('cpa', CPA(self, 'cpa'))
        self.add_submodule('lakeshore', Lakeshore(self, 'lakeshore'))
        self.add_submodule('maxigauge', Maxigauge(self, 'maxigauge'))
        self.add_submodule('vc', VC(self, 'vc'))
        self.add_submodule('tc400', PfeifferTC400(self, 'tc400'))
        self.add_submodule('nxds', EdwardsNXDS(self, 'nxds'))
        self.add_submodule('control_unit', ControlUnit(self, 'control_unit'))

    def _get_request_uri(self, target: str) -> str:
        endpoint = f'{target}'.replace('.', '/')
        return f"{self.__url}/{endpoint}/{self.__uri_vars}"

    def _get_value_request(self, target: str) -> Response:
        request_uri = self._get_request_uri(target)
        response = requests.get(request_uri,
                                headers={"Content-Type": "application/json"},
                                verify=self._certificate_path)
        response.raise_for_status()
        return response

    def _post_request(self, target: str, **content) -> Response:
        request_uri = f'{self.__url}/{self.__uri_vars}'
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

    def call_method(self, target: str) -> None:
        self._post_request(target, call=1)

    def get_value(self, target: str) -> Any:
        data = self._get_value_request(target)
        return _get_value_from_response(data.json(), target)

    def set_value(self, target: str, value: Any) -> None:
        self._post_request(target, value=value)
