#!/usr/bin/env python

import sys
import statsd
import tellcore.telldus as td
import tellcore.constants as const

if sys.version_info < (3, 0):
    import tellcore.library as lib
    lib.Library.DECODE_STRINGS = False

core = td.TelldusCore()
sensors = core.sensors()

valid_sensors = dict()
valid_sensors[21] = 'stue'
valid_sensors[31] = 'server'
valid_sensors[51] = 'kjokken'

c = statsd.StatsClient('192.168.3.42', 8125, prefix='telldus')

for sensor in sensors:
	if sensor.id in valid_sensors.keys():
		print '%s - %s' % (sensor.id, valid_sensors[sensor.id])
		temp = sensor.temperature()
		print temp.value
		c.gauge(valid_sensors[sensor.id], temp.value)


