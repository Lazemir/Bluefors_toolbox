import os
from flask import Flask
from dotenv import load_dotenv

from bluefors_temperature_exporter import ParseError
from scr.bluefors_exporter import BlueforsAPIExporter

load_dotenv()

print(os.getenv("CERTIFICATE_PATH"))
exporter = BlueforsAPIExporter(ip=os.getenv("IP"),
                               port=int(os.getenv("PORT")),
                               key=os.getenv("API_KEY"),
                               certificate_path=os.getenv("CERTIFICATE_PATH")
                               )

app = Flask(__name__)
NaN = float('NaN')

def get_temperature(stage):
    try:
        temperature = exporter.get_temperature(flange=stage)
        return temperature
    except ParseError:
        return NaN

def get_pressure(channel):
    try:
        pressure = exporter.get_pressure(channel=channel)
        return pressure
    except ParseError:
        return NaN

def get_flow():
    try:
        flow = exporter.get_flow()
        return flow
    except ParseError:
        return NaN

@app.route('/')
def main():
    return "Prometheus metrics exporter for dilution refrigerator"

@app.route('/metrics', methods=["GET"])
def get_metrics():
    """Add temperature, pressure and flow metrics"""
    metrics = []

    flange_stage_mapping = {"50k": 1, "4k": 2, "still": 3, "mixing": 4}

    for flange in ["50k", "4k", "still", "mixing"]:
        temperature = get_temperature(flange)
        metric = f"bluefors_temperature{{stage=\"{flange_stage_mapping[flange]}\"}} {temperature}"
        metrics.append(metric)

    for channel in range(1, 7):
        pressure = get_pressure(channel)
        channel = f"CH{channel}"
        metric = f"bluefors_pressure{{channel=\"{channel}\"}} {pressure}"
        metrics.append(metric)

    flow = get_flow()
    metric = f'bluefors_flow {flow}'
    metrics.append(metric)
    return "\n".join(metrics), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9101)
