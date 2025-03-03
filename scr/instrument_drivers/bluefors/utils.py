from typing import Unpack, Any, TYPE_CHECKING

import qcodes
from qcodes import InstrumentChannel
from qcodes.instrument import InstrumentModule, InstrumentBaseKWArgs

if TYPE_CHECKING:
    from .bluefors_LD400 import BlueforsLD400


class ReadonlyParameter(qcodes.parameters.Parameter):
    instrument: 'BlueforsApiModule'

    def __init__(self, name: str, target=None, **kwargs):
        super().__init__(name, **kwargs)
        self.target = name
        if target is not None:
            self.target = target

    def get_raw(self) -> qcodes.parameters.ParamRawDataType:
        """Read the value of the parameter."""
        return self.instrument.get_value(self.target)


class Parameter(ReadonlyParameter):
    def set_raw(self, value: qcodes.parameters.ParamRawDataType) -> None:
        """Set the value of the parameter."""
        self.instrument.set_value(self.target, value)


class BlueforsApiModule(InstrumentModule):
    parent: 'BlueforsLD400'
    device: str

    def __init__(self, parent: 'BlueforsApi | BlueforsApiModule', name: str, **kwargs: Unpack[InstrumentBaseKWArgs]):
        super().__init__(parent, name, **kwargs)

    def _get_target(self, target: str) -> str:
        return f'{self.device}.{target}'.strip('.')

    def call_method(self, target: str):
        target = self._get_target(target)
        self.parent.call_method(target)

    def get_value(self, target: str) -> Any:
        target = self._get_target(target)
        return self.parent.get_value(target)

    def set_value(self, target: str, value: Any) -> None:
        target = self._get_target(target)
        self.parent.set_value(target, value)


class BlueforsApiChannel(BlueforsApiModule, InstrumentChannel):
    pass
