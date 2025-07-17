#!/bin/bash

# CloudWatch MCP Server SAM Cleanup Script
# Remove deployed Lambda functions and CloudFormation stack

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
ENVIRONMENT="dev"
AWS_REGION="us-east-1"
STACK_NAME="cloudwatch-mcp-functions"
PROFILE=""
FORCE=false

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

Cleanup CloudWatch Lambda functions deployed via SAM

OPTIONS:
    -e, --environment ENV     Environment name (dev, staging, prod). Default: dev
    -r, --region REGION       AWS region. Default: us-east-1
    -s, --stack-name NAME     CloudFormation stack name. Default: cloudwatch-mcp-functions
    -p, --profile PROFILE     AWS profile to use
    -f, --force               Skip confirmation prompt
    -h, --help                Show this help message

EXAMPLES:
    $0
    $0 --environment prod --region us-west-2
    $0 --force

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
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
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

print_info "Cleanup configuration:"
print_info "  Environment: $ENVIRONMENT"
print_info "  AWS Region: $AWS_REGION"
print_info "  Stack Name: $STACK_NAME_FULL"
print_info "  AWS Profile: ${PROFILE:-default}"

# Check if stack exists
print_info "Checking if CloudFormation stack exists..."
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS >/dev/null 2>&1; then
    print_warn "CloudFormation stack $STACK_NAME_FULL does not exist."
    exit 0
fi

# Get stack outputs before deletion
print_info "Retrieving stack information..."
STACK_OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME_FULL" \
    --query 'Stacks[0].Outputs' \
    $AWS_CLI_OPTIONS 2>/dev/null || echo "[]")

LOGS_FUNCTION_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="CloudWatchLogsHandlerFunctionName") | .OutputValue' 2>/dev/null || echo "")
METRICS_FUNCTION_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="CloudWatchMetricsHandlerFunctionName") | .OutputValue' 2>/dev/null || echo "")

# Confirmation prompt
if [[ "$FORCE" != true ]]; then
    print_warn "This will delete the following resources:"
    print_warn "  - CloudFormation stack: $STACK_NAME_FULL"
    if [[ -n "$LOGS_FUNCTION_NAME" ]]; then
        print_warn "  - Lambda function: $LOGS_FUNCTION_NAME"
    fi
    if [[ -n "$METRICS_FUNCTION_NAME" ]]; then
        print_warn "  - Lambda function: $METRICS_FUNCTION_NAME"
    fi
    print_warn "  - IAM roles and policies created by the stack"
    print_warn "  - CloudWatch log groups"
    print_warn "  - API Gateway (if created)"
    print_warn ""
    
    echo -n "Are you sure you want to proceed? (yes/no): "
    read -r confirmation
    
    if [[ "$confirmation" != "yes" ]]; then
        print_info "Cleanup cancelled."
        exit 0
    fi
fi

# Change to SAM directory
cd "$SCRIPT_DIR"

print_info "Found CloudFormation stack: $STACK_NAME_FULL"

# Delete the SAM stack
print_info "Deleting SAM stack..."
sam delete \
    --stack-name "$STACK_NAME_FULL" \
    --no-prompts \
    $SAM_OPTIONS

print_info "SAM stack deletion completed successfully!"

# Verify deletion
print_info "Verifying stack deletion..."
if aws cloudformation describe-stacks --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS >/dev/null 2>&1; then
    print_warn "Stack still exists, waiting for deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS || {
        print_error "Stack deletion failed or timed out"
        print_info "You may need to check the AWS Console for stack deletion issues"
        exit 1
    }
fi

print_info "Cleanup completed successfully!"
print_info ""
print_info "The following resources have been removed:"
print_info "✓ CloudFormation stack: $STACK_NAME_FULL"
if [[ -n "$LOGS_FUNCTION_NAME" ]]; then
    print_info "✓ Lambda function: $LOGS_FUNCTION_NAME"
fi
if [[ -n "$METRICS_FUNCTION_NAME" ]]; then
    print_info "✓ Lambda function: $METRICS_FUNCTION_NAME"
fi
print_info "✓ IAM roles and policies"
print_info "✓ CloudWatch log groups"
print_info "✓ API Gateway resources"
print_info ""
print_info "Your AWS account has been cleaned up successfully."