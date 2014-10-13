import boto
import boto.ec2.elb
import sys

from boundary_aws_plugin.cloudwatch_plugin import CloudwatchPlugin
from boundary_aws_plugin.cloudwatch_metrics import CloudwatchMetrics


class ElbCloudwatchMetrics(CloudwatchMetrics):
    def __init__(self, access_key_id, secret_access_key):
        return super(ElbCloudwatchMetrics, self).__init__(access_key_id, secret_access_key, 'AWS/ELB')

    def get_region_list(self):
        # Some regions are returned that actually do not support EC2.  Skip those.
        return [r for r in boto.ec2.elb.regions() if r.name not in ['cn-north-1', 'us-gov-west-1']]

    def get_entities_for_region(self, region):
        elb = boto.connect_elb(self.access_key_id, self.secret_access_key, region=region)
        return elb.get_all_load_balancers()

    def get_entity_dimensions(self, region, load_balancer):
        return dict(LoadBalancerName=load_balancer.name)

    def get_metric_list(self):
        return (
            ('HealthyHostCount', 'Average', 'AWS_ELB_HEALTHY_HOST_COUNT'),
            ('UnHealthyHostCount', 'Average', 'AWS_ELB_UNHEALTHY_HOST_COUNT'),
            ('RequestCount', 'Sum', 'AWS_ELB_REQUEST_COUNT'),
            ('Latency', 'Average', 'AWS_ELB_LATENCY'),
            ('HTTPCode_ELB_4XX', 'Sum', 'AWS_ELB_HTTP_CODE_4XX'),
            ('HTTPCode_ELB_5XX', 'Sum', 'AWS_ELB_HTTP_CODE_5XX'),
            ('HTTPCode_Backend_2XX', 'Sum', 'AWS_ELB_HTTP_CODE_BACKEND_2XX'),
            ('HTTPCode_Backend_3XX', 'Sum', 'AWS_ELB_HTTP_CODE_BACKEND_3XX'),
            ('HTTPCode_Backend_4XX', 'Sum', 'AWS_ELB_HTTP_CODE_BACKEND_4XX'),
            ('HTTPCode_Backend_5XX', 'Sum', 'AWS_ELB_HTTP_CODE_BACKEND_5XX'),
            ('BackendConnectionErrors', 'Sum', 'AWS_ELB_BACKEND_CONNECTION_ERRORS'),
            ('SurgeQueueLength', 'Maximum', 'AWS_ELB_SURGE_QUEUE_LENGTH'),
            ('SpilloverCount', 'Sum', 'AWS_ELB_SPILLOVER_COUNT'),
        )


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '-v':
        import logging
        logging.basicConfig(level=logging.INFO)

    plugin = CloudwatchPlugin(ElbCloudwatchMetrics, '', 'boundary-plugin-aws-elb-python-status')
    plugin.main()

