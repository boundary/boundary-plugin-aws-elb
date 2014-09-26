import boto
import datetime
import logging

__all__ = ['get_elb_metrics']

'''
List of all ELB metrics we will collect.  Each tuple in the list should have the form
    (metric_name, [statistic])
where metric_name is the AWS metric name, and statistic is the statistic to collect (defaults to 'Sum'
if not provided).
'''
ELB_METRICS = (
    ('HealthyHostCount', 'Average'),
    ('UnHealthyHostCount', 'Average'),
    ('RequestCount',),
    ('Latency', 'Average'),
    ('HTTPCode_ELB_4XX',),
    ('HTTPCode_ELB_5XX',),
    ('HTTPCode_Backend_2XX',),
    ('HTTPCode_Backend_3XX',),
    ('HTTPCode_Backend_4XX',),
    ('HTTPCode_Backend_5XX',),
    ('BackendConnectionErrors',),
    ('SurgeQueueLength', 'Maximum'),
    ('SpilloverCount',),
)

def get_elb_metrics(access_key_id, secret_access_key, only_latest=True, start_time=None, end_time=None):
    '''
    Retrieves latest values for all AWS ELB metrics.
    @param access_key_id AWS Access Key ID.
    @param secret_access_key AWS Secret Access Key.
    @param only_latest True to return only the single latest sample for each metric; False to return
        all the metrics returned between start_time and end_time.
    @param start_time The earliest metric time to retrieve (inclusive); defaults to 20 minutes before end_time.
    @param end_time The latest metric time to retrieve (exclusive); defaults to now.
    @return A dictionary, with keys being load balancer names and values being
        dictionaries of metrics.  In the metrics dictionary, the metric name is the
        key and the value is itself a dictionary, as follows:
        {'LoadBalancerName': {'Metric1': {'Timestamp': datetime_object, 'Value': metric_value, 'Statistic': statistic}},
                             {'Metric2': {'Timestamp': datetime_object, 'Value': metric_value, 'Statistic': statistic}},
        }
        If only_latest is False, the value of the metric dictionary will be a list of dictionaries instead of a single one,
        as follows:
        {'LoadBalancerName': {'Metric1': [{'Timestamp': datetime_object, 'Value': metric_value, 'Statistic': statistic}, ...]},
                             {'Metric2': [{'Timestamp': datetime_object, 'Value': metric_value, 'Statistic': statistic}, ...]},
        }
    @note AWS reports metrics in either 60-second or 5-minute intervals, depending on monitoring service level and metric.
        This function will return the latest datapoint for each metric, but keep in mind that datapoint may be up to 5
        minutes in the past.
    @note The Timestamp value will be for the *beginning* of each period.  For example, for a period of 60 seconds, a metric
        returned with a timestamp of 11:23 will be for the period of [11:23, 11:24); or the period of 11:23:00 through 11:23:59.999.
    '''
    logger = logging.getLogger('get_elb_metrics')
    # TBD: May need to iterate regions?

    out = dict()

    elb = boto.connect_elb(access_key_id, secret_access_key)
    cw = boto.connect_cloudwatch(access_key_id, secret_access_key)

    # Note: although we want a 60-second period, not all ELB metrics are provided in 60-second
    # periods, depending on service level and metric.  Instead, query the last 20 minutes, and take
    # the latest period we can get.
    period = 60
    end_time = end_time or datetime.datetime.utcnow()
    start_time = start_time or (end_time - datetime.timedelta(minutes=20))

    load_balancers = elb.get_all_load_balancers()
    for lb in load_balancers:
        out_lb = dict()
        logger.info("ELB: %s" % lb.name)

        for metric in ELB_METRICS:
            metric_name = metric[0]
            metric_statistic = metric[1] if len(metric) > 1 else 'Sum'
            logger.info("\tELB Metric: %s %s" % (metric_name, metric_statistic))
            
            data = cw.get_metric_statistics(period=period, start_time=start_time, end_time=end_time,
                                            metric_name=metric_name, namespace='AWS/ELB',
                                            statistics=metric_statistic,
                                            dimensions=dict(LoadBalancerName=lb.name))
            if not data:
                logger.info("\t\tNo data")
                continue

            if only_latest:
                # Pick out the latest sample
                sample = max(data, key=lambda d: d['Timestamp'])
                
                logger.info("\t\tELB Value: %s: %s" % (sample['Timestamp'], sample[metric_statistic]))
                out_lb[metric_name] = {'Timestamp': sample['Timestamp'], 'Value': sample[metric_statistic], 'Statistic': metric_statistic}
            else:
                # Output all retrieved samples as a list, sorted by timestamp
                data = sorted(data, key=lambda d: d['Timestamp'])
                out_metric = []
                for sample in data:
                    logger.info("\t\tELB Value: %s: %s" % (sample['Timestamp'], sample[metric_statistic]))
                    out_metric.append({'Timestamp': sample['Timestamp'], 'Value': sample[metric_statistic], 'Statistic': metric_statistic})
                out_lb[metric_name] = out_metric

        out[lb.name] = out_lb

    return out

# For testing, if this script is called directly, attempt to get some data and
# print it nicely.
if __name__ == '__main__':
    import pprint
    from elb_plugin import parse_params

    logging.basicConfig(level=logging.INFO)
    settings = parse_params()

    data = get_elb_metrics(settings['access_key_id'], settings['secret_access_key'])
    pprint.pprint(data)

