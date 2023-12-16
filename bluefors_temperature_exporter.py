from flask import Flask
import datetime

app = Flask(__name__)

@app.route("/metrics")
def metrics():
    today = datetime.date.today()

    log_folder_path = ('C:/Users/User/Documents/LabVIEW Data/LVInternalReports/Lsci372Reader/4.3.8.0/')
    res = ''
    for stage, channel_num in enumerate([1, 2, 5, 6], 1):
        log_file_path = f'{today.strftime("%y-%m-%d")}/CH{channel_num} T {today.strftime("%y-%m-%d")}.log'
        temperature = float("NaN")
        try:
            with open(log_folder_path + log_file_path, "r") as log_file:
                line = log_file.readlines()[-1].split(',')
                file_time = datetime.time.fromisoformat(line[1])
                time_diff = datetime.datetime.now() - datetime.datetime.combine(today, file_time)
                if time_diff.seconds < 120:
                    temperature = line[2]
        except FileNotFoundError:
            pass
        res += f'bluefors_temperature{{stage="{stage}"}} {temperature}'
    return res

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9101)