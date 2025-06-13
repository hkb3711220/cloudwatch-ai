# CloudWatch Logs AI Agent MCP Server

Model Context Protocol (MCP) server for the CloudWatch Logs AI Agent system. This server exposes the existing agent functionality as MCP tools for integration with external AI tools like Cursor, Claude Desktop, and other MCP clients.

## Features

- **CloudWatch Log Investigation**: Natural language queries to investigate CloudWatch logs
- **Log Groups Management**: List and filter available log groups
- **Agent System Status**: Monitor the health of the underlying agent system
- **Connection Testing**: Verify AWS and agent system connectivity
- **Japanese Language Support**: All responses are provided in Japanese

## MCP Tools

### `investigate_cloudwatch_logs`

CloudWatch ログを調査します

**Parameters:**

- `query` (string, required): 調査クエリ（自然言語）
- `log_group` (string, optional): 調査対象のロググループ
- `start_time` (string, optional): 開始時間（ISO 形式）
- `end_time` (string, optional): 終了時間（ISO 形式）
- `max_results` (integer, optional): 最大結果数（デフォルト：100）

**Returns:** 調査結果（日本語）

### `list_available_log_groups`

利用可能な CloudWatch ロググループを一覧表示します

**Parameters:**

- `pattern` (string, optional): フィルタパターン

**Returns:** ロググループ一覧（JSON 形式）

### `get_agent_status`

エージェントシステムの状態を取得します

**Returns:** システム状態情報（JSON 形式）

### `test_connection`

AWS 接続とエージェントシステムの接続をテストします

**Returns:** 接続テスト結果（JSON 形式）

## Installation

1. Install the MCP Python SDK:

```bash
pip install "mcp>=1.0.0"
```

2. Verify installation:

```bash
python test_mcp_server.py
```

## Usage

### Running the Server

#### Option 1: Direct execution

```bash
python run_mcp_server.py
```

#### Option 2: Using the module

```bash
python -m src.mcp.server
```

#### Option 3: With custom configuration

```bash
export MCP_LOG_LEVEL=DEBUG
export MCP_TRANSPORT=sse
export MCP_PORT=8000
python run_mcp_server.py
```

### Cursor IDE Integration

The server is automatically configured for Cursor IDE via `.cursor/mcp.json`. After starting Cursor, the CloudWatch MCP tools will be available in the AI assistant.

### Claude Desktop Integration

Add the following to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "cloudwatch-logs-ai-agent": {
      "command": "python",
      "args": ["run_mcp_server.py"],
      "cwd": "/path/to/cloudwatch-log-agent",
      "env": {
        "ANTHROPIC_API_KEY": "your-key-here",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

## Configuration

### Environment Variables

- `MCP_SERVER_NAME`: Server name (default: "CloudWatch Logs AI Agent")
- `MCP_TRANSPORT`: Transport type - stdio, sse, streamable-http (default: "stdio")
- `MCP_HOST`: Host for network transports (default: "localhost")
- `MCP_PORT`: Port for network transports (default: 8000)
- `MCP_LOG_LEVEL`: Logging level (default: "INFO")
- `MCP_DEBUG`: Enable debug mode (default: "false")
- `AWS_REGION`: AWS region for CloudWatch
- `AWS_PROFILE`: AWS profile to use

### Agent System Integration

The MCP server automatically integrates with the existing agent system:

- **Agent Manager**: Uses `SimplifiedAgentManager` for investigations
- **CloudWatch Tools**: Leverages existing CloudWatch tools from `src/tools/aws_utils.py`
- **Configuration**: Inherits settings from `src/config/settings.py`

If the agent system is not available, the server provides fallback responses with appropriate error messages.

## Architecture

```
src/mcp/
├── __init__.py          # Module exports
├── config.py            # Configuration management
├── server.py            # Main MCP server implementation
├── tools.py             # MCP tools and agent integration
└── README.md            # This documentation

Root files:
├── run_mcp_server.py    # Server startup script
└── test_mcp_server.py   # Testing and validation
```

## Development

### Testing

Run the test suite to verify functionality:

```bash
python test_mcp_server.py
```

Test output:

- ✅ MCP SDK Imports
- ✅ Server Initialization
- ✅ Tools Manager

### Debugging

Enable debug logging:

```bash
export MCP_DEBUG=true
export MCP_LOG_LEVEL=DEBUG
python run_mcp_server.py
```

### Development Mode

For development with live reloading, use:

```bash
# Install in development mode
pip install -e .

# Run with MCP dev tools (if available)
mcp dev run_mcp_server.py
```

## Error Handling

The server includes comprehensive error handling:

- **Agent System Unavailable**: Provides fallback responses
- **AWS Connection Issues**: Returns structured error messages
- **Configuration Errors**: Graceful degradation with warnings
- **Tool Failures**: Detailed error reporting in Japanese

## Logging

Structured logging is available at multiple levels:

- **INFO**: General operation status
- **DEBUG**: Detailed operation traces
- **WARNING**: Non-fatal issues
- **ERROR**: Error conditions

Logs are output to console with timestamps and component identification.

## Integration Examples

### Basic Investigation

```python
# Via MCP client
result = await session.call_tool(
    "investigate_cloudwatch_logs",
    {"query": "API errors in the last hour"}
)
```

### Status Check

```python
# Check system health
status = await session.call_tool("get_agent_status")
```

### List Log Groups

```python
# Get available log groups
log_groups = await session.call_tool(
    "list_available_log_groups",
    {"pattern": "/aws/lambda/*"}
)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Python path includes project root
2. **MCP SDK Missing**: Install with `pip install "mcp>=1.0.0"`
3. **Agent System Unavailable**: Check existing agent configuration
4. **AWS Credentials**: Verify AWS configuration and permissions

### Diagnostic Commands

```bash
# Test imports and basic functionality
python test_mcp_server.py

# Check MCP SDK installation
python -c "import mcp; print(mcp.__version__)"

# Verify agent system
python -c "from src.agents.simplified_agents import SimplifiedAgentManager"
```

## License

This MCP server is part of the CloudWatch Logs AI Agent project and follows the same licensing terms.
