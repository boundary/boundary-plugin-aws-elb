import logging
import datetime
import time
import socket
import json

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
    out = "%s %s %s%s" % (stat_name, stat_value, stat_source, (' %d' % stat_timestamp) if stat_timestamp else '')
    print out
    with open('reports.log', 'a') as f:
        f.write(out + "\n")

def parse_params():
    with open('param.json') as f:
        params = json.loads(f.read())
        return params

def flatten_elb_metrics(data):
    '''
    Converts the data returned by elb_metrics.get_elb_metrics into a flat dictionary.
    @return A dictionary, with each key being a tuple
        (LoadBalancerName, MetricName)
    and the value being a tuple
        (Timestamp, Value)
    '''
    out = dict()
    for lb_name,lb_data in data.items():
        for metric_name,metric_data in lb_data.items():
            out[(lb_name, metric_name)] = (metric_data['Timestamp'], metric_data['Value'])
    return out

if __name__ == '__main__':
    settings = parse_params()

    logging.basicConfig(level=logging.ERROR, filename=settings.get('log_file', None))

    reported_metrics = dict()
    while True:
        data = get_elb_metrics(settings['access_key_id'], settings['secret_access_key'])
        flat_data = flatten_elb_metrics(data)

        for k,v in flat_data.items():
            # Do not report duplicate samples, since Boundary sums them up
            # instead of ignoring them.
            # TEMPORARY WORKAROUND: Always report the HealthyHostCount metric, because
            # if we report nothing the relay thinks we're dead.  That specific metric
            # doesn't hurt to report multiple times, because it's averaged out anyway.
            if reported_metrics.get(k, None) == v and k[1] != 'HealthyHostCount':
                continue

            lb_name, metric_name = k
            metric_timestamp, metric_value = v

            reported_metrics[k] = v
            boundary_report_stat('AWS_ELB_' + metric_name, metric_value, 'ELB_' + lb_name, metric_timestamp)

        time.sleep(float(settings.get("pollInterval", 60*1000) / 1000))

