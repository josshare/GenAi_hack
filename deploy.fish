#!/usr/bin/env fish


# Compatible with Fish Shell on macOS

set -g SCRIPT_DIR (dirname (realpath (status --current-filename)))
set -g PROJECT_ROOT $SCRIPT_DIR
set -g CONFIG_DIR "$PROJECT_ROOT/config"
set -g INFRA_DIR "$PROJECT_ROOT/infrastructure"
set -g SRC_DIR "$PROJECT_ROOT/src"
set -g SCRIPTS_DIR "$PROJECT_ROOT/scripts"

# Color codes for output
set -g RED '\033[0;31m'
set -g GREEN '\033[0;32m'
set -g YELLOW '\033[1;33m'
set -g BLUE '\033[0;34m'
set -g NC '\033[0m' # No Color

# Deployment configuration
set -g AWS_PROFILE ""
set -g AWS_REGION ""
set -g ENVIRONMENT "dev"
set -g DRY_RUN false
set -g FORCE false
set -g SKIP_TESTS false
set -g SKIP_INFRA false

function print_usage
    echo "Usage: ./deploy.fish [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  init          Initialize deployment (first time setup)"
    echo "  deploy        Deploy application and infrastructure"
    echo "  update        Update existing deployment"
    echo "  rollback      Rollback to previous version"
    echo "  status        Check deployment status"
    echo "  destroy       Destroy all resources (use with caution)"
    echo ""
    echo "Options:"
    echo "  -p, --profile PROFILE    AWS profile to use"
    echo "  -r, --region REGION      AWS region (default: us-east-1)"
    echo "  -e, --env ENVIRONMENT    Environment (dev|staging|prod, default: dev)"
    echo "  -d, --dry-run            Show what would be done without executing"
    echo "  -f, --force              Force deployment without confirmation"
    echo "  --skip-tests             Skip running tests"
    echo "  --skip-infra             Skip infrastructure deployment"
    echo "  -h, --help               Show this help message"
end

function log_info
    echo -e "$BLUE[INFO]$NC" $argv
end

function log_success
    echo -e "$GREEN[SUCCESS]$NC" $argv
end

function log_warning
    echo -e "$YELLOW[WARNING]$NC" $argv
end

function log_error
echo -e "$RED[ERROR]$NC" "$argv"
end

function check_dependencies
    log_info "Checking dependencies..."
    
    # Check required tools
    set -l required_tools python3 pip npm terraform aws
    for tool in $required_tools
        if not command -v $tool >/dev/null
            log_error "Required tool '$tool' not found. Please install it first."
            return 1
        end
    end
    
    # Check Python version
    set python_version (python3 --version | cut -d' ' -f2)
    set major_version (echo $python_version | cut -d'.' -f1)
    set minor_version (echo $python_version | cut -d'.' -f2)
    
    if test $major_version -lt 3; or test $major_version -eq 3 -a $minor_version -lt 9
        log_error "Python 3.9 or higher is required. Found: $python_version"
        return 1
    end
    
    # Check AWS CLI configuration
    if test -z "$AWS_PROFILE"
        if not aws sts get-caller-identity >/dev/null 2>&1
            log_error "AWS CLI not configured. Please run 'aws configure' or set AWS_PROFILE."
            return 1
        end
    else
        if not aws sts get-caller-identity --profile $AWS_PROFILE >/dev/null 2>&1
            log_error "AWS profile '$AWS_PROFILE' not found or not configured."
            return 1
        end
    end
    
    log_success "All dependencies check passed."
    return 0
end

function setup_environment
    log_info "Setting up environment for $ENVIRONMENT..."
    
    # Set AWS profile if specified
    if test -n "$AWS_PROFILE"
        set -gx AWS_PROFILE $AWS_PROFILE
        log_info "Using AWS profile: $AWS_PROFILE"
    end
    
    # Set AWS region
    if test -z "$AWS_REGION"
        set AWS_REGION "us-east-1"
    end
    set -gx AWS_DEFAULT_REGION $AWS_REGION
    log_info "Using AWS region: $AWS_REGION"
    
    # Check if config files exist
    if not test -f "$CONFIG_DIR/config.yaml"
        if test -f "$CONFIG_DIR/config.example.yaml"
            log_warning "config.yaml not found. Copying from example..."
            cp "$CONFIG_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
            log_warning "Please edit $CONFIG_DIR/config.yaml with your settings before proceeding."
            return 1
        else
            log_error "No configuration files found. Please create config.yaml."
            return 1
        end
    end
    
    # Check if .env file exists
    if not test -f "$PROJECT_ROOT/.env"
        if test -f "$PROJECT_ROOT/env.example"
            log_warning ".env not found. Copying from example..."
            cp "$PROJECT_ROOT/env.example" "$PROJECT_ROOT/.env"
            log_warning "Please edit .env with your settings before proceeding."
            return 1
        else
            log_error "No environment file found. Please create .env."
            return 1
        end
    end
    
    log_success "Environment setup completed."
    return 0
