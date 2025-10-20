#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');
const AWS = require('aws-sdk');
const commander = require('commander');
const chalk = require('chalk');
const ora = require('ora');

// Configure AWS SDK
AWS.config.update({ region: process.env.AWS_DEFAULT_REGION || 'us-east-1' });

const program = new commander.Command();

program
  .name('deploy')
  .description('Deploy Intelligent Automation AI Agent to AWS')
  .version('1.0.0')
  .option('-e, --environment <env>', 'deployment environment', 'dev')
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .option('-p, --profile <profile>', 'AWS profile to use')
  .option('--skip-build', 'skip build process')
  .option('--skip-tests', 'skip running tests')
  .option('--dry-run', 'show what would be deployed without actually deploying')
  .option('-v, --verbose', 'verbose output');

program.parse(process.argv);

const options = program.opts();

// Configure AWS with profile if specified
if (options.profile) {
  process.env.AWS_PROFILE = options.profile;
  AWS.config.credentials = new AWS.SharedIniFileCredentials({ profile: options.profile });
}

// Update region
AWS.config.update({ region: options.region });

const lambda = new AWS.Lambda();
const s3 = new AWS.S3();
const iam = new AWS.IAM();
const dynamodb = new AWS.DynamoDB();
const cloudwatch = new AWS.CloudWatch();

// Project paths
const PROJECT_ROOT = path.resolve(__dirname, '..');
const SRC_DIR = path.join(PROJECT_ROOT, 'src');
const CONFIG_DIR = path.join(PROJECT_ROOT, 'config');
const DIST_DIR = path.join(PROJECT_ROOT, 'dist');
const STACK_OUTPUTS = path.join(PROJECT_ROOT, 'stack-outputs.json');

// Logging utilities
const log = {
  info: (msg) => console.log(chalk.blue('[INFO]'), msg),
  success: (msg) => console.log(chalk.green('[SUCCESS]'), msg),
  warning: (msg) => console.log(chalk.yellow('[WARNING]'), msg),
  error: (msg) => console.log(chalk.red('[ERROR]'), msg),
  verbose: (msg) => options.verbose && console.log(chalk.gray('[VERBOSE]'), msg)
};

// Lambda function configurations
const LAMBDA_FUNCTIONS = [
  {
    name: 'incident-processor',
    handler: 'incident_processor.lambda_handler',
    runtime: 'python3.11',
    timeout: 300,
    memorySize: 512,
    environment: {
      ENVIRONMENT: options.environment,
      LOG_LEVEL: 'INFO'
    }
  },
  {
    name: 'action-executor',
    handler: 'action_executor.lambda_handler',
    runtime: 'python3.11',
    timeout: 900,
    memorySize: 1024,
    environment: {
      ENVIRONMENT: options.environment,
      LOG_LEVEL: 'INFO'
    }
  }
];

// Utility functions
function executeCommand(command, options = {}) {
  log.verbose(`Executing: ${command}`);
  try {
    const result = execSync(command, {
      encoding: 'utf8',
      stdio: options.stdio || 'pipe',
      cwd: options.cwd || PROJECT_ROOT,
      ...options
    });
    return result.toString().trim();
  } catch (error) {
    log.error(`Command failed: ${command}`);
    log.error(error.message);
    throw error;
  }
}

