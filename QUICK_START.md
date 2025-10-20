# AI Agent - Quick Deployment Guide

This is the fastest way to get your Intelligent Automation AI Agent up and running on AWS.

## Prerequisites (5 minutes)

1. **AWS CLI configured**: `aws configure`
2. **Required tools installed**:
   ```bash
   # Check if you have the tools (install if missing)
   python3 --version  # 3.9+
   node --version     # 18+
   uv --version       # uv package manager
   aws --version      # 2.x
   ```

## Quick Deployment (10 minutes)

### 1. Initialize Project
```bash
# Make sure you're in the project directory
cd /path/to/GenAi_hack

# Install dependencies (first time only)
uv pip install -r requirements.txt
npm install
```

### 2. Configure Settings
```bash
# Copy and edit configuration files
cp config/config.example.yaml config/config.yaml
cp env.example .env

# Edit with your AWS account details
vim config/config.yaml  # Set your AWS account_id and region
vim .env                # Set ENVIRONMENT and AWS_DEFAULT_REGION
```

### 3. Deploy via GitHub Actions
Push to your repository's default branch or run the Deploy AI Agent workflow manually.
Infrastructure is managed with CloudFormation.

### 4. Verify Deployment
```bash
# Check status
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `dev-ai-agent`)].{Name:FunctionName,Runtime:Runtime,LastModified:LastModified}' --output table

# View logs
aws logs tail /aws/lambda/dev-ai-agent-incident-processor --follow
```

## Update Application (2 minutes)

Push your changes to trigger the GitHub Actions workflow. It will package with uv and update the Lambda functions.

## Common Actions

```bash
# Run tests
pytest tests/ -v
# Linting and type checking
flake8 src/ tests/
mypy src/
```

 

## Examples

Use the Actions tab to run the Deploy AI Agent workflow with custom inputs (environment, region).

## Troubleshooting

### Common Issues

**AWS Credentials Error:**
```bash
aws configure  # Set your credentials
```

**Configuration Error:**
```bash
python3 scripts/validate-config.py config/config.yaml --env .env
```

**Permission Error:**
```bash
# Make sure you have permissions for:
# Lambda, DynamoDB, CloudWatch, IAM, KMS, S3, SNS, Bedrock
```

**CloudFormation Rollback or Failure:** Check stack Events in the AWS console. Fix template/parameters or IAM permissions, then re-run the workflow.

### Get Help

```bash
# Show help
./deploy.fish --help

# Verbose deployment for debugging
./deploy.fish deploy --env dev 2>&1 | tee deployment.log
```

## What Gets Deployed

**Infrastructure (CloudFormation):**
- Lambda functions (incident-processor, action-executor)
- DynamoDB tables (incidents, actions)
- CloudWatch alarms and log groups
- IAM roles and policies
- KMS keys for encryption
- S3 bucket for artifacts
- SNS topic for alerts

**Application (Node.js):**
- Lambda function code deployment
- Environment variables
- CloudWatch monitoring setup
- Validation and health checks

## Configuration Files

- `config/config.yaml` - Main configuration
- `.env` - Environment variables
- `infrastructure/stack.yaml` - CloudFormation template

## Next Steps

1. **Monitor the deployment**: Check AWS Lambda console
2. **Test the agent**: Send a test CloudWatch alarm
3. **Customize configuration**: Adjust thresholds and actions
4. **Set up notifications**: Configure Slack/Teams integration
5. **Read full documentation**: See `DEPLOYMENT.md` for details

## Support

- Full documentation: `DEPLOYMENT.md`
- Configuration validation: `python3 scripts/validate-config.py`
- Project rules: `WARP.md`

---

**⚡ That's it! Your AI Agent should now be deployed and monitoring your AWS infrastructure.**