import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scr.instrument_drivers.bluefors.bluefors_LD400 import BlueforsLD400


class TestBlueforsSystemInfo(unittest.TestCase):
    def test_system_info_is_fetched_during_initialization(self) -> None:
        payload = {
            "data": {
                "system_name": "",
                "system_version": "v2.0",
                "api_version": "v2.0",
            }
        }

        fake_response = SimpleNamespace(json=lambda: payload)

        with patch.object(BlueforsLD400, "_get_system_request", return_value=fake_response):
            instrument = BlueforsLD400("bluefors", api_key="secret", certificate_path=None)

        self.assertEqual(instrument.api_version, "v2.0")
        self.assertEqual(instrument.system_version, "v2.0")
        self.assertEqual(instrument.system_name, "")
        self.assertEqual(instrument.system_info, payload["data"])


if __name__ == "__main__":
    unittest.main()
