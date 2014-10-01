import logging
import datetime
import time
import socket
import json
import sys

from elb_metrics import get_elb_metrics
import boundary_plugin
import status_store

'''
If getting statistics from CloudWatch fails, we will retry up to this number of times before
giving up and aborting the plugin.  Use 0 for unlimited retries.
'''
PLUGIN_RETRY_COUNT = 0
'''
If getting statistics from CloudWatch fails, we will wait this long (in seconds) before retrying.
This value must not be greater than 30 seconds, because the Boundary Relay will think we've
timed out and terminate us after 30 seconds of inactivity.
'''
PLUGIN_RETRY_DELAY = 5

def get_elb_metrics_with_retries(*args, **kwargs):
    '''
    Calls the get_elb_metrics function, taking into account retry configuration.
    '''
    retry_range = xrange(PLUGIN_RETRY_COUNT) if PLUGIN_RETRY_COUNT > 0 else iter(int, 1)
    for _ in retry_range:
        try:
            return get_elb_metrics(*args, **kwargs)
        except Exception as e:
            logging.error("Error retrieving CloudWatch data: %s" % e)
            boundary_plugin.report_alive()
            time.sleep(PLUGIN_RETRY_DELAY)
            boundary_plugin.report_alive()

    logging.fatal("Max retries exceeded retrieving CloudWatch data")
    raise Exception("Max retries exceeded retrieving CloudWatch data")

def handle_elb_metrics(data, reported_metrics):
    # Data format:
    # (RegionId, LoadBalancerName, MetricName) -> [(Timestamp, Value, Statistic), (Timestamp, Value, Statistic), ...]
    for metric_key, metric_list in data.items():
        region_id, load_balancer_name, metric_name = metric_key

        for metric_list_item in metric_list:
            # Do not report duplicate or past samples (note: we are comparing tuples here, which
            # amounts to comparing their timestamps).
            if reported_metrics.get(metric_key, None) >= metric_list_item:
                continue

            metric_timestamp, metric_value, metric_statistic , metric_name_id = metric_list_item

            boundary_plugin.boundary_report_metric(metric_name_id, metric_value, load_balancer_name, metric_timestamp)
            reported_metrics[metric_key] = metric_list_item

    status_store.save_status_store(reported_metrics)

if __name__ == '__main__':

    settings = boundary_plugin.parse_params()
    access_key_id = settings['access_key_id']
    secret_key = settings['secret_key']

    reported_metrics = status_store.load_status_store() or dict()

    logging.basicConfig(level=logging.ERROR, filename=settings.get('log_file', None))
    boundary_plugin.log_metrics_to_file("reports.log")

    # Bring us up to date!  Get all data since the last time we know we reported valid data
    # (minus 20 minutes as a buffer), and report it now, so that we report data on any time
    # this plugin was down for any reason.
    try:
        earliest_timestamp = max(reported_metrics.values(), key=lambda v: v[0])[0] - datetime.timedelta(minutes=20)
    except ValueError:
        # Probably first run or someone deleted our status store file - just start from now
        logging.error("No status store data; starting data collection from now")
        pass
    else:
        logging.error("Starting historical data collection from %s" % earliest_timestamp)
        data = get_elb_metrics_with_retries(access_key_id, secret_key, only_latest=False, start_time=earliest_timestamp, end_time=datetime.datetime.utcnow())
        handle_elb_metrics(data, reported_metrics)
        logging.error("Historical data collection complete")

    while True:
        data = get_elb_metrics_with_retries(access_key_id, secret_key)
        handle_elb_metrics(data, reported_metrics)
        boundary_plugin.sleep_interval()

