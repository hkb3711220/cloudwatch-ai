#!/bin/bash

# CloudWatch Lambda MCP Server Deployment Script
# This script deploys Lambda functions for CloudWatch MCP Server integration

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"
LAMBDA_DIR="$PROJECT_ROOT/src/lambda_functions"

# Default values
ENVIRONMENT="dev"
AWS_REGION="us-east-1"
STACK_NAME="cloudwatch-mcp-lambda-functions"
DEPLOYMENT_BUCKET=""
PROFILE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy CloudWatch Lambda MCP Server functions to AWS

OPTIONS:
    -e, --environment ENV     Environment name (dev, staging, prod). Default: dev
    -r, --region REGION       AWS region. Default: us-east-1
    -s, --stack-name NAME     CloudFormation stack name. Default: cloudwatch-mcp-lambda-functions
    -b, --bucket BUCKET       S3 bucket for deployment artifacts (required)
    -p, --profile PROFILE     AWS profile to use
    -h, --help                Show this help message

EXAMPLES:
    $0 --bucket my-deployment-bucket
    $0 --environment prod --region us-west-2 --bucket my-deployment-bucket
    $0 --profile my-aws-profile --bucket my-deployment-bucket

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -b|--bucket)
            DEPLOYMENT_BUCKET="$2"
            shift 2
            ;;
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$DEPLOYMENT_BUCKET" ]]; then
    print_error "Deployment bucket is required. Use --bucket option."
    show_usage
    exit 1
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
    exit 1
fi

# Set AWS CLI options
AWS_CLI_OPTIONS="--region $AWS_REGION"
if [[ -n "$PROFILE" ]]; then
    AWS_CLI_OPTIONS="$AWS_CLI_OPTIONS --profile $PROFILE"
fi

print_info "Starting deployment with the following configuration:"
print_info "  Environment: $ENVIRONMENT"
print_info "  AWS Region: $AWS_REGION"
print_info "  Stack Name: $STACK_NAME-$ENVIRONMENT"
print_info "  Deployment Bucket: $DEPLOYMENT_BUCKET"
print_info "  AWS Profile: ${PROFILE:-default}"

# Create temporary directory for deployment artifacts
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

print_info "Created temporary directory: $TEMP_DIR"

# Function to create Lambda deployment package
create_lambda_package() {
    local function_name=$1
    local source_file=$2
    local package_file=$3
    
    print_info "Creating deployment package for $function_name..."
    
    # Create package directory
    local package_dir="$TEMP_DIR/$function_name"
    mkdir -p "$package_dir"
    
    # Copy source file
    cp "$source_file" "$package_dir/"
    
    # Install dependencies if requirements.txt exists
    if [[ -f "$DEPLOY_DIR/lambda/requirements.txt" ]]; then
        print_info "Installing dependencies for $function_name..."
        pip install -r "$DEPLOY_DIR/lambda/requirements.txt" -t "$package_dir" --quiet
    fi
    
    # Create ZIP package
    cd "$package_dir"
    zip -r "$package_file" . > /dev/null
    cd - > /dev/null
    
    print_info "Created deployment package: $package_file"
}

# Create deployment packages
print_info "Creating Lambda deployment packages..."

LOGS_PACKAGE="$TEMP_DIR/cloudwatch-logs-handler.zip"
METRICS_PACKAGE="$TEMP_DIR/cloudwatch-metrics-handler.zip"

create_lambda_package "cloudwatch-logs-handler" "$LAMBDA_DIR/cloudwatch_logs_handler.py" "$LOGS_PACKAGE"
create_lambda_package "cloudwatch-metrics-handler" "$LAMBDA_DIR/cloudwatch_metrics_handler.py" "$METRICS_PACKAGE"

# Upload packages to S3
print_info "Uploading deployment packages to S3..."

S3_PREFIX="cloudwatch-mcp-lambda/$ENVIRONMENT"
LOGS_S3_KEY="$S3_PREFIX/cloudwatch-logs-handler.zip"
METRICS_S3_KEY="$S3_PREFIX/cloudwatch-metrics-handler.zip"

aws s3 cp "$LOGS_PACKAGE" "s3://$DEPLOYMENT_BUCKET/$LOGS_S3_KEY" $AWS_CLI_OPTIONS
aws s3 cp "$METRICS_PACKAGE" "s3://$DEPLOYMENT_BUCKET/$METRICS_S3_KEY" $AWS_CLI_OPTIONS

print_info "Uploaded deployment packages to S3"

# Deploy CloudFormation stack
print_info "Deploying CloudFormation stack..."

STACK_NAME_FULL="$STACK_NAME-$ENVIRONMENT"

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS >/dev/null 2>&1; then
    print_info "Stack $STACK_NAME_FULL exists, updating..."
    STACK_OPERATION="update-stack"
else
    print_info "Stack $STACK_NAME_FULL does not exist, creating..."
    STACK_OPERATION="create-stack"
fi

# Deploy/update stack
aws cloudformation $STACK_OPERATION \
    --stack-name "$STACK_NAME_FULL" \
    --template-body "file://$DEPLOY_DIR/cloudformation/lambda-functions.yaml" \
    --parameters \
        ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
    --capabilities CAPABILITY_NAMED_IAM \
    $AWS_CLI_OPTIONS

print_info "CloudFormation stack operation initiated"

# Wait for stack operation to complete
print_info "Waiting for stack operation to complete..."
if [[ "$STACK_OPERATION" == "create-stack" ]]; then
    aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS
else
    aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS
fi

# Update Lambda function code
print_info "Updating Lambda function code..."

LOGS_FUNCTION_NAME="cloudwatch-logs-handler-$ENVIRONMENT"
METRICS_FUNCTION_NAME="cloudwatch-metrics-handler-$ENVIRONMENT"

aws lambda update-function-code \
    --function-name "$LOGS_FUNCTION_NAME" \
    --s3-bucket "$DEPLOYMENT_BUCKET" \
    --s3-key "$LOGS_S3_KEY" \
    $AWS_CLI_OPTIONS > /dev/null

aws lambda update-function-code \
    --function-name "$METRICS_FUNCTION_NAME" \
    --s3-bucket "$DEPLOYMENT_BUCKET" \
    --s3-key "$METRICS_S3_KEY" \
    $AWS_CLI_OPTIONS > /dev/null

print_info "Lambda function code updated"

# Get stack outputs
print_info "Retrieving stack outputs..."

STACK_OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME_FULL" \
    --query 'Stacks[0].Outputs' \
    $AWS_CLI_OPTIONS)

echo "$STACK_OUTPUTS" | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'

# Test Lambda functions
print_info "Testing Lambda functions..."

# Test logs handler
LOGS_TEST_PAYLOAD='{"operation": "test_connection", "parameters": {}}'
LOGS_TEST_RESULT=$(aws lambda invoke \
    --function-name "$LOGS_FUNCTION_NAME" \
    --payload "$LOGS_TEST_PAYLOAD" \
    --output text \
    --query 'StatusCode' \
    $AWS_CLI_OPTIONS \
    /dev/null)

if [[ "$LOGS_TEST_RESULT" == "200" ]]; then
    print_info "✓ CloudWatch Logs handler test passed"
else
    print_warn "✗ CloudWatch Logs handler test failed (Status: $LOGS_TEST_RESULT)"
fi

# Test metrics handler
METRICS_TEST_PAYLOAD='{"operation": "test_connection", "parameters": {}}'
METRICS_TEST_RESULT=$(aws lambda invoke \
    --function-name "$METRICS_FUNCTION_NAME" \
    --payload "$METRICS_TEST_PAYLOAD" \
    --output text \
    --query 'StatusCode' \
    $AWS_CLI_OPTIONS \
    /dev/null)

if [[ "$METRICS_TEST_RESULT" == "200" ]]; then
    print_info "✓ CloudWatch Metrics handler test passed"
else
    print_warn "✗ CloudWatch Metrics handler test failed (Status: $METRICS_TEST_RESULT)"
fi

print_info "Deployment completed successfully!"
print_info ""
print_info "Next steps:"
print_info "1. Update your MCP server configuration with the Lambda function names:"
print_info "   - Logs function: $LOGS_FUNCTION_NAME"
print_info "   - Metrics function: $METRICS_FUNCTION_NAME"
print_info "2. Use the Lambda MCP server with these function names"
print_info "3. Configure your MCP client to use the Lambda-based server"

# Save deployment information
DEPLOYMENT_INFO="$TEMP_DIR/deployment-info.json"
cat > "$DEPLOYMENT_INFO" << EOF
{
  "deployment_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environment": "$ENVIRONMENT",
  "aws_region": "$AWS_REGION",
  "stack_name": "$STACK_NAME_FULL",
  "deployment_bucket": "$DEPLOYMENT_BUCKET",
  "lambda_functions": {
    "logs_handler": "$LOGS_FUNCTION_NAME",
    "metrics_handler": "$METRICS_FUNCTION_NAME"
  },
  "s3_artifacts": {
    "logs_handler": "s3://$DEPLOYMENT_BUCKET/$LOGS_S3_KEY",
    "metrics_handler": "s3://$DEPLOYMENT_BUCKET/$METRICS_S3_KEY"
  }
}
EOF

print_info "Deployment information saved to: $DEPLOYMENT_INFO"