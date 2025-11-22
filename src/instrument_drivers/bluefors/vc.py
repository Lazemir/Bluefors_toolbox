from typing import Unpack

from qcodes.instrument import InstrumentBaseKWArgs

from src.instrument_drivers.bluefors.utils import BlueforsApiModule, ReadonlyParameter


class VC(BlueforsApiModule):
    device = 'driver.vc'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        self.add_parameter('flow',
                           ReadonlyParameter,
                           get_parser=float,
                           unit='mmol/s')
