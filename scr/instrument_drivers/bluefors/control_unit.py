from typing import Unpack

from qcodes.instrument import InstrumentBaseKWArgs

from .utils import BlueforsApiModule, ReadonlyParameter, _bool_mapping


class ControlUnit(BlueforsApiModule):
    device = 'mapper.bflegacy.boolean'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        for valve_number in range(1, 21 + 1):
            self.add_parameter(f'v{valve_number}',
                               ReadonlyParameter,
                               val_mapping=_bool_mapping)

        for heat_switch_name in ('still', 'mc'):
            self.add_parameter(f'hs_{heat_switch_name}',
                               ReadonlyParameter,
                               target=f'hs-{heat_switch_name}',
                               val_mapping=_bool_mapping)

        self.pulse_tube = self.add_parameter('pulse_tube',
                                     ReadonlyParameter,
                                     target='pulsetube',
                                     val_mapping=_bool_mapping)

        for scroll_number in range(1, 2 + 1):
            self.add_parameter(f'scroll{scroll_number}',
                               ReadonlyParameter,
                               val_mapping=_bool_mapping)

        self.turbo1 = self.add_parameter('turbo1',
                                         ReadonlyParameter,
                                         val_mapping=_bool_mapping)

        self.compressor = self.add_parameter('compressor',
                                             ReadonlyParameter,
                                             val_mapping=_bool_mapping)
