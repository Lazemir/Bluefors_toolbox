from typing import Unpack

from qcodes.instrument import InstrumentBaseKWArgs

from .utils import BlueforsApiModule, BlueforsApiChannel, ReadonlyParameter, Parameter


class PressureSensor(BlueforsApiChannel):
    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)
        self.device = self._short_name

        self.add_parameter('pressure',
                           ReadonlyParameter,
                           target='',
                           get_parser=float,
                           unit='bar')

        self.add_parameter('enabled',
                           Parameter,
                           get_parser=bool)


# class Settings(BlueforsApiModule):
#     device = 'pressures'
#
#     def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
#         super().__init__(parent, name, **kwargs)
#
#         for channel in range(1, 7):
#             sensor_name = f'p{channel}'
#             self.add_submodule(sensor_name, SensorSettings(self, sensor_name))


class Maxigauge(BlueforsApiModule):
    device = 'driver.maxigauge.pressures'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        # self.add_submodule('settings', Settings(self, 'settings'))

        for channel in range(1, 7):
            sensor_name = f'p{channel}'
            self.add_submodule(sensor_name, PressureSensor(self, sensor_name))

            # self.add_parameter(sensor_name,
            #                    ReadonlyParameter,
            #                    target=f'pressures.{sensor_name}',
            #                    get_parser=float)


