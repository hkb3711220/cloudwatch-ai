# CloudWatch Integration with AWS Serverless MCP Server

This document describes how to integrate CloudWatch logs and metrics investigation with the **AWS Serverless MCP Server**. This approach leverages AWS's official serverless MCP server infrastructure, eliminating the need for local MCP server processes.

## Architecture Overview

```
MCP Client <--> AWS Serverless MCP Server <--> Lambda Functions <--> CloudWatch Services
                                                    |
                                                    +--> CloudWatch Logs
                                                    +--> CloudWatch Metrics
```

### Key Benefits

- **No Local Server**: Uses AWS's hosted MCP server infrastructure
- **Serverless**: Automatic scaling with AWS Lambda
- **Cost-Effective**: Pay-per-invocation pricing model
- **Secure**: Function-level IAM isolation and AWS security
- **Managed**: No infrastructure to maintain

## Components

### 1. AWS Serverless MCP Server
- Official AWS MCP server that runs in AWS infrastructure
- Handles MCP protocol communication with clients
- Invokes your Lambda functions for CloudWatch operations
- Installed via `uvx` package manager

### 2. CloudWatch Lambda Functions
- **CloudWatch Logs Handler** - 6 log operations
- **CloudWatch Metrics Handler** - 6 metrics operations
- Deployed using AWS SAM (Serverless Application Model)

### 3. API Gateway (Optional)
- Provides HTTP endpoints for Lambda functions
- Enables additional integration patterns if needed

## Prerequisites

### Software Requirements
- **AWS SAM CLI** - For deployment and management
- **AWS CLI** - For AWS service interaction
- **uvx** - For installing AWS Serverless MCP Server
- **jq** - For JSON processing in scripts

### AWS Requirements
- AWS account with appropriate permissions
- IAM permissions for Lambda, CloudWatch, and CloudFormation
- S3 bucket for SAM deployment artifacts

### Installation Commands
```bash
# Install AWS SAM CLI
brew install aws-sam-cli  # macOS
# or follow: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

# Install uvx (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installations
sam --version
uvx --version
aws --version
jq --version
```

## Deployment

### 1. Deploy Lambda Functions

```bash
# Navigate to SAM deployment directory
cd deploy/sam

# Deploy with required S3 bucket
./deploy.sh --bucket your-sam-deployment-bucket

# Deploy to specific environment/region
./deploy.sh \
  --environment prod \
  --region us-west-2 \
  --bucket your-bucket \
  --profile your-aws-profile
```

The deployment script will:
- Validate and build the SAM application
- Deploy Lambda functions with proper IAM roles
- Create CloudWatch log groups
- Test function connectivity
- Provide MCP client configuration

### 2. Configure MCP Client

After deployment, add the following to your MCP client configuration:

#### Cursor IDE (`~/.cursor/mcp.json`)
```json
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
        "AWS_PROFILE": "your-profile",
        "AWS_REGION": "us-east-1",
        "CLOUDWATCH_LOGS_FUNCTION": "cloudwatch-logs-handler-dev",
        "CLOUDWATCH_METRICS_FUNCTION": "cloudwatch-metrics-handler-dev"
      }
    }
  }
}
```

#### Claude Desktop (`claude_desktop_config.json`)
```json
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
        "AWS_PROFILE": "your-profile",
        "AWS_REGION": "us-east-1",
        "CLOUDWATCH_LOGS_FUNCTION": "cloudwatch-logs-handler-dev",
        "CLOUDWATCH_METRICS_FUNCTION": "cloudwatch-metrics-handler-dev"
      }
    }
  }
}
```

## Available Tools

The AWS Serverless MCP Server will automatically discover and expose your Lambda functions as MCP tools:

