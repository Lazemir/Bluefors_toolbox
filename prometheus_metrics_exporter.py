import os

from dotenv import load_dotenv
from prometheus_client import make_wsgi_app
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from waitress import serve

from scr.instrument_drivers import BlueforsLD400
from metrics import (BlueforsMetrics, PulseTubeCompressorMetrics, GasHandlingSystemMetrics, TemperatureMetrics,
                     ScrollPumpMetrics, TurboPumpMetrics)

load_dotenv()

bluefors = BlueforsLD400('bluefors',
                         ip=os.getenv("IP"),
                         port=int(os.getenv("PORT")),
                         api_key=os.getenv("API_KEY"),
                         certificate_path=os.getenv("CERTIFICATE_PATH"))

metrics_list: list[BlueforsMetrics] = [
    PulseTubeCompressorMetrics(bluefors),
    GasHandlingSystemMetrics(bluefors),
    TemperatureMetrics(bluefors),
    ScrollPumpMetrics(bluefors),
    TurboPumpMetrics(bluefors)
]

app = Flask(__name__)

@app.route('/')
def main():
    return "Prometheus metrics exporter for dilution refrigerator"


class MetricsWSGIApp:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        for metrics in metrics_list:
            metrics.update_metrics()
        return self.wsgi_app(environ, start_response)


app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': MetricsWSGIApp(make_wsgi_app())
})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=9101)