from __future__ import (absolute_import, division, print_function, unicode_literals)
import boto
import boto.ec2.cloudwatch
import datetime
import logging
import abc

class CloudwatchMetrics(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, access_key_id, secret_access_key, cloudwatch_namespace):
        '''
        Initializes the class.
        @param access_key_id AWS Access Key ID.
        @param secret_access_key AWS Secret Access Key.
        @param cloudwatch_namespace The namespace of all metrics this class will
            request from CloudWatch, e.g. 'AWS/ELB'.
        '''
        self.access_key_id, self.secret_access_key = access_key_id, secret_access_key
        self.cloudwatch_namespace = cloudwatch_namespace

    @abc.abstractmethod
    def get_region_list(self):
        '''
        Returns a list of boto.regioninfo.RegionInfo objects for all regions this class
        will be getting metrics for.
        Abstract method, to be implemented by child classes.
        '''
        raise NotImplementedError()

    @abc.abstractmethod
    def get_entities_for_region(self, region):
        '''
        Returns a list of entities to get metrics for in a given region.
        @param region The boto.regioninfo.RegionInfo object for the region to get entities for.
        Abstract method, to be implemented by child classes.
        '''
        raise NotImplementedError()

    @abc.abstractmethod
    def get_entity_dimensions(self, region, entity):
        '''
        Returns a dictionary of dimensions needed to get metrics for a given entity (this
        will be an entity returned by get_entities_for_region).
        Abstract method, to be implemented by child classes.
        '''
        raise NotImplementedError()

    def get_entity_source_name(self, entity):
        '''
        Returns the source name to be reported for an entity
        (typically, this will be the entity's name).  Override if the entities used
        in a child class do not have a "name" property.
        '''
        return entity.name

    @abc.abstractmethod
    def get_metric_list(self):
        '''
        Returns a list of metrics to be retrieved for each entity.
        Each tuple in the list should have the form
            (metric_name, statistic, metric_name_id, [metric_description])
        where
            metric_name is the AWS metric name (e.g. HTTPCode_ELB_4XX)
            statistic is the statistic to collect (e.g. Sum or Average)
            metric_name_id is the metric identifier in Boundary (e.g. AWS_ELB_HTTP_CODE_4XX)
            metric_description is an optional metric description (not used by the plugin directly)

        Abstract method, to be implemented by child classes.
        '''
        raise NotImplementedError()

    def get_metric_data(self, only_latest=True, start_time=None, end_time=None):
        '''
        Retrieves AWS ELB metrics from CloudWatch.
        @param only_latest True to return only the single latest sample for each metric; False to return
            all the metrics returned between start_time and end_time.
        @param start_time The earliest metric time to retrieve (inclusive); defaults to 20 minutes before end_time.
        @param end_time The latest metric time to retrieve (exclusive); defaults to now.
        @return A dictionary, in the following format:
            {(RegionId, EntityName, MetricName): [(Timestamp, Value, Statistic), (Timestamp, Value, Statistic), ...],
             (RegionId, EntityName, MetricName): [(Timestamp, Value, Statistic), (Timestamp, Value, Statistic), ...], ...}
            That is, the dictionary keys are tuples of the region, entity name and metric name, and the
            dictionary values are lists of tuples of timestamp, value and statistic (TVS).  The TVS lists are
            guaranteed to be sorted in ascending order (latest timestamp last).
            If only_latest is True, each TVS list is guaranteed to have at most one
            value (but may have zero if no data is available for the requested range).

        @note AWS reports metrics in either 60-second or 5-minute intervals, depending on monitoring service level and metric.
            Keep in mind that even if end_time is now, the latest datapoint returned may be up to 5 minutes in the past.
        @note The Timestamp value will be for the *beginning* of each period.  For example, for a period of 60 seconds, a metric
            returned with a timestamp of 11:23 will be for the period of [11:23, 11:24); or the period of 11:23:00 through 11:23:59.999.
        '''
        logger = logging.getLogger('CloudwatchMetrics')

        # Note: although we want a 60-second period, not all CloudWatch metrics are provided in 60-second
        # periods, depending on service level and metric.  Instead, query the last 20 minutes, and take
        # the latest period we can get.
        period = 60
        end_time = end_time or datetime.datetime.utcnow()
        start_time = start_time or (end_time - datetime.timedelta(minutes=20))

        # CloudWatch can return a maximum of 1,440 datapoints in a single call.  With a period of 60 seconds, that
        # works out to 1,440 minutes = 24 hours.  If we need more than 24 hours of data, split into a number of
        # calls.  To prevent off-by-one issues, use 23 hours as the maximum time.
        time_ranges = []
        while end_time - start_time > datetime.timedelta(hours=23):
            block_end = start_time + datetime.timedelta(hours=23)
            time_ranges.append((start_time, block_end))
            start_time = block_end
        # Use a 30-second buffer for equality checks so we ignore things like leap seconds
        # (the CloudWatch period is 60 seconds anyway, so any less than that doesn't matter)
        if end_time - start_time > datetime.timedelta(seconds=30):
            time_ranges.append((start_time, end_time))

        out = dict()
        for region in self.get_region_list():
            logger.info("Region: %s", region.name)

            cw = boto.ec2.cloudwatch.connect_to_region(region.name, aws_access_key_id=self.access_key_id, aws_secret_access_key=self.secret_access_key)

            entities = self.get_entities_for_region(region)
            for entity in entities:
                logger.info("\tEntity: %s" % self.get_entity_source_name(entity))

                for metric in self.get_metric_list():
                    metric_name, metric_statistic, metric_boundary_id = metric[:3]
                    logger.info("\t\tMetric: %s %s %s" % (metric_name, metric_statistic, metric_boundary_id))
                    
                    data = []
                    for st, et in time_ranges:
                        data.extend(cw.get_metric_statistics(period=period, start_time=st, end_time=et,
                                                             metric_name=metric_name, namespace=self.cloudwatch_namespace,
                                                             statistics=metric_statistic,
                                                             dimensions=self.get_entity_dimensions(region, entity)))

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
                        logger.info("\t\t\tValue: %s: %s" % (sample['Timestamp'], sample[metric_statistic]))
                        out_metric.append((sample['Timestamp'], sample[metric_statistic], metric_statistic))
                    out[(region.name, self.get_entity_source_name(entity), metric_boundary_id)] = out_metric

        return out
