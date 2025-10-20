"""Logging configuration for the Intelligent Automation AI Agent."""

import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
import structlog
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from .config import get_config


class CustomJSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        
        # Add trace ID if available
        if hasattr(record, 'trace_id'):
            log_entry["trace_id"] = record.trace_id
        
        # Add any extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


class DevOpsAILogger:
    """Main logger class for the DevOps AI Agent."""
    
    def __init__(self, name: str = "devops-ai-agent"):
        self.name = name
        self.config = get_config()
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Create logger
        self.logger = structlog.get_logger(self.name)
        
        # Set up handlers based on configuration
        for destination in self.config.logging.destinations:
            if destination == "cloudwatch":
                self._setup_cloudwatch_handler()
            elif destination == "s3":
                self._setup_s3_handler()
    
    def _setup_cloudwatch_handler(self) -> None:
        """Set up CloudWatch logging handler."""
        try:
            from aws_lambda_powertools.logging.logger import set_package_logger
            set_package_logger(self.logger)
        except ImportError:
            # Fallback to standard logging if AWS Lambda Powertools not available
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(CustomJSONFormatter())
            self.logger.addHandler(handler)
    
    def _setup_s3_handler(self) -> None:
        """Set up S3 logging handler."""
        # This would be implemented for S3 log storage
        # For now, we'll use CloudWatch as the primary destination
        pass
    
    def get_logger(self) -> structlog.BoundLogger:
        """Get the configured logger instance."""
        return self.logger
    
    def with_context(self, **kwargs) -> structlog.BoundLogger:
        """Create a logger with additional context."""
        return self.logger.bind(**kwargs)


class LambdaLogger:
    """AWS Lambda specific logger using Lambda Powertools."""
    
    def __init__(self, service_name: str = "devops-ai-agent"):
        self.logger = Logger(service=service_name)
        self.config = get_config()

    def get_logger(self) -> Logger:
        """Get the Lambda Powertools logger."""
        return self.logger

    def log_event(self, event: Dict[str, Any],
                  context: Optional[LambdaContext] = None) -> None:
        """Log Lambda event with context."""
        self.logger.info("Lambda event received", event=event)

        if context:
            self.logger.info(
                "Lambda context",
                function_name=context.function_name,
                function_version=context.function_version,
                memory_limit=context.memory_limit_in_mb,
                remaining_time=context.get_remaining_time_in_millis()
            )

    def log_response(self, response: Dict[str, Any]) -> None:
        """Log Lambda response."""
        self.logger.info("Lambda response", response=response)

    def log_error(self, error: Exception,
                  context: Optional[LambdaContext] = None) -> None:
        """Log error with context."""
        self.logger.error(
            "Lambda error occurred",
            error=str(error),
            error_type=type(error).__name__,
            exc_info=True
        )

        if context:
            self.logger.error(
                "Lambda context during error",
                function_name=context.function_name,
                remaining_time=context.get_remaining_time_in_millis()
            )


class AgentLogger:
    """Specialized logger for AI agent operations."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.base_logger = DevOpsAILogger(f"agent-{agent_name}")
        self.logger = self.base_logger.get_logger()

    def log_decision(self, decision: str, confidence: float,
                     context: Dict[str, Any]) -> None:
        """Log agent decision making."""
        self.logger.info(
            "Agent decision made",
            agent=self.agent_name,
            decision=decision,
            confidence=confidence,
            context=context
        )

    def log_action(self, action: str, target: str, status: str,
                   details: Dict[str, Any]) -> None:
        """Log agent action execution."""
        self.logger.info(
            "Agent action executed",
            agent=self.agent_name,
            action=action,
            target=target,
            status=status,
            details=details
        )

    def log_incident(self, incident_id: str, severity: str, description: str,
                     metrics: Dict[str, Any]) -> None:
        """Log incident detection and handling."""
        self.logger.warning(
            "Incident detected",
            agent=self.agent_name,
            incident_id=incident_id,
            severity=severity,
            description=description,
            metrics=metrics
        )

    def log_escalation(self, incident_id: str, reason: str,
                       target: str) -> None:
        """Log escalation events."""
        self.logger.error(
            "Incident escalated",
            agent=self.agent_name,
            incident_id=incident_id,
            reason=reason,
            target=target
        )

    def log_metrics(self, metrics: Dict[str, Any]) -> None:
        """Log performance metrics."""
        self.logger.info(
            "Performance metrics",
            agent=self.agent_name,
            metrics=metrics
        )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a logger instance."""
    if name:
        return DevOpsAILogger(name).get_logger()
    return DevOpsAILogger().get_logger()


def get_lambda_logger(service_name: str = "devops-ai-agent") -> LambdaLogger:
    """Get a Lambda-specific logger."""
    return LambdaLogger(service_name)


def get_agent_logger(agent_name: str) -> AgentLogger:
    """Get an agent-specific logger."""
    return AgentLogger(agent_name)


# Global logger instances
devops_logger = DevOpsAILogger()
agent_logger = AgentLogger("main")