import time
import threading
from collections import deque
from typing import Literal, Callable, Optional
import numpy as np
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from scipy.optimize import curve_fit

# For displaying the chart in Jupyter Notebook
import plotly.graph_objects as go
from IPython.display import display

from scr.instrument_drivers.bluefors.lakeshore_model_372 import Heater


class TimedQueue:
    def __init__(self, ttl: timedelta, minimal_timespan: timedelta) -> None:
        self._temperature_queue = deque()
        self._time_queue = deque()
        assert ttl > minimal_timespan, "TTL must exceed minimal timespan"
        self.ttl = ttl
        self.full_time = minimal_timespan

    def _cleanup(self) -> None:
        now = datetime.now()
        while self._time_queue and now - self._time_queue[0] > self.ttl:
            self._time_queue.popleft()
            self._temperature_queue.popleft()

    def append(self, value: float) -> None:
        self._cleanup()
        self._time_queue.append(datetime.now())
        self._temperature_queue.append(value)

    def span(self) -> float:
        self._cleanup()
        if len(self._temperature_queue) < 2:
            raise RuntimeError('Not enough data to compute span')
        return float(np.max(self._temperature_queue) - np.min(self._temperature_queue))

    def mean(self) -> float:
        self._cleanup()
        return float(np.mean(self._temperature_queue))

    def std(self) -> float:
        self._cleanup()
        return float(np.std(self._temperature_queue))

    def is_full(self) -> bool:
        self._cleanup()
        return bool(self._time_queue and self._time_queue[-1] - self._time_queue[0] >= self.full_time)

    def get_data(self):
        """Return lists of timestamps and temperature values."""
        self._cleanup()
        return list(self._time_queue), list(self._temperature_queue)


class BackgroundWorker(ABC):
    def __init__(self, update_interval: timedelta):
        self._update_interval = update_interval
        self._stop_flag = threading.Event()
        self._event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        self._event.set()
        if self._thread:
            self._thread.join()

    @abstractmethod
    def _run(self):
        pass


class TemperaturePoller(BackgroundWorker):
    def __init__(
            self,
            queue: TimedQueue,
            sensor_read: Callable[[], float],
            context_getter: Callable[[], bool],
            interval_context: timedelta = timedelta(seconds=1),
            interval_no_context: timedelta = timedelta(seconds=60)
    ):
        """
        Poll sensor in background, append to queue, switch rate by context.
        """
        super().__init__(update_interval=interval_no_context)
        self._queue = queue
        self._sensor_read = sensor_read
        self._context_getter = context_getter
        self._interval_ctx = interval_context

    def _run(self):
        while not self._stop_flag.is_set():
            try:
                val = self._sensor_read()
                self._queue.append(val)
            except Exception as e:
                print(f"Polling error: {e}")
            # determine next wait
            interval = self._interval_ctx if self._context_getter() else self._update_interval
            self._event.wait(interval.total_seconds())
            self._event.clear()


class StableTemperaturePoller(TemperaturePoller):
    def __init__(
        self,
        queue: TimedQueue,
        sensor_read: Callable[[], float],
        context_getter: Callable[[], bool],
        stability_kelvin: float,
        interval_context: timedelta = timedelta(seconds=1),
        interval_no_context: timedelta = timedelta(seconds=60)
    ):
        """
        Extends poller: detects stability when slope*window <= stability_kelvin.
        """
        super().__init__(queue, sensor_read, context_getter, interval_context, interval_no_context)
        self.stability_kelvin = stability_kelvin
        self._stable_event = threading.Event()
        self._stable_start: Optional[datetime] = None

    def _evaluate_stability(self):
        if not self._queue.is_full():
            return
        times, temps = self._queue.get_data()
        t0 = times[0]
        t_secs = np.array([(t - t0).total_seconds() for t in times])
        y = np.array(temps)
        k, _ = curve_fit(lambda t, k, b: k * t + b, t_secs, y)[0]
        window_sec = self._queue.full_time.total_seconds()
        # total change over window: slope * window length
        if abs(k * window_sec) <= self.stability_kelvin:
            if not self._stable_event.is_set():
                self._stable_start = datetime.now() - self._queue.full_time
                self._stable_event.set()

    def _run(self):
        while not self._stop_flag.is_set():
            try:
                val = self._sensor_read()
                self._queue.append(val)
                self._evaluate_stability()
            except Exception as e:
                print(f"Stable poll error: {e}")
            interval = self._interval_ctx if self._context_getter() else self._update_interval
            self._event.wait(interval.total_seconds())
            self._event.clear()

    @property
    def stable_start_time(self) -> Optional[datetime]:
        """Returns the datetime when stability was first detected."""
        return self._stable_start

    def wait_for_stability(self, timeout: Optional[float] = None) -> timedelta:
        """
        Blocks until stability is detected or timeout expires.
        Returns the elapsed time until stability is reached.
        Raises TimeoutError if the timeout is reached before stability.
        """
        start_time = datetime.now()
        if not self._stable_event.wait(timeout):
            raise TimeoutError("Temperature did not stabilize within the given timeout")
        detect_time = datetime.now()
        return detect_time - start_time

