#!/usr/bin/env python

import sys
import statsd
from apcaccess import status as apc

stats = ['TIMELEFT', 'LOADPCT', 'OUTPUTV','LINEV']

c = statsd.StatsClient('192.168.3.40', 8125, prefix='ups')

data = apc.parse(apc.get(), strip_units=True)

for stat in stats:
    print "%s = %s" % (stat.lower(), data[stat])
    c.gauge(stat.lower(), data[stat])
