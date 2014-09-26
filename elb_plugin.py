import logging
import datetime
import time
import socket
import json

from elb_metrics import get_elb_metrics
import boundary_plugin
import status_store

'''
If getting statistics from CloudWatch fails, we will retry up to this number of times before
giving up and aborting the plugin.  Use 0 for unlimited retries.
WARNING: Due to a Boundary Relay 
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
    settings = boundary_plugin.parse_params()
    reported_metrics = status_store.load_status_store() or dict()

    logging.basicConfig(level=logging.ERROR, filename=settings.get('log_file', None))
    boundary_plugin.log_metrics_to_file("reports.log")

    while True:
        data = get_elb_metrics_with_retries(settings['access_key_id'], settings['secret_access_key'])
        flat_data = flatten_elb_metrics(data)

        for k,v in flat_data.items():
            # Do not report duplicate samples, since Boundary sums them up
            # instead of ignoring them.
            if reported_metrics.get(k, None) == v:
                continue

            lb_name, metric_name = k
            metric_timestamp, metric_value = v

            reported_metrics[k] = v
            boundary_plugin.boundary_report_metric('AWS_ELB_' + metric_name, metric_value, 'ELB_' + lb_name, metric_timestamp)

        status_store.save_status_store(reported_metrics)
        boundary_plugin.sleep_interval()

