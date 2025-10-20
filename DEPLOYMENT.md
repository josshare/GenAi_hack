# Intelligent Automation AI Agent - Deployment Guide

This guide provides comprehensive instructions for deploying the AI Agent for DevOps and Cloud Management to AWS.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Deployment Commands](#deployment-commands)
- [Configuration](#configuration)
- [Updates and Maintenance](#updates-and-maintenance)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites

### Required Tools

Make sure you have the following tools installed on your system:

```bash
# Check if required tools are installed
python3 --version  # Python 3.9 or higher
uv --version       # Python package manager
node --version     # Node.js 18 or higher  
npm --version
aws --version      # AWS CLI v2
```

### AWS Requirements

1. **AWS Account**: Active AWS account with appropriate permissions
2. **AWS CLI**: Configured with credentials (`aws configure`)
3. **Bedrock Access**: Enable Amazon Bedrock in your region and request access to Claude 3 Sonnet
4. **IAM Permissions**: User/role with permissions for:
   - Lambda, DynamoDB, CloudWatch, IAM, KMS, S3, SNS
   - Bedrock model access
   - EC2, ECS, Auto Scaling (for remediation actions)

### System Requirements

- **Operating System**: macOS, Linux, or WSL2 on Windows
- **Shell**: Fish shell (for the main deployment script) or Bash/Zsh
- **Memory**: At least 4GB RAM for build process
- **Storage**: At least 2GB free space for dependencies and build artifacts

## Quick Start

For a rapid deployment, follow these steps:

### 1. Initialize the Project

```bash
# Clone the repository and navigate to it
cd /path/to/GenAi_hack

# Install dependencies (first time only)
uv pip install -r requirements.txt
npm install
```

### 2. Configure Settings

```bash
# Edit configuration files with your specific settings
vim config/config.yaml  # Main configuration
vim .env                 # Environment variables
```

### 3. Deploy Infrastructure and Application

Deployment is now performed via GitHub Actions using CloudFormation. Push to the default branch or run the workflow manually. The workflow deploys the stack (`infrastructure/stack.yaml`) and then packages and updates the Lambda functions using uv.

### 4. Verify Deployment

```bash
# Check deployment status
./deploy.fish status
```

## Detailed Setup

### Step 1: Environment Setup

1. **Configure AWS Credentials**
   ```bash
   aws configure
   # OR use AWS profiles
   aws configure --profile ai-agent-prod
   ```

2. **Set Up Configuration Files**
   ```bash
   # Copy example files
   cp config/config.example.yaml config/config.yaml
   cp env.example .env
   
   # Edit with your specific values
   vim config/config.yaml
   vim .env
   ```

3. **Validate Configuration**
   ```bash
   # Validate your configuration
   python3 scripts/validate-config.py config/config.yaml --env .env
   ```

### Step 2: Infrastructure Deployment

Infrastructure is defined in CloudFormation `infrastructure/stack.yaml` and deployed by the GitHub Actions workflow.

### Step 3: Application Deployment

Lambda packaging and updates are handled by the workflow via `scripts/deploy.js` and uv. You can still run it locally if needed:

```bash
node scripts/deploy.js --environment dev --region us-east-1
```

## Deployment Commands

### Deployment via GitHub Actions

The workflow `.github/workflows/deploy.yml` deploys CloudFormation and updates the functions. Inputs `environment` and `region` are supported for manual runs.

#### Command Options

```bash
-p, --profile PROFILE    # AWS profile to use
-r, --region REGION      # AWS region (default: us-east-1)
-e, --env ENVIRONMENT    # Environment (dev|staging|prod, default: dev)
-d, --dry-run            # Show what would be done without executing
-f, --force              # Force deployment without confirmation
--skip-tests             # Skip running tests
--skip-infra             # Skip infrastructure deployment
-h, --help               # Show help message
```

#### Examples

```bash
# Deploy to production with specific AWS profile
./deploy.fish deploy --env prod --profile production --region us-west-2

# Dry run to see what would be deployed
./deploy.fish deploy --dry-run --env staging

# Force update without confirmation (for CI/CD)
./deploy.fish update --force --skip-tests

# Rollback production deployment
./deploy.fish rollback --env prod --profile production
```

### Node.js Deployment Scripts

For more granular control, use the Node.js scripts:

```bash
# Deploy application with Node.js script
node scripts/deploy.js --environment=prod --region=us-west-2

# Rollback deployment
node scripts/rollback.js --environment=prod --version=3

# With dry-run mode
node scripts/deploy.js --dry-run --verbose
```

### NPM Scripts

Use predefined NPM scripts for common tasks:

```bash
# Run tests
npm run test
npm run lint
npm run type-check

# Application deployment (local)
npm run deploy
```

## Configuration

### Main Configuration File (`config/config.yaml`)

Key configuration sections:

1. **AWS Configuration**
   ```yaml
   aws:
     region: "us-east-1"
     account_id: "123456789012"
     profile: ""  # Optional AWS profile
   ```

2. **Bedrock Configuration**
   ```yaml
   bedrock:
     model_id: "anthropic.claude-3-sonnet-20240229-v1:0"
     temperature: 0.1
     max_tokens: 4000
   ```

3. **Agent Behavior**
   ```yaml
   agent:
     confidence_threshold: 0.8  # Lower = more autonomous
     max_iterations: 3
     enabled_actions:
       - "restart_service"
       - "scale_up"
       - "escalate"
   ```

### Environment Variables (`.env`)

```bash
# Required environment variables
AWS_DEFAULT_REGION=us-east-1
ENVIRONMENT=dev

# Optional
AWS_PROFILE=ai-agent-dev
LOG_LEVEL=INFO
```

### Environment-Specific Configuration

The configuration supports environment-specific overrides:

```yaml
environments:
  dev:
    agent:
      confidence_threshold: 0.9  # More cautious in dev
  prod:
    agent:
      confidence_threshold: 0.8  # More autonomous in prod
    notifications:
      slack:
        enabled: true
```

## Updates and Maintenance

### Regular Updates

Push to your repository to trigger the workflow, or run `node scripts/deploy.js` locally for code-only updates.

### Rolling Updates

For zero-downtime updates using Lambda aliases:

```bash
# Deploy with gradual rollout
node scripts/deploy.js --environment=prod --gradual-deployment
```

### Rollback Procedures

If something goes wrong after deployment:

```bash
# Automatic rollback to previous version
./deploy.fish rollback

# Rollback to specific version
node scripts/rollback.js --environment=prod --version=5

# Force rollback without confirmation
./deploy.fish rollback --force
```

### Monitoring Deployments

After deployment, monitor the system:

1. **Check Lambda Functions**
   ```bash
   aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `prod-ai-agent`)].FunctionName'
   ```

2. **Monitor CloudWatch Logs**
   ```bash
   aws logs describe-log-groups --log-group-name-prefix '/aws/lambda/prod-ai-agent'
   ```

3. **Check DynamoDB Tables**
   ```bash
   aws dynamodb list-tables --query 'TableNames[?starts_with(@, `prod-ai-agent`)]'
   ```

## Troubleshooting

### Common Issues

#### 1. AWS Credentials Not Found

```bash
Error: AWS credentials not configured
```

**Solution:**
```bash
# Configure AWS credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

#### 2. CloudFormation Rollback

If the stack rolls back, check Events and fix the underlying error (permissions, parameters, limits) and re-run the workflow.

#### 3. Lambda Deployment Package Too Large

```bash
Error: Unzipped size must be smaller than 262144000 bytes
```

**Solution:**
```bash
# Clean up dependencies and rebuild
rm -rf dist/
./deploy.fish deploy --skip-tests
```

#### 4. Bedrock Access Denied

```bash
Error: User is not authorized to perform: bedrock:InvokeModel
```

**Solution:**
1. Enable Bedrock in your region
2. Request access to Claude 3 Sonnet model
3. Add Bedrock permissions to your IAM role/user

#### 5. DynamoDB Throttling

```bash
Error: ProvisionedThroughputExceededException
```

**Solution:**
The tables use PAY_PER_REQUEST billing, but if you encounter throttling:
```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics --namespace AWS/DynamoDB --metric-name ConsumedReadCapacityUnits
```

### Debug Mode

Run deployments with verbose output for debugging:

```bash
# Fish script with debug info
./deploy.fish deploy --env dev 2>&1 | tee deployment.log

# Node.js script with verbose output
node scripts/deploy.js --verbose --environment=dev
```

### Log Analysis

Check application logs for issues:

```bash
# View Lambda logs
aws logs tail /aws/lambda/dev-ai-agent-incident-processor --follow

# Check specific log stream
aws logs get-log-events --log-group-name /aws/lambda/dev-ai-agent-incident-processor --log-stream-name LATEST
```

### Health Checks

Verify system health after deployment:

```bash
# Run configuration validation
python3 scripts/validate-config.py config/config.yaml --verbose

# Check deployment status
./deploy.fish status

# Test Lambda function
aws lambda invoke --function-name dev-ai-agent-incident-processor --payload '{"test": true}' response.json
```

## Advanced Configuration

### CI/CD Integration

For automated deployments in CI/CD pipelines:

```bash
# GitHub Actions example
./deploy.fish deploy --force --skip-tests --env prod --profile ci-cd-role

# Jenkins example
node scripts/deploy.js --environment=prod --dry-run=false --skip-tests
```

### Multi-Region Deployment

Run the workflow with different `region` inputs for each target region.

### Custom Resource Tags

Add custom tags by extending `infrastructure/stack.yaml` resources and their Tags sections.

### Security Hardening

1. **Enable encryption at rest**
2. **Use KMS customer-managed keys**
3. **Enable VPC endpoints**
4. **Implement least-privilege IAM policies**

### Performance Optimization

1. **Adjust Lambda memory settings based on usage**
2. **Configure DynamoDB auto-scaling if needed**
3. **Optimize CloudWatch log retention**
4. **Use Lambda provisioned concurrency for consistent performance**

## Support and Maintenance

### Regular Maintenance Tasks

1. **Monitor costs**: Check AWS Cost Explorer monthly
2. **Review logs**: Check CloudWatch logs weekly
3. **Update dependencies**: Update Python packages monthly
4. **Security patches**: Apply security updates promptly
5. **Backup validation**: Test backup restoration quarterly

### Getting Help

1. **Check logs first**: Lambda functions, CloudWatch, DynamoDB
2. **Validate configuration**: Run `validate-config.py`
3. **Test connectivity**: Verify AWS credentials and permissions
4. **Review documentation**: Check AWS service documentation
5. **Community support**: Search AWS forums and Stack Overflow

### Contact Information

- **Project Repository**: [GitHub Repository URL]
- **Documentation**: [Documentation URL]
- **Issue Tracker**: [Issues URL]
- **Team Contact**: devops-team@example.com

---

**Last Updated**: October 2024  
**Version**: 1.0.0