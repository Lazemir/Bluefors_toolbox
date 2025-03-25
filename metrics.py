from abc import ABC, abstractmethod
from enum import IntEnum
from functools import wraps
import re

from prometheus_client import Gauge, Counter, Enum
from prometheus_client.metrics import MetricWrapperBase

from scr.instrument_drivers import BlueforsLD400
from scr.exceptions import APIError
from scr.instrument_drivers.bluefors.edwards_nXDS import EdwardsNXDS
from scr.instrument_drivers.bluefors.lakeshore_model_372 import Heater
from scr.instrument_drivers.bluefors.pfeiffer_TC400 import PfeifferTC400

NaN = float('NaN')


def handle_exceptions(*exceptions):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions:
                return NaN

        return wrapper

    return decorator


def to_celsius(temp: float) -> float:
    """

    :param temp: Temperature in Kelvins
    :return: Temperature in degrees of Celsius
    """
    return temp - 273.15


# Base class for metrics
class Metrics(ABC):
    """
    Base class for creating and managing metrics.
    Automatically appends `namespace` and `subsystem` to metric names.
    """

    def __init__(self, namespace='', subsystem=''):
        self.namespace = namespace
        self.subsystem = subsystem
        self.metrics = {}  # Dictionary to store all created metrics

    def _create_metric(self, metric_type: type(MetricWrapperBase), name: str, **kwargs):
        """
        Utility function to create a Prometheus Metric.
        """
        # Add the metric to the dictionary for reuse
        self.metrics[name] = metric_type(
            name=name,
            namespace=self.namespace,
            subsystem=self.subsystem,
            **kwargs
        )
        return self.metrics[name]

    def create_gauge(self, name: str, **kwargs):
        """
        Utility function to create a Prometheus Gauge.
        """
        return self._create_metric(Gauge, name, **kwargs)

    def create_counter(self, name: str, **kwargs):
        """
        Utility function to create a Prometheus Counter.
        """
        return self._create_metric(Counter, name, **kwargs)

    def create_enum(self, name: str, **kwargs):
        """
        Utility function to create a Prometheus Enum.
        """
        return self._create_metric(Enum, name, **kwargs)

    @abstractmethod
    def update_metrics(self):
        pass


class BlueforsMetrics(Metrics, ABC):
    def __init__(self, api: BlueforsLD400, subsystem: str):
        super().__init__('bluefors', subsystem)
        self.api = api


class PulseTubeCompressorMetrics(BlueforsMetrics):
    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='pulse_tube_compressor')
        # Create and define metrics using the base class utility method
        self.motor_current = self.create_gauge(name='motor_current',
                                               documentation='Motor current of pulse tube compressor',
                                               unit='amperes')
        self.coolant_in_temperature = self.create_gauge(name='coolant_in_temperature',
                                                        documentation='Coolant input temperature of pulse tube compressor',
                                                        unit='celsius')
        self.coolant_out_temperature = self.create_gauge(name='coolant_out_temperature',
                                                         documentation='Coolant output temperature of pulse tube compressor',
                                                         unit='celsius')
        self.oil_temperature = self.create_gauge(name='oil_temperature',
                                                 documentation='Oil temperature in pulse tube compressor',
                                                 unit='celsius')
        self.helium_temperature = self.create_gauge(name='helium_temperature',
                                                    documentation='Helium temperature in pulse tube circuit',
                                                    unit='celsius')
        self.low_pressure = self.create_gauge(name='low_pressure',
                                              documentation='Low pressure in pulse tube circuit',
                                              unit='bars')
        self.high_pressure = self.create_gauge(name='high_pressure',
                                               documentation='High pressure in pulse tube circuit',
                                               unit='bars')
    @handle_exceptions(APIError)
    def get_motor_current(self):
        return self.api.cpa.motor_current()

    @handle_exceptions(APIError)
    def get_coolant_in_temperature(self):
        return to_celsius(self.api.cpa.coolant_in_temperature())

    @handle_exceptions(APIError)
    def get_coolant_out_temperature(self):
        return to_celsius(self.api.cpa.coolant_out_temperature())

    @handle_exceptions(APIError)
    def get_oil_temperature(self):
        return self.api.cpa.oil_temperature()

    @handle_exceptions(APIError)
    def get_helium_temperature(self):
        return self.api.cpa.helium_temperature()

    @handle_exceptions(APIError)
    def get_low_pressure(self):
        return self.api.cpa.low_pressure()

    @handle_exceptions(APIError)
    def get_high_pressure(self):
        return self.api.cpa.high_pressure()

    def update_metrics(self):
        self.motor_current.set(self.get_motor_current())
        self.coolant_in_temperature.set(self.get_coolant_in_temperature())
        self.coolant_out_temperature.set(self.get_coolant_out_temperature())
        self.oil_temperature.set(to_celsius(self.get_oil_temperature()))
        self.helium_temperature.set(to_celsius(self.get_helium_temperature()))
        self.low_pressure.set(self.get_low_pressure())
        self.high_pressure.set(self.get_high_pressure())


