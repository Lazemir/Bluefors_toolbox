import time
import threading
from collections import deque
from typing import Literal, Callable, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from numpy.typing import NDArray
from scipy.optimize import curve_fit

# For displaying the chart in Jupyter Notebook
import plotly.graph_objects as go
from IPython.display import display
from sklearn.metrics import r2_score

from scr.instrument_drivers.bluefors.lakeshore_model_372 import Heater


class TimedQueue:
    def __init__(self, ttl: timedelta, minimal_timespan: Optional[timedelta] = None) -> None:
        self._values: deque[float] = deque()
        self._times: deque[datetime] = deque()
        self.ttl = ttl
        self.full_time = minimal_timespan if minimal_timespan else ttl - timedelta(minutes=1)
        assert self.ttl > self.full_time, "TTL must exceed minimal timespan"

    def _cleanup(self) -> None:
        now = datetime.now()
        while self._times and now - self._times[0] > self.ttl:
            self._times.popleft()
            self._values.popleft()

    def append(self, value: float) -> None:
        self._cleanup()
        self._times.append(datetime.now())
        self._values.append(value)

    def span(self) -> float:
        self._cleanup()
        if len(self._values) < 2:
            raise RuntimeError('Not enough data to compute span')
        return float(np.max(self._values) - np.min(self._values))

    def mean(self) -> float:
        self._cleanup()
        return float(np.mean(self._values))

    def std(self) -> float:
        self._cleanup()
        return float(np.std(self._values))

    def is_full(self) -> bool:
        self._cleanup()
        return bool(self._times and (self._times[-1] - self._times[0] >= self.full_time))

    def get_data(self) -> Tuple[NDArray[datetime], NDArray[float]]:
        self._cleanup()
        return np.asarray(self._times), np.asarray(self._values)

    def clear(self) -> None:
        self._times.clear()
        self._values.clear()


class BackgroundWorker(ABC):
    def __init__(self, update_interval: timedelta):
        self._update_interval = update_interval
        self._stop_flag = threading.Event()
        self._wakeup = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __del__(self):
        self.stop()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        self._wakeup.set()
        if self._thread:
            self._thread.join()

    def _wait(self):
        self._wakeup.wait(self._update_interval.total_seconds())
        self._wakeup.clear()

    @abstractmethod
    def _run(self):
        pass


class TemperaturePoller(BackgroundWorker):
    def __init__(
            self,
            queue: TimedQueue,
            sensor_read: Callable[[], float],
            update_interval: timedelta = timedelta(seconds=1),
    ):
        """
        Poll sensor in background, append to queue, switch rate by context.
        """
        super().__init__(update_interval)
        self._queue = queue
        self._sensor_read = sensor_read

    def _run(self):
        while not self._stop_flag.is_set():
            try:
                val = self._sensor_read()
                self._queue.append(val)
            except Exception as e:
                print(f"Polling error: {e}")
            # determine next wait
            self._wait()


def _fit_linear(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """
    Fit a linear function y = m * x + b to the data (x, y) using curve_fit,
    and compute the coefficient of determination R² using sklearn's r2_score.

    Parameters
    ----------
    x : np.ndarray
        Independent variable data.
    y : np.ndarray
        Dependent variable data.

    Returns
    -------
    k : float
        Slope of the fitted line.
    r2 : float
        Coefficient of determination R² of the fit.
    """

    # Model definition
    def linear_model(x, k, b):
        return k * x + b

        # Fit the model to data

    popt, _ = curve_fit(linear_model, x, y)
    k, b = popt

    # Generate predictions
    y_pred = linear_model(x, k, b)

    # Compute R² score
    r2 = r2_score(y, y_pred)

    return k, r2


class StableTemperaturePoller(TemperaturePoller):
    def __init__(
            self,
            stability_queue: TimedQueue,
            *additional_queues: TimedQueue,
            sensor_read: Callable[[], float],
            stability_kelvin: float,
            update_interval: timedelta = timedelta(seconds=1),
    ):
        super().__init__(stability_queue, sensor_read, update_interval)
        self._additional_queues = additional_queues
        self._sensor_read = sensor_read
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
        k, r2 = _fit_linear(t_secs, y)
        window_sec = self._queue.full_time.total_seconds()
        if abs(k * window_sec) <= self.stability_kelvin and r2 > 0.95:
            if not self._stable_event.is_set():
                self._stable_start = datetime.now() - self._queue.full_time
                self._stable_event.set()
        else:
            if self._stable_event.is_set():
                self._stable_event.clear()
                self._queue.clear()
                self._stable_start = None

    def _run(self):
        while not self._stop_flag.is_set():
            try:
                val = self._sensor_read()
                # append to both queues
                self._queue.append(val)
                for queue in self._additional_queues:
                    queue.append(val)
                self._evaluate_stability()
            except Exception as e:
                print(f"Stable poll error: {e}")
            self._wait()

    @property
    def stable_start_time(self) -> Optional[datetime]:
        return self._stable_start

    def wait_for_stability(self, timeout: Optional[float] = None) -> timedelta:
        start_time = datetime.now()
        if not self._stable_event.wait(timeout):
            raise TimeoutError("Temperature did not stabilize within timeout")
        return datetime.now() - start_time


class TemperaturePlotter(BackgroundWorker):
    def __init__(
            self,
            queue: TimedQueue,
            update_interval: timedelta = timedelta(seconds=1),
            stable_getter: Optional[Callable[[], Optional[datetime]]] = None
    ):
        super().__init__(update_interval)
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
            self._wait()


class TemperatureController:
    def __init__(
            self,
            lakeshore,
            target_sensor: Literal['pt1', 'pt2', 'still', 'mxc'],
            max_temperature: float,
            plot_window: timedelta = timedelta(minutes=10),
            stability_window: timedelta = timedelta(minutes=30),
            # min_plot_span: timedelta = timedelta(minutes=5),
            # min_stability_span: timedelta = timedelta(seconds=30),
            stability_kelvin: float = 1e-3
    ):
        # separate queues for plotting and stability
        self.plot_queue = TimedQueue(plot_window)
        self.stability_queue = TimedQueue(stability_window)

        self._lakeshore = lakeshore
        self._target_sensor = getattr(self._lakeshore.sensors, target_sensor).temperature
        self._context_active = False

        # Poller writes to both queues
        self._poller = StableTemperaturePoller(
            self.stability_queue,
            self.plot_queue,
            sensor_read=self._target_sensor,
            stability_kelvin=stability_kelvin
        )
        self._poller.start()

    def __enter__(self):
        scanner = self._lakeshore.scanner
        self._autoscan_state_at_enter = scanner.autoscan()
        if self._autoscan_state_at_enter:
            scanner.autoscan(False)
        self._context_active = True

        # Start background plotter on plot_queue
        self._plotter = TemperaturePlotter(
            queue=self.plot_queue,
            stable_getter=lambda: self._poller.stable_start_time
        )
        self._plotter.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self._plotter
        self._context_active = False
        # restore autoscan
        if self._autoscan_state_at_enter:
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
            try:
                self.wait_for_stability()
                results.append(True)
            except TimeoutError:
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
            try:
                self.wait_for_stability()
                break
            except TimeoutError:
                p *= 2
        p = np.clip(p * 0.6, 0, 1e4)
        with self.heater.write_session():
            self.heater.p(p)

    def calibrate_i(self, setpoint: float, tolerance: float):
        ...