end

function install_dependencies
    log_info "Installing dependencies..."
    
    # Install Python dependencies
    if test -f "$PROJECT_ROOT/requirements.txt"
        log_info "Installing Python dependencies..."
        pip3 install -r "$PROJECT_ROOT/requirements.txt"
        if test $status -ne 0
            log_error "Failed to install Python dependencies."
            return 1
        end
    end
    
    # Install Node.js dependencies
    if test -f "$PROJECT_ROOT/package.json"
        log_info "Installing Node.js dependencies..."
        npm install
        if test $status -ne 0
            log_error "Failed to install Node.js dependencies."
            return 1
        end
    end
    
    log_success "Dependencies installed successfully."
    return 0
end

function run_tests
    if test "$SKIP_TESTS" = "true"
        log_info "Skipping tests as requested."
        return 0
    end
    
    log_info "Running tests..."
    
    # Run Python tests
    if test -d "$PROJECT_ROOT/tests"
        log_info "Running Python tests..."
        pytest "$PROJECT_ROOT/tests/" -v
        if test $status -ne 0
            log_error "Python tests failed."
            return 1
        end
    end
    
    # Run linting
    log_info "Running code linting..."
    if test -d "$SRC_DIR"
        flake8 "$SRC_DIR/" "$PROJECT_ROOT/tests/"
        if test $status -ne 0
            log_warning "Linting issues found, but continuing deployment."
        end
    end
    
    # Run type checking
    log_info "Running type checking..."
    if test -d "$SRC_DIR"
        mypy "$SRC_DIR/"
        if test $status -ne 0
            log_warning "Type checking issues found, but continuing deployment."
        end
    end
    
    log_success "Tests completed successfully."
    return 0
end

function deploy_infrastructure
    if test "$SKIP_INFRA" = "true"
        log_info "Skipping infrastructure deployment as requested."
        return 0
    end
    
    log_info "Deploying infrastructure with Terraform..."
    
    if not test -d "$INFRA_DIR"
        log_error "Infrastructure directory not found: $INFRA_DIR"
        return 1
    end
    
    # Change to infrastructure directory
    pushd "$INFRA_DIR"
    
    # Initialize Terraform
    log_info "Initializing Terraform..."
    terraform init
    if test $status -ne 0
        log_error "Terraform initialization failed."
        popd
        return 1
    end
    
    # Plan infrastructure changes
    log_info "Planning infrastructure changes..."
    if test "$DRY_RUN" = "true"
        terraform plan -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION"
        popd
        return 0
    else
        terraform plan -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION" -out=tfplan
        if test $status -ne 0
            log_error "Terraform planning failed."
            popd
            return 1
        end
    end
    
    # Apply infrastructure changes
    if test "$FORCE" != "true"
        echo -n "Apply infrastructure changes? [y/N]: "
        read -l confirm
        if test "$confirm" != "y" -a "$confirm" != "Y"
            log_info "Infrastructure deployment cancelled."
            popd
            return 1
        end
    end
    
    log_info "Applying infrastructure changes..."
    terraform apply tfplan
    if test $status -ne 0
        log_error "Terraform apply failed."
        popd
        return 1
    end
    
    # Get outputs for use in application deployment
    terraform output -json > ../terraform-outputs.json
    
    popd
    log_success "Infrastructure deployment completed."
    return 0
end

function deploy_application
    log_info "Deploying application..."
    
    # Use Node.js deployment script if available
    if test -f "$SCRIPTS_DIR/deploy.js"
        log_info "Using Node.js deployment script..."
        node "$SCRIPTS_DIR/deploy.js" --environment="$ENVIRONMENT" --region="$AWS_REGION"
        if test $status -ne 0
            log_error "Node.js deployment script failed."
            return 1
        end
    else
        log_info "Node.js deployment script not found. Using direct AWS CLI deployment..."
        
        # Package and deploy Lambda functions
        if test -d "$SRC_DIR/functions"
            for func_dir in "$SRC_DIR/functions"/*
                if test -d "$func_dir"
                    set func_name (basename "$func_dir")
                    log_info "Deploying function: $func_name"
                    
                    # Create deployment package
                    pushd "$func_dir"
                    zip -r "../$func_name.zip" . -x "*.pyc" "__pycache__/*"
                    
                    # Deploy to AWS Lambda
                    aws lambda update-function-code \
                        --function-name "$ENVIRONMENT-ai-agent-$func_name" \
                        --zip-file "fileb://../$func_name.zip"
                    
                    popd
                end
            end
        end
    end
    
    log_success "Application deployment completed."
    return 0
end

function get_deployment_status
    log_info "Checking deployment status..."
    
    # Check Lambda functions
    log_info "Lambda functions:"
    aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `'$ENVIRONMENT'-ai-agent`)].{Name:FunctionName,Runtime:Runtime,LastModified:LastModified}' --output table
    
    # Check DynamoDB tables
    log_info "DynamoDB tables:"
    aws dynamodb list-tables --query 'TableNames[?starts_with(@, `'$ENVIRONMENT'-ai-agent`)]' --output table
    
    # Check CloudWatch alarms
    log_info "CloudWatch alarms:"
    aws cloudwatch describe-alarms --alarm-name-prefix "$ENVIRONMENT-ai-agent" --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}' --output table
end

function rollback_deployment
    log_info "Rolling back deployment..."
    log_warning "This will rollback to the previous version."
    
    if test "$FORCE" != "true"
        echo -n "Are you sure you want to rollback? [y/N]: "
        read -l confirm
        if test "$confirm" != "y" -a "$confirm" != "Y"
            log_info "Rollback cancelled."
            return 1
        end
    end
    
    # Use Node.js rollback if available
    if test -f "$SCRIPTS_DIR/rollback.js"
        node "$SCRIPTS_DIR/rollback.js" --environment="$ENVIRONMENT"
    else
        log_warning "Automatic rollback not implemented. Please rollback manually using AWS console or CLI."
        return 1
    end
    
    log_success "Rollback completed."
    return 0
end

function destroy_deployment
    log_warning "This will DESTROY ALL RESOURCES for environment: $ENVIRONMENT"
    log_warning "This action cannot be undone!"
    
    if test "$FORCE" != "true"
        echo -n "Are you absolutely sure? Type 'DESTROY' to confirm: "
        read -l confirm
        if test "$confirm" != "DESTROY"
            log_info "Destruction cancelled."
            return 1
        end
    end
    
    log_info "Destroying deployment..."
    
    # Destroy infrastructure with Terraform
    if test -d "$INFRA_DIR"
        pushd "$INFRA_DIR"
        terraform destroy -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION" -auto-approve
        popd
    end
    
    log_success "Deployment destroyed."
    return 0
end

function init_deployment
    log_info "Initializing deployment setup..."
    
    check_dependencies
    if test $status -ne 0
        return 1
    end
    
    setup_environment
    if test $status -ne 0
        return 1
    end
    
    install_dependencies
    if test $status -ne 0
        return 1
    end
    
    log_success "Initialization completed successfully."
    log_info "Next steps:"
    log_info "1. Edit config/config.yaml with your specific settings"
    log_info "2. Edit .env with your environment variables"
    log_info "3. Run './deploy.fish deploy' to deploy the application"
end

function full_deployment
    log_info "Starting full deployment for environment: $ENVIRONMENT"
    
    check_dependencies
    if test $status -ne 0
        return 1
    end
    
    setup_environment
    if test $status -ne 0
        return 1
    end
    
    install_dependencies
    if test $status -ne 0
        return 1
    end
    
    run_tests
    if test $status -ne 0
        return 1
    end
    
    deploy_infrastructure
    if test $status -ne 0
        return 1
    end
    
    deploy_application
    if test $status -ne 0
        return 1
    end
    
    get_deployment_status
    
    log_success "Deployment completed successfully!"
    return 0
end

function update_deployment
    log_info "Starting deployment update for environment: $ENVIRONMENT"
    
    check_dependencies
    if test $status -ne 0
        return 1
    end
    
    setup_environment
    if test $status -ne 0
        return 1
    end
    
    run_tests
    if test $status -ne 0
        return 1
    end
    
    deploy_application
    if test $status -ne 0
        return 1
    end
    
    get_deployment_status
    
    log_success "Update completed successfully!"
    return 0
end

# Parse command line arguments
set -l cmd ""
while test (count $argv) -gt 0
    switch $argv[1]
        case -p --profile
            set AWS_PROFILE $argv[2]
            set argv $argv[3..]
        case -r --region
            set AWS_REGION $argv[2]
            set argv $argv[3..]
        case -e --env
            set ENVIRONMENT $argv[2]
            set argv $argv[3..]
        case -d --dry-run
            set DRY_RUN true
            set argv $argv[2..]
        case -f --force
            set FORCE true
            set argv $argv[2..]
        case --skip-tests
            set SKIP_TESTS true
            set argv $argv[2..]
        case --skip-infra
            set SKIP_INFRA true
            set argv $argv[2..]
        case -h --help
            print_usage
            exit 0
        case init deploy update rollback status destroy
            set cmd $argv[1]
            set argv $argv[2..]
        case -*
            log_error "Unknown option: $argv[1]"
            print_usage
            exit 1
        case '*'
            if test -z "$cmd"
                set cmd $argv[1]
            else
                log_error "Unknown argument: $argv[1]"
                print_usage
                exit 1
            end
            set argv $argv[2..]
    end
end

# Execute command
switch $cmd
    case init
        init_deployment
    case deploy
        full_deployment
    case update
        update_deployment
    case rollback
        rollback_deployment
    case status
        get_deployment_status
    case destroy
        destroy_deployment
    case ''
        log_error "No command specified."
        print_usage
        exit 1
    case '*'
        log_error "Unknown command: $cmd"
        print_usage
        exit 1
end

exit $status