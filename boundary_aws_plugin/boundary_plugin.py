from __future__ import (absolute_import, division, print_function, unicode_literals)
import logging
import datetime
import time
import socket
import json
import multiprocessing
from contextlib import contextmanager
import sys
import os

HOSTNAME = socket.gethostname()

metric_log_file = None
plugin_params = None
keepalive_process = None
keepalive_lock = None

"""
If the plugin doesn't generate any output for 30 seconds (hard-coded), the
Boundary Relay thinks we're dead and kills us.  Because we may not have any
data to output for much longer than that, we workaround this by outputting
a bogus metric every so often.  This constant controls the delay between
bogus metrics; it should be significantly less than 30 seconds to prevent
any timing issues.
"""
KEEPALIVE_INTERVAL = 15


def log_metrics_to_file(filename):
    """
    Logs all reported metrics to a file for debugging purposes.
    @param filename File name to log to; specify None to disable logging.
    """
    global metric_log_file
    metric_log_file = filename


def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.days * 86400 + delta.seconds + delta.microseconds / 1e6


def unix_time_millis(dt):
    return unix_time(dt) * 1000.0


@contextmanager
def maybe_lock(lock):
    if lock: lock.acquire()
    yield
    if lock: lock.release()
    return


def boundary_report_metric(name, value, source=None, timestamp=None):
    """
    Reports a metric to the Boundary relay.
    @param name Metric name, as defined in the plugin's plugin.json file.
    @param value Metric value, should be a number.
    @param source Metric source.  Defaults to the machine's hostname.
    @param timestamp Timestamp of the metric as a Python datetime object.  Defaults to none
        (Boundary uses the current time in that case).
    """
    with maybe_lock(keepalive_lock) as _:
        source = source or HOSTNAME
        if timestamp:
            timestamp = unix_time_millis(timestamp)
        out = "%s %s %s%s" % (name, value, source, (' %d' % timestamp) if timestamp else '')
        print(out)
        # Flush stdout before we release the lock so output doesn't get intermixed
        sys.stdout.flush()

        global metric_log_file
        if metric_log_file:
            with open(metric_log_file, 'a') as f:
                f.write(out + "\n")


def report_alive():
    """
    Reports a bogus metric just so the Boundary Relay doesn't think we're dead.
    See notes on KEEPALIVE_INTERVAL for more information.
    """
    boundary_report_metric('BOGUS_METRIC', 0)


def parse_params():
    """
    Parses and returns the contents of the plugin's "param.json" file.
    """
    global plugin_params
    if not plugin_params:
        with open('param.json') as f:
            plugin_params = json.loads(f.read())
    return plugin_params


def sleep_interval():
    """
    Sleeps for the plugin's poll interval, as configured in the plugin's parameters.
    """
    params = parse_params()
    time.sleep(float(params.get("pollInterval", 1000) / 1000))


def __keepalive_process_main(parent_pid):
    # Workaround: on Linux, the Boundary Relay's sends SIGTERM to kill the plugin, which kills the main process but
    # doesn't kill the keepalive process.  We work around this by identifying that our parent has died (and
    # accordingly, our parent is now init) and killing ourselves.
    # Note that os.getppid() doesn't exist on Windows, hence the getattr workaround.
    while parent_pid == getattr(os, 'getppid', lambda: parent_pid)():
        report_alive()
        time.sleep(KEEPALIVE_INTERVAL)


def start_keepalive_subprocess():
    """
    Starts the subprocess that keeps us alive by reporting bogus metrics.
    This function should be called only once on plugin startup.
    See notes on KEEPALIVE_INTERVAL for more information.
    """
    global keepalive_lock, keepalive_process

    assert not keepalive_lock and not keepalive_process
    keepalive_lock = multiprocessing.Lock()
    keepalive_process = multiprocessing.Process(target=__keepalive_process_main, args=(os.getpid(),))
    keepalive_process.start()