### CloudWatch Logs Tools (6)
| Tool | Lambda Operation | Description |
|------|------------------|-------------|
| `investigate_cloudwatch_logs` | `investigate_logs` | Detailed log investigation with pattern analysis |
| `list_available_log_groups` | `list_log_groups` | List and filter log groups |
| `analyze_log_patterns` | `analyze_patterns` | Pattern analysis and trend detection |
| `get_log_streams` | `get_log_streams` | Stream enumeration for log groups |
| `get_recent_events` | `get_recent_events` | Recent log event retrieval |
| `test_logs_connection` | `test_connection` | CloudWatch Logs connectivity testing |

### CloudWatch Metrics Tools (6)
| Tool | Lambda Operation | Description |
|------|------------------|-------------|
| `investigate_cloudwatch_metrics` | `investigate_metrics` | Comprehensive metrics analysis |
| `list_available_metrics` | `list_metrics` | Available metrics discovery |
| `get_metric_statistics` | `get_metric_statistics` | Detailed metric statistics |
| `list_metric_namespaces` | `list_namespaces` | Available namespace enumeration |
| `analyze_metric_trends` | `analyze_metric_trends` | Trend analysis over time |
| `test_metrics_connection` | `test_connection` | CloudWatch Metrics connectivity testing |

## Usage Examples

### CloudWatch Logs Investigation
```text
過去24時間のLambda関数エラーを調査してください。
ロググループ: /aws/lambda/my-function
```

### CloudWatch Metrics Analysis
```text
EC2インスタンス i-1234567890abcdef0 の過去1時間のCPU使用率を調査してください。
```

### Combined Investigation
```text
API Gatewayでエラー率が上昇しています。
メトリクスとログの両方を調査して根本原因を特定してください。
```

## Configuration Details

### Environment Variables

The AWS Serverless MCP Server uses these environment variables:

```bash
# Required: AWS Authentication
AWS_PROFILE=your-profile
AWS_REGION=us-east-1

# Required: Lambda Function Names (set by deployment)
CLOUDWATCH_LOGS_FUNCTION=cloudwatch-logs-handler-dev
CLOUDWATCH_METRICS_FUNCTION=cloudwatch-metrics-handler-dev

# Optional: Additional Configuration
AWS_ACCESS_KEY_ID=your-key-id        # Alternative to profile
AWS_SECRET_ACCESS_KEY=your-secret    # Alternative to profile
```

### Lambda Function Naming Convention

The deployment follows this naming pattern:
- **Development**: `cloudwatch-logs-handler-dev`, `cloudwatch-metrics-handler-dev`
- **Staging**: `cloudwatch-logs-handler-staging`, `cloudwatch-metrics-handler-staging`
- **Production**: `cloudwatch-logs-handler-prod`, `cloudwatch-metrics-handler-prod`

## Troubleshooting

### Common Issues

1. **AWS Serverless MCP Server Not Found**
   ```
   Error: command not found: uvx
   ```
   **Solution**: Install uvx using the installation command above

2. **Lambda Function Not Found**
   ```
   Error: Function not found: cloudwatch-logs-handler-dev
   ```
   **Solution**: Verify deployment completed and function names match environment variables

3. **Permission Denied**
   ```
   Error: User is not authorized to perform: lambda:InvokeFunction
   ```
   **Solution**: Check AWS credentials and Lambda invocation permissions

4. **SAM Deployment Failed**
   ```
   Error: S3 bucket does not exist
   ```
   **Solution**: Create S3 bucket or verify bucket name and permissions

### Debugging Steps

1. **Verify AWS Serverless MCP Server Installation**
   ```bash
   uvx awslabs.aws-serverless-mcp-server@latest --version
   ```

2. **Test Lambda Functions Directly**
   ```bash
   aws lambda invoke \
     --function-name cloudwatch-logs-handler-dev \
     --payload '{"operation": "test_connection", "parameters": {}}' \
     response.json
   cat response.json
   ```

3. **Check SAM Stack Status**
   ```bash
   sam list stack-outputs \
     --stack-name cloudwatch-mcp-functions-dev \
     --region us-east-1
   ```

4. **View Lambda Function Logs**
   ```bash
   sam logs \
     --stack-name cloudwatch-mcp-functions-dev \
     --name CloudWatchLogsFunction \
     --tail
   ```

## Performance & Cost

### Performance Characteristics
- **Cold Start**: 1-3 seconds for first invocation
- **Warm Execution**: 100-500ms for subsequent calls
- **Concurrent Executions**: Up to 1000 by default (configurable)
- **API Gateway Latency**: Additional 10-50ms if using HTTP endpoints

### Cost Considerations
- **Lambda**: $0.0000166667 per GB-second + $0.20 per 1M requests
- **API Gateway**: $3.50 per million API calls (if used)
- **CloudWatch Logs**: $0.50 per GB ingested + $0.03 per GB stored
- **AWS Serverless MCP Server**: No additional cost (uses your AWS resources)

### Example Monthly Cost (1000 investigations)
- Lambda (512MB, 2s avg): ~$0.02
- CloudWatch API calls: ~$0.01
- Total: **~$0.03/month** for moderate usage

## Security

### IAM Permissions
Lambda functions use minimal required permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams", 
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    }
  ]
}
```

### Network Security
- Functions run in AWS-managed VPC by default
- All communication stays within AWS infrastructure
- Optional VPC configuration for additional isolation

### Data Privacy
- No sensitive data is logged or persisted
- Responses are returned directly to MCP client
- All processing occurs within your AWS account

## Management

### Updating Lambda Functions
```bash
# Redeploy with latest code
./deploy.sh --bucket your-bucket

# Deploy to different environment
./deploy.sh --environment staging --bucket your-bucket
```

### Monitoring
```bash
# View recent logs
sam logs --stack-name cloudwatch-mcp-functions-dev --tail

# Check function metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=cloudwatch-logs-handler-dev \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

### Cleanup
```bash
# Remove all deployed resources
./cleanup.sh

# Remove specific environment
./cleanup.sh --environment staging --force
```

## Comparison with Other Approaches

| Feature | AWS Serverless MCP Server | Local MCP Server | Direct Integration |
|---------|---------------------------|------------------|--------------------|
| **Infrastructure** | AWS-managed | Self-managed | Self-managed |
| **Scaling** | Automatic | Manual | Manual |
| **Cost** | Pay-per-use | Continuous compute | Continuous compute |
| **Latency** | 100-3000ms | <100ms | <50ms |
| **Maintenance** | None | Process management | Code maintenance |
| **Security** | AWS isolation | Network security | Application security |
| **Deployment** | SAM/CloudFormation | Local installation | Direct deployment |

## Migration from Local MCP Server

If migrating from a local MCP server:

1. **Deploy Lambda functions** using the SAM template
2. **Update MCP client configuration** to use AWS Serverless MCP Server
3. **Remove local server** processes and configuration
4. **Test functionality** with new serverless architecture
5. **Monitor performance** and adjust as needed

## Advanced Configuration

### Custom Function Names
```bash
# Override default function names in deployment
sam deploy \
  --parameter-overrides \
    Environment=prod \
    LogsHandlerName=my-custom-logs-handler \
    MetricsHandlerName=my-custom-metrics-handler
```

### VPC Configuration
Add to SAM template for VPC deployment:
```yaml
VpcConfig:
  SecurityGroupIds:
    - sg-12345678
  SubnetIds:
    - subnet-12345678
    - subnet-87654321
```

### Custom IAM Policies
Extend the CloudFormation template to add custom permissions as needed.

## Resources

- [AWS Serverless MCP Server Documentation](https://awslabs.github.io/mcp/servers/aws-serverless-mcp-server/)
- [AWS SAM CLI User Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)

## Support

For issues related to:
- **AWS Serverless MCP Server**: Check AWS documentation and GitHub issues
- **Lambda Functions**: Review CloudWatch logs and deployment outputs
- **SAM Deployment**: Verify SAM CLI installation and AWS permissions
- **CloudWatch Integration**: Test Lambda functions independently first