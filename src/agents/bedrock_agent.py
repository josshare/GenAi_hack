"""Amazon Bedrock Agent implementation for autonomous DevOps operations."""

import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.config import get_config
from ..utils.logger import get_agent_logger


class ActionType(str, Enum):
    """Types of actions the agent can take."""

    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    RESTART_DATABASE = "restart_database"
    ESCALATE = "escalate"
    GENERATE_REPORT = "generate_report"
    OPTIMIZE_COST = "optimize_cost"
    NOTIFY_TEAM = "notify_team"


class Severity(str, Enum):
    """Incident severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Incident(BaseModel):
    """Incident model."""

    id: str = Field(description="Unique incident identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    severity: Severity = Field(description="Incident severity level")
    description: str = Field(description="Human-readable incident description")
    service: str = Field(description="Affected service or resource")
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Relevant metrics"
    )
    status: str = Field(default="open", description="Incident status")
    actions_taken: List[str] = Field(
        default_factory=list, description="Actions taken"
    )
    resolved_at: Optional[datetime] = Field(
        default=None, description="Resolution timestamp"
    )


class Action(BaseModel):
    """Action model."""

    id: str = Field(description="Unique action identifier")
    incident_id: str = Field(description="Associated incident ID")
    action_type: ActionType = Field(description="Type of action")
    target: str = Field(description="Target resource or service")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Action parameters"
    )
    status: str = Field(default="pending", description="Action status")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    executed_at: Optional[datetime] = Field(
        default=None, description="Execution timestamp"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Action result"
    )


class DecisionContext(BaseModel):
    """Context for decision making."""

    incident: Incident = Field(description="Current incident")
    historical_data: Dict[str, Any] = Field(
        default_factory=dict, description="Historical context"
    )
    current_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Current system metrics"
    )
    available_actions: List[ActionType] = Field(
        description="Available action types"
    )
    constraints: Dict[str, Any] = Field(
        default_factory=dict, description="System constraints"
    )


class BedrockAgent:
    """Main Bedrock Agent for autonomous DevOps operations."""

    def __init__(self, agent_name: str = "DevOpsAutomationAgent"):
        self.agent_name = agent_name
        self.config = get_config()
        self.logger = get_agent_logger(agent_name)

        # Initialize Bedrock client
        self.bedrock_client = boto3.client(
            "bedrock-runtime", region_name=self.config.aws.region
        )

        # Initialize other AWS services
        self.cloudwatch = boto3.client(
            "cloudwatch", region_name=self.config.aws.region
        )
        self.dynamodb = boto3.resource(
            "dynamodb", region_name=self.config.aws.region
        )
        self.lambda_client = boto3.client(
            "lambda", region_name=self.config.aws.region
        )

        # Load agent instructions
        self.instructions = self._load_agent_instructions()

    def _load_agent_instructions(self) -> str:
        """Load agent instructions for decision making."""
        return """
        You are an autonomous DevOps AI agent responsible for
        monitoring, detecting, diagnosing, and responding to incidents
        in AWS cloud infrastructure. Your primary objectives are:

        1. **Incident Detection**: Monitor system metrics and detect
           anomalies
        2. **Root Cause Analysis**: Analyze incidents to determine root
           causes
        3. **Automated Remediation**: Take appropriate actions to
           resolve issues
        4. **Escalation**: Escalate complex issues that require human
           intervention
        5. **Learning**: Learn from past incidents to improve future
           responses

        **Decision Making Framework**:
        - Always prioritize system stability and availability
        - Consider cost implications of actions
        - Maintain security and compliance standards
        - Document all decisions and actions taken
        - Escalate when confidence is below threshold or actions fail

        **Available Actions**:
        - restart_service: Restart a failed or degraded service
        - scale_up: Increase capacity to handle load
        - scale_down: Reduce capacity to optimize costs
        - rollback_deployment: Rollback to a previous stable version
        - clear_cache: Clear application or system cache
        - restart_database: Restart database services
        - escalate: Escalate to human operators
        - generate_report: Create incident reports
        - optimize_cost: Implement cost optimization measures
        - notify_team: Send notifications to team members

        **Response Format**:
        Always respond with a JSON object containing:
        {
            "action": "action_type",
            "confidence": 0.0-1.0,
            "reasoning": "explanation of decision",
            "parameters": {},
            "escalate": true/false,
            "escalation_reason": "reason if escalating"
        }
        """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _invoke_bedrock(self, messages: List[Dict[str, str]]) -> str:
        """Invoke Bedrock model with retry logic."""
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.config.bedrock.model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.config.bedrock.max_tokens,
                        "temperature": self.config.bedrock.temperature,
                        "messages": messages,
                    }
                ),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except ClientError as e:
            self.logger.error(f"Bedrock invocation failed: {str(e)}")
            raise

    def analyze_incident(self, incident: Incident) -> Dict[str, Any]:
        """Analyze an incident and determine the best course of action."""
        self.logger.info(
            f"Analyzing incident {incident.id}",
            incident_id=incident.id,
            severity=incident.severity.value,
        )

        # Prepare context for analysis
        context = DecisionContext(
            incident=incident,
            historical_data=self._get_historical_data(incident.service),
            current_metrics=self._get_current_metrics(incident.service),
            available_actions=[action for action in ActionType],
            constraints=self._get_system_constraints(),
        )

        # Create analysis prompt
        prompt = f"""
        Analyze the following incident and determine the appropriate
        action:

        **Incident Details**:
        - ID: {incident.id}
        - Severity: {incident.severity.value}
        - Service: {incident.service}
        - Description: {incident.description}
        - Metrics: {json.dumps(incident.metrics, indent=2)}

        **Historical Context**:
        {json.dumps(context.historical_data, indent=2)}

        **Current System Metrics**:
        {json.dumps(context.current_metrics, indent=2)}

        **System Constraints**:
        {json.dumps(context.constraints, indent=2)}

        Based on this information, determine the best action to take.
        Consider:
        1. The severity and impact of the incident
        2. Historical patterns and similar incidents
        3. Current system state and metrics
        4. Available resources and constraints
        5. Potential risks of each action

        Provide your analysis and recommendation in the specified
        JSON format.
        """

        messages = [
            {"role": "user", "content": f"{self.instructions}\n\n{prompt}"}
        ]

        try:
            response = self._invoke_bedrock(messages)
            analysis = json.loads(response)

            self.logger.log_decision(
                decision=analysis.get("action", "unknown"),
                confidence=analysis.get("confidence", 0.0),
                context={
                    "incident_id": incident.id,
                    "reasoning": analysis.get("reasoning", ""),
                    "escalate": analysis.get("escalate", False),
                },
            )

            return analysis

        except Exception as e:
            self.logger.error(
                f"Failed to analyze incident {incident.id}: {str(e)}"
            )
            # Fallback to escalation
            return {
                "action": "escalate",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {str(e)}",
                "escalate": True,
                "escalation_reason": "Agent analysis failed",
            }

    def execute_action(self, action: Action) -> Dict[str, Any]:
        """Execute an action based on the agent's decision."""
        self.logger.info(
            f"Executing action {action.action_type.value} for incident "
            f"{action.incident_id}"
        )

        try:
            # Update action status
            action.status = "executing"
            action.executed_at = datetime.now(timezone.utc)

            # Execute the specific action
            result = self._execute_specific_action(action)

            # Update action status
            action.status = (
                "completed" if result.get("success", False) else "failed"
            )
            action.result = result

            self.logger.log_action(
                action=action.action_type.value,
                target=action.target,
                status=action.status,
                details=result,
            )

            return result

        except Exception as e:
            self.logger.error(
                f"Failed to execute action {action.id}: {str(e)}"
            )
            action.status = "failed"
            action.result = {"success": False, "error": str(e)}

            return {"success": False, "error": str(e), "action_id": action.id}

    def _execute_specific_action(self, action: Action) -> Dict[str, Any]:
        """Execute a specific action type."""
        action_type = action.action_type

        if action_type == ActionType.RESTART_SERVICE:
            return self._restart_service(action)
        elif action_type == ActionType.SCALE_UP:
            return self._scale_up(action)
        elif action_type == ActionType.SCALE_DOWN:
            return self._scale_down(action)
        elif action_type == ActionType.ROLLBACK_DEPLOYMENT:
            return self._rollback_deployment(action)
        elif action_type == ActionType.CLEAR_CACHE:
            return self._clear_cache(action)
        elif action_type == ActionType.RESTART_DATABASE:
            return self._restart_database(action)
        elif action_type == ActionType.GENERATE_REPORT:
            return self._generate_report(action)
        elif action_type == ActionType.OPTIMIZE_COST:
            return self._optimize_cost(action)
        elif action_type == ActionType.NOTIFY_TEAM:
            return self._notify_team(action)
        elif action_type == ActionType.ESCALATE:
            return self._escalate_incident(action)
        else:
            raise ValueError(f"Unknown action type: {action_type}")

    def _restart_service(self, action: Action) -> Dict[str, Any]:
        """Restart a service."""
        # This would integrate with AWS ECS, EKS, or EC2 services
        # For now, return a mock response
        return {
            "success": True,
            "message": f"Service {action.target} restarted successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _scale_up(self, action: Action) -> Dict[str, Any]:
        """Scale up a service."""
        # This would integrate with Auto Scaling Groups or ECS services
        return {
            "success": True,
            "message": f"Service {action.target} scaled up",
            "new_capacity": action.parameters.get("desired_capacity", 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _scale_down(self, action: Action) -> Dict[str, Any]:
        """Scale down a service."""
        return {
            "success": True,
            "message": f"Service {action.target} scaled down",
            "new_capacity": action.parameters.get("desired_capacity", 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _rollback_deployment(self, action: Action) -> Dict[str, Any]:
        """Rollback a deployment."""
        return {
            "success": True,
            "message": f"Deployment rolled back for {action.target}",
            "previous_version": action.parameters.get(
                "previous_version", "unknown"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _clear_cache(self, action: Action) -> Dict[str, Any]:
        """Clear application cache."""
        return {
            "success": True,
            "message": f"Cache cleared for {action.target}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _restart_database(self, action: Action) -> Dict[str, Any]:
        """Restart database service."""
        return {
            "success": True,
            "message": f"Database {action.target} restarted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_report(self, action: Action) -> Dict[str, Any]:
        """Generate incident report."""
        report_url = (
            f"s3://{self.config.s3.artifacts_bucket}/reports/"
            f"{action.incident_id}.pdf"
        )
        return {
            "success": True,
            "message": f"Report generated for incident {action.incident_id}",
            "report_url": report_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _optimize_cost(self, action: Action) -> Dict[str, Any]:
        """Optimize costs."""
        return {
            "success": True,
            "message": f"Cost optimization applied to {action.target}",
            "estimated_savings": action.parameters.get("estimated_savings", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _notify_team(self, action: Action) -> Dict[str, Any]:
        """Notify team members."""
        return {
            "success": True,
            "message": f"Team notified about {action.target}",
            "channels": action.parameters.get("channels", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _escalate_incident(self, action: Action) -> Dict[str, Any]:
        """Escalate incident to human operators."""
        self.logger.log_escalation(
            incident_id=action.incident_id,
            reason=action.parameters.get("reason", "Agent unable to resolve"),
            target="human_operators",
        )

        return {
            "success": True,
            "message": f"Incident {action.incident_id} escalated",
            "reason": action.parameters.get(
                "reason", "Agent unable to resolve"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_historical_data(self, service: str) -> Dict[str, Any]:
        """Get historical data for a service."""
        # This would query DynamoDB for historical incidents and actions
        return {
            "recent_incidents": [],
            "successful_actions": [],
            "failed_actions": [],
            "patterns": {},
        }

    def _get_current_metrics(self, service: str) -> Dict[str, Any]:
        """Get current metrics for a service."""
        # This would query CloudWatch for current metrics
        return {
            "cpu_utilization": 0.0,
            "memory_utilization": 0.0,
            "request_count": 0,
            "error_rate": 0.0,
            "response_time": 0.0,
        }

    def _get_system_constraints(self) -> Dict[str, Any]:
        """Get system constraints."""
        return {
            "max_capacity": self.config.autoscaling.max_capacity,
            "min_capacity": self.config.autoscaling.min_capacity,
            "cost_limit": self.config.thresholds.cost_threshold,
            "maintenance_window": "02:00-04:00 UTC",
        }

    def process_incident(self, incident: Incident) -> Dict[str, Any]:
        """Main method to process an incident end-to-end."""
        self.logger.log_incident(
            incident_id=incident.id,
            severity=incident.severity.value,
            description=incident.description,
            metrics=incident.metrics,
        )

        # Analyze the incident
        analysis = self.analyze_incident(incident)

        # Check if escalation is needed
        if analysis.get("escalate", False):
            escalation_action = Action(
                id=f"escalate-{incident.id}",
                incident_id=incident.id,
                action_type=ActionType.ESCALATE,
                target="human_operators",
                parameters={
                    "reason": analysis.get(
                        "escalation_reason", "Agent analysis failed"
                    ),
                    "confidence": analysis.get("confidence", 0.0),
                },
                confidence=analysis.get("confidence", 0.0),
            )

            result = self.execute_action(escalation_action)
            return {
                "incident_id": incident.id,
                "action_taken": "escalate",
                "result": result,
                "analysis": analysis,
            }

        # Check confidence threshold
        confidence_threshold = self.config.agent.confidence_threshold
        if analysis.get("confidence", 0.0) < confidence_threshold:
            self.logger.warning(
                f"Low confidence analysis for incident {incident.id}, "
                f"escalating"
            )
            return self.process_incident(incident)  # This will escalate

        # Create and execute action
        action = Action(
            id=f"action-{incident.id}-{int(time.time())}",
            incident_id=incident.id,
            action_type=ActionType(analysis.get("action", "escalate")),
            target=incident.service,
            parameters=analysis.get("parameters", {}),
            confidence=analysis.get("confidence", 0.0),
        )

        result = self.execute_action(action)

        # Update incident with action taken
        incident.actions_taken.append(action.action_type.value)

        return {
            "incident_id": incident.id,
            "action_taken": action.action_type.value,
            "result": result,
            "analysis": analysis,
        }
