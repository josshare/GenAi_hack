# AI Agent - Quick Deployment Guide

This is the fastest way to get your Intelligent Automation AI Agent up and running on AWS.

## Prerequisites (5 minutes)

1. **AWS CLI configured**: `aws configure`
2. **Required tools installed**:
   ```bash
   # Check if you have the tools (install if missing)
   python3 --version  # 3.9+
   node --version     # 18+
   terraform --version # 1.5+
   aws --version      # 2.x
   ```

## Quick Deployment (10 minutes)

### 1. Initialize Project
```bash
# Make sure you're in the project directory
cd /path/to/GenAi_hack

# Initialize (first time only)
./deploy.fish init
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

### 3. Deploy Everything
```bash
# Deploy infrastructure and application
./deploy.fish deploy

# Or deploy to a specific environment
./deploy.fish deploy --env prod --region us-west-2
```

### 4. Verify Deployment
```bash
# Check status
./deploy.fish status

# View logs
aws logs tail /aws/lambda/dev-ai-agent-incident-processor --follow
```

## Update Application (2 minutes)

For code changes (no infrastructure changes needed):

```bash
# Quick update
./deploy.fish update

# Update specific environment
./deploy.fish update --env prod
```

## Common Commands

```bash
# Initialize (first time only)
./deploy.fish init

# Deploy everything
./deploy.fish deploy

# Update application only
./deploy.fish update

# Check status
./deploy.fish status

# Rollback if needed
./deploy.fish rollback

# Destroy resources (careful!)
./deploy.fish destroy
```

## Command Options

```bash
# Options available for all commands
-e, --env ENVIRONMENT    # dev|staging|prod (default: dev)
-r, --region REGION      # AWS region (default: us-east-1)
-p, --profile PROFILE    # AWS profile to use
-d, --dry-run            # Show what would be done
-f, --force              # Skip confirmations
--skip-tests             # Skip running tests
--skip-infra             # Skip infrastructure deployment
```

## Examples

```bash
# Deploy to production
./deploy.fish deploy --env prod --profile production

# Dry run to see what would happen
./deploy.fish deploy --dry-run

# Force update without confirmation (CI/CD)
./deploy.fish update --force --skip-tests

# Deploy only application, skip infrastructure
./deploy.fish deploy --skip-infra
```

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

**Terraform Lock:**
```bash
cd infrastructure
terraform force-unlock LOCK_ID
```

### Get Help

```bash
# Show help
./deploy.fish --help

# Verbose deployment for debugging
./deploy.fish deploy --env dev 2>&1 | tee deployment.log
```

## What Gets Deployed

**Infrastructure (Terraform):**
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
- `infrastructure/main.tf` - Terraform configuration

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