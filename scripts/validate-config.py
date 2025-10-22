#!/usr/bin/env python3

"""
Configuration validation script for AI Agent deployment.
Validates YAML configuration files and environment variables.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import yaml
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of configuration validation"""

    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def add_error(self, error: str) -> None:
        """Add an error message"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message"""
        self.warnings.append(warning)


class ConfigValidator:
    """Configuration validator for AI Agent"""

    def __init__(self, config_path: str, env_path: Optional[str] = None):
        self.config_path = Path(config_path)
        self.env_path = Path(env_path) if env_path else None
        self.result = ValidationResult(True, [], [])

    def validate_all(self) -> ValidationResult:
        """Run all validation checks"""
        logger.info("Starting configuration validation...")

        # Check if files exist
        self._check_files_exist()

        if not self.result.is_valid:
            return self.result

        # Load and validate configuration
        config = self._load_config()
        if config:
            self._validate_aws_config(config)
            self._validate_bedrock_config(config)
            self._validate_agent_config(config)
            self._validate_monitoring_config(config)
            self._validate_security_config(config)

        # Validate environment variables
        if self.env_path:
            self._validate_env_file()

        # Validate AWS connectivity
        self._validate_aws_connectivity(config)

        # Print results
        self._print_results()

        return self.result

    def _check_files_exist(self) -> None:
        """Check if required configuration files exist"""
        if not self.config_path.exists():
            self.result.add_error(f"Configuration file not found: {self.config_path}")

        if self.env_path and not self.env_path.exists():
            self.result.add_warning(f"Environment file not found: {self.env_path}")

    def _load_config(self) -> Optional[Dict[str, Any]]:
        """Load YAML configuration file"""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            logger.info("Configuration file loaded successfully")
            return config
        except yaml.YAMLError as e:
            self.result.add_error(f"Invalid YAML in config file: {e}")
            return None
        except Exception as e:
            self.result.add_error(f"Failed to read config file: {e}")
            return None

    def _validate_aws_config(self, config: Dict[str, Any]) -> None:
        """Validate AWS configuration"""
        aws_config = config.get("aws", {})

        # Required fields
        required_fields = ["region", "account_id"]
        for field in required_fields:
            if not aws_config.get(field):
                self.result.add_error(f"Missing AWS {field} in configuration")

        # Validate region format
        region = aws_config.get("region", "")
        if region and not region.replace("-", "").replace("_", "").isalnum():
            self.result.add_error(f"Invalid AWS region format: {region}")

        # Validate account ID
        account_id = aws_config.get("account_id", "")
        if account_id and (not str(account_id).isdigit() or len(str(account_id)) != 12):
            self.result.add_error(f"Invalid AWS account ID: {account_id}")

        logger.info("AWS configuration validation completed")

    def _validate_bedrock_config(self, config: Dict[str, Any]) -> None:
        """Validate Amazon Bedrock configuration"""
        bedrock_config = config.get("bedrock", {})

        # Model configuration
        model_id = bedrock_config.get("model_id")
        if not model_id:
            self.result.add_error("Missing Bedrock model_id in configuration")
        elif not model_id.startswith("anthropic.claude"):
            self.result.add_warning(f"Unexpected Bedrock model: {model_id}")

        # Temperature validation
        temperature = bedrock_config.get("temperature", 0.1)
        if not (0 <= temperature <= 1):
            self.result.add_error(
                f"Bedrock temperature must be between 0 and 1: {temperature}"
            )

        # Max tokens validation
        max_tokens = bedrock_config.get("max_tokens", 1000)
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            self.result.add_error(
                f"Bedrock max_tokens must be positive integer: {max_tokens}"
            )

        logger.info("Bedrock configuration validation completed")

    def _validate_agent_config(self, config: Dict[str, Any]) -> None:
        """Validate AI agent configuration"""
        agent_config = config.get("agent", {})

        # Confidence threshold
        confidence_threshold = agent_config.get("confidence_threshold", 0.8)
        if not (0 <= confidence_threshold <= 1):
            self.result.add_error(
                "Agent confidence_threshold must be between 0 and 1: "
                f"{confidence_threshold}"
            )

        # Max iterations
        max_iterations = agent_config.get("max_iterations", 3)
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            self.result.add_error(
                "Agent max_iterations must be positive integer: " f"{max_iterations}"
            )

        # Escalation timeout
        escalation_timeout = agent_config.get("escalation_timeout", 900)
        if not isinstance(escalation_timeout, int) or escalation_timeout <= 0:
            self.result.add_error(
                "Agent escalation_timeout must be positive integer: "
                f"{escalation_timeout}"
            )

        # Enabled actions
        enabled_actions = agent_config.get("enabled_actions", [])
        if not enabled_actions:
            self.result.add_warning("No enabled actions specified for agent")

        valid_actions = [
            "restart_service",
            "scale_up",
            "scale_down",
            "rollback_deployment",
            "clear_cache",
            "restart_database",
            "escalate",
        ]

        for action in enabled_actions:
            if action not in valid_actions:
                self.result.add_warning(f"Unknown action in enabled_actions: {action}")

        logger.info("Agent configuration validation completed")

    def _validate_monitoring_config(self, config: Dict[str, Any]) -> None:
        """Validate monitoring configuration"""
        monitoring_config = config.get("monitoring", {})
        thresholds = monitoring_config.get("thresholds", {})

        # Validate threshold values
        threshold_configs = {
            "cpu_threshold": (0, 100),
            "memory_threshold": (0, 100),
            "error_rate_threshold": (0, 100),
            "response_time_threshold": (0, None),
        }

        for threshold_name, (min_val, max_val) in threshold_configs.items():
            value = thresholds.get(threshold_name)
            if value is not None:
                if not isinstance(value, (int, float)) or value < min_val:
                    self.result.add_error(f"Invalid {threshold_name}: {value}")
                elif max_val and value > max_val:
                    self.result.add_error(
                        f"Invalid {threshold_name}: {value} " f"(max: {max_val})"
                    )

        # Log retention
        log_retention = monitoring_config.get("log_retention_days", 14)
        if not isinstance(log_retention, int) or log_retention <= 0:
            self.result.add_error(f"Invalid log_retention_days: {log_retention}")

        logger.info("Monitoring configuration validation completed")

    def _validate_security_config(self, config: Dict[str, Any]) -> None:
        """Validate security configuration"""
        security_config = config.get("security", {})

        # Encryption settings
        if security_config.get("encryption_enabled", True):
            kms_key = security_config.get("kms_key_id")
            if kms_key and not (
                kms_key.startswith("arn:aws:kms:")
                or kms_key.startswith("alias/")
                or len(kms_key) == 36  # UUID format
            ):
                self.result.add_warning(
                    f"Potentially invalid KMS key format: {kms_key}"
                )

        # IAM settings
        iam_config = security_config.get("iam", {})
        if iam_config.get("create_roles", True):
            role_prefix = iam_config.get("role_prefix", "ai-agent")
            if (
                not role_prefix
                or not role_prefix.replace("-", "").replace("_", "").isalnum()
            ):
                self.result.add_error(f"Invalid IAM role_prefix: {role_prefix}")

        logger.info("Security configuration validation completed")

    def _validate_env_file(self) -> None:
        """Validate environment file"""
        if not self.env_path.exists():
            return

        try:
            with open(self.env_path, "r") as f:
                lines = f.readlines()

            required_vars = ["AWS_DEFAULT_REGION", "ENVIRONMENT"]

            found_vars = set()
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    var_name = line.split("=")[0]
                    found_vars.add(var_name)

            missing_vars = set(required_vars) - found_vars
            if missing_vars:
                self.result.add_warning(
                    "Missing environment variables: " f"{', '.join(missing_vars)}"
                )

            logger.info("Environment file validation completed")

        except Exception as e:
            self.result.add_error(f"Failed to validate environment file: {e}")

    def _validate_aws_connectivity(self, config: Optional[Dict[str, Any]]) -> None:
        """Validate AWS connectivity and permissions"""
        if not config:
            return

        try:
            # Test STS access (basic connectivity)
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            logger.info(
                "AWS connectivity validated " f"(Account: {identity.get('Account')})"
            )

            # Test Bedrock access
            bedrock_config = config.get("bedrock", {})
            if bedrock_config:
                try:
                    boto3.client("bedrock-runtime")
                    # This doesn't make an actual call, just validates
                    # client creation
                    logger.info("Bedrock client access validated")
                except Exception as e:
                    self.result.add_warning(f"Bedrock access may be limited: {e}")

            # Test DynamoDB access
            try:
                dynamodb = boto3.client("dynamodb")
                dynamodb.list_tables()
                logger.info("DynamoDB access validated")
            except Exception as e:
                self.result.add_warning(f"DynamoDB access may be limited: {e}")

            # Test CloudWatch access
            try:
                cloudwatch = boto3.client("cloudwatch")
                cloudwatch.list_metrics(MaxRecords=1)
                logger.info("CloudWatch access validated")
            except Exception as e:
                self.result.add_warning(f"CloudWatch access may be limited: {e}")

        except NoCredentialsError:
            self.result.add_error("AWS credentials not configured")
        except ClientError as e:
            self.result.add_error(f"AWS access error: {e}")
        except Exception as e:
            self.result.add_error(f"AWS connectivity test failed: {e}")

    def _print_results(self) -> None:
        """Print validation results"""
        print("\n" + "=" * 60)
        print("CONFIGURATION VALIDATION RESULTS")
        print("=" * 60)

        if self.result.is_valid:
            print("✅ Configuration is VALID")
        else:
            print("❌ Configuration is INVALID")

        if self.result.errors:
            print(f"\n🚨 Errors ({len(self.result.errors)}):")
            for i, error in enumerate(self.result.errors, 1):
                print(f"  {i}. {error}")

        if self.result.warnings:
            print(f"\n⚠️  Warnings ({len(self.result.warnings)}):")
            for i, warning in enumerate(self.result.warnings, 1):
                print(f"  {i}. {warning}")

        if not self.result.errors and not self.result.warnings:
            print("\n✨ No issues found!")

        print("=" * 60)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Validate AI Agent configuration files"
    )
    parser.add_argument("config", help="Path to configuration YAML file")
    parser.add_argument("--env", help="Path to environment file (optional)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run validation
    validator = ConfigValidator(args.config, args.env)
    result = validator.validate_all()

    # Exit with appropriate code
    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
