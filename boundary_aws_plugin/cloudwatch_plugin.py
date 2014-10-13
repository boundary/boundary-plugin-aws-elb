from __future__ import (absolute_import, division, print_function, unicode_literals)
import logging
import datetime
import time

from . import boundary_plugin
from . import status_store

"""
If getting statistics from CloudWatch fails, we will retry up to this number of times before
giving up and aborting the plugin.  Use 0 for unlimited retries.
"""
PLUGIN_RETRY_COUNT = 0
"""
If getting statistics from CloudWatch fails, we will wait this long (in seconds) before retrying.
This value must not be greater than 30 seconds, because the Boundary Relay will think we've
timed out and terminate us after 30 seconds of inactivity.
"""
PLUGIN_RETRY_DELAY = 5


class CloudwatchPlugin(object):
    def __init__(self, cloudwatch_metrics_type, boundary_metric_prefix, status_store_filename):
        self.cloudwatch_metrics_type = cloudwatch_metrics_type
        self.boundary_metric_prefix = boundary_metric_prefix
        self.status_store_filename = status_store_filename

    def get_metric_data_with_retries(self, *args, **kwargs):
        """
        Calls the get_metric_data function, taking into account retry configuration.
        """
        retry_range = xrange(PLUGIN_RETRY_COUNT) if PLUGIN_RETRY_COUNT > 0 else iter(int, 1)
        for _ in retry_range:
            try:
                return self.cloudwatch_metrics.get_metric_data(*args, **kwargs)
            except Exception as e:
                logging.error("Error retrieving CloudWatch data: %s" % e)
                boundary_plugin.report_alive()
                time.sleep(PLUGIN_RETRY_DELAY)
                boundary_plugin.report_alive()

        logging.fatal("Max retries exceeded retrieving CloudWatch data")
        raise Exception("Max retries exceeded retrieving CloudWatch data")

    def handle_metrics(self, data, reported_metrics):
        # Data format:
        # (RegionId, EntityName, MetricName) -> [(Timestamp, Value, Statistic), (Timestamp, Value, Statistic), ...]
        for metric_key, metric_list in data.items():
            region_id, entity_name, metric_name = metric_key

            for metric_list_item in metric_list:
                # Do not report duplicate or past samples (note: we are comparing tuples here, which
                # amounts to comparing their timestamps).
                if reported_metrics.get(metric_key, (datetime.datetime.min,)) >= metric_list_item:
                    continue

                metric_timestamp, metric_value, metric_statistic = metric_list_item

                boundary_plugin.boundary_report_metric(self.boundary_metric_prefix + metric_name,
                                                       metric_value, entity_name, metric_timestamp)
                reported_metrics[metric_key] = metric_list_item

        status_store.save_status_store(self.status_store_filename, reported_metrics)

    def main(self):
        settings = boundary_plugin.parse_params()
        reported_metrics = status_store.load_status_store(self.status_store_filename) or dict()

        logging.basicConfig(level=logging.ERROR, filename=settings.get('log_file', None))
        reports_log = settings.get('report_log_file', None)
        if reports_log:
            boundary_plugin.log_metrics_to_file(reports_log)
        boundary_plugin.start_keepalive_subprocess()

        self.cloudwatch_metrics = self.cloudwatch_metrics_type(settings['access_key_id'], settings['secret_key'])

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
            data = self.get_metric_data_with_retries(only_latest=False,
                                                     start_time=earliest_timestamp, end_time=datetime.datetime.utcnow())
            self.handle_metrics(data, reported_metrics)
            logging.error("Historical data collection complete")

        while True:
            data = self.get_metric_data_with_retries()
            self.handle_metrics(data, reported_metrics)
            boundary_plugin.sleep_interval()
