"""Configuration management for the Intelligent Automation AI Agent."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseSettings, Field
from pydantic_settings import SettingsConfigDict


class AWSConfig(BaseSettings):
    """AWS-specific configuration."""

    region: str = Field(default="us-east-1", description="AWS region")
    profile: str = Field(default="default", description="AWS profile")
    account_id: str = Field(description="AWS account ID")


class BedrockConfig(BaseSettings):
    """Bedrock-specific configuration."""

    model_id: str = Field(default="anthropic.claude-3-sonnet-20240229-v1:0")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4000, ge=1, le=8000)
    timeout: int = Field(default=300, ge=1)


class AgentConfig(BaseSettings):
    """Agent-specific configuration."""

    name: str = Field(default="DevOpsAutomationAgent")
    description: str = Field(
        default="Autonomous AI agent for DevOps and cloud management"
    )
    max_iterations: int = Field(default=10, ge=1, le=100)
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    escalation_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class CloudWatchConfig(BaseSettings):
    """CloudWatch-specific configuration."""

    namespace: str = Field(default="DevOpsAI/Agent")
    log_retention_days: int = Field(default=30, ge=1, le=3653)
    alarm_sns_topic: str = Field(default="devops-ai-alerts")
    metrics: list[str] = Field(
        default_factory=lambda: [
            "CPUUtilization",
            "MemoryUtilization",
            "RequestCount",
            "ErrorRate",
            "ResponseTime",
        ]
    )


class DynamoDBConfig(BaseSettings):
    """DynamoDB-specific configuration."""

    incidents_table: str = Field(default="devops-ai-incidents")
    context_table: str = Field(default="devops-ai-context")
    actions_table: str = Field(default="devops-ai-actions")
    billing_mode: str = Field(default="PAY_PER_REQUEST")


class LambdaConfig(BaseSettings):
    """Lambda-specific configuration."""

    timeout: int = Field(default=900, ge=1, le=900)
    memory: int = Field(default=1024, ge=128, le=10240)
    runtime: str = Field(default="python3.11")
    environment: Dict[str, str] = Field(
        default_factory=lambda: {"LOG_LEVEL": "INFO", "MAX_RETRIES": "3"}
    )


class S3Config(BaseSettings):
    """S3-specific configuration."""

    logs_bucket: str = Field(default="devops-ai-logs")
    artifacts_bucket: str = Field(default="devops-ai-artifacts")
    backup_bucket: str = Field(default="devops-ai-backup")


class ChatOpsConfig(BaseSettings):
    """ChatOps-specific configuration."""

    slack_enabled: bool = Field(default=True)
    slack_webhook_url: Optional[str] = Field(default=None)
    slack_bot_token: Optional[str] = Field(default=None)
    slack_channels: list[str] = Field(
        default_factory=lambda: ["devops-alerts", "incident-response"]
    )

    teams_enabled: bool = Field(default=False)
    teams_webhook_url: Optional[str] = Field(default=None)


class ThresholdsConfig(BaseSettings):
    """Monitoring thresholds configuration."""

    cpu_high: float = Field(default=80.0, ge=0.0, le=100.0)
    memory_high: float = Field(default=85.0, ge=0.0, le=100.0)
    error_rate_high: float = Field(default=5.0, ge=0.0, le=100.0)
    response_time_high: int = Field(default=2000, ge=1)
    cost_threshold: float = Field(default=1000.0, ge=0.0)


class AutoscalingConfig(BaseSettings):
    """Autoscaling configuration."""

    enabled: bool = Field(default=True)
    min_capacity: int = Field(default=2, ge=1)
    max_capacity: int = Field(default=20, ge=1)
    target_cpu: float = Field(default=70.0, ge=0.0, le=100.0)
    scale_up_cooldown: int = Field(default=300, ge=0)
    scale_down_cooldown: int = Field(default=600, ge=0)


class RemediationConfig(BaseSettings):
    """Remediation configuration."""

    enabled_actions: list[str] = Field(
        default_factory=lambda: [
            "restart_service",
            "scale_up",
            "rollback_deployment",
            "clear_cache",
            "restart_database",
        ]
    )
    escalation_enabled: bool = Field(default=True)
    escalation_timeout_minutes: int = Field(default=30, ge=1)
    notification_channels: list[str] = Field(
        default_factory=lambda: ["slack", "email"]
    )


class SecurityConfig(BaseSettings):
    """Security configuration."""

    encryption_enabled: bool = Field(default=True)
    kms_key_id: str = Field(default="alias/devops-ai-key")
    assume_role_timeout: int = Field(default=3600, ge=1)
    session_duration: int = Field(default=3600, ge=1)
    secrets_rotation_days: int = Field(default=90, ge=1)
    secrets_backup_enabled: bool = Field(default=True)


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = Field(default="INFO")
    format: str = Field(default="json")
    include_request_id: bool = Field(default=True)
    include_trace_id: bool = Field(default=True)
    destinations: list[str] = Field(
        default_factory=lambda: ["cloudwatch", "s3"]
    )


class FeaturesConfig(BaseSettings):
    """Feature flags configuration."""

    autoscaling: bool = Field(default=True)
    remediation: bool = Field(default=True)
    chatops: bool = Field(default=True)
    cost_optimization: bool = Field(default=True)
    predictive_scaling: bool = Field(default=False)
    multi_region: bool = Field(default=False)


class AppConfig(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8"
    )

    aws: AWSConfig = Field(default_factory=AWSConfig)
    bedrock: BedrockConfig = Field(default_factory=BedrockConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    cloudwatch: CloudWatchConfig = Field(default_factory=CloudWatchConfig)
    dynamodb: DynamoDBConfig = Field(default_factory=DynamoDBConfig)
    lambda_: LambdaConfig = Field(default_factory=LambdaConfig)
    s3: S3Config = Field(default_factory=S3Config)
    chatops: ChatOpsConfig = Field(default_factory=ChatOpsConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    autoscaling: AutoscalingConfig = Field(default_factory=AutoscalingConfig)
    remediation: RemediationConfig = Field(default_factory=RemediationConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)

    @classmethod
    def from_yaml(cls, config_path: str) -> "AppConfig":
        """Load configuration from YAML file."""
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}"
            )

        with open(config_file, "r") as f:
            config_data = yaml.safe_load(f)

        # Convert nested dict to config objects
        return cls(**cls._flatten_config(config_data))

    @staticmethod
    def _flatten_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested configuration dictionary."""
        flattened = {}

        for key, value in config_data.items():
            if isinstance(value, dict):
                flattened[key] = value
            else:
                flattened[key] = value

        return flattened

    def validate_config(self) -> None:
        """Validate configuration values."""
        # Validate AWS account ID format
        if not self.aws.account_id.isdigit() or len(self.aws.account_id) != 12:
            raise ValueError("AWS account ID must be 12 digits")

        # Validate Bedrock model ID format
        if not self.bedrock.model_id.startswith(
            ("anthropic.", "amazon.", "ai21.")
        ):
            raise ValueError("Invalid Bedrock model ID format")

        # Validate thresholds
        if self.thresholds.cpu_high >= 100:
            raise ValueError("CPU high threshold must be less than 100%")

        if self.thresholds.memory_high >= 100:
            raise ValueError("Memory high threshold must be less than 100%")


# Global configuration instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    global _config

    if _config is None:
        config_path = os.getenv("CONFIG_PATH", "config/config.yaml")
        _config = AppConfig.from_yaml(config_path)
        _config.validate_config()

    return _config


def set_config(config: AppConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def reload_config(config_path: Optional[str] = None) -> AppConfig:
    """Reload configuration from file."""
    global _config

    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "config/config.yaml")

    _config = AppConfig.from_yaml(config_path)
    _config.validate_config()

    return _config