function createZipPackage(functionName, sourcePath) {
  const spinner = ora(`Creating deployment package for ${functionName}...`).start();
  
  try {
    const zipPath = path.join(DIST_DIR, `${functionName}.zip`);
    
    // Ensure dist directory exists
    if (!fs.existsSync(DIST_DIR)) {
      fs.mkdirSync(DIST_DIR, { recursive: true });
    }
    
    // Create a temporary directory for the package
    const tempDir = path.join(DIST_DIR, `temp_${functionName}`);
    if (fs.existsSync(tempDir)) {
      executeCommand(`rm -rf "${tempDir}"`);
    }
    fs.mkdirSync(tempDir, { recursive: true });
    
    // Copy source files
    if (fs.existsSync(sourcePath)) {
      executeCommand(`cp -r "${sourcePath}"/* "${tempDir}"/`, { stdio: 'ignore' });
    }
    
    // Copy common modules
    const commonPath = path.join(SRC_DIR, 'utils');
    if (fs.existsSync(commonPath)) {
      executeCommand(`cp -r "${commonPath}" "${tempDir}"/utils`, { stdio: 'ignore' });
    }
    
    const agentsPath = path.join(SRC_DIR, 'agents');
    if (fs.existsSync(agentsPath)) {
      executeCommand(`cp -r "${agentsPath}" "${tempDir}"/agents`, { stdio: 'ignore' });
    }
    
    const integrationsPath = path.join(SRC_DIR, 'integrations');
    if (fs.existsSync(integrationsPath)) {
      executeCommand(`cp -r "${integrationsPath}" "${tempDir}"/integrations`, { stdio: 'ignore' });
    }
    
    // Install dependencies using uv (replaces pip)
    executeCommand(`uv pip install -r "${PROJECT_ROOT}/requirements.txt" -t "${tempDir}"`, { stdio: 'ignore' });
    
    // Create zip file
    executeCommand(`cd "${tempDir}" && zip -r "${zipPath}" . -x "*.pyc" "__pycache__/*" "*.git*"`, { stdio: 'ignore' });
    
    // Clean up temp directory
    executeCommand(`rm -rf "${tempDir}"`);
    
    spinner.succeed(`Package created: ${zipPath}`);
    return zipPath;
  } catch (error) {
    spinner.fail(`Failed to create package for ${functionName}`);
    throw error;
  }
}

async function deployLambdaFunction(functionConfig, zipPath) {
  const functionName = `${options.environment}-ai-agent-${functionConfig.name}`;
  const spinner = ora(`Deploying Lambda function: ${functionName}...`).start();
  
  try {
    const zipBuffer = fs.readFileSync(zipPath);
    
    // Check if function exists
    let functionExists = false;
    try {
      await lambda.getFunction({ FunctionName: functionName }).promise();
      functionExists = true;
    } catch (error) {
      if (error.code !== 'ResourceNotFoundException') {
        throw error;
      }
    }
    
    if (functionExists) {
      // Update existing function
      if (!options.dryRun) {
        await lambda.updateFunctionCode({
          FunctionName: functionName,
          ZipFile: zipBuffer
        }).promise();
        
        await lambda.updateFunctionConfiguration({
          FunctionName: functionName,
          Handler: functionConfig.handler,
          Runtime: functionConfig.runtime,
          Timeout: functionConfig.timeout,
          MemorySize: functionConfig.memorySize,
          Environment: {
            Variables: functionConfig.environment
          }
        }).promise();
      }
      spinner.succeed(`Updated Lambda function: ${functionName}`);
    } else {
      // Create new function
      if (!options.dryRun) {
        // Get execution role ARN from stack outputs (CloudFormation) or fallback
        let roleArn = `arn:aws:iam::${await getAccountId()}:role/${options.environment}-ai-agent-lambda-role`;

        // Prefer CloudFormation stack outputs if available
        if (fs.existsSync(STACK_OUTPUTS)) {
          try {
            const stackOutputs = JSON.parse(fs.readFileSync(STACK_OUTPUTS, 'utf8'));
            if (stackOutputs.LambdaExecutionRoleArn) {
              roleArn = stackOutputs.LambdaExecutionRoleArn;
            }
          } catch (_) { /* ignore parse errors */ }
        }
        
        await lambda.createFunction({
          FunctionName: functionName,
          Runtime: functionConfig.runtime,
          Role: roleArn,
          Handler: functionConfig.handler,
          Code: { ZipFile: zipBuffer },
          Timeout: functionConfig.timeout,
          MemorySize: functionConfig.memorySize,
          Environment: {
            Variables: functionConfig.environment
          },
          Tags: {
            Environment: options.environment,
            Project: 'ai-agent',
            ManagedBy: 'deployment-script'
          }
        }).promise();
      }
      spinner.succeed(`Created Lambda function: ${functionName}`);
    }
    
    return functionName;
  } catch (error) {
    spinner.fail(`Failed to deploy Lambda function: ${functionName}`);
    log.error(error.message);
    throw error;
  }
}

async function getAccountId() {
  const sts = new AWS.STS();
  const identity = await sts.getCallerIdentity().promise();
  return identity.Account;
}

