import logging
import datetime
import time
import socket

import settings
from elb_metrics import get_elb_metrics

HOSTNAME = socket.gethostname()

def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.days * 86400 + delta.seconds + delta.microseconds / 1e6

def unix_time_millis(dt):
    return unix_time(dt) * 1000.0

def boundary_report_stat(stat_name, stat_value, stat_source=None, stat_timestamp=None):
    stat_source = stat_source or HOSTNAME
    if stat_timestamp:
        stat_timestamp = unix_time_millis(stat_timestamp)
    print "%s %s %s%s" % (stat_name, stat_value, stat_source, (' %d' % stat_timestamp) if stat_timestamp else '')

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, filename=getattr(settings, 'LOG_FILE', None))

    while True:
        data = get_elb_metrics(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)

        for lb_name,lb_data in data.items():
            for metric_name,metric_data in lb_data.items():
                boundary_report_stat('AWS_ELB_' + metric_name, metric_data['Value'], 'ELB_' + lb_name, metric_data['Timestamp'])

        print ""
        time.sleep(float(settings.POLL_INTERVAL) / 1000)

