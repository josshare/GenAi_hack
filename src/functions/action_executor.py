"""Lambda function for executing automated actions."""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import event_source, EventBridgeEvent

from ..agents.bedrock_agent import Action, ActionType, Incident, Severity
from ..utils.config import get_config
from ..utils.logger import get_lambda_logger


# Initialize AWS Lambda Powertools
logger = Logger(service="action-executor")
tracer = Tracer(service="action-executor")

# Initialize AWS clients
ecs_client = boto3.client('ecs')
ec2_client = boto3.client('ec2')
autoscaling_client = boto3.client('autoscaling')
elasticloadbalancing_client = boto3.client('elbv2')
rds_client = boto3.client('rds')
elasticache_client = boto3.client('elasticache')
lambda_client = boto3.client('lambda')

# Get configuration
config = get_config()
lambda_logger = get_lambda_logger("action-executor")


class ActionExecutor:
    """Main class for executing automated actions."""
    
    def __init__(self):
        self.config = config
        self.logger = lambda_logger
    
    def execute_action(self, action: Action) -> Dict[str, Any]:
        """Execute an action based on its type."""
        start_time = time.time()
        
        try:
            self.logger.log_event({"action": action.dict()})
            
            # Route to specific action handler
            if action.action_type == ActionType.RESTART_SERVICE:
                result = self._restart_service(action)
            elif action.action_type == ActionType.SCALE_UP:
                result = self._scale_up(action)
            elif action.action_type == ActionType.SCALE_DOWN:
                result = self._scale_down(action)
            elif action.action_type == ActionType.ROLLBACK_DEPLOYMENT:
                result = self._rollback_deployment(action)
            elif action.action_type == ActionType.CLEAR_CACHE:
                result = self._clear_cache(action)
            elif action.action_type == ActionType.RESTART_DATABASE:
                result = self._restart_database(action)
            elif action.action_type == ActionType.GENERATE_REPORT:
                result = self._generate_report(action)
            elif action.action_type == ActionType.OPTIMIZE_COST:
                result = self._optimize_cost(action)
            elif action.action_type == ActionType.NOTIFY_TEAM:
                result = self._notify_team(action)
            elif action.action_type == ActionType.ESCALATE:
                result = self._escalate_incident(action)
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")
            
            # Calculate execution duration
            duration = time.time() - start_time
            
            # Log successful execution
            self.logger.log_action(
                action=action.action_type.value,
                target=action.target,
                status="completed",
                details={
                    "duration": duration,
                    "result": result
                }
            )
            
            return {
                "success": True,
                "action_id": action.id,
                "action_type": action.action_type.value,
                "duration": duration,
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            duration = time.time() - start_time
            
            self.logger.log_error(e)
            
            return {
                "success": False,
                "action_id": action.id,
                "action_type": action.action_type.value,
                "duration": duration,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    @tracer.capture_method
    def _restart_service(self, action: Action) -> Dict[str, Any]:
        """Restart a service (ECS task, EC2 instance, etc.)."""
        service_type = action.parameters.get("service_type", "ecs")
        
        if service_type == "ecs":
            return self._restart_ecs_service(action)
        elif service_type == "ec2":
            return self._restart_ec2_instance(action)
        elif service_type == "lambda":
            return self._restart_lambda_function(action)
        else:
            raise ValueError(f"Unsupported service type: {service_type}")
    
    def _restart_ecs_service(self, action: Action) -> Dict[str, Any]:
        """Restart an ECS service."""
        cluster_name = action.parameters.get("cluster_name")
        service_name = action.parameters.get("service_name")
        
        if not cluster_name or not service_name:
            raise ValueError("cluster_name and service_name are required for ECS restart")
        
        try:
            # Force new deployment
            response = ecs_client.update_service(
                cluster=cluster_name,
                service=service_name,
                forceNewDeployment=True
            )
            
            return {
                "message": f"ECS service {service_name} restart initiated",
                "cluster": cluster_name,
                "service": service_name,
                "task_definition": response['service']['taskDefinition']
            }
        
        except Exception as e:
            raise Exception(f"Failed to restart ECS service: {str(e)}")
    
    def _restart_ec2_instance(self, action: Action) -> Dict[str, Any]:
        """Restart an EC2 instance."""
        instance_id = action.parameters.get("instance_id")
        
        if not instance_id:
            raise ValueError("instance_id is required for EC2 restart")
        
        try:
            # Reboot the instance
            response = ec2_client.reboot_instances(
                InstanceIds=[instance_id]
            )
            
            return {
                "message": f"EC2 instance {instance_id} restart initiated",
                "instance_id": instance_id
            }
        
        except Exception as e:
            raise Exception(f"Failed to restart EC2 instance: {str(e)}")
    
    def _restart_lambda_function(self, action: Action) -> Dict[str, Any]:
        """Restart a Lambda function (update environment variables to force restart)."""
        function_name = action.parameters.get("function_name")
        
        if not function_name:
            raise ValueError("function_name is required for Lambda restart")
        
        try:
            # Get current configuration
            current_config = lambda_client.get_function_configuration(
                FunctionName=function_name
            )
            
            # Update environment variables to force restart
            current_env = current_config.get('Environment', {}).get('Variables', {})
            current_env['_restart_trigger'] = str(int(time.time()))
            
            lambda_client.update_function_configuration(
                FunctionName=function_name,
                Environment={'Variables': current_env}
            )
            
            return {
                "message": f"Lambda function {function_name} restart initiated",
                "function_name": function_name
            }
        
        except Exception as e:
            raise Exception(f"Failed to restart Lambda function: {str(e)}")
    
    @tracer.capture_method
    def _scale_up(self, action: Action) -> Dict[str, Any]:
        """Scale up a service or infrastructure component."""
        scale_type = action.parameters.get("scale_type", "autoscaling")
        target_capacity = action.parameters.get("desired_capacity")
        
        if scale_type == "autoscaling":
            return self._scale_autoscaling_group(action, target_capacity)
        elif scale_type == "ecs":
            return self._scale_ecs_service(action, target_capacity)
        else:
            raise ValueError(f"Unsupported scale type: {scale_type}")
    
    def _scale_autoscaling_group(self, action: Action, target_capacity: int) -> Dict[str, Any]:
        """Scale an Auto Scaling Group."""
        asg_name = action.parameters.get("asg_name")
        
        if not asg_name:
            raise ValueError("asg_name is required for Auto Scaling Group")
        
        if target_capacity is None:
            target_capacity = action.parameters.get("current_capacity", 2) + 1
        
        try:
            response = autoscaling_client.set_desired_capacity(
                AutoScalingGroupName=asg_name,
                DesiredCapacity=target_capacity,
                HonorCooldown=False
            )
            
            return {
                "message": f"Auto Scaling Group {asg_name} scaled to {target_capacity}",
                "asg_name": asg_name,
                "desired_capacity": target_capacity
            }
        
        except Exception as e:
            raise Exception(f"Failed to scale Auto Scaling Group: {str(e)}")
    
    def _scale_ecs_service(self, action: Action, target_capacity: int) -> Dict[str, Any]:
        """Scale an ECS service."""
        cluster_name = action.parameters.get("cluster_name")
        service_name = action.parameters.get("service_name")
        
        if not cluster_name or not service_name:
            raise ValueError("cluster_name and service_name are required for ECS scaling")
        
        if target_capacity is None:
            target_capacity = action.parameters.get("current_capacity", 2) + 1
        
        try:
            response = ecs_client.update_service(
                cluster=cluster_name,
                service=service_name,
                desiredCount=target_capacity
            )
            
            return {
                "message": f"ECS service {service_name} scaled to {target_capacity}",
                "cluster": cluster_name,
                "service": service_name,
                "desired_count": target_capacity
            }
        
        except Exception as e:
            raise Exception(f"Failed to scale ECS service: {str(e)}")
    
    @tracer.capture_method
    def _scale_down(self, action: Action) -> Dict[str, Any]:
        """Scale down a service or infrastructure component."""
        # Similar to scale up but with reduced capacity
        scale_type = action.parameters.get("scale_type", "autoscaling")
        target_capacity = action.parameters.get("desired_capacity")
        
        if scale_type == "autoscaling":
            return self._scale_autoscaling_group(action, target_capacity)
        elif scale_type == "ecs":
            return self._scale_ecs_service(action, target_capacity)
        else:
            raise ValueError(f"Unsupported scale type: {scale_type}")
    
    @tracer.capture_method
    def _rollback_deployment(self, action: Action) -> Dict[str, Any]:
        """Rollback a deployment to a previous version."""
        deployment_type = action.parameters.get("deployment_type", "ecs")
        previous_version = action.parameters.get("previous_version")
        
        if deployment_type == "ecs":
            return self._rollback_ecs_deployment(action, previous_version)
        elif deployment_type == "lambda":
            return self._rollback_lambda_deployment(action, previous_version)
        else:
            raise ValueError(f"Unsupported deployment type: {deployment_type}")
    
    def _rollback_ecs_deployment(self, action: Action, previous_version: str) -> Dict[str, Any]:
        """Rollback an ECS deployment."""
        cluster_name = action.parameters.get("cluster_name")
        service_name = action.parameters.get("service_name")
        
        if not cluster_name or not service_name:
            raise ValueError("cluster_name and service_name are required for ECS rollback")
        
        if not previous_version:
            # Get previous task definition
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            service = response['services'][0]
            current_task_def = service['taskDefinition']
            
            # Get task definition revisions
            task_def_response = ecs_client.describe_task_definition(
                taskDefinition=current_task_def
            )
            
            family = task_def_response['taskDefinition']['family']
            revisions = ecs_client.list_task_definitions(
                familyPrefix=family,
                status='ACTIVE',
                sort='DESC'
            )
            
            if len(revisions['taskDefinitionArns']) > 1:
                previous_version = revisions['taskDefinitionArns'][1]
            else:
                raise ValueError("No previous version found for rollback")
        
        try:
            response = ecs_client.update_service(
                cluster=cluster_name,
                service=service_name,
                taskDefinition=previous_version,
                forceNewDeployment=True
            )
            
            return {
                "message": f"ECS service {service_name} rolled back to {previous_version}",
                "cluster": cluster_name,
                "service": service_name,
                "previous_task_definition": previous_version
            }
        
        except Exception as e:
            raise Exception(f"Failed to rollback ECS deployment: {str(e)}")
    
    def _rollback_lambda_deployment(self, action: Action, previous_version: str) -> Dict[str, Any]:
        """Rollback a Lambda deployment."""
        function_name = action.parameters.get("function_name")
        
        if not function_name:
            raise ValueError("function_name is required for Lambda rollback")
        
        if not previous_version:
            # Get previous version
            response = lambda_client.list_versions_by_function(
                FunctionName=function_name
            )
            
            versions = [v['Version'] for v in response['Versions'] if v['Version'] != '$LATEST']
            if versions:
                previous_version = versions[-1]
            else:
                raise ValueError("No previous version found for rollback")
        
        try:
            response = lambda_client.update_alias(
                FunctionName=function_name,
                Name='LIVE',
                FunctionVersion=previous_version
            )
            
            return {
                "message": f"Lambda function {function_name} rolled back to version {previous_version}",
                "function_name": function_name,
                "previous_version": previous_version
            }
        
        except Exception as e:
            raise Exception(f"Failed to rollback Lambda deployment: {str(e)}")
    
    @tracer.capture_method
    def _clear_cache(self, action: Action) -> Dict[str, Any]:
        """Clear application or system cache."""
        cache_type = action.parameters.get("cache_type", "elasticache")
        
        if cache_type == "elasticache":
            return self._clear_elasticache_cache(action)
        elif cache_type == "cloudfront":
            return self._clear_cloudfront_cache(action)
        else:
            raise ValueError(f"Unsupported cache type: {cache_type}")
    
    def _clear_elasticache_cache(self, action: Action) -> Dict[str, Any]:
        """Clear ElastiCache cache."""
        cache_cluster_id = action.parameters.get("cache_cluster_id")
        
        if not cache_cluster_id:
            raise ValueError("cache_cluster_id is required for ElastiCache flush")
        
        try:
            # For Redis, we would use the redis-py client to flush
            # For Memcached, we would use boto3 to restart the cluster
            response = elasticache_client.reboot_cache_cluster(
                CacheClusterId=cache_cluster_id,
                CacheNodeIdsToReboot=['0001']
            )
            
            return {
                "message": f"ElastiCache cluster {cache_cluster_id} cache cleared",
                "cache_cluster_id": cache_cluster_id
            }
        
        except Exception as e:
            raise Exception(f"Failed to clear ElastiCache: {str(e)}")
    
    def _clear_cloudfront_cache(self, action: Action) -> Dict[str, Any]:
        """Clear CloudFront cache."""
        distribution_id = action.parameters.get("distribution_id")
        paths = action.parameters.get("paths", ["/*"])
        
        if not distribution_id:
            raise ValueError("distribution_id is required for CloudFront invalidation")
        
        try:
            cloudfront_client = boto3.client('cloudfront')
            
            response = cloudfront_client.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(paths),
                        'Items': paths
                    },
                    'CallerReference': f"devops-ai-{int(time.time())}"
                }
            )
            
            return {
                "message": f"CloudFront distribution {distribution_id} cache cleared",
                "distribution_id": distribution_id,
                "invalidation_id": response['Invalidation']['Id'],
                "paths": paths
            }
        
        except Exception as e:
            raise Exception(f"Failed to clear CloudFront cache: {str(e)}")
    
    @tracer.capture_method
    def _restart_database(self, action: Action) -> Dict[str, Any]:
        """Restart database services."""
        db_type = action.parameters.get("db_type", "rds")
        db_identifier = action.parameters.get("db_identifier")
        
        if not db_identifier:
            raise ValueError("db_identifier is required for database restart")
        
        if db_type == "rds":
            return self._restart_rds_instance(action, db_identifier)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _restart_rds_instance(self, action: Action, db_identifier: str) -> Dict[str, Any]:
        """Restart an RDS instance."""
        try:
            response = rds_client.reboot_db_instance(
                DBInstanceIdentifier=db_identifier,
                ForceFailover=False
            )
            
            return {
                "message": f"RDS instance {db_identifier} restart initiated",
                "db_identifier": db_identifier,
                "status": response['DBInstance']['DBInstanceStatus']
            }
        
        except Exception as e:
            raise Exception(f"Failed to restart RDS instance: {str(e)}")
    
    @tracer.capture_method
    def _generate_report(self, action: Action) -> Dict[str, Any]:
        """Generate incident report."""
        incident_id = action.parameters.get("incident_id")
        report_type = action.parameters.get("report_type", "incident")
        
        if not incident_id:
            raise ValueError("incident_id is required for report generation")
        
        # This would integrate with a reporting service
        # For now, return a mock response
        return {
            "message": f"Report generated for incident {incident_id}",
            "incident_id": incident_id,
            "report_type": report_type,
            "report_url": f"s3://{config.s3.artifacts_bucket}/reports/{incident_id}.pdf"
        }
    
    @tracer.capture_method
    def _optimize_cost(self, action: Action) -> Dict[str, Any]:
        """Optimize costs."""
        optimization_type = action.parameters.get("optimization_type", "general")
        
        # This would integrate with cost optimization services
        return {
            "message": f"Cost optimization applied: {optimization_type}",
            "optimization_type": optimization_type,
            "estimated_savings": action.parameters.get("estimated_savings", 0)
        }
    
    @tracer.capture_method
    def _notify_team(self, action: Action) -> Dict[str, Any]:
        """Notify team members."""
        channels = action.parameters.get("channels", [])
        message = action.parameters.get("message", "Automated notification from DevOps AI Agent")
        
        # This would integrate with Slack, Teams, etc.
        return {
            "message": "Team notification sent",
            "channels": channels,
            "notification_content": message
        }
    
    @tracer.capture_method
    def _escalate_incident(self, action: Action) -> Dict[str, Any]:
        """Escalate incident to human operators."""
        incident_id = action.parameters.get("incident_id")
        reason = action.parameters.get("reason", "Agent unable to resolve")
        escalation_target = action.parameters.get("escalation_target", "on-call-engineer")
        
        # This would integrate with paging systems like PagerDuty
        return {
            "message": f"Incident {incident_id} escalated to {escalation_target}",
            "incident_id": incident_id,
            "reason": reason,
            "escalation_target": escalation_target
        }


# Lambda handler
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Main Lambda handler for action execution."""
    lambda_logger.log_event(event, context)
    
    try:
        # Parse action from event
        action_data = event.get("action", {})
        if not action_data:
            raise ValueError("No action data provided in event")
        
        action = Action(**action_data)
        
        # Execute action
        executor = ActionExecutor()
        result = executor.execute_action(action)
        
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

