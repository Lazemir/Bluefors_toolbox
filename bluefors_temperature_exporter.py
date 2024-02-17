from flask import Flask
import datetime


class ParseError(Exception):
    def __init__(self, *args):
        super.__init__(*args)


app = Flask(__name__)
log_folder_path = './Bluefors_HASSALEH/log_files/'
temperature_folder_path = log_folder_path + 'Lsci372Reader/'
valve_control_folder_path = log_folder_path + 'ValveControl/'

NaN = float('NaN')


def get_folder_name(date):
    return f'{date.strftime("%y-%m-%d")}/'


def get_full_filename(partial_filename, date):
    return f'{partial_filename}{date.strftime("%y-%m-%d")}.log'


def _parse_line(log_file_path):
    with open(log_file_path, "r") as log_file:
        return log_file.readlines()[-1].split(',')


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
    return line


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
        actual_line = parse_actual_line(temperature_folder_path, partial_filename, max_line_delay=1000000)
    except ParseError:
        return NaN

    temperature = float(actual_line[2])

    if temperature == 0:
        return NaN

    return temperature


def get_temperatures():
    result = ''
    for stage, channel_num in enumerate([1, 2, 5, 6], start=1):
        temperature = get_temperature(channel_num)
        result += f'bluefors_temperature{{stage="{stage}"}} {temperature}\n'
    return result


@app.route("/metrics")
def metrics():
    res = ''
    res += get_temperatures()
    return res


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9101)
