import unittest
import os
from typing import Iterable

from dotenv import load_dotenv

from src.instrument_drivers.bluefors import BlueforsLD400
from src.instrument_drivers.bluefors.edwards_nXDS import EdwardsNXDS
from src.instrument_drivers.bluefors.lakeshore_model_372 import Heater
from src.instrument_drivers.bluefors.pfeiffer_TC400 import PfeifferTC400
from src.instrument_drivers.bluefors.control_unit import ControlUnit

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
        self.assertIsInstance(lakeshore.scanner.channel(), str)

        sensors = lakeshore.sensors
        channels = [sensors.pt1, sensors.pt2, sensors.still, sensors.mxc]

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

    def test_heater(self):
        heaters: Iterable[str] = ('sample', )

        for heater_name in heaters:
            heater: Heater = getattr(self.bluefors.lakeshore.heaters, heater_name)
            self.assertIsInstance(heater.p(), float)
            self.assertIsInstance(heater.i(), float)
            self.assertIsInstance(heater.d(), float)
            self.assertIsInstance(heater.setpoint(), float)

            self.assertIsInstance(heater.range(), str)
            self.assertIsInstance(heater.mode(), str)
            self.assertIsInstance(heater.manual_value(), float)
            self.assertIsInstance(heater.display_units(), str)

    def test_control_unit(self):
        control_unit: ControlUnit = self.bluefors.control_unit

        for valve_number in range(1, 21 + 1):
            valve = getattr(control_unit, f'v{valve_number}')
            self.assertIsInstance(valve(), bool)

        for heat_switch_name in ('still', 'mc'):
            heat_switch = getattr(control_unit, f'hs_{heat_switch_name}')
            self.assertIsInstance(heat_switch(), bool)

        self.assertIsInstance(control_unit.pulse_tube(), bool)

        for scroll_number in range(1, 2 + 1):
            scroll = getattr(control_unit, f'scroll{scroll_number}')
            self.assertIsInstance(scroll(), bool)

        self.assertIsInstance(control_unit.turbo1(), bool)

        self.assertIsInstance(control_unit.compressor(), bool)

    def test_context_manager(self):
        with self.bluefors.read_session():
            self.test_cpa()
            self.test_lakeshore()
            self.test_maxigauge()
            self.test_vs()
            self.test_tc400()
            self.test_nxds()
            self.test_heater()
            self.test_control_unit()