from typing import Unpack

from qcodes.instrument import InstrumentBaseKWArgs

from src.instrument_drivers.bluefors.utils import BlueforsApiModule, ReadonlyParameter


class EdwardsNXDS(BlueforsApiModule):
    device = 'driver.nxds'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        self.add_parameter('controller_temperature',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='K')

        self.add_parameter('link_current',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='A')

        self.add_parameter('link_power',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='W')

        self.add_parameter('link_voltage',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='V')

        self.add_parameter('pump_temperature',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='K')

        self.add_parameter('rotational_frequency',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='Hz')

        self.add_parameter('run_hours',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='h')
