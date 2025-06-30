# CloudWatch Logs & Metrics AI Agent - Claude Context

## Project Overview

This is a **CloudWatch Logs & Metrics AI Agent** that provides two main integration modes:
1. **MCP Server** - For integration with Cursor IDE, Claude Desktop, and other MCP-compatible tools
2. **AutoGen Agent System** - For complex multi-agent log and metrics investigation

**Key Technologies:**
- **Language:** Python 3.8+ (3.11+ recommended)
- **Frameworks:** Microsoft AutoGen v0.4 + Model Context Protocol (MCP)
- **AWS Services:** CloudWatch Logs, CloudWatch Metrics
- **Primary Language:** Japanese-first with English support

## Architecture

### Core Components

1. **MCP Server** (`src/mcp/`)
   - `server.py` - Main MCP server using FastMCP
   - `config.py` - Configuration management with environment variable priority
   - `tools.py` - Direct CloudWatch integration tools
   - `request_handler.py` - Request processing and validation
   - `validators.py` - Input validation and sanitization

2. **AutoGen Agents** (`src/agents/`)
   - `simplified_agents.py` - AutoGen v0.4 multi-agent system for complex investigations

3. **CloudWatch Tools** (`src/tools/`)
   - `cloudwatch_logs_tools.py` - Core CloudWatch Logs operations
   - `cloudwatch_metrics_tools.py` - CloudWatch Metrics operations  
   - `aws_utils.py` - High-level AWS utility functions

4. **Configuration** (`src/config/`)
   - `settings.py` - Main configuration classes
   - `env_loader.py` - Environment variable loading with priority support

5. **Logging System** (`src/logging/`)
   - Comprehensive logging with structured output, rotation, and debug support

6. **Error Handling** (`src/errors/`)
   - Specialized exception classes for different components

## Available Tools

### MCP Tools (10 total)

#### CloudWatch Logs Tools (6)
- `investigate_cloudwatch_logs` - Detailed log investigation with AI analysis
- `list_available_log_groups` - List and filter log groups
- `analyze_log_patterns` - Pattern analysis and trend detection
- `test_connection` - AWS connectivity testing
- `get_log_streams` - Stream enumeration for log groups
- `get_recent_events` - Recent log event retrieval

#### CloudWatch Metrics Tools (2)
- `investigate_cloudwatch_metrics` - Comprehensive metrics analysis
- `list_available_metrics` - Available metrics discovery

#### System Management Tools (2)
- `get_request_metrics` - MCP server performance metrics
- `get_active_requests` - Active request monitoring

## Configuration

### Environment Variable Priority
1. **External environment variables** (highest) - MCP `env` section, system environment
2. **`.env.{profile}` files** - Profile-specific settings
3. **`.env` file** - Local overrides
4. **`.env.cloudwatch`** - Base configuration (lowest)

**Important:** External environment variables are NEVER overridden by `.env` files.

### Key Environment Variables

#### MCP Server (No AI API keys required)
```bash
# AWS Configuration
AWS_PROFILE=default
AWS_REGION=ap-northeast-1

# MCP Server Settings
MCP_SERVER__NAME=CloudWatch Logs MCP Server
MCP_SERVER__VERSION=0.3.0
MCP_SERVER__TRANSPORT=stdio  # stdio, sse, streamable-http
MCP_SERVER__HOST=localhost   # for sse/streamable-http
MCP_SERVER__PORT=8000        # for sse/streamable-http

# Logging
LOG_LEVEL=INFO
```

#### AutoGen Agents (AI API keys required)
```bash
# AWS Configuration
AWS_PROFILE=default
AWS_REGION=ap-northeast-1

# AI API Keys (choose one)
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
AZURE_OPENAI_API_KEY=your_key
GOOGLE_API_KEY=your_key

# Agent Configuration
AGENT_LOG_LEVEL=INFO
ENABLE_DEBUG_LOGGING=false
```

## Usage Patterns

### 1. MCP Server Integration

**Cursor IDE Setup** (`~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "cloudwatch-logs-ai-agent": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/cloudwatch-log-agent",
        "run", "python", "run_mcp_server.py"
      ],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_REGION": "ap-northeast-1",
        "MCP_SERVER__TRANSPORT": "stdio"
      }
    }
  }
}
```

**Example Queries:**
- "過去24時間のLambda関数エラーを調査してください"
- "EC2インスタンスのCPU使用率を分析してください"
- "API Gatewayのレイテンシ問題を特定してください"

### 2. AutoGen Agent System

**Python Script Usage:**
```python
from src.agents.simplified_agents import create_cloudwatch_orchestrator

orchestrator = create_cloudwatch_orchestrator()
result = orchestrator.investigate("Lambda関数でエラーが発生しています。調査してください。")
```

**Command Line:**
```bash
# Interactive mode
python src/main.py

# Single investigation
python src/main.py --investigate "エラーログを調査してください" --output result.json
```

## Entry Points

1. **`run_mcp_server.py`** - MCP server launcher with environment checking
2. **`src/main.py`** - AutoGen agent system entry point
3. **`run_agent_example.py`** - Example usage script

## Development Notes

### Code Structure
- **Japanese-first**: Comments and documentation primarily in Japanese
- **Defensive Coding**: Comprehensive error handling and validation
- **Modular Design**: Clean separation between MCP and AutoGen systems
- **Configuration Flexibility**: Multiple environment file support with priority

### Testing Commands
- No specific test framework mentioned in codebase
- Recommend checking for existing test files or asking user for testing approach

### Dependencies
- **Core:** `fastmcp>=0.5.0`, `mcp>=1.0.0`, `boto3`, `autogen-agentchat==0.6.1`
- **Utilities:** `python-dotenv`, `aiofiles`, `pytest`
- **AWS:** Requires CloudWatch Logs/Metrics permissions

### Logging
- Multiple log files: `mcp_server.log`, `cloudwatch_agent.log`
- Structured logging with context and rotation support
- Debug mode available via `DEBUG=true` environment variable

## Current Status

**Branch:** `features-add-env`
**Recent Changes:** Environment variable handling improvements, MCP server updates
**TODO Items:** MCP environment variable configuration (per README)

## Key Implementation Details

- **FastMCP** for MCP server implementation
- **AutoGen v0.4** with `SelectorGroupChat` for multi-agent coordination
- **Boto3** for AWS service integration
- **Asyncio** for concurrent operations
- **Dataclasses** for configuration management
- **Type hints** throughout codebase for better IDE support