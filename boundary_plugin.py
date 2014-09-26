import logging
import datetime
import time
import socket
import json

HOSTNAME = socket.gethostname()

metric_log_file = None
plugin_params = None
'''
Used for the anti-timeout workaround in sleep_interval.  See function documentation
for more information.
'''
reported_anything = False

def log_metrics_to_file(filename):
    '''
    Logs all reported metrics to a file for debugging purposes.
    @param filename File name to log to; specify None to disable logging.
    '''
    metric_log_file = filename

def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.days * 86400 + delta.seconds + delta.microseconds / 1e6

def unix_time_millis(dt):
    return unix_time(dt) * 1000.0

def boundary_report_metric(name, value, source=None, timestamp=None):
    '''
    Reports a metric to the Boundary relay.
    @param name Metric name, as defined in the plugin's plugin.json file.
    @param value Metric value, should be a number.
    @param source Metric source.  Defaults to the machine's hostname.
    @param timestamp Timestamp of the metric as a Python datetime object.  Defaults to none
        (Boundary uses the current time in that case).
    '''
    source = source or HOSTNAME
    if timestamp:
        timestamp = unix_time_millis(timestamp)
    out = "%s %s %s%s" % (name, value, source, (' %d' % timestamp) if timestamp else '')
    print out

    global metric_log_file
    if metric_log_file:
        with open(metric_log_file, 'a') as f:
            f.write(out + "\n")

    reported_anything = True

def report_alive():
    '''
    Reports a bogus metric just so the Boundary Relay doesn't think we're dead.
    See function notes on sleep_interval for more information.
    '''
    boundary_report_metric('BOGUS_METRIC', 0)

def parse_params():
    '''
    Parses and returns the contents of the plugin's "param.json" file.
    '''
    global plugin_params
    if not plugin_params:
        with open('param.json') as f:
            plugin_params = json.loads(f.read())
    return plugin_params

def sleep_interval(alive_workaround=True):
    '''
    Sleeps for the plugin's poll interval, as configured in the plugin's parameters.
    TEMPORARY WORKAROUND: If no metric has been reported since the last sleep, this
    function also reports a bogus metric just so Boundary Relay doesn't think we're
    dead (it times out after a hard-coded 30 seconds of no output).  It looks like
    the unknown metrics are currently ignored by the upstream API.
    @param alive_workaround Whether to enable the temporary anti-timeout workaround
        detailed above.
    '''
    if alive_workaround:
        global reported_anything
        if not reported_anything:
            report_alive()

    params = parse_params()
    time.sleep(float(params.get("pollInterval", 1000) / 1000))

    reported_anything = False