class ScrollPumpMetrics(BlueforsMetrics):
    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='scroll_compressor')

        self.controller_temperature = self.create_gauge(name='controller_temperature',
                                                        documentation='Scroll pump controller temperature',
                                                        unit='celsius')
        self.link_current = self.create_gauge(name='link_current',
                                              documentation='Scroll pump current',
                                              unit='amperes')
        self.link_power = self.create_gauge(name='link_power',
                                            documentation='Scroll pump power',
                                            unit='watt')
        self.link_voltage = self.create_gauge(name='link_voltage',
                                              documentation='Scroll pump voltage',
                                              unit='volts')
        self.pump_temperature = self.create_gauge(name='pump_temperature',
                                                  documentation='Scroll pump temperature',
                                                  unit='celsius')
        self.rotational_frequency = self.create_gauge(name='rotational_frequency',
                                                      documentation='Scroll pump rotational frequency',
                                                      unit='hertz')

    @handle_exceptions(APIError)
    def get_controller_temperature(self):
        return to_celsius(self.api.nxds.controller_temperature())

    @handle_exceptions(APIError)
    def get_link_current(self):
        return self.api.nxds.link_current()

    @handle_exceptions(APIError)
    def get_link_power(self):
        return self.api.nxds.link_power()

    @handle_exceptions(APIError)
    def get_link_voltage(self):
        return self.api.nxds.link_voltage()

    @handle_exceptions(APIError)
    def get_pump_temperature(self):
        return to_celsius(self.api.nxds.pump_temperature())

    @handle_exceptions(APIError)
    def get_rotational_frequency(self):
        return self.api.nxds.rotational_frequency()

    def update_metrics(self):
        self.controller_temperature.set(self.get_controller_temperature())
        self.link_current.set(self.get_link_current())
        self.link_power.set(self.get_link_power())
        self.link_voltage.set(self.get_link_voltage())
        self.pump_temperature.set(self.get_pump_temperature())
        self.rotational_frequency.set(self.get_rotational_frequency())


class TurboPumpMetrics(BlueforsMetrics):
    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='turbo_compressor')

        self.active_rotational_speed = self.create_gauge('active_rotational_speed',
                                                         documentation='Current speed of the pump turbine',
                                                         unit='hertz')

        self.drive_power = self.create_gauge('drive_power',
                                             documentation='Current power of the pump',
                                             unit='watt')

    @handle_exceptions(APIError)
    def get_active_rotational_speed(self):
        return self.api.tc400.active_rotational_speed()

    @handle_exceptions(APIError)
    def get_drive_power(self):
        return self.api.tc400.drive_power()

    def update_metrics(self):
        self.active_rotational_speed.set(self.get_active_rotational_speed())
        self.drive_power.set(self.get_drive_power())


class ValveState(IntEnum):
    CLOSED = False
    OPEN = True


class SwitchState(IntEnum):
    OFF = False
    ON = True


def transform_valve_index(valve: str) -> str:
    match = re.match(r"(v)(\d+)$", valve)
    if match:
        prefix, num_str = match.groups()
        if len(num_str) == 1:
            num_str = num_str.zfill(2)
        return f"{prefix}{num_str}"
    return valve


