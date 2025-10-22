"""CloudWatch integration for monitoring and alerting."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from ..utils.config import get_config
from ..utils.logger import get_logger


class MetricData(BaseModel):
    """CloudWatch metric data model."""

    metric_name: str = Field(description="Name of the metric")
    namespace: str = Field(description="CloudWatch namespace")
    dimensions: Dict[str, str] = Field(
        default_factory=dict, description="Metric dimensions"
    )
    value: float = Field(description="Metric value")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    unit: str = Field(default="Count", description="Metric unit")


class AlarmConfig(BaseModel):
    """CloudWatch alarm configuration."""

    alarm_name: str = Field(description="Name of the alarm")
    metric_name: str = Field(description="Metric to monitor")
    namespace: str = Field(description="CloudWatch namespace")
    dimensions: Dict[str, str] = Field(
        default_factory=dict, description="Metric dimensions"
    )
    threshold: float = Field(description="Alarm threshold")
    comparison_operator: str = Field(description="Comparison operator")
    evaluation_periods: int = Field(
        default=2, description="Number of evaluation periods"
    )
    period: int = Field(default=300, description="Period in seconds")
    statistic: str = Field(default="Average", description="Statistic to use")
    unit: str = Field(default="Count", description="Metric unit")
    alarm_description: str = Field(description="Description of the alarm")
    alarm_actions: List[str] = Field(
        default_factory=list, description="SNS topics for alarm actions"
    )
    ok_actions: List[str] = Field(
        default_factory=list, description="SNS topics for OK actions"
    )


class CloudWatchMonitor:
    """CloudWatch monitoring and alerting integration."""

    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("cloudwatch-monitor")

        # Initialize CloudWatch client
        self.cloudwatch = boto3.client("cloudwatch", region_name=self.config.aws.region)

        # Initialize SNS client for notifications
        self.sns = boto3.client("sns", region_name=self.config.aws.region)

    def put_metric(self, metric_data: MetricData) -> bool:
        """Put a custom metric to CloudWatch."""
        try:
            _ = self.cloudwatch.put_metric_data(
                Namespace=metric_data.namespace,
                MetricData=[
                    {
                        "MetricName": metric_data.metric_name,
                        "Dimensions": [
                            {"Name": name, "Value": value}
                            for name, value in metric_data.dimensions.items()
                        ],
                        "Value": metric_data.value,
                        "Timestamp": metric_data.timestamp,
                        "Unit": metric_data.unit,
                    }
                ],
            )

            self.logger.info(
                "Metric published to CloudWatch",
                metric_name=metric_data.metric_name,
                namespace=metric_data.namespace,
                value=metric_data.value,
            )

            return True

        except ClientError as e:
            self.logger.error(f"Failed to put metric: {str(e)}")
            return False

    def get_metric_statistics(
        self,
        metric_name: str,
        namespace: str,
        dimensions: Dict[str, str],
        start_time: datetime,
        end_time: datetime,
        period: int = 300,
        statistic: str = "Average",
        unit: str = "Count",
    ) -> List[Dict[str, Any]]:
        """Get metric statistics from CloudWatch."""
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[
                    {"Name": name, "Value": value} for name, value in dimensions.items()
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=[statistic],
                Unit=unit,
            )

            return response.get("Datapoints", [])

        except ClientError as e:
            self.logger.error(f"Failed to get metric statistics: {str(e)}")
            return []

    def create_alarm(self, alarm_config: AlarmConfig) -> bool:
        """Create a CloudWatch alarm."""
        try:
            _ = self.cloudwatch.put_metric_alarm(
                AlarmName=alarm_config.alarm_name,
                AlarmDescription=alarm_config.alarm_description,
                MetricName=alarm_config.metric_name,
                Namespace=alarm_config.namespace,
                Dimensions=[
                    {"Name": name, "Value": value}
                    for name, value in alarm_config.dimensions.items()
                ],
                Threshold=alarm_config.threshold,
                ComparisonOperator=alarm_config.comparison_operator,
                EvaluationPeriods=alarm_config.evaluation_periods,
                Period=alarm_config.period,
                Statistic=alarm_config.statistic,
                Unit=alarm_config.unit,
                AlarmActions=alarm_config.alarm_actions,
                OKActions=alarm_config.ok_actions,
                TreatMissingData="breaching",
            )

            self.logger.info(f"Alarm created: {alarm_config.alarm_name}")
            return True

        except ClientError as e:
            self.logger.error(f"Failed to create alarm: {str(e)}")
            return False

    def delete_alarm(self, alarm_name: str) -> bool:
        """Delete a CloudWatch alarm."""
        try:
            self.cloudwatch.delete_alarms(AlarmNames=[alarm_name])
            self.logger.info(f"Alarm deleted: {alarm_name}")
            return True

        except ClientError as e:
            self.logger.error(f"Failed to delete alarm: {str(e)}")
            return False

    def list_alarms(self, state_value: Optional[str] = None) -> List[Dict[str, Any]]:
        """List CloudWatch alarms."""
        try:
            params = {}
            if state_value:
                params["StateValue"] = state_value

            response = self.cloudwatch.describe_alarms(**params)
            return response.get("MetricAlarms", [])

        except ClientError as e:
            self.logger.error(f"Failed to list alarms: {str(e)}")
            return []

    def set_alarm_state(
        self, alarm_name: str, state_value: str, state_reason: str
    ) -> bool:
        """Set alarm state."""
        try:
            self.cloudwatch.set_alarm_state(
                AlarmName=alarm_name, StateValue=state_value, StateReason=state_reason
            )

            self.logger.info(f"Alarm state set: {alarm_name} -> {state_value}")
            return True

        except ClientError as e:
            self.logger.error(f"Failed to set alarm state: {str(e)}")
            return False

    def get_current_alarm_state(self, alarm_name: str) -> Optional[str]:
        """Get current alarm state."""
        try:
            response = self.cloudwatch.describe_alarms(AlarmNames=[alarm_name])
            alarms = response.get("MetricAlarms", [])

            if alarms:
                return alarms[0].get("StateValue")

            return None

        except ClientError as e:
            self.logger.error(f"Failed to get alarm state: {str(e)}")
            return None


class DevOpsAIMonitor:
    """Specialized monitor for DevOps AI Agent operations."""

    def __init__(self):
        self.monitor = CloudWatchMonitor()
        self.config = get_config()
        self.logger = get_logger("devops-ai-monitor")

    def create_standard_alarms(self) -> List[str]:
        """Create standard alarms for DevOps AI monitoring."""
        created_alarms = []

        # CPU utilization alarm
        cpu_alarm = AlarmConfig(
            alarm_name="devops-ai-cpu-high",
            metric_name="CPUUtilization",
            namespace=self.config.cloudwatch.namespace,
            dimensions={"Service": "DevOpsAI"},
            threshold=self.config.thresholds.cpu_high,
            comparison_operator="GreaterThanThreshold",
            alarm_description="High CPU utilization detected",
            alarm_actions=[self.config.cloudwatch.alarm_sns_topic],
        )

        if self.monitor.create_alarm(cpu_alarm):
            created_alarms.append(cpu_alarm.alarm_name)

        # Memory utilization alarm
        memory_alarm = AlarmConfig(
            alarm_name="devops-ai-memory-high",
            metric_name="MemoryUtilization",
            namespace=self.config.cloudwatch.namespace,
            dimensions={"Service": "DevOpsAI"},
            threshold=self.config.thresholds.memory_high,
            comparison_operator="GreaterThanThreshold",
            alarm_description="High memory utilization detected",
            alarm_actions=[self.config.cloudwatch.alarm_sns_topic],
        )

        if self.monitor.create_alarm(memory_alarm):
            created_alarms.append(memory_alarm.alarm_name)

        # Error rate alarm
        error_alarm = AlarmConfig(
            alarm_name="devops-ai-error-rate-high",
            metric_name="ErrorRate",
            namespace=self.config.cloudwatch.namespace,
            dimensions={"Service": "DevOpsAI"},
            threshold=self.config.thresholds.error_rate_high,
            comparison_operator="GreaterThanThreshold",
            alarm_description="High error rate detected",
            alarm_actions=[self.config.cloudwatch.alarm_sns_topic],
        )

        if self.monitor.create_alarm(error_alarm):
            created_alarms.append(error_alarm.alarm_name)

        # Response time alarm
        response_alarm = AlarmConfig(
            alarm_name="devops-ai-response-time-high",
            metric_name="ResponseTime",
            namespace=self.config.cloudwatch.namespace,
            dimensions={"Service": "DevOpsAI"},
            threshold=self.config.thresholds.response_time_high,
            comparison_operator="GreaterThanThreshold",
            unit="Milliseconds",
            alarm_description="High response time detected",
            alarm_actions=[self.config.cloudwatch.alarm_sns_topic],
        )

        if self.monitor.create_alarm(response_alarm):
            created_alarms.append(response_alarm.alarm_name)

        self.logger.info(f"Created {len(created_alarms)} standard alarms")
        return created_alarms

    def publish_agent_metrics(
        self,
        agent_name: str,
        metrics: Dict[str, float],
        dimensions: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Publish agent-specific metrics."""
        if dimensions is None:
            dimensions = {}

        dimensions.update({"Agent": agent_name, "Environment": "production"})

        success_count = 0

        for metric_name, value in metrics.items():
            metric_data = MetricData(
                metric_name=metric_name,
                namespace=self.config.cloudwatch.namespace,
                dimensions=dimensions,
                value=value,
            )

            if self.monitor.put_metric(metric_data):
                success_count += 1

        self.logger.info(
            f"Published {success_count}/{len(metrics)} metrics "
            f"for agent {agent_name}"
        )

        return success_count == len(metrics)

    def publish_incident_metrics(
        self, incident_id: str, severity: str, service: str, metrics: Dict[str, float]
    ) -> bool:
        """Publish incident-specific metrics."""
        dimensions = {
            "IncidentID": incident_id,
            "Severity": severity,
            "Service": service,
        }

        return self.publish_agent_metrics("incident-monitor", metrics, dimensions)

    def publish_action_metrics(
        self, action_type: str, success: bool, duration: float, confidence: float
    ) -> bool:
        """Publish action execution metrics."""
        metrics = {
            "ActionDuration": duration,
            "ActionConfidence": confidence,
            "ActionSuccess": 1.0 if success else 0.0,
        }

        dimensions = {"ActionType": action_type, "Success": str(success)}

        return self.publish_agent_metrics("action-executor", metrics, dimensions)

    def get_service_health_metrics(
        self, service_name: str, hours_back: int = 1
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get health metrics for a service."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        health_metrics = {}

        for metric_name in self.config.cloudwatch.metrics:
            datapoints = self.monitor.get_metric_statistics(
                metric_name=metric_name,
                namespace=self.config.cloudwatch.namespace,
                dimensions={"Service": service_name},
                start_time=start_time,
                end_time=end_time,
                period=300,
                statistic="Average",
            )

            health_metrics[metric_name] = datapoints

        return health_metrics

    def detect_anomalies(
        self, service_name: str, hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in service metrics."""
        anomalies = []

        # Get historical metrics
        health_metrics = self.get_service_health_metrics(service_name, hours_back)

        # Simple anomaly detection based on thresholds
        for metric_name, datapoints in health_metrics.items():
            if not datapoints:
                continue

            # Calculate average and check against thresholds
            values = [dp["Average"] for dp in datapoints if "Average" in dp]

            if not values:
                continue

            avg_value = sum(values) / len(values)

            # Check against configured thresholds
            threshold_key = f"{metric_name.lower()}_high"
            if hasattr(self.config.thresholds, threshold_key):
                threshold = getattr(self.config.thresholds, threshold_key)

                if avg_value > threshold:
                    anomalies.append(
                        {
                            "metric": metric_name,
                            "value": avg_value,
                            "threshold": threshold,
                            "severity": (
                                "high" if avg_value > threshold * 1.5 else "medium"
                            ),
                            "service": service_name,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        return anomalies

    def create_dashboard(
        self, dashboard_name: str, widgets: List[Dict[str, Any]]
    ) -> bool:
        """Create a CloudWatch dashboard."""
        try:
            dashboard_body = {"widgets": widgets}

            self.monitor.cloudwatch.put_dashboard(
                DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body)
            )

            self.logger.info(f"Dashboard created: {dashboard_name}")
            return True

        except ClientError as e:
            self.logger.error(f"Failed to create dashboard: {str(e)}")
            return False

    def create_agent_dashboard(self) -> bool:
        """Create a dashboard for agent monitoring."""
        widgets = [
            {
                "type": "metric",
                "x": 0,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            self.config.cloudwatch.namespace,
                            "CPUUtilization",
                            "Service",
                            "DevOpsAI",
                        ],
                        [".", "MemoryUtilization", ".", "."],
                        [".", "ErrorRate", ".", "."],
                        [".", "ResponseTime", ".", "."],
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": self.config.aws.region,
                    "title": "DevOps AI Agent Metrics",
                    "period": 300,
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 6,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            self.config.cloudwatch.namespace,
                            "ActionSuccess",
                            "Agent",
                            "action-executor",
                        ],
                        [".", "ActionDuration", ".", "."],
                        [".", "ActionConfidence", ".", "."],
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": self.config.aws.region,
                    "title": "Agent Action Metrics",
                    "period": 300,
                },
            },
        ]

        return self.create_dashboard("DevOpsAI-Agent-Dashboard", widgets)
