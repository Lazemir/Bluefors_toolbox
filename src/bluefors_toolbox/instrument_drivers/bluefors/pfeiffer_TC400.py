from typing import Unpack

from qcodes.instrument import InstrumentBaseKWArgs

from .utils import BlueforsApiModule, ReadonlyParameter


class PfeifferTC400(BlueforsApiModule):
    device = 'driver.tc400'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        self.add_parameter('active_rotational_speed',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='Hz')

        self.add_parameter('drive_power',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='W')