async function setupCloudWatchAlarms() {
  const spinner = ora('Setting up CloudWatch alarms...').start();
  
  try {
    const alarms = [
      {
        AlarmName: `${options.environment}-ai-agent-lambda-errors`,
        ComparisonOperator: 'GreaterThanThreshold',
        EvaluationPeriods: 2,
        MetricName: 'Errors',
        Namespace: 'AWS/Lambda',
        Period: 300,
        Statistic: 'Sum',
        Threshold: 5,
        ActionsEnabled: true,
        AlarmDescription: 'Lambda function errors',
        Dimensions: [
          {
            Name: 'FunctionName',
            Value: `${options.environment}-ai-agent-incident-processor`
          }
        ]
      },
      {
        AlarmName: `${options.environment}-ai-agent-lambda-duration`,
        ComparisonOperator: 'GreaterThanThreshold',
        EvaluationPeriods: 3,
        MetricName: 'Duration',
        Namespace: 'AWS/Lambda',
        Period: 300,
        Statistic: 'Average',
        Threshold: 240000, // 4 minutes
        ActionsEnabled: true,
        AlarmDescription: 'Lambda function duration',
        Dimensions: [
          {
            Name: 'FunctionName',
            Value: `${options.environment}-ai-agent-incident-processor`
          }
        ]
      }
    ];
    
    if (!options.dryRun) {
      for (const alarm of alarms) {
        await cloudwatch.putMetricAlarm(alarm).promise();
      }
    }
    
    spinner.succeed('CloudWatch alarms configured');
  } catch (error) {
    spinner.fail('Failed to setup CloudWatch alarms');
    log.warning(error.message);
    // Don't fail deployment for alarm setup issues
  }
}

async function validateDeployment() {
  const spinner = ora('Validating deployment...').start();
  
  try {
    const validationResults = {
      lambdaFunctions: [],
      dynamodbTables: [],
      cloudwatchAlarms: []
    };
    
    // Check Lambda functions
    const functions = await lambda.listFunctions().promise();
    for (const func of LAMBDA_FUNCTIONS) {
      const functionName = `${options.environment}-ai-agent-${func.name}`;
      const lambdaFunction = functions.Functions.find(f => f.FunctionName === functionName);
      
      if (lambdaFunction) {
        validationResults.lambdaFunctions.push({
          name: functionName,
          status: 'OK',
          lastModified: lambdaFunction.LastModified,
          runtime: lambdaFunction.Runtime
        });
      } else {
        validationResults.lambdaFunctions.push({
          name: functionName,
          status: 'MISSING'
        });
      }
    }
    
    // Check DynamoDB tables
    const tables = await dynamodb.listTables().promise();
    const expectedTables = [`${options.environment}-ai-agent-incidents`, `${options.environment}-ai-agent-actions`];
    
    for (const tableName of expectedTables) {
      if (tables.TableNames.includes(tableName)) {
        const tableInfo = await dynamodb.describeTable({ TableName: tableName }).promise();
        validationResults.dynamodbTables.push({
          name: tableName,
          status: tableInfo.Table.TableStatus,
          itemCount: tableInfo.Table.ItemCount || 0
        });
      } else {
        validationResults.dynamodbTables.push({
          name: tableName,
          status: 'MISSING'
        });
      }
    }
    
    // Check CloudWatch alarms
    const alarms = await cloudwatch.describeAlarms({
      AlarmNamePrefix: `${options.environment}-ai-agent`
    }).promise();
    
    validationResults.cloudwatchAlarms = alarms.MetricAlarms.map(alarm => ({
      name: alarm.AlarmName,
      state: alarm.StateValue,
      reason: alarm.StateReason
    }));
    
    spinner.succeed('Deployment validation completed');
    
    // Display results
    log.info('\n--- Deployment Validation Results ---');
    
    log.info('\nLambda Functions:');
    validationResults.lambdaFunctions.forEach(func => {
      const status = func.status === 'OK' ? chalk.green(func.status) : chalk.red(func.status);
      log.info(`  ${func.name}: ${status}`);
      if (func.lastModified) {
        log.verbose(`    Last Modified: ${func.lastModified}`);
        log.verbose(`    Runtime: ${func.runtime}`);
      }
    });
    
    log.info('\nDynamoDB Tables:');
    validationResults.dynamodbTables.forEach(table => {
      const status = table.status === 'ACTIVE' ? chalk.green(table.status) : 
                    table.status === 'MISSING' ? chalk.red(table.status) : chalk.yellow(table.status);
      log.info(`  ${table.name}: ${status}`);
      if (table.itemCount !== undefined) {
        log.verbose(`    Item Count: ${table.itemCount}`);
      }
    });
    
    log.info('\nCloudWatch Alarms:');
    validationResults.cloudwatchAlarms.forEach(alarm => {
      const state = alarm.state === 'OK' ? chalk.green(alarm.state) : chalk.yellow(alarm.state);
      log.info(`  ${alarm.name}: ${state}`);
      log.verbose(`    Reason: ${alarm.reason}`);
    });
    
    return validationResults;
  } catch (error) {
    spinner.fail('Deployment validation failed');
    log.error(error.message);
    throw error;
  }
}