class GasHandlingSystemMetrics(BlueforsMetrics):
    pressure_sensors = [f'p{i}' for i in range(1, 6 + 1)]
    valves = [f'v{i}' for i in range(1, 21 + 1)]
    turbos = ['turbo1']
    scrolls = [f'scroll{i}' for i in range(1, 2 + 1)]

    @handle_exceptions(APIError)
    def get_pressure(self, sensor: str) -> float:
        sensor = getattr(self.api.maxigauge, sensor)
        pressure: float = sensor.pressure()
        return pressure

    @handle_exceptions(APIError)
    def get_flow(self) -> float:
        flow_mmol_per_s: float = self.api.vc.flow()
        flow_mol_per_s = flow_mmol_per_s / 1000
        return flow_mol_per_s

    @handle_exceptions(APIError)
    def get_valve_state(self, valve: str) -> ValveState:
        valve = getattr(self.api.control_unit, valve)
        valve_state = ValveState(valve())
        return valve_state

    @handle_exceptions(APIError)
    def get_turbo_state(self, turbo_index: str) -> bool:
        turbo = getattr(self.api.control_unit, turbo_index)
        turbo_state = turbo()
        return turbo_state

    @handle_exceptions(APIError)
    def get_scroll_state(self, scroll_index: str) -> bool:
        scroll = getattr(self.api.control_unit, scroll_index)
        scroll_state = scroll()
        return scroll_state

    @handle_exceptions(APIError)
    def get_compressor_state(self) -> bool:
        scroll = self.api.control_unit.compressor
        scroll_state = scroll()
        return scroll_state

    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='mixture')

        self.pressure = self.create_gauge(name="pressure",
                                          documentation="Gas handling system's pressures",
                                          labelnames=('sensor', ),
                                          unit='bars')

        self.flow = self.create_gauge(name='flow',
                                      documentation='Mixture flow through dilution refrigerator',
                                      unit='moles_per_second')

        self.valve = self.create_gauge(name="valve_state",
                                       documentation="Gas handling system's valve state",
                                       labelnames=('valve', )
                                       )

        self.turbo = self.create_gauge(name='turbo_state',
                                       documentation="Gas handling system's turbo pump state",
                                       labelnames=('turbo', )
                                       )

        self.scroll = self.create_gauge(name='scroll_state',
                                        documentation="Gas handling system's turbo pump state",
                                        labelnames=('scroll', )
                                        )

        self.compressor = self.create_gauge(name='compressor_state',
                                            documentation="Gas handling system's compressor state")


    def update_metrics(self):
        for sensor in self.pressure_sensors:
            pressure = self.get_pressure(sensor)
            self.pressure.labels(sensor).set(pressure)

        self.flow.set(self.get_flow())

        for valve in self.valves:
            valve_state = self.get_valve_state(valve)
            self.valve.labels(transform_valve_index(valve)).set(valve_state)

        for turbo in self.turbos:
            turbo_state = self.get_turbo_state(turbo)
            self.turbo.labels(turbo).set(turbo_state)

        for scroll in self.scrolls:
            scroll_state = self.get_scroll_state(scroll)
            self.scroll.labels(scroll).set(scroll_state)

        self.compressor.set(self.get_compressor_state())


class ControlUnitMetrics(BlueforsMetrics):
    heat_switches = ['hs_still', 'hs_mc']

    @handle_exceptions(APIError)
    def get_heat_switch_state(self, heat_switch: str) -> bool:
        heat_switch = getattr(self.api.control_unit, heat_switch)
        heat_switch_state = heat_switch()
        return heat_switch_state

    @handle_exceptions(APIError)
    def get_pulse_tube_state(self) -> bool:
        pulse_tube = self.api.control_unit.pulse_tube
        pulse_tube_state = pulse_tube()
        return pulse_tube_state

    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='control_unit')

        self.heat_switch = self.create_gauge(name='heat_switch_state',
                                             documentation="Heat switch state",
                                             labelnames=('heat_switch', ))

        self.pulse_tube = self.create_gauge(name='pulse_tube_state',
                                            documentation="Pulse tube compressor state")
    def update_metrics(self):
        for heat_switch in self.heat_switches:
            heat_switch_state = self.get_heat_switch_state(heat_switch)
            self.heat_switch.labels(heat_switch).set(heat_switch_state)

        self.pulse_tube.set(self.get_pulse_tube_state())


