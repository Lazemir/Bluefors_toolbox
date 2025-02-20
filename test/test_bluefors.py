import unittest
import os

from dotenv import load_dotenv

from scr.instrument_drivers.bluefors import BlueforsLD400
from scr.instrument_drivers.bluefors.edwards_nXDS import EdwardsNXDS
from scr.instrument_drivers.bluefors.pfeiffer_TC400 import PfeifferTC400

load_dotenv()


class TestBlueforsApi(unittest.TestCase):
    bluefors = BlueforsLD400('bluefors',
                             ip=os.getenv("IP"),
                             port=int(os.getenv("PORT")),
                             api_key=os.getenv("API_KEY"),
                             certificate_path=os.getenv("CERTIFICATE_PATH"))

    def test_cpa(self):
        cpa = self.bluefors.cpa
        self.assertIsInstance(cpa.motor_current(), float)
        self.assertIsInstance(cpa.hours_of_operation(), float)
        self.assertIsInstance(cpa.coolant_in_temperature(), float)
        self.assertIsInstance(cpa.coolant_out_temperature(), float)
        self.assertIsInstance(cpa.oil_temperature(), float)
        self.assertIsInstance(cpa.helium_temperature(), float)
        self.assertIsInstance(cpa.low_pressure(), float)
        self.assertIsInstance(cpa.high_pressure(), float)

    def test_lakeshore(self):
        lakeshore = self.bluefors.lakeshore

        self.assertIsInstance(lakeshore.scanner.autoscan(), bool)
        self.assertIsInstance(lakeshore.scanner.channel(), int)

        sensors = lakeshore.sensors
        channels = [sensors.pt1, sensors.pt2, sensors.still, sensors.mc]

        for channel in channels:
            self.assertIsInstance(channel.temperature(), float)

    def test_maxigauge(self):
        maxigauge = self.bluefors.maxigauge

        for channel in range(1, 7):
            sensor_name = f'p{channel}'

            sensor = getattr(maxigauge, sensor_name)

            self.assertIsInstance(sensor.pressure(), float)
            self.assertIsInstance(sensor.enabled(), bool)

    def test_vs(self):
        vc = self.bluefors.vc

        self.assertIsInstance(vc.flow(), float)

    def test_tc400(self):
        tc400: PfeifferTC400 = self.bluefors.tc400

        self.assertIsInstance(tc400.active_rotational_speed(), float)
        self.assertIsInstance(tc400.drive_power(), float)

    def test_nxds(self):
        nxds: EdwardsNXDS = self.bluefors.nxds

        self.assertIsInstance(nxds.controller_temperature(), float)
        self.assertIsInstance(nxds.link_current(), float)
        self.assertIsInstance(nxds.link_power(), float)
        self.assertIsInstance(nxds.link_voltage(), float)
        self.assertIsInstance(nxds.pump_temperature(), float)
        self.assertIsInstance(nxds.rotational_frequency(), float)
        self.assertIsInstance(nxds.run_hours(), float)
