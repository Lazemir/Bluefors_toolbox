from enum import verify
from typing import Optional
import requests
from .exceptions import PIDConfigException, APIError


class BlueforsAPIExporter:
    def __init__(
            self,
            ip: Optional[str] = "localhost",
            port: Optional[int] = 49098,
            key: Optional[str] = None,
            certificate_path: Optional[str] = None):
        self.ip = ip
        self.port = port
        self.key = key
        self.certificate_path = certificate_path

    def _get_request_path(self, target: str):
        if self.key is None:
            raise PIDConfigException("No key provided for value request.")
        return f"https://{self.ip}:{self.port}/values/{target.replace('.', '/')}/?prettyprint=1&key={self.key}"

    def _get_value_request(self, target):
        request_path = self._get_request_path(target)
        try:
            if self.certificate_path is not None:
                response = requests.get(request_path, verify=self.certificate_path)
            else:
                response = requests.get(request_path, verify=False)
            response.raise_for_status()
        except (
            requests.exceptions.BaseHTTPError,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
        ) as err:
            print(err)
            print(type(err))
            entry = {
                "data": {
                    "content": {
                        "latest_valid_value": {"value": float("nan"), "status": "ERROR"}
                    }
                }
            }
            return entry
        except Exception as e:
            print(e)
            print(type(e))
            return None

        return response.json()

    @staticmethod
    def _get_value_from_response(data, target: str):
        try:
            value = data["data"][f"{target}"]["content"]["latest_valid_value"]["value"]
            return value
        except KeyError as e:
            raise APIError(f"Data not found: {e}", status_code=404)
        except Exception as e:
            print(e)
            print(type(e))
            return False

    def _get_value_from_target(self, target: str):
        data = self._get_value_request(target)
        return self._get_value_from_response(data, target=target)

    def get_pressure(self, channel: int):
        target_value = f"mapper.bflegacy.double.p{channel}"
        return float(self._get_value_from_target(target_value)) * 1e-3

    def get_temperature(self, flange: str):
        target_value = f"mapper.bflegacy.double.t{flange}"
        return float(self._get_value_from_target(target_value))

    def get_flow(self):
        target_value = f"mapper.bflegacy.double.flow"
        return float(self._get_value_from_target(target_value))