async function main() {
  try {
    log.info(chalk.bold(`\n🚀 Deploying AI Agent to AWS`));
    log.info(`Environment: ${chalk.cyan(options.environment)}`);
    log.info(`Region: ${chalk.cyan(options.region)}`);
    if (options.profile) {
      log.info(`AWS Profile: ${chalk.cyan(options.profile)}`);
    }
    if (options.dryRun) {
      log.warning('DRY RUN MODE - No actual deployment will occur');
    }
    
    // Validate AWS credentials
    const spinner = ora('Validating AWS credentials...').start();
    try {
      const sts = new AWS.STS();
      const identity = await sts.getCallerIdentity().promise();
      spinner.succeed(`AWS credentials valid (Account: ${identity.Account})`);
    } catch (error) {
      spinner.fail('Invalid AWS credentials');
      throw error;
    }
    
    // Check if Terraform outputs exist
    if (!fs.existsSync(TERRAFORM_OUTPUTS)) {
      log.warning('Terraform outputs not found. Make sure infrastructure is deployed first.');
    }
    
    // Run tests if not skipped
    if (!options.skipTests && !options.dryRun) {
      const testSpinner = ora('Running tests...').start();
      try {
        executeCommand('pytest tests/ -v', { stdio: 'ignore' });
        testSpinner.succeed('All tests passed');
      } catch (error) {
        testSpinner.fail('Tests failed');
        if (process.env.NODE_ENV !== 'development') {
          throw error;
        } else {
          log.warning('Continuing deployment despite test failures (development mode)');
        }
      }
    }
    
    // Build and package Lambda functions
    if (!options.skipBuild) {
      log.info('\n📦 Building and packaging Lambda functions...');
      
      const deployedFunctions = [];
      
      for (const functionConfig of LAMBDA_FUNCTIONS) {
        const sourcePath = path.join(SRC_DIR, 'functions', functionConfig.name);
        
        if (!fs.existsSync(sourcePath)) {
          log.error(`Function source path not found: ${sourcePath}`);
          continue;
        }
        
        // Create deployment package
        const zipPath = createZipPackage(functionConfig.name, sourcePath);
        
        // Deploy to Lambda
        const functionName = await deployLambdaFunction(functionConfig, zipPath);
        deployedFunctions.push(functionName);
      }
      
      log.success(`\n✅ Deployed ${deployedFunctions.length} Lambda functions`);
    }
    
    // Setup CloudWatch monitoring
    if (!options.dryRun) {
      await setupCloudWatchAlarms();
    }
    
    // Validate deployment
    if (!options.dryRun) {
      await validateDeployment();
    }
    
    log.success(chalk.bold('\n🎉 Deployment completed successfully!'));
    
    if (options.dryRun) {
      log.info('\nThis was a dry run. No actual resources were deployed.');
    } else {
      log.info('\n📊 Next steps:');
      log.info('1. Check AWS Lambda console for function status');
      log.info('2. Monitor CloudWatch logs for any issues');
      log.info('3. Test the deployed functions with sample events');
    }
    
  } catch (error) {
    log.error(chalk.bold('\n❌ Deployment failed!'));
    log.error(error.message);
    if (options.verbose) {
      console.error(error.stack);
    }
    process.exit(1);
  }
}

// Handle process termination
process.on('SIGINT', () => {
  log.warning('\nDeployment interrupted by user');
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled Rejection at:', promise, 'reason:', reason);
  process.exit(1);
});

// Run the deployment
main();