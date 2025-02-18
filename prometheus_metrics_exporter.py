import os

from dotenv import load_dotenv
from prometheus_client import Gauge, make_wsgi_app
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from waitress import serve
from functools import wraps

from scr.exceptions import APIError
from scr.instrument_drivers import BlueforsLD400

load_dotenv()

bluefors = BlueforsLD400('bluefors',
                         ip=os.getenv("IP"),
                         port=int(os.getenv("PORT")),
                         api_key=os.getenv("API_KEY"),
                         certificate_path=os.getenv("CERTIFICATE_PATH"))

app = Flask(__name__)
NaN = float('NaN')


def handle_exceptions(*exceptions):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions:
                return NaN
        return wrapper
    return decorator


@handle_exceptions(APIError)
def get_temperature(flange: str) -> float:
    sensor = getattr(bluefors.lakeshore.sensors, flange)
    temperature: float = sensor.temperature()
    if temperature == 0:
        return NaN
    return temperature


@handle_exceptions(APIError)
def get_pressure(sensor: str) -> float:
    sensor = getattr(bluefors.maxigauge, sensor)
    pressure: float = sensor.pressure()
    return pressure


@handle_exceptions(APIError)
def get_flow() -> float:
    flow: float = bluefors.vc.flow()
    return flow


flanges = ('pt1', 'pt2', 'still', 'mc')
temperature_metric = Gauge(namespace='bluefors',
                           name="temperature",
                           documentation="Temperature of flanges",
                           labelnames=('flange',),
                           unit='K')

pressure_sensors = (f'p{i}' for i in range(1, 7))
pressure_metric = Gauge(namespace='bluefors',
                        name="pressure",
                        documentation="Pressures of DR cycle",
                        labelnames=('sensor',),
                        unit='bar')

flow_metric = Gauge(namespace='bluefors',
                    name='flow',
                    documentation='Flow in DR cycle',
                    unit='mmol_per_s')

def update_metrics():
    for flange in flanges:
        temperature = get_temperature(flange)
        temperature_metric.labels(flange).set(temperature)

    for sensor in pressure_sensors:
        pressure = get_pressure(sensor)
        pressure_metric.labels(sensor).set(pressure)

    flow = get_flow()
    flow_metric.set(flow)


@app.route('/')
def main():
    return "Prometheus metrics exporter for dilution refrigerator"


class MetricsWSGIApp:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        update_metrics()
        return self.wsgi_app(environ, start_response)


app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': MetricsWSGIApp(make_wsgi_app())
})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=9101)