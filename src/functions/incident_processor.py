"""Lambda function for processing incidents and triggering agent actions."""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List
import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import event_source, EventBridgeEvent

from ..agents.bedrock_agent import BedrockAgent, Action, ActionType, Incident, Severity
from ..integrations.cloudwatch import DevOpsAIMonitor
from ..utils.config import get_config
from ..utils.logger import get_lambda_logger


# Initialize AWS Lambda Powertools
logger = Logger(service="incident-processor")
tracer = Tracer(service="incident-processor")

# Initialize AWS clients
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

# Get configuration
config = get_config()
lambda_logger = get_lambda_logger("incident-processor")


class IncidentProcessor:
    """Main class for processing incidents and coordinating agent actions."""

    def __init__(self):
        self.config = config
        self.logger = lambda_logger
        self.agent = BedrockAgent()
        self.monitor = DevOpsAIMonitor()

        # Initialize DynamoDB tables
        self.incidents_table = dynamodb.Table(config.dynamodb.incidents_table)
        self.context_table = dynamodb.Table(config.dynamodb.context_table)
        self.actions_table = dynamodb.Table(config.dynamodb.actions_table)

    def process_cloudwatch_alarm(self,
        alarm_data: Dict[str,
        Any]) -> Dict[str,
        Any]:
        """Process a CloudWatch alarm event."""
        try:
            # Extract alarm information
            alarm_name = alarm_data.get('AlarmName', 'unknown')
            alarm_state = alarm_data.get('NewStateValue', 'UNKNOWN')
            alarm_reason = alarm_data.get('StateChangeTime', 'unknown')

            self.logger.info(f"Processing CloudWatch alarm: {alarm_name}",
                           alarm_state=alarm_state)

            # Create incident from alarm
            incident = self._create_incident_from_alarm(alarm_data)

            # Store incident in DynamoDB
            self._store_incident(incident)

            # Process incident with agent
            result = self._process_incident_with_agent(incident)

            return {
                "success": True,
                "incident_id": incident.id,
                "alarm_name": alarm_name,
                "action_taken": result.get("action_taken"),
                    "result": result
            }

        except Exception as e:
            self.logger.error(f"Failed to process CloudWatch alarm: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                    "alarm_data": alarm_data
            }

    def process_custom_event(self,
        event_data: Dict[str,
        Any]) -> Dict[str,
        Any]:
        """Process a custom event (API call, manual trigger, etc.)."""
        try:
            # Extract event information
            event_type = event_data.get('event_type', 'unknown')
            service = event_data.get('service', 'unknown')
            severity = event_data.get('severity', 'medium')

            self.logger.info(f"Processing custom event: {event_type}",
                           service=service, severity=severity)

            # Create incident from event
            incident = self._create_incident_from_event(event_data)

            # Store incident in DynamoDB
            self._store_incident(incident)

            # Process incident with agent
            result = self._process_incident_with_agent(incident)

            return {
                "success": True,
                "incident_id": incident.id,
                "event_type": event_type,
                "action_taken": result.get("action_taken"),
                    "result": result
            }

        except Exception as e:
            self.logger.error(f"Failed to process custom event: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                    "event_data": event_data
            }

    def _create_incident_from_alarm(self,
        alarm_data: Dict[str,
        Any]) -> Incident:
        """Create an incident from CloudWatch alarm data."""
        alarm_name = alarm_data.get('AlarmName', 'unknown')
        alarm_state = alarm_data.get('NewStateValue', 'UNKNOWN')

        # Determine severity based on alarm name and state
        severity = self._determine_severity_from_alarm(alarm_name, alarm_state)

        # Extract service information from alarm name
        service = self._extract_service_from_alarm_name(alarm_name)

        # Create incident description
        description = f"CloudWatch alarm '{alarm_name}' changed state to '{alarm_state}'"

        # Extract relevant metrics
        metrics = {
            "alarm_name": alarm_name,
            "alarm_state": alarm_state,
            "state_change_time": alarm_data.get('StateChangeTime'),
                "reason": alarm_data.get('NewStateReason', ''),
                "threshold": alarm_data.get('Threshold', 0),
                "metric_name": alarm_data.get('MetricName', ''),
                "namespace": alarm_data.get('Namespace', '')
        }

        return Incident(
            id=f"incident-{int(time.time())}-{alarm_name}",
            severity=severity,
            description=description,
            service=service,
            metrics=metrics
        )

    def _create_incident_from_event(self,
        event_data: Dict[str,
        Any]) -> Incident:
        """Create an incident from custom event data."""
        event_type = event_data.get('event_type', 'unknown')
        service = event_data.get('service', 'unknown')
        severity_str = event_data.get('severity', 'medium')

        # Convert severity string to enum
        try:
            severity = Severity(severity_str.lower())
        except ValueError:
            severity = Severity.MEDIUM

        # Create incident description
        description = event_data.get('description',
            f"Custom event: {event_type}")

        # Use provided metrics or create default
        metrics = event_data.get('metrics', {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "custom_event"
        })

        return Incident(
            id=f"incident-{int(time.time())}-{event_type}",
            severity=severity,
            description=description,
            service=service,
            metrics=metrics
        )

    def _determine_severity_from_alarm(self,
        alarm_name: str,
        alarm_state: str) -> Severity:
        """Determine incident severity from alarm name and state."""
        if alarm_state != 'ALARM':
            return Severity.LOW

        # Map alarm names to severity levels
        if 'critical' in alarm_name.lower() or 'error' in alarm_name.lower():
            return Severity.CRITICAL
        elif 'high' in alarm_name.lower() or 'cpu' in alarm_name.lower():
            return Severity.HIGH
        elif 'medium' in alarm_name.lower() or 'warning' in alarm_name.lower():
            return Severity.MEDIUM
        else:
            return Severity.MEDIUM

    def _extract_service_from_alarm_name(self, alarm_name: str) -> str:
        """Extract service name from alarm name."""
        # Simple extraction logic - can be enhanced
        if 'ecs' in alarm_name.lower():
            return 'ecs-service'
        elif 'lambda' in alarm_name.lower():
            return 'lambda-function'
        elif 'rds' in alarm_name.lower():
            return 'rds-database'
        elif 'ec2' in alarm_name.lower():
            return 'ec2-instance'
        else:
            return 'unknown-service'

    def _store_incident(self, incident: Incident) -> None:
        """Store incident in DynamoDB."""
        try:
            self.incidents_table.put_item(
                Item={
                    'incident_id': incident.id,
                    'timestamp': incident.timestamp.isoformat(),
                        'severity': incident.severity.value,
                    'description': incident.description,
                    'service': incident.service,
                    'metrics': incident.metrics,
                    'status': incident.status,
                    'actions_taken': incident.actions_taken,
                    'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
                        'ttl': int((datetime.now(timezone.utc).timestamp() + 86400 * 30))  # 30 days TTL
                }
            )

            self.logger.info(f"Incident stored: {incident.id}")

        except Exception as e:
            self.logger.error(f"Failed to store incident: {str(e)}")
            raise

    def _process_incident_with_agent(self,
        incident: Incident) -> Dict[str,
        Any]:
        """Process incident using the Bedrock agent."""
        try:
            # Process incident with agent
            result = self.agent.process_incident(incident)

            # Store action in DynamoDB if one was taken
            if result.get("action_taken") and result["action_taken"] != "escalate":
                self._store_action(incident, result)

            # Update incident status
            self._update_incident_status(incident, result)

            # Publish metrics
            self.monitor.publish_incident_metrics(
                incident_id=incident.id,
                severity=incident.severity.value,
                service=incident.service,
                metrics={
                    "incident_processed": 1.0,
                    "action_taken": 1.0 if result.get("action_taken") else 0.0,
                        "escalated": 1.0 if result.get("action_taken") == "escalate" else 0.0
                }
            )

            return result

        except Exception as e:
            self.logger.error(f"Failed to process incident with agent: {str(e)}")

            # Escalate on agent failure
            return {
                "incident_id": incident.id,
                "action_taken": "escalate",
                "result": {
                    "success": False,
                    "error": str(e),
                        "escalation_reason": "Agent processing failed"
                }
            }

    def _store_action(self,
        incident: Incident,
        result: Dict[str,
        Any]) -> None:
        """Store action in DynamoDB."""
        try:
            action_data = result.get("result", {})

            action_item = {
                'action_id': f"action-{incident.id}-{int(time.time())}",
                    'incident_id': incident.id,
                'action_type': result.get("action_taken"),
                    'target': incident.service,
                'parameters': action_data.get("parameters", {}),
                    'status': "pending",
                'confidence': result.get("analysis",
                    {}).get("confidence",
                    0.0),
                'created_at': datetime.now(timezone.utc).isoformat(),
                    'ttl': int((datetime.now(timezone.utc).timestamp() + 86400 * 30))  # 30 days TTL
            }

            self.actions_table.put_item(Item=action_item)

            self.logger.info(f"Action stored: {action_item['action_id']}")

        except Exception as e:
            self.logger.error(f"Failed to store action: {str(e)}")

    def _update_incident_status(self,
        incident: Incident,
        result: Dict[str,
        Any]) -> None:
        """Update incident status in DynamoDB."""
        try:
            # Determine new status based on result
            if result.get("action_taken") == "escalate":
                new_status = "escalated"
            elif result.get("result", {}).get("success", False):
                new_status = "action_taken"
            else:
                new_status = "failed"

            # Update incident
            self.incidents_table.update_item(
                Key={'incident_id': incident.id},
                UpdateExpression=(
                    'SET #status = :status, '
                    '#actions_taken = list_append(#actions_taken, :action)'
                ),
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#actions_taken': 'actions_taken'
                },
                ExpressionAttributeValues={
                    ':status': new_status,
                    ':action': [result.get("action_taken", "unknown")]
                }
            )

            self.logger.info(f"Incident status updated: {incident.id} -> {new_status}")

        except Exception as e:
            self.logger.error(f"Failed to update incident status: {str(e)}")

    def get_incident_history(self,
        service: str,
        hours_back: int = 24) -> List[Dict[str,
        Any]]:
        """Get incident history for a service."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours_back)

            _ = self.incidents_table.scan(
                FilterExpression='service = :service AND #timestamp BETWEEN :start_time AND :end_time',
                ExpressionAttributeNames={'#timestamp': 'timestamp'},
                ExpressionAttributeValues={
                    ':service': service,
                    ':start_time': start_time.isoformat(),
                        ':end_time': end_time.isoformat()
                }
            )

            return response.get('Items', [])

        except Exception as e:
            self.logger.error(f"Failed to get incident history: {str(e)}")
            return []

    def resolve_incident(self,
        incident_id: str,
        resolution_notes: str = "") -> Dict[str,
        Any]:
        """Manually resolve an incident."""
        try:
            self.incidents_table.update_item(
                Key={'incident_id': incident_id},
                UpdateExpression='SET #status = :status, #resolved_at = :resolved_at, #resolution_notes = :notes',
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#resolved_at': 'resolved_at',
                    '#resolution_notes': 'resolution_notes'
                },
                ExpressionAttributeValues={
                    ':status': 'resolved',
                    ':resolved_at': datetime.now(timezone.utc).isoformat(),
                        ':notes': resolution_notes
                }
            )

            self.logger.info(f"Incident resolved: {incident_id}")

            return {
                "success": True,
                "incident_id": incident_id,
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to resolve incident: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# Lambda handler for CloudWatch alarms
@logger.inject_lambda_context
@tracer.capture_lambda_handler
@event_source(data_class=EventBridgeEvent)
def cloudwatch_alarm_handler(event: EventBridgeEvent,
    context: LambdaContext) -> Dict[str,
    Any]:
    """Handle CloudWatch alarm events."""
    lambda_logger.log_event(event.raw_event, context)

    try:
        processor = IncidentProcessor()

        # Extract alarm data from EventBridge event
        alarm_data = event.detail

        result = processor.process_cloudwatch_alarm(alarm_data)

        lambda_logger.log_response(result)

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:
        lambda_logger.log_error(e, context)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }


# Lambda handler for custom events
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def custom_event_handler(event: Dict[str,
    Any],
    context: LambdaContext) -> Dict[str,
    Any]:
    """Handle custom events."""
    lambda_logger.log_event(event, context)

    try:
        processor = IncidentProcessor()
        result = processor.process_custom_event(event)

        lambda_logger.log_response(result)

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:
        lambda_logger.log_error(e, context)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }


# Lambda handler for incident management API
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def incident_api_handler(event: Dict[str,
    Any],
    context: LambdaContext) -> Dict[str,
    Any]:
    """Handle incident management API requests."""
    lambda_logger.log_event(event, context)

    try:
        processor = IncidentProcessor()

        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')

        if http_method == 'GET' and path.startswith('/incidents/history'):
            # Get incident history
            service = event.get('queryStringParameters', {}).get('service', '')
            hours_back = int(event.get('queryStringParameters',
                {}).get('hours',
                24))

            incidents = processor.get_incident_history(service, hours_back)

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "incidents": incidents,
                    "count": len(incidents)
                })
            }

        elif http_method == 'POST' and path == '/incidents/resolve':
            # Resolve incident
            body = json.loads(event.get('body', '{}'))
            incident_id = body.get('incident_id')
            resolution_notes = body.get('resolution_notes', '')

            if not incident_id:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "error": "incident_id is required"
                    })
                }

            result = processor.resolve_incident(incident_id, resolution_notes)

            return {
                "statusCode": 200,
                "body": json.dumps(result)
            }

        elif http_method == 'POST' and path == '/incidents/create':
            # Create incident manually
            body = json.loads(event.get('body', '{}'))
            result = processor.process_custom_event(body)

            return {
                "statusCode": 201,
                "body": json.dumps(result)
            }

        else:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Not found"
                })
            }

    except Exception as e:
        lambda_logger.log_error(e, context)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }
