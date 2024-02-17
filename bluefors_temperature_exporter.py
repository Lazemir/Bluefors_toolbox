from flask import Flask
import datetime
import numpy as np


class ParseError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


app = Flask(__name__)
log_folder_path = 'C:/Users/User/Desktop/BlueFors_HASSALEH/log_files/'
temperature_folder_path = log_folder_path + 'Lsci372Reader/'
valve_control_folder_path = log_folder_path + 'ValveControl/'

NaN = float('NaN')


def get_folder_name(date):
    return f'{date.strftime("%y-%m-%d")}/'


def get_full_filename(partial_filename, date):
    return f'{partial_filename}{date.strftime("%y-%m-%d")}.log'


def _parse_line(log_file_path):
    with open(log_file_path, "r") as log_file:
        line = log_file.readlines()[-1].rstrip(' ' + ',' + '\n')
        return line.split(',')


def get_line_delay(line):
    today = datetime.date.today()
    line_time = datetime.time.fromisoformat(line[1])
    line_datetime = datetime.datetime.combine(today, line_time)
    line_delay = datetime.datetime.now() - line_datetime
    return line_delay


def check_noon():
    now = datetime.datetime.now()
    return now.hour == 0 and now.minute == 0


def _parse_actual_line(log_folder_path, partial_filename, date, max_line_delay):
    log_file_path = log_folder_path + get_full_filename(partial_filename, date)
    line = _parse_line(log_file_path)
    if get_line_delay(line).seconds > max_line_delay:
        raise ParseError
    return line[2:]


def parse_actual_line(log_folder_path, partial_filename, max_line_delay=120):
    today = datetime.date.today()
    current_log_folder_path = log_folder_path + get_folder_name(today)
    try:
        return _parse_actual_line(current_log_folder_path, partial_filename, today, max_line_delay)
    except FileNotFoundError as e:
        if not check_noon():
            raise e
        yesterday = today - datetime.timedelta(1)
        return _parse_actual_line(current_log_folder_path, partial_filename, yesterday, max_line_delay)


def get_temperature(channel_num):
    partial_filename = f'CH{channel_num} T '
    try:
        actual_line = parse_actual_line(temperature_folder_path, partial_filename)
    except ParseError:
        return NaN

    temperature = float(actual_line[0])

    if temperature == 0:
        return NaN

    return temperature

def get_temperatures():
    result = ''
    for stage, channel_num in enumerate([1, 2, 5, 6], start=1):
        temperature = get_temperature(channel_num)
        result += f'bluefors_temperature{{stage="{stage}"}} {temperature}\n'
    return result

def get_pressures():
    channels_num = 6
    result = ''
    partial_filename = 'maxigauge '
    try:
        line = parse_actual_line(valve_control_folder_path, partial_filename)
        data = np.asarray(line).reshape((channels_num, -1))
        for channel, status, pressure in zip(data[:, 0], data[:, 2], data[:, 3]):
            if not int(status):
                pressure = NaN
            result += f'bluefors_pressure{{channel="{channel}"}} {pressure}\n'
        return result
    except ParseError:
        return ''


def get_flow():
    partial_filename = 'Flowmeter '
    try:
        line = parse_actual_line(valve_control_folder_path, partial_filename)
        return f'bluefors_flow {line[0]}'
    except ParseError:
        return ''


@app.route("/metrics")
def metrics():
    res = ''
    res += get_temperatures()
    res += get_pressures()
    res += get_flow()
    return res


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9101)
