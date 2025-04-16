import time
import threading
from collections import deque
from typing import Literal
import numpy as np
from datetime import datetime, timedelta

import plotly.graph_objects as go
from IPython.display import display

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

    def get_data(self):
        """Returns lists of recorded times and temperatures."""
        self._cleanup()
        return list(self._time_queue), list(self._temperature_queue)


class TemperatureController:
    def __init__(self, lakeshore, target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'], max_temperature: float):
        self.last_temperatures = TimedQueue(ttl=timedelta(minutes=10),
                                            minimal_timespan=timedelta(minutes=5))
        self._lakeshore = lakeshore
        # Get the temperature function for the given sensor
        self._temperature = getattr(self._lakeshore.sensors, target_sensor).temperature
        self._context_active = False
        self._target_sensor = target_sensor
        self._max_temperature = max_temperature

        # Flags and events for the polling thread
        self._monitor_stop_flag = False
        self._poll_thread = None
        self._monitor_event = threading.Event()

        # Flags and events for the plotting thread
        self._plot_stop_flag = False
        self._plot_thread = None
        self._plot_event = threading.Event()

    def __enter__(self):
        scanner = self._lakeshore.scanner
        scanner.channel(self._target_sensor)
        self._autoscan_at_enter = scanner.autoscan()
        if self._autoscan_at_enter:
            scanner.autoscan(False)
        self._context_active = True
        # Signal any waiting thread to switch to fast polling
        self._monitor_event.set()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._context_active = False
        if self._autoscan_at_enter:
            self._lakeshore.scanner.autoscan(self._autoscan_at_enter)
        # Signal waiting threads so they can switch mode promptly
        self._monitor_event.set()

    def _check_context(self):
        if not self._context_active:
            raise RuntimeError("The methods of this object can only be used within a 'with' block")

    def update_temperature(self) -> None:
        """Polls the temperature within context (expected to be called every second)."""
        self._check_context()
        temperature = self._temperature()
        self.last_temperatures.append(temperature)
        if temperature > self._max_temperature:
            raise RuntimeError('Maximum temperature exceeded')

    def poll_temperature(self) -> None:
        """
        Polls the temperature regardless of context.
        Used in the polling thread to update the measurement queue.
        """
        temperature = self._temperature()
        self.last_temperatures.append(temperature)
        if temperature > self._max_temperature:
            raise RuntimeError('Maximum temperature exceeded')

    def wait_temperature_to_stabilize(self, tolerance: float) -> timedelta:
        """
        Waits until the temperature stabilizes within a given tolerance.
        This function continues until the span of values in the full time window is below the tolerance.
        """
        start_time = datetime.now()
        self._check_context()
        while True:
            span = self.last_temperatures.span()
            if self.last_temperatures.is_full() and span < tolerance:
                full_waiting_time = datetime.now() - start_time
                stabilization_time = full_waiting_time - self.last_temperatures.full_time
                return stabilization_time
            time.sleep(1)

    def start_polling(self,
                      update_interval_context: timedelta = timedelta(seconds=1),
                      update_interval_no_context: timedelta = timedelta(seconds=60)):
        """
        Starts a separate thread to poll temperature at the specified intervals.
        The polling interval is faster (e.g. 1 second) when in context and slower (e.g. 60 seconds) otherwise.
        """
        if self._poll_thread and self._poll_thread.is_alive():
            print("Polling thread is already running.")
            return
        self._monitor_stop_flag = False
        self._poll_thread = threading.Thread(
            target=self._polling,
            args=(update_interval_context, update_interval_no_context),
            daemon=True
        )
        self._poll_thread.start()

    def _polling(self, update_interval_context: timedelta, update_interval_no_context: timedelta):
        while not self._monitor_stop_flag:
            current_interval = update_interval_context if self._context_active else update_interval_no_context
            try:
                # Poll temperature without checking for context
                self.poll_temperature()
            except Exception as e:
                print(f"Error updating temperature: {e}")
            wait_seconds = current_interval.total_seconds()
            # Wait using event.wait() so that it can be interrupted promptly
            self._monitor_event.wait(wait_seconds)
            self._monitor_event.clear()

    def stop_polling(self):
        """Stops the polling thread."""
        self._monitor_stop_flag = True
        self._monitor_event.set()

    def start_plotting(self, update_interval: timedelta = timedelta(seconds=1)):
        """
        Starts a separate plotting thread that builds and continuously updates a Plotly chart.
        The chart displays all data available in the internal queue.
        """
        if self._plot_thread and self._plot_thread.is_alive():
            print("Plotting thread is already running.")
            return
        self._plot_stop_flag = False
        self._plot_thread = threading.Thread(
            target=self._plotting,
            args=(update_interval,),
            daemon=True
        )
        self._plot_thread.start()

    def _plotting(self, update_interval: timedelta):
        # Create and display the Plotly chart in the Notebook
        fig = go.FigureWidget(data=[go.Scatter(x=[], y=[], mode='lines+markers')])
        fig.update_layout(
            title="Temperature vs Time",
            xaxis_title="Time",
            yaxis_title="Temperature"
        )
        display(fig)
        while not self._plot_stop_flag:
            # Get all data from the queue (all timestamps and temperatures)
            times, temps = self.last_temperatures.get_data()
            # Update the chart with all available data
            with fig.batch_update():
                fig.data[0].x = times
                fig.data[0].y = temps
            wait_seconds = update_interval.total_seconds()
            # Wait using event.wait() so that plotting can be stopped promptly
            self._plot_event.wait(wait_seconds)
            self._plot_event.clear()

    def stop_plotting(self):
        """Stops the plotting thread."""
        self._plot_stop_flag = True
        self._plot_event.set()


class PIDCalibrator(TemperatureController):
    def __init__(self, lakeshore, target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'], heater: Heater, **kwargs):
        super().__init__(lakeshore, target_sensor, **kwargs)
        self.heater = heater

    def calibrate_ranges(self, tolerance=1e-3):
        ranges = []
        with self.heater.write_session():
            self.heater.mode('open_loop')
            self.heater.manual_value(50)
        for range_value in Heater.RANGES:
            if range_value == 'off':
                continue
            with self.heater.write_session():
                self.heater.range(range_value)
            time.sleep(5)
            try:
                print(f'{datetime.now()}: Begin temperature stabilization for range {range_value}')
                stabilization_time = self.wait_temperature_to_stabilize(tolerance=tolerance)
                print(f'{datetime.now()}: Temperature is stable for range {range_value}')
                ranges.append(stabilization_time)
            except RuntimeError as e:
                break
        self.heater.turn_off()
        return ranges

    def __exit__(self, exc_type, exc_value, traceback):
        super().__exit__(exc_type, exc_value, traceback)
        self.heater.turn_off()

    def calibrate_p(self, setpoint: float, tolerance: float):
        with self.heater.write_session():
            self.heater.mode('closed_loop')
            self.heater.setpoint(setpoint)
        p = 5
        while p < 1e4:
            with self.heater.write_session():
                self.heater.p(p)
            mean_temperature = self.wait_temperature_to_stabilize(tolerance=tolerance)
            if mean_temperature > setpoint - tolerance:
                break
            p *= 2
        p = np.clip(p, 0, 1e4 - 1) * 0.6
        with self.heater.write_session():
            self.heater.p(p)

    def calibrate_i(self, setpoint: float, tolerance: float):
        ...

