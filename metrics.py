from abc import ABC, abstractmethod
from functools import wraps

from prometheus_client import Gauge, Counter

from scr.instrument_drivers import BlueforsLD400
from scr.exceptions import APIError
from scr.instrument_drivers.bluefors.edwards_nXDS import EdwardsNXDS
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

    def create_gauge(self, name: str, **kwargs):
        """
        Utility function to create a Prometheus Gauge.
        """
        # Add the metric to the dictionary for reuse
        self.metrics[name] = Gauge(
            name=name,
            namespace=self.namespace,
            subsystem=self.subsystem,
            **kwargs
        )
        return self.metrics[name]

    def create_counter(self, name: str, **kwargs):
        """
        Utility function to create a Prometheus Counter.
        """
        # Add the metric to the dictionary for reuse
        self.metrics[name] = Counter(
            name=name,
            namespace=self.namespace,
            subsystem=self.subsystem,
            **kwargs
        )
        return self.metrics[name]

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

    def update_metrics(self):
        cpa = self.api.cpa
        self.motor_current.set(cpa.motor_current())
        self.coolant_in_temperature.set(to_celsius(cpa.coolant_in_temperature()))
        self.coolant_out_temperature.set(to_celsius(cpa.coolant_out_temperature()))
        self.oil_temperature.set(to_celsius(cpa.oil_temperature()))
        self.helium_temperature.set(to_celsius(cpa.helium_temperature()))
        self.low_pressure.set(cpa.low_pressure())
        self.high_pressure.set(cpa.high_pressure())


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


    def update_metrics(self):
        nxds: EdwardsNXDS = self.api.nxds

        self.controller_temperature.set(to_celsius(nxds.controller_temperature()))
        self.link_current.set(nxds.link_current())
        self.link_power.set(nxds.link_power())
        self.link_voltage.set(nxds.link_voltage())
        self.pump_temperature.set(to_celsius(nxds.pump_temperature()))
        self.rotational_frequency.set(nxds.rotational_frequency())


class TurboPumpMetrics(BlueforsMetrics):
    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='turbo_compressor')

        self.active_rotational_speed = self.create_gauge('active_rotational_speed',
                                                         documentation='Current speed of the pump turbine',
                                                         unit='hertz')

        self.drive_power = self.create_gauge('drive_power',
                                             documentation='Current power of the pump',
                                             unit='watt')

    def update_metrics(self):
        tc400: PfeifferTC400 = self.api.tc400

        self.active_rotational_speed.set(tc400.active_rotational_speed())
        self.drive_power.set(tc400.drive_power())


class GasHandlingSystemMetrics(BlueforsMetrics):
    pressure_sensors = [f'p{i}' for i in range(1, 7)]

    @handle_exceptions(APIError)
    def get_pressure(self, sensor: str) -> float:
        sensor = getattr(self.api.maxigauge, sensor)
        pressure: float = sensor.pressure()
        return pressure

    @handle_exceptions(APIError)
    def get_flow(self) -> float:
        flow: float = self.api.vc.flow()
        return flow

    def __init__(self, api: BlueforsLD400):
        super().__init__(api, subsystem='mixture')

        self.pressure = self.create_gauge(name="pressure",
                          documentation="Gas handling system pressures",
                          labelnames=('sensor',),
                          unit='bars')

        self.flow = self.create_gauge(name='flow',
                          documentation='Mixture flow through dilution refrigerate',
                          unit='millimoles_per_second')

    def update_metrics(self):
        for sensor in self.pressure_sensors:
            pressure = self.get_pressure(sensor)
            self.pressure.labels(sensor).set(pressure)

        flow = self.get_flow()
        self.flow.set(flow)


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
