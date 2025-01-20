import time

from serial import Serial

BAUDRATE = 115200
ADDRESS = '/dev/cu.usbserial-1420'

class LiquidNitrogenLevelMeter:
    def __init__(self):
        self._inst = Serial(ADDRESS, baudrate=BAUDRATE, timeout=2)
        time.sleep(10)

    def write(self, scpi_cmd: str) -> int:
        scpi_bytes = (scpi_cmd + '\n').encode()
        self._inst.write(scpi_bytes)
        return 0

    def query(self, scpi_cmd: str) -> str:
        self.write(scpi_cmd)
        return self._inst.readline().decode('utf-8').strip()

    def measure_level(self):
        return float(self.query(':LEVel:MEASure?'))