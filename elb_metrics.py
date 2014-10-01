import boto
import boto.ec2.elb
import datetime
import logging
from boto.ec2.cloudwatch import CloudWatchConnection
from boto.ec2 import RegionInfo

__all__ = ['get_elb_metrics']

'''
List of all ELB metrics we will collect.  Each tuple in the list should have the form
    (metric_name, statistic, metric_name_id)
where
  metric_name is the AWS metric name
  statistic is the statistic to collect
  metric_name_id is the metric identifier in Boundary
'''
ELB_METRICS = (
    ('HealthyHostCount', 'Average','AWS_ELB_HEALTHY_HOST_COUNT'),
    ('UnHealthyHostCount', 'Average','AWS_ELB_UNHEALTHY_HOST_COUNT'),
    ('RequestCount','Sum','AWS_ELB_REQUEST_COUNT'),
    ('Latency', 'Average','AWS_ELB_LATENCY'),
    ('HTTPCode_ELB_4XX','Sum','AWS_ELB_HTTP_CODE_4XX'),
    ('HTTPCode_ELB_5XX','Sum','AWS_ELB_HTTP_CODE_5XX'),
    ('HTTPCode_Backend_2XX','Sum','AWS_ELB_HTTP_CODE_BACKEND_2XX'),
    ('HTTPCode_Backend_3XX','Sum','AWS_ELB_HTTP_CODE_BACKEND_3XX'),
    ('HTTPCode_Backend_4XX','Sum','AWS_ELB_HTTP_CODE_BACKEND_4XX'),
    ('HTTPCode_Backend_5XX','Sum','AWS_ELB_HTTP_CODE_BACKEND_5XX'),
    ('BackendConnectionErrors','Sum','AWS_ELB_BACKEND_CONNECTION_ERRORS'),
    ('SurgeQueueLength', 'Maximum','AWS_ELB_SURGE_QUEUE_LENGTH'),
    ('SpilloverCount','Sum','AWS_ELB_SPILLOVER_COUNT'),
)

def get_elb_metrics(access_key_id, secret_access_key, only_latest=True, start_time=None, end_time=None):
    '''
    Retrieves AWS ELB metrics from CloudWatch.
    @param access_key_id AWS Access Key ID.
    @param secret_access_key AWS Secret Access Key.
    @param only_latest True to return only the single latest sample for each metric; False to return
        all the metrics returned between start_time and end_time.
    @param start_time The earliest metric time to retrieve (inclusive); defaults to 20 minutes before end_time.
    @param end_time The latest metric time to retrieve (exclusive); defaults to now.
    @return A dictionary, in the following format:
        {(RegionId, LoadBalancerName, MetricName): [(Timestamp, Value, Statistic), (Timestamp, Value, Statistic), ...],
         (RegionId, LoadBalancerName, MetricName): [(Timestamp, Value, Statistic), (Timestamp, Value, Statistic), ...], ...}
        That is, the dictionary keys are tuples of the region, load balancer name and metric name, and the
        dictionary values are lists of tuples of timestamp, value and statistic (TVS).  The TVS lists are
        guaranteed to be sorted in ascending order (latest timestamp last).
        If only_latest is True, each TVS list is guaranteed to have at most one
        value (but may have zero if no data is available for the requested range).

    @note AWS reports metrics in either 60-second or 5-minute intervals, depending on monitoring service level and metric.
        Keep in mine that even if end_time is now, the latest datapoint returned may be up to 5 minutes in the past.
    @note The Timestamp value will be for the *beginning* of each period.  For example, for a period of 60 seconds, a metric
        returned with a timestamp of 11:23 will be for the period of [11:23, 11:24); or the period of 11:23:00 through 11:23:59.999.
    '''
    logger = logging.getLogger('get_elb_metrics')

    # Note: although we want a 60-second period, not all ELB metrics are provided in 60-second
    # periods, depending on service level and metric.  Instead, query the last 20 minutes, and take
    # the latest period we can get.
    period = 60
    end_time = end_time or datetime.datetime.utcnow()
    start_time = start_time or (end_time - datetime.timedelta(minutes=20))

    out = dict()
    for region in boto.ec2.elb.regions():
        logger.info("Region: %s", region.name)
        # Some regions are returned that actually do not support EC2.  Skip those.
        if region.name in ['cn-north-1', 'us-gov-west-1']:
            continue
        elb = boto.connect_elb(access_key_id, secret_access_key, region=region)
        cloud_watch = boto.connect_cloudwatch(access_key_id, secret_access_key,region=region)

        load_balancers = elb.get_all_load_balancers()
        for lb in load_balancers:
            logger.info("\tELB: %s" % lb.name)

            for metric in ELB_METRICS:
                # AWS ELB Metric Name
                metric_name = metric[0]
                # AWS Statistic
                metric_statistic = metric[1]
                # Boundary metric identifier
                metric_name_id = metric[2]
                logger.info("\t\tELB Metric: %s %s %s" % (metric_name, metric_statistic, metric_name_id))
                
                region = RegionInfo(name=region.name,endpoint="monitoring." + region.name + ".amazonaws.com")
                cw = boto.connect_cloudwatch(access_key_id, secret_access_key,region=region)
                data = cw.get_metric_statistics(period=period, start_time=start_time, end_time=end_time,
                                                metric_name=metric_name, namespace='AWS/ELB',
                                                statistics=metric_statistic,
                                                dimensions=dict(LoadBalancerName=lb.name))
                if not data:
                    logger.info("\t\t\tNo data")
                    continue

                if only_latest:
                    # Pick out the latest sample only
                    data = [max(data, key=lambda d: d['Timestamp'])]
                else:
                    # Output all retrieved samples as a list, sorted by timestamp
                    data = sorted(data, key=lambda d: d['Timestamp'])

                out_metric = []
                for sample in data:
                    logger.info("\t\t\tELB Value: %s: %s" % (sample['Timestamp'], sample[metric_statistic]))
                    out_metric.append((sample['Timestamp'], sample[metric_statistic], metric_statistic, metric_name_id))
                out[(region.name, lb.name, metric_name)] = out_metric

    return out

# For testing, if this script is called directly, attempt to get some data and
# print it nicely.
if __name__ == '__main__':
    import pprint
    from boundary_plugin import parse_params

    logging.basicConfig(level=logging.ERROR)
    settings = parse_params()

    data = get_elb_metrics(settings['access_key_id'], settings['secret_key'])
    pprint.pprint(data)

