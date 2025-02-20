from typing import Unpack, TYPE_CHECKING

from qcodes.instrument import InstrumentBaseKWArgs

from scr.instrument_drivers.bluefors.utils import BlueforsApiModule, ReadonlyParameter

if TYPE_CHECKING:
    from .bluefors_LD400 import BlueforsLD400


class CPA(BlueforsApiModule):
    device: str = 'driver.cpa'

    def __init__(self, parent: 'BlueforsLD400', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        self.motor_current: ReadonlyParameter = self.add_parameter('motor_current',
                                                                   ReadonlyParameter,
                                                                   get_parser=float,
                                                                   unit='A')

        self.hours_of_operation: ReadonlyParameter = self.add_parameter('hours_of_operation',
                                                                        ReadonlyParameter,
                                                                        get_parser=float,
                                                                        unit='H')

        self.coolant_in_temperature: ReadonlyParameter = self.add_parameter('coolant_in_temperature',
                                                                            ReadonlyParameter,
                                                                            get_parser=float,
                                                                            unit='K')

        self.coolant_out_temperature: ReadonlyParameter = self.add_parameter('coolant_out_temperature',
                                                                             ReadonlyParameter,
                                                                             get_parser=float,
                                                                             unit='K')

        self.oil_temperature: ReadonlyParameter = self.add_parameter('oil_temperature',
                                                                     ReadonlyParameter,
                                                                     get_parser=float,
                                                                     unit='K')

        self.helium_temperature: ReadonlyParameter = self.add_parameter('helium_temperature',
                                                                        ReadonlyParameter,
                                                                        get_parser=float,
                                                                        unit='K')

        self.low_pressure: ReadonlyParameter = self.add_parameter('low_pressure',
                                                                  ReadonlyParameter,
                                                                  get_parser=float,
                                                                  unit='bar')

        self.high_pressure: ReadonlyParameter = self.add_parameter('high_pressure',
                                                                   ReadonlyParameter,
                                                                   get_parser=float,
                                                                   unit='bar')