class TemperatureMetrics(BlueforsMetrics):
    flanges = ('pt1', 'pt2', 'still', 'mxc')

    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='flanges')

        self.temperature = self.create_gauge(name='temperature',
                                             documentation="Temperature of flanges",
                                             labelnames=('flange',),
                                             unit='kelvins')

    @handle_exceptions(APIError)
    def get_temperature(self, flange: str) -> float:
        sensor = getattr(self.api.lakeshore.sensors, flange)
        temperature: float = sensor.temperature()
        if temperature == 0:
            return NaN
        return temperature

    def update_metrics(self):
        for flange in self.flanges:
            temperature = self.get_temperature(flange)
            self.temperature.labels(flange).set(temperature)


class HeaterMetrics(BlueforsMetrics):
    heaters = {
        'still',
        'sample'
    }

    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='heater')

        self.mode = self.create_gauge(name='mode',
                                      documentation=f"Heater mode, one of: {Heater.MODES}",
                                      labelnames=('heater',))
        self.range = self.create_gauge(name='range',
                                       documentation=f"Heater range, one of: {Heater.RANGES}",
                                       labelnames=('heater',))
        self.p = self.create_gauge(name='p',
                                   documentation="Proportional Gain (P)",
                                   labelnames=('heater',))
        self.i = self.create_gauge(name='i',
                                   documentation="Integral Gain (I)",
                                   labelnames=('heater',))
        self.d = self.create_gauge(name='d',
                                   documentation="Derivative Gain (D)",
                                   labelnames=('heater',))
        self.setpoint = self.create_gauge(name='setpoint',
                                          documentation="Heater setpoint",
                                          labelnames=('heater',),
                                          unit='kelvins')
        self.manual_value = self.create_gauge(name='manual_value',
                                              documentation="Manual heater value",
                                              labelnames=('heater',))

    def _get_heater(self, heater_name):
        return getattr(self.api.lakeshore.heaters, heater_name)

    @handle_exceptions(APIError)
    def get_mode(self, heater: str) -> str:
        heater = self._get_heater(heater)
        return heater.mode()

    @handle_exceptions(APIError)
    def get_range(self, heater: str) -> str:
        heater = self._get_heater(heater)
        return heater.range()

    @handle_exceptions(APIError)
    def get_p(self, heater: str) -> float:
        heater = self._get_heater(heater)
        return heater.p()

    @handle_exceptions(APIError)
    def get_i(self, heater: str) -> float:
        heater = self._get_heater(heater)
        return heater.i()

    @handle_exceptions(APIError)
    def get_d(self, heater: str) -> float:
        heater = self._get_heater(heater)
        return heater.d()

    @handle_exceptions(APIError)
    def get_setpoint(self, heater: str) -> float:
        heater = self._get_heater(heater)
        return heater.setpoint()

    @handle_exceptions(APIError)
    def get_manual_value(self, heater: str) -> float:
        heater = self._get_heater(heater)
        return heater.manual_value()

    def update_metrics(self):
        for heater in self.heaters:
            mode: str = self.get_mode(heater)
            self.mode.labels(heater).set(Heater.MODES[mode])

            self.range.labels(heater).set(Heater.RANGES[self.get_range(heater)])

            if mode == 'open_loop':
                self.p.labels(heater).set(self.get_p(heater))
                self.i.labels(heater).set(self.get_i(heater))
                self.d.labels(heater).set(self.get_d(heater))
                self.setpoint.labels(heater).set(self.get_setpoint(heater))
            else:
                self.p.labels(heater).set(NaN)
                self.i.labels(heater).set(NaN)
                self.d.labels(heater).set(NaN)
                self.setpoint.labels(heater).set(NaN)

            if mode == 'closed_loop' or mode == 'open_loop':
                self.manual_value.labels(heater).set(self.get_manual_value(heater))
            else:
                self.manual_value.labels(heater).set(NaN)