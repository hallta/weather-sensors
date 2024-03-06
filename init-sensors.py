#!/usr/bin/env python

from smbus2 import SMBus
from bme280 import BME280
from gpiozero import Button

import math
import glob
import time
import json
import random
import requests
import sys
import os
from datetime import datetime, timedelta


class DS18B20(object):
    def __init__(self):
        self.device_file = glob.glob("/sys/bus/w1/devices/28*")[0] + "/w1_slave"

    def read_temp_raw(self):
        f = open(self.device_file, "r")
        lines = f.readlines()
        f.close()
        return lines

    def crc_check(self, lines):
        return lines[0].strip()[-3:] == "YES"

    def read_temp(self):
        temp_c = -255
        attempts = 0

        lines = self.read_temp_raw()
        success = self.crc_check(lines)

        while not success and attempts < 3:
            time.sleep(.2)
            lines = self.read_temp_raw()
            success = self.crc_check(lines)
            attempts += 1

        if success:
            temp_line = lines[1]
            equal_pos = temp_line.find("t=")
            if equal_pos != -1:
                temp_string = temp_line[equal_pos+2:]
                temp_c = float(temp_string)/1000.0

        return temp_c

## Globals

i = 0
interval = 30
#interval = 5
bus = SMBus(1)
bme280 = BME280(i2c_dev=bus)
ds18b = DS18B20()
wind = Button(5)
wind_count = 0
rain = Button(6)
rain_count = 0

RAIN_PER_BUCKET=0.2794 # mm
MM_TO_INCH=25.4

## Functions

def put(t, type, state, value, md):
    sql = 'insert into sensor_data values(?, ?, ?, ?, ?)'
    params = [[t, type, state, value, md]]
    payload = '"sql": "{}", "params": {}'.format(sql, json.dumps(params))
    host = os.getenv('HOST')
    port = os.getenv('PORT')

    r = requests.post("http://{}:{}/sql/1/put".format(host, port),
                        data='{' + payload + '}',
                        headers={'content-type': 'application/json'})

    return r.status_code != 200


def speed_cmh(i):
    # All in cm

    global wind_count

    cir = (2 * math.pi) * 9 # radius = 9cm
    rot = wind_count / 2
    dist = cir * rot
    cmh = dist / i

    return cmh


def spin():
    global wind_count
    wind_count = wind_count + 1


def rain_catch():
    global rain_count
    rain_count = rain_count + 1


def get_rainfall():
    total_fallen = rain_count * RAIN_PER_BUCKET
    return total_fallen


wind.when_pressed = spin
rain.when_pressed = rain_catch
while True:
    temperature = bme280.get_temperature()
    pressure = bme280.get_pressure()
    humidity = bme280.get_humidity()
    soiltemp = ds18b.read_temp()
    wind_cmh = round(speed_cmh(interval), 2)
    wind_mph = round((wind_cmh / 160900), 2)
    rain_mm  = get_rainfall()
    rain_in  = round(rain_mm / 25.4, 2)

    state = 'init' if (i == 0) else 'post-init'

    put(int(time.time()), 'temperature', state, temperature, '{}')
    put(int(time.time()), 'pressure', state, pressure, '{}')
    put(int(time.time()), 'humidity', state, humidity, '{}')
    put(int(time.time()), 'soil_temp', state, soiltemp, '{}')
    put(int(time.time()), 'wind_cmh', state, wind_cmh, '{}')
    put(int(time.time()), 'wind_mph', state, wind_mph, '{}')
    put(int(time.time()), 'rain_mm', state, rain_mm, '{}')
    put(int(time.time()), 'rain_in', state, rain_in, '{}')

    print(f"{temperature:05.2f}°C, " +
        f"{pressure:05.2f}hPa, " +
        f"{humidity:05.2f}%, " +
        f"{soiltemp:05.2f}°C " +
        f"{wind_cmh:05.2f}cm/h " +
        f"{wind_mph:05.2f}mp/h " +
        f"{rain_mm:05.2f}mm " +
        f"{rain_in:05.2f}in"
        )

    time.sleep(interval)

    i = i + 1
    wind_count = 0
    rain_count = 0
