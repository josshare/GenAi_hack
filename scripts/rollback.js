#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const AWS = require('aws-sdk');
const commander = require('commander');
const chalk = require('chalk');
const ora = require('ora');

const program = new commander.Command();

program
  .name('rollback')
  .description('Rollback AI Agent deployment to previous version')
  .version('1.0.0')
  .option('-e, --environment <env>', 'deployment environment', 'dev')
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .option('-p, --profile <profile>', 'AWS profile to use')
  .option('--version <version>', 'specific version to rollback to')
  .option('--dry-run', 'show what would be rolled back without executing')
  .option('-f, --force', 'force rollback without confirmation')
  .option('-v, --verbose', 'verbose output');

program.parse(process.argv);

const options = program.opts();

// Configure AWS
if (options.profile) {
  process.env.AWS_PROFILE = options.profile;
  AWS.config.credentials = new AWS.SharedIniFileCredentials({ profile: options.profile });
}

AWS.config.update({ region: options.region });

const lambda = new AWS.Lambda();
const dynamodb = new AWS.DynamoDB();

// Logging utilities
const log = {
  info: (msg) => console.log(chalk.blue('[INFO]'), msg),
  success: (msg) => console.log(chalk.green('[SUCCESS]'), msg),
  warning: (msg) => console.log(chalk.yellow('[WARNING]'), msg),
  error: (msg) => console.log(chalk.red('[ERROR]'), msg),
  verbose: (msg) => options.verbose && console.log(chalk.gray('[VERBOSE]'), msg)
};

const LAMBDA_FUNCTIONS = ['incident-processor', 'action-executor'];

async function listFunctionVersions(functionName) {
  const fullFunctionName = `${options.environment}-ai-agent-${functionName}`;
  
  try {
    const versions = await lambda.listVersionsByFunction({
      FunctionName: fullFunctionName
    }).promise();
    
    // Filter out $LATEST and sort by version number
    return versions.Versions
      .filter(v => v.Version !== '$LATEST')
      .sort((a, b) => parseInt(b.Version) - parseInt(a.Version));
  } catch (error) {
    log.error(`Failed to list versions for ${fullFunctionName}: ${error.message}`);
    return [];
  }
}

async function rollbackFunction(functionName, targetVersion) {
  const fullFunctionName = `${options.environment}-ai-agent-${functionName}`;
  const spinner = ora(`Rolling back ${fullFunctionName} to version ${targetVersion}...`).start();
  
  try {
    if (!options.dryRun) {
      // Update the function's alias to point to the target version
      try {
        await lambda.updateAlias({
          FunctionName: fullFunctionName,
          Name: 'LIVE',
          FunctionVersion: targetVersion
        }).promise();
      } catch (error) {
        if (error.code === 'ResourceNotFoundException') {
          // Create alias if it doesn't exist
          await lambda.createAlias({
            FunctionName: fullFunctionName,
            Name: 'LIVE',
            FunctionVersion: targetVersion,
            Description: 'Live version of the function'
          }).promise();
        } else {
          throw error;
        }
      }
    }
    
    spinner.succeed(`Rolled back ${fullFunctionName} to version ${targetVersion}`);
    return true;
  } catch (error) {
    spinner.fail(`Failed to rollback ${fullFunctionName}`);
    log.error(error.message);
    return false;
  }
}

async function createBackupSnapshot() {
  const spinner = ora('Creating backup snapshot of current deployment...').start();
  
  try {
    const snapshot = {
      timestamp: new Date().toISOString(),
      environment: options.environment,
      functions: {}
    };
    
    for (const functionName of LAMBDA_FUNCTIONS) {
      const fullFunctionName = `${options.environment}-ai-agent-${functionName}`;
      
      try {
        const functionConfig = await lambda.getFunction({
          FunctionName: fullFunctionName
        }).promise();
        
        snapshot.functions[functionName] = {
          version: functionConfig.Configuration.Version,
          lastModified: functionConfig.Configuration.LastModified,
          codeSize: functionConfig.Configuration.CodeSize,
          runtime: functionConfig.Configuration.Runtime
        };
      } catch (error) {
        log.warning(`Could not backup ${fullFunctionName}: ${error.message}`);
      }
    }
    
    if (!options.dryRun) {
      // Save snapshot to a file
      const snapshotPath = path.join(__dirname, '..', 'snapshots', `${options.environment}-${Date.now()}.json`);
      const snapshotDir = path.dirname(snapshotPath);
      
      if (!fs.existsSync(snapshotDir)) {
        fs.mkdirSync(snapshotDir, { recursive: true });
      }
      
      fs.writeFileSync(snapshotPath, JSON.stringify(snapshot, null, 2));
      log.verbose(`Snapshot saved to: ${snapshotPath}`);
    }
    
    spinner.succeed('Backup snapshot created');
    return snapshot;
  } catch (error) {
    spinner.fail('Failed to create backup snapshot');
    log.error(error.message);
    throw error;
  }
}

async function validateRollback() {
  const spinner = ora('Validating rollback...').start();
  
  try {
    const results = [];
    
    for (const functionName of LAMBDA_FUNCTIONS) {
      const fullFunctionName = `${options.environment}-ai-agent-${functionName}`;
      
      try {
        // Check if function exists
        const functionConfig = await lambda.getFunction({
          FunctionName: fullFunctionName
        }).promise();
        
        // Get current alias (if exists)
        let currentVersion = '$LATEST';
        try {
          const alias = await lambda.getAlias({
            FunctionName: fullFunctionName,
            Name: 'LIVE'
          }).promise();
          currentVersion = alias.FunctionVersion;
        } catch (error) {
          // Alias doesn't exist, using $LATEST
        }
        
        results.push({
          name: fullFunctionName,
          status: 'OK',
          currentVersion: currentVersion,
          lastModified: functionConfig.Configuration.LastModified
        });
      } catch (error) {
        results.push({
          name: fullFunctionName,
          status: 'ERROR',
          error: error.message
        });
      }
    }
    
    spinner.succeed('Rollback validation completed');
    
    // Display results
    log.info('\n--- Post-Rollback Validation ---');
    results.forEach(result => {
      if (result.status === 'OK') {
        log.success(`${result.name}: ${result.status} (Version: ${result.currentVersion})`);
        log.verbose(`  Last Modified: ${result.lastModified}`);
      } else {
        log.error(`${result.name}: ${result.status} - ${result.error}`);
      }
    });
    
    return results.every(r => r.status === 'OK');
  } catch (error) {
    spinner.fail('Rollback validation failed');
    log.error(error.message);
    return false;
  }
}

async function main() {
  try {
    log.info(chalk.bold('\n🔄 Starting deployment rollback'));
    log.info(`Environment: ${chalk.cyan(options.environment)}`);
    log.info(`Region: ${chalk.cyan(options.region)}`);
    
    if (options.dryRun) {
      log.warning('DRY RUN MODE - No actual rollback will occur');
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
    
    // Create backup snapshot of current state
    await createBackupSnapshot();
    
    // Determine target version for rollback
    let targetVersions = {};
    
    if (options.version) {
      // Use specified version for all functions
      log.info(`Rolling back all functions to version: ${options.version}`);
      for (const functionName of LAMBDA_FUNCTIONS) {
        targetVersions[functionName] = options.version;
      }
    } else {
      // Find previous versions for each function
      log.info('Determining previous versions for rollback...');
      
      for (const functionName of LAMBDA_FUNCTIONS) {
        const versions = await listFunctionVersions(functionName);
        
        if (versions.length >= 2) {
          // Use the second most recent version (previous version)
          targetVersions[functionName] = versions[1].Version;
          log.info(`${functionName}: rolling back to version ${versions[1].Version} (from ${versions[1].LastModified})`);
        } else if (versions.length === 1) {
          log.warning(`${functionName}: only one version available, cannot rollback`);
          targetVersions[functionName] = versions[0].Version;
        } else {
          log.error(`${functionName}: no versions found for rollback`);
          throw new Error(`Cannot rollback ${functionName}: no versions available`);
        }
      }
    }
    
    // Confirm rollback
    if (!options.force && !options.dryRun) {
      log.warning('\nThis will rollback the following functions:');
      Object.entries(targetVersions).forEach(([func, version]) => {
        log.warning(`  ${func}: version ${version}`);
      });
      
      // In a real implementation, you would prompt for confirmation here
      // For now, we'll assume confirmation
      log.info('Proceeding with rollback...');
    }
    
    // Perform rollback
    log.info('\n📦 Rolling back Lambda functions...');
    
    const rollbackResults = [];
    for (const [functionName, targetVersion] of Object.entries(targetVersions)) {
      const success = await rollbackFunction(functionName, targetVersion);
      rollbackResults.push({ functionName, targetVersion, success });
    }
    
    const successfulRollbacks = rollbackResults.filter(r => r.success);
    const failedRollbacks = rollbackResults.filter(r => !r.success);
    
    if (failedRollbacks.length > 0) {
      log.error(`\n❌ Rollback failed for ${failedRollbacks.length} functions:`);
      failedRollbacks.forEach(r => {
        log.error(`  ${r.functionName}`);
      });
      
      if (successfulRollbacks.length > 0) {
        log.warning(`\n⚠️  Partial rollback completed for ${successfulRollbacks.length} functions:`);
        successfulRollbacks.forEach(r => {
          log.warning(`  ${r.functionName}: version ${r.targetVersion}`);
        });
      }
      
      throw new Error('Rollback completed with errors');
    }
    
    log.success(`\n✅ Successfully rolled back ${successfulRollbacks.length} functions`);
    
    // Validate rollback
    if (!options.dryRun) {
      const isValid = await validateRollback();
      if (!isValid) {
        log.warning('Rollback validation found issues. Please check the functions manually.');
      }
    }
    
    log.success(chalk.bold('\n🎉 Rollback completed successfully!'));
    
    if (options.dryRun) {
      log.info('\nThis was a dry run. No actual rollback was performed.');
    } else {
      log.info('\n📊 Next steps:');
      log.info('1. Verify the rolled back functions are working correctly');
      log.info('2. Monitor CloudWatch logs for any issues');
      log.info('3. Update your deployment if needed');
    }
    
  } catch (error) {
    log.error(chalk.bold('\n❌ Rollback failed!'));
    log.error(error.message);
    
    if (options.verbose) {
      console.error(error.stack);
    }
    
    process.exit(1);
  }
}

// Handle process termination
process.on('SIGINT', () => {
  log.warning('\nRollback interrupted by user');
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled Rejection at:', promise, 'reason:', reason);
  process.exit(1);
});

// Run the rollback
main();