#!/bin/bash

# CloudWatch MCP Server SAM Deployment Script
# Deploy Lambda functions for AWS Serverless MCP Server integration

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT="dev"
AWS_REGION="us-east-1"
STACK_NAME="cloudwatch-mcp-functions"
PROFILE=""
S3_BUCKET=""

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

Deploy CloudWatch Lambda functions for AWS Serverless MCP Server integration using SAM

OPTIONS:
    -e, --environment ENV     Environment name (dev, staging, prod). Default: dev
    -r, --region REGION       AWS region. Default: us-east-1
    -s, --stack-name NAME     CloudFormation stack name. Default: cloudwatch-mcp-functions
    -b, --bucket BUCKET       S3 bucket for SAM deployment artifacts (required)
    -p, --profile PROFILE     AWS profile to use
    -h, --help                Show this help message

EXAMPLES:
    $0 --bucket my-sam-deployment-bucket
    $0 --environment prod --region us-west-2 --bucket my-bucket
    $0 --profile my-aws-profile --bucket my-bucket

PREREQUISITES:
    - AWS SAM CLI installed (sam command available)
    - AWS CLI configured with appropriate permissions
    - S3 bucket for deployment artifacts

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
            S3_BUCKET="$2"
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
if [[ -z "$S3_BUCKET" ]]; then
    print_error "S3 bucket is required for SAM deployment. Use --bucket option."
    show_usage
    exit 1
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    print_error "AWS SAM CLI is not installed. Please install it first:"
    print_error "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

# Set AWS CLI options
AWS_CLI_OPTIONS="--region $AWS_REGION"
SAM_OPTIONS="--region $AWS_REGION"
if [[ -n "$PROFILE" ]]; then
    AWS_CLI_OPTIONS="$AWS_CLI_OPTIONS --profile $PROFILE"
    SAM_OPTIONS="$SAM_OPTIONS --profile $PROFILE"
fi

STACK_NAME_FULL="$STACK_NAME-$ENVIRONMENT"

print_info "Starting SAM deployment with the following configuration:"
print_info "  Environment: $ENVIRONMENT"
print_info "  AWS Region: $AWS_REGION"
print_info "  Stack Name: $STACK_NAME_FULL"
print_info "  S3 Bucket: $S3_BUCKET"
print_info "  AWS Profile: ${PROFILE:-default}"

# Change to SAM directory
cd "$SCRIPT_DIR"

# Validate SAM template
print_info "Validating SAM template..."
sam validate $SAM_OPTIONS

# Build SAM application
print_info "Building SAM application..."
sam build $SAM_OPTIONS

# Deploy SAM application
print_info "Deploying SAM application..."
sam deploy \
    --stack-name "$STACK_NAME_FULL" \
    --s3-bucket "$S3_BUCKET" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    $SAM_OPTIONS

print_info "SAM deployment completed successfully!"

# Get stack outputs
print_info "Retrieving stack outputs..."
STACK_OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME_FULL" \
    --query 'Stacks[0].Outputs' \
    $AWS_CLI_OPTIONS)

echo "$STACK_OUTPUTS" | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'

# Extract key information for AWS Serverless MCP Server configuration
LOGS_FUNCTION_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="CloudWatchLogsHandlerFunctionName") | .OutputValue')
METRICS_FUNCTION_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="CloudWatchMetricsHandlerFunctionName") | .OutputValue')
API_URL=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiGatewayUrl") | .OutputValue')

# Test Lambda functions
print_info "Testing deployed Lambda functions..."

# Test logs handler
if [[ -n "$LOGS_FUNCTION_NAME" ]]; then
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
fi

# Test metrics handler
if [[ -n "$METRICS_FUNCTION_NAME" ]]; then
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
fi

print_info ""
print_info "🎉 Deployment completed successfully!"
print_info ""
print_info "AWS Serverless MCP Server Configuration:"
print_info "========================================"
print_info ""
print_info "Add the following to your MCP client configuration:"
print_info ""

# Generate MCP configuration snippet
cat << EOF
{
  "mcpServers": {
    "aws-serverless-cloudwatch": {
      "command": "uvx",
      "args": [
        "awslabs.aws-serverless-mcp-server@latest",
        "--allow-write",
        "--allow-sensitive-data-access"
      ],
      "env": {
        "AWS_PROFILE": "${PROFILE:-default}",
        "AWS_REGION": "$AWS_REGION",
        "CLOUDWATCH_LOGS_FUNCTION": "$LOGS_FUNCTION_NAME",
        "CLOUDWATCH_METRICS_FUNCTION": "$METRICS_FUNCTION_NAME"
      }
    }
  }
}
EOF

print_info ""
print_info "Lambda Functions Deployed:"
print_info "  - Logs Handler: $LOGS_FUNCTION_NAME"
print_info "  - Metrics Handler: $METRICS_FUNCTION_NAME"
if [[ -n "$API_URL" ]]; then
    print_info "  - API Gateway URL: $API_URL"
fi
print_info ""
print_info "You can now use these Lambda functions with the AWS Serverless MCP Server!"
print_info ""
print_info "For more information, see:"
print_info "  - Project documentation: docs/AWS_SERVERLESS_MCP_SERVER.md"
print_info "  - Project documentation: docs/LAMBDA_MCP_SERVER.md"