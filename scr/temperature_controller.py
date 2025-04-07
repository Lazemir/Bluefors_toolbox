import time
from collections import deque
from typing import Literal, Optional

import numpy as np
from datetime import datetime, timedelta
from numpy import clip

from scr.instrument_drivers.bluefors.lakeshore_model_372 import Lakeshore, LakeshoreInputs, Heater, LakeshoreOutputs

from scr.instrument_drivers import BlueforsLD400


class TimedQueue:
    def __init__(self, ttl: timedelta, minimal_timespan: timedelta) -> None:
        self._temperature_queue = deque()
        self._time_queue = deque()
        assert ttl > minimal_timespan
        self.ttl = ttl
        self.full_time = minimal_timespan

    def _cleanup(self) -> None:
        current_time = datetime.now()
        while self._time_queue and current_time - self._time_queue[0] > self.ttl:
            self._time_queue.popleft()
            self._temperature_queue.popleft()

    def append(self, value) -> None:
        self._cleanup()
        current_time = datetime.now()
        self._time_queue.append(current_time)
        self._temperature_queue.append(value)

    def span(self) -> float:
        self._cleanup()
        if len(self._time_queue) < 2:
            raise RuntimeError('The queue is empty')
        return np.max(self._temperature_queue) - np.min(self._temperature_queue)

    def mean(self) -> float:
        self._cleanup()
        return np.mean(self._temperature_queue)

    def std(self) -> float:
        self._cleanup()
        return np.std(self._temperature_queue)

    def is_full(self):
        return self._time_queue and self._time_queue[-1] - self._time_queue[0] > self.full_time



from typing import Literal
import time
import numpy as np


class TemperatureController:
    def __init__(self, lakeshore, target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'], max_temperature: float):
        self.last_temperatures = TimedQueue(ttl=timedelta(minutes=10), minimal_timespan=timedelta(minutes=5))
        self._lakeshore = lakeshore
        self._temperature = getattr(self._lakeshore.sensors, target_sensor).temperature
        # self._lakeshore.scanner.channel(LakeshoreInputs.sensors[target_sensor])
        self._context_active = False
        self._target_sensor = target_sensor
        self._max_temperature = max_temperature

    def __enter__(self):
        if self._target_sensor == 'mxc':
            self._lakeshore.scanner.channel(6)
        if self._target_sensor == 'still':
            self._lakeshore.scanner.channel(5)
        self._lakeshore.scanner.autoscan(False)
        self._context_active = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._context_active = False
        self._lakeshore.scanner.autoscan(True)

    def _check_context(self):
        if not self._context_active:
            raise RuntimeError("Методы этого объекта можно вызывать только внутри блока with!")

    def update_temperature(self) -> None:
        self._check_context()
        temperature = self._temperature()
        self.last_temperatures.append(temperature)
        if temperature > self._max_temperature:
            raise RuntimeError('Maximum temperature exceeded')

    def wait_temperature_to_stabilize(self, tolerance: float) -> timedelta:
# TODO Relative tolerance is better
        start_time = datetime.now()
        self._check_context()
        for i in range(10):
            self.update_temperature()
            time.sleep(1)
        while True:
            self.update_temperature()
            span = self.last_temperatures.span()
            if self.last_temperatures.is_full() and span < tolerance:
                full_waiting_time = datetime.now() - start_time
                stabilization_time = full_waiting_time - self.last_temperatures.full_time
                return stabilization_time
            time.sleep(1)


class PIDCalibrator(TemperatureController):
    def __init__(self, lakeshore, target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'], heater: Heater, **kwargs):
        super().__init__(lakeshore, target_sensor, **kwargs)
        self.heater = heater

    def calibrate_ranges(self, tolerance=1e-3):
        ranges = []

        self.heater.mode('open_loop')
        self.heater.manual_value(50)
        self.heater.accept()
        for range_value in Heater.RANGES:
            if range_value == 'off':
                continue
            self.heater.range(range_value)
            self.heater.accept()
            time.sleep(5)
            try:
                print(f'{datetime.now()}: Begin temperature stabilization for range {range_value}')
                temperature = self.wait_temperature_to_stabilize(tolerance=tolerance)
                print(f'{datetime.now()}: Temperature is stable for range {range_value}')
                ranges.append(temperature)
            except RuntimeError as e:
                break
        self.heater.range('off')
        self.heater.manual_value(0)
        self.heater.accept()
        return ranges

    #TODO turn off heater on __exit__

    def calibrate_p(self, setpoint: float, tolerance: float):
        self.heater.mode('closed_loop')
        p = 5
        self.heater.setpoint(setpoint)
        while p < 1e4:
            self.heater.p(p)
            mean_temperature = self.wait_temperature_to_stabilize(tolerance=tolerance)
            if mean_temperature > setpoint - tolerance:
                break
            p *= 2
        p = np.clip(p, 0, 1e4 - 1) * 0.6
        self.heater.p(p)

    def calibrate_i(self, setpoint: float, tolerance: float):
        ...