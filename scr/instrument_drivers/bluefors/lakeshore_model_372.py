from typing import Unpack, TYPE_CHECKING

from qcodes.instrument import InstrumentBaseKWArgs

from scr.instrument_drivers.bluefors.utils import BlueforsApiChannel, ReadonlyParameter, BlueforsApiModule, Parameter

if TYPE_CHECKING:
    from .bluefors_LD400 import BlueforsLD400


class LakeshoreChannel(BlueforsApiChannel):
    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)
        self.device = f'channel{self._short_name}'


class Sensor(LakeshoreChannel):
    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)
        self.device = f'channel{self._short_name}'

        self.temperature = self.add_parameter('temperature',
                                              ReadonlyParameter,
                                              get_parser=float,
                                              unit='K')


class Heater(LakeshoreChannel):
    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)


class LakeshoreInputs(BlueforsApiModule):
    device = 'status.inputs'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        sensors = {'pt1': 1,
                   'pt2': 2,
                   'still': 5,
                   'mc': 6}

        for channel_name, channel_index in sensors.items():
            channel = Sensor(self, str(channel_index))
            self.add_submodule(channel_name, channel)


class LakeshoreOutputs(BlueforsApiModule):
    device: str = 'settings.outputs'

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        heaters = {
            'warm_up',
            'still',
            'sample'
        }

        for heater_name in heaters:
            channel = Heater(self, heater_name)
            self.add_submodule(heater_name, channel)


class LakeshoreScanner(BlueforsApiModule):
    device: str = 'status.scanner'

    def __init__(self, parent: BlueforsApiModule, name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        self.autoscan: Parameter = self.add_parameter('autoscan',
                                                      Parameter,
                                                      get_parser=bool)

        self.channel: Parameter = self.add_parameter('channel',
                                                     Parameter,
                                                     get_parser=int)


class Lakeshore(BlueforsApiModule):
    device: str = 'driver.lakeshore'

    def __init__(self, parent: 'BlueforsLD400', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

        self.add_submodule('scanner', LakeshoreScanner(self, 'scanner'))
        self.add_submodule('sensors', LakeshoreInputs(self, 'sensors'))
        self.add_submodule('heaters', LakeshoreOutputs(self, 'heaters'))
