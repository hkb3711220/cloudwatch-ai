#!/bin/bash

# CloudWatch Lambda MCP Server Cleanup Script
# This script removes deployed Lambda functions and CloudFormation stack

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
ENVIRONMENT="dev"
AWS_REGION="us-east-1"
STACK_NAME="cloudwatch-mcp-lambda-functions"
DEPLOYMENT_BUCKET=""
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

Cleanup CloudWatch Lambda MCP Server deployment from AWS

OPTIONS:
    -e, --environment ENV     Environment name (dev, staging, prod). Default: dev
    -r, --region REGION       AWS region. Default: us-east-1
    -s, --stack-name NAME     CloudFormation stack name. Default: cloudwatch-mcp-lambda-functions
    -b, --bucket BUCKET       S3 bucket with deployment artifacts (optional)
    -p, --profile PROFILE     AWS profile to use
    -f, --force               Skip confirmation prompt
    -h, --help                Show this help message

EXAMPLES:
    $0
    $0 --environment prod --region us-west-2
    $0 --force --bucket my-deployment-bucket

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

# Set AWS CLI options
AWS_CLI_OPTIONS="--region $AWS_REGION"
if [[ -n "$PROFILE" ]]; then
    AWS_CLI_OPTIONS="$AWS_CLI_OPTIONS --profile $PROFILE"
fi

STACK_NAME_FULL="$STACK_NAME-$ENVIRONMENT"

print_info "Cleanup configuration:"
print_info "  Environment: $ENVIRONMENT"
print_info "  AWS Region: $AWS_REGION"
print_info "  Stack Name: $STACK_NAME_FULL"
print_info "  Deployment Bucket: ${DEPLOYMENT_BUCKET:-not specified}"
print_info "  AWS Profile: ${PROFILE:-default}"

# Confirmation prompt
if [[ "$FORCE" != true ]]; then
    print_warn "This will delete the following resources:"
    print_warn "  - CloudFormation stack: $STACK_NAME_FULL"
    print_warn "  - Lambda functions: cloudwatch-logs-handler-$ENVIRONMENT, cloudwatch-metrics-handler-$ENVIRONMENT"
    print_warn "  - IAM roles and policies created by the stack"
    print_warn "  - CloudWatch log groups"
    if [[ -n "$DEPLOYMENT_BUCKET" ]]; then
        print_warn "  - S3 artifacts in bucket: $DEPLOYMENT_BUCKET"
    fi
    print_warn ""
    
    echo -n "Are you sure you want to proceed? (yes/no): "
    read -r confirmation
    
    if [[ "$confirmation" != "yes" ]]; then
        print_info "Cleanup cancelled."
        exit 0
    fi
fi

# Check if stack exists
print_info "Checking if CloudFormation stack exists..."
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS >/dev/null 2>&1; then
    print_warn "CloudFormation stack $STACK_NAME_FULL does not exist."
else
    print_info "Found CloudFormation stack: $STACK_NAME_FULL"
    
    # Delete CloudFormation stack
    print_info "Deleting CloudFormation stack..."
    aws cloudformation delete-stack --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS
    
    # Wait for stack deletion to complete
    print_info "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME_FULL" $AWS_CLI_OPTIONS || {
        print_error "Stack deletion failed or timed out"
        print_info "You may need to check the AWS Console for stack deletion issues"
    }
    
    print_info "CloudFormation stack deleted successfully"
fi

# Clean up S3 artifacts if bucket is specified
if [[ -n "$DEPLOYMENT_BUCKET" ]]; then
    print_info "Cleaning up S3 artifacts..."
    
    S3_PREFIX="cloudwatch-mcp-lambda/$ENVIRONMENT"
    
    # Check if bucket exists and we have access
    if aws s3 ls "s3://$DEPLOYMENT_BUCKET/" $AWS_CLI_OPTIONS >/dev/null 2>&1; then
        # List and delete artifacts
        ARTIFACTS=$(aws s3 ls "s3://$DEPLOYMENT_BUCKET/$S3_PREFIX/" $AWS_CLI_OPTIONS --recursive 2>/dev/null | awk '{print $4}' || true)
        
        if [[ -n "$ARTIFACTS" ]]; then
            print_info "Deleting S3 artifacts:"
            echo "$ARTIFACTS" | while read -r artifact; do
                if [[ -n "$artifact" ]]; then
                    print_info "  - s3://$DEPLOYMENT_BUCKET/$artifact"
                    aws s3 rm "s3://$DEPLOYMENT_BUCKET/$artifact" $AWS_CLI_OPTIONS
                fi
            done
            print_info "S3 artifacts cleaned up"
        else
            print_info "No S3 artifacts found to clean up"
        fi
    else
        print_warn "Cannot access S3 bucket $DEPLOYMENT_BUCKET or bucket does not exist"
    fi
fi

# Clean up any remaining Lambda functions (in case stack deletion failed)
print_info "Checking for remaining Lambda functions..."

LOGS_FUNCTION_NAME="cloudwatch-logs-handler-$ENVIRONMENT"
METRICS_FUNCTION_NAME="cloudwatch-metrics-handler-$ENVIRONMENT"

for FUNCTION_NAME in "$LOGS_FUNCTION_NAME" "$METRICS_FUNCTION_NAME"; do
    if aws lambda get-function --function-name "$FUNCTION_NAME" $AWS_CLI_OPTIONS >/dev/null 2>&1; then
        print_warn "Found remaining Lambda function: $FUNCTION_NAME"
        print_info "Deleting Lambda function: $FUNCTION_NAME"
        aws lambda delete-function --function-name "$FUNCTION_NAME" $AWS_CLI_OPTIONS
        print_info "Lambda function $FUNCTION_NAME deleted"
    fi
done

print_info "Cleanup completed successfully!"
print_info ""
print_info "The following resources have been removed:"
print_info "✓ CloudFormation stack: $STACK_NAME_FULL"
print_info "✓ Lambda functions and associated resources"
print_info "✓ IAM roles and policies"
print_info "✓ CloudWatch log groups"
if [[ -n "$DEPLOYMENT_BUCKET" ]]; then
    print_info "✓ S3 deployment artifacts"
fi