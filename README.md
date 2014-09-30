Boundary AWS ELB Plugin
=======================

The Boundary AWS ELB plugin collects information on AWS [Elastic Load Balancers](http://aws.amazon.com/elasticloadbalancing/) using the [CloudWatch](http://aws.amazon.com/cloudwatch/) API.

The plugin requires Python 2.6 or later, as well as the [Boto Python library](https://github.com/boto/boto).  [Click here](https://github.com/boto/boto#installation) for Boto installation instructions.

## Metrics

The plugin reports all ELB metrics reported by CloudWatch.  For a full list of these metrics and their descriptions, see [this AWS documentation article](http://docs.aws.amazon.com/AmazonCloudWatch/latest/DeveloperGuide/elb-metricscollected.html).

**Note:** CloudWatch will not supply values for metrics that do not have any activity.  For example, the RequestCount metric will not be supplied for periods where there were no requests to a load balancer.  In this case, you will see holes in the Boundary graph.  This is normal and a product of how CloudWatch works.

**Note:** CloudWatch reports ELB metrics in 60 second periods.  You will only see data appear in Boundary every 60 seconds for the preceding 60 seconds.  This is normal and a product of how CloudWatch works.

## Adding the ELB Plugin to Premium Boundary

1. Login into Boundary Premium
2. Display the settings dialog by clicking on the _settings icon_: ![](src/main/resources/settings_icon.png)
3. Click on the _Plugins_ in the settings dialog.
4. Locate the _aws_elb_ plugin item and click on the _Install_ button.
5. A confirmation dialog is displayed indicating the plugin was installed successfully, along with the metrics and the dashboards.
6. Click on the _OK_ button to dismiss the dialog.

## Removing the ELB Plugin from Premium Boundary

1. Login into Boundary Premium
2. Display the settings dialog by clicking on the _settings icon_: ![](src/main/resources/settings_icon.png)
3. Click on the _Plugins_ in the settings dialog which lists the installed plugins.
4. Locate the _aws_elb_ plugin and click on the item, which then displays the uninstall dialog.
5. Click on the _Uninstall_ button which displays a confirmation dialog along with the details on what metrics and dashboards will be removed.
6. Click on the _Uninstall_ button to perfom the actual uninstall and then click on the _Close_ button to dismiss the dialog.

## Configuration

Once the ELB plugin is installed, metric collection requires that a _relay_ is installed on the target system. Instructions on how to install a relay for Linux/Unix can found [here](http://premium-documentation.boundary.com/relays), and for Windows [here](http://premium-support.boundary.com/customer/portal/articles/1656465-installing-relay-on-windows).

Before the plugin will collect metrics, you must provide it with a valid AWS Access Key ID and Secret Access Key.  [Click here](http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSGettingStartedGuide/AWSCredentials.html) for more information on where to find/generate these keys.  The keys you generate should be for a user with access to both CloudWatch and ELB.

General operations for plugins are described in [this article](http://premium-support.boundary.com/customer/portal/articles/1635550-plugins---how-to).