class TemperaturePlotter(BackgroundWorker):
    def __init__(
            self,
            queue: TimedQueue,
            interval: timedelta = timedelta(seconds=1),
            stable_getter: Optional[Callable[[], Optional[datetime]]] = None
    ):
        """
        Background plotter: shows queue data, highlights stable points.
        """
        super().__init__(update_interval=interval)
        self._queue = queue
        self._stable_getter = stable_getter

    def _run(self):
        fig = go.FigureWidget(data=[
            go.Scatter(x=[], y=[], mode='lines+markers', name='Temp'),
            go.Scatter(x=[], y=[], mode='markers', marker=dict(color='green'), name='Stable')
        ])
        fig.update_layout(title='Temperature vs Time', xaxis_title='Time', yaxis_title='Temp')
        display(fig)
        while not self._stop_flag.is_set():
            times, temps = self._queue.get_data()
            stable_start = self._stable_getter() if self._stable_getter else None
            if stable_start:
                stable_times = [t for t in times if t >= stable_start]
                stable_vals = [v for t, v in zip(times, temps) if t >= stable_start]
            else:
                stable_times, stable_vals = [], []
            with fig.batch_update():
                fig.data[0].x, fig.data[0].y = times, temps
                fig.data[1].x, fig.data[1].y = stable_times, stable_vals
            self._event.wait(self._update_interval.total_seconds())
            self._event.clear()


class TemperatureController:
    def __init__(
            self,
            lakeshore,
            target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'],
            max_temperature: float,
            stability_kelvin: float = 1e-3
    ):
        self.last_temperatures = TimedQueue(
            ttl=timedelta(minutes=10), minimal_timespan=timedelta(minutes=5)
        )
        self._lakeshore = lakeshore
        self._target_sensor_name = target_sensor
        self._temperature = getattr(self._lakeshore.sensors, target_sensor).temperature
        self._context_active = False
        self._poller = StableTemperaturePoller(
            queue=self.last_temperatures,
            sensor_read=self._temperature,
            context_getter=lambda: self._context_active,
            stability_kelvin=stability_kelvin
        )
        self._poller.start()
        self._plotter: Optional[TemperaturePlotter] = None

    def __enter__(self):
        scanner = self._lakeshore.scanner
        scanner.channel(self._target_sensor_name)
        self._autoscan_at_enter = scanner.autoscan()
        if self._autoscan_at_enter:
            scanner.autoscan(False)
        self._context_active = True
        # start plotter
        self._plotter = TemperaturePlotter(
            queue=self.last_temperatures,
            stable_getter=lambda: self._poller.stable_start_time
        )
        self._plotter.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # stop plotter
        if self._plotter:
            self._plotter.stop()
        self._context_active = False
        # restore previous autoscan status
        if self._autoscan_at_enter:
            self._lakeshore.scanner.autoscan(True)

    def wait_for_stability(self, timeout: Optional[float] = None) -> timedelta:
        return self._poller.wait_for_stability(timeout)

    def __del__(self):
        self._poller.stop()


class PIDCalibrator(TemperatureController):
    def __init__(
            self,
            lakeshore,
            target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'],
            heater: Heater,
            **kwargs
    ):
        super().__init__(lakeshore, target_sensor, **kwargs)
        self.heater = heater

    def calibrate_ranges(self, tolerance=1e-3):
        results = []
        with self.heater.write_session():
            self.heater.mode('open_loop')
            self.heater.manual_value(50)
        for r in Heater.RANGES:
            if r == 'off':
                continue
            with self.heater.write_session():
                self.heater.range(r)
            time.sleep(5)
            if self.wait_for_stability(timeout=None):
                results.append(True)
            else:
                results.append(False)
                break
        self.heater.turn_off()
        return results

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        self.heater.turn_off()

    def calibrate_p(self, setpoint: float, tolerance: float):
        with self.heater.write_session():
            self.heater.mode('closed_loop')
            self.heater.setpoint(setpoint)
        p = 5.0
        while p < 1e4:
            with self.heater.write_session():
                self.heater.p(p)
            if self.wait_for_stability(timeout=None):
                break
            p *= 2
        p = np.clip(p * 0.6, 0, 1e4)
        with self.heater.write_session():
            self.heater.p(p)

    def calibrate_i(self, setpoint: float, tolerance: float):
        ...

