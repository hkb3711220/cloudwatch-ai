"""CloudWatch MCP Server Request Handler

Simple request handling system for the MCP server with:
- MCP protocol compliance and validation
- Basic request routing
- Request/response logging and metrics
- Error handling
"""

import asyncio
import json
import logging
import time
import traceback
from typing import Dict, Any, Optional, Union, Callable, Awaitable, List, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from collections import defaultdict
import uuid
from enum import Enum

try:
    from fastmcp import FastMCP
    from fastmcp.server.lowlevel import Server, NotificationOptions
    from fastmcp.server.models import InitializationOptions
    import fastmcp.types as mcp_types
    import fastmcp.server.stdio

    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    # Fallback types for compatibility

    class mcp_types:
        class JSONRPCMessage:
            pass

        class JSONRPCRequest:
            pass

        class JSONRPCResponse:
            pass

        class JSONRPCError:
            pass


# Initialize logger
logger = logging.getLogger(__name__)


class RequestMethod(Enum):
    """Standard MCP request methods"""

    # Core protocol
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    PING = "ping"

    # Capabilities
    LIST_TOOLS = "tools/list"
    CALL_TOOL = "tools/call"
    LIST_RESOURCES = "resources/list"
    READ_RESOURCE = "resources/read"
    SUBSCRIBE_RESOURCE = "resources/subscribe"
    UNSUBSCRIBE_RESOURCE = "resources/unsubscribe"
    LIST_PROMPTS = "prompts/list"
    GET_PROMPT = "prompts/get"

    # Completion
    COMPLETE = "completion/complete"

    # Logging
    SET_LEVEL = "logging/setLevel"

    # Notifications
    CANCELLED = "notifications/cancelled"
    PROGRESS = "notifications/progress"
    RESOURCE_UPDATED = "notifications/resources/updated"
    RESOURCE_LIST_CHANGED = "notifications/resources/list_changed"
    TOOL_LIST_CHANGED = "notifications/tools/list_changed"
    PROMPT_LIST_CHANGED = "notifications/prompts/list_changed"


class RequestStatus(Enum):
    """Request processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class RequestContext:
    """Context information for request processing"""

    request_id: str
    method: str
    timestamp: float
    client_ip: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestMetrics:
    """Metrics for request processing"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    average_response_time: float = 0.0
    active_requests: int = 0
    requests_by_method: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class ProcessingRequest:
    """Active request being processed"""

    request_id: str
    method: str
    params: Dict[str, Any]
    context: RequestContext
    start_time: float
    timeout: Optional[float] = None
    status: RequestStatus = RequestStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: float = 0.0


class MCPRequestValidator:
    """Validates MCP protocol compliance and request format"""

    REQUIRED_FIELDS = {"jsonrpc": str, "method": str, "id": (str, int, type(None))}

    SUPPORTED_JSONRPC_VERSION = "2.0"

    @classmethod
    def validate_request(
        cls, request_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate MCP request format and protocol compliance"""

        # Check required fields
        for field, expected_type in cls.REQUIRED_FIELDS.items():
            if field not in request_data:
                return False, f"Missing required field: {field}"

            if not isinstance(request_data[field], expected_type):
                return (
                    False,
                    f"Invalid type for field {field}: expected {expected_type}, got {type(request_data[field])}",
                )

        # Check JSON-RPC version
        if request_data.get("jsonrpc") != cls.SUPPORTED_JSONRPC_VERSION:
            return False, f"Unsupported JSON-RPC version: {request_data.get('jsonrpc')}"

        # Validate method name
        method = request_data.get("method", "")
        if not method or not isinstance(method, str):
            return False, "Method name must be a non-empty string"

        # Check if method is supported
        try:
            RequestMethod(method)
        except ValueError:
            # Allow custom methods but log warning
            logger.warning(f"Unknown method: {method}")

        return True, None

    @classmethod
    def validate_params(
        cls, method: str, params: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate method-specific parameters"""

        # Method-specific validation rules
        validation_rules = {
            RequestMethod.INITIALIZE.value: ["protocolVersion", "capabilities"],
            RequestMethod.CALL_TOOL.value: ["name"],
            RequestMethod.READ_RESOURCE.value: ["uri"],
            RequestMethod.GET_PROMPT.value: ["name"],
        }

        if method in validation_rules:
            required_params = validation_rules[method]
            for param in required_params:
                if param not in params:
                    return False, f"Missing required parameter for {method}: {param}"

        return True, None


class MCPResponseFormatter:
    """Formats responses according to MCP protocol"""

    @staticmethod
    def success_response(
        request_id: Union[str, int, None], result: Any
    ) -> Dict[str, Any]:
        """Format successful response"""
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def error_response(
        request_id: Union[str, int, None],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Format error response"""
        error_obj = {"code": code, "message": message}
        if data is not None:
            error_obj["data"] = data

        return {"jsonrpc": "2.0", "id": request_id, "error": error_obj}

    @staticmethod
    def notification(
        method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Format notification message"""
        notification = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params
        return notification


class MCPRequestRouter:
    """Routes MCP requests to appropriate handlers"""

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []
        self.before_handlers: List[Callable] = []
        self.after_handlers: List[Callable] = []

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a specific method"""
        self.handlers[method] = handler

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to the request processing pipeline"""
        self.middleware.append(middleware)

    def add_before_handler(self, handler: Callable) -> None:
        """Add a handler to run before request processing"""
        self.before_handlers.append(handler)

    def add_after_handler(self, handler: Callable) -> None:
        """Add a handler to run after request processing"""
        self.after_handlers.append(handler)

    async def route_request(
        self, method: str, params: Dict[str, Any], context: RequestContext
    ) -> Any:
        """Route request to appropriate handler"""

        # Run before handlers
        for handler in self.before_handlers:
            await handler(context, params)

        # Run middleware
        for middleware in self.middleware:
            params = await middleware(context, params)

        # Find and execute handler
        if method not in self.handlers:
            raise ValueError(f"No handler registered for method: {method}")

        handler = self.handlers[method]
        result = await handler(params, context)

        # Run after handlers
        for handler in self.after_handlers:
            await handler(context, result)

        return result


class MCPRequestHandler:
    """Handles MCP requests with protocol compliance and metrics"""

    def __init__(self, config, tools_manager):
        """Initialize request handler"""
        self.config = config
        self.tools_manager = tools_manager

        # Initialize components
        self.validator = MCPRequestValidator()
        self.formatter = MCPResponseFormatter()
        self.router = MCPRequestRouter()

        # Request tracking
        self.active_requests: Dict[str, ProcessingRequest] = {}
        self.request_history: List[ProcessingRequest] = []
        self.metrics = RequestMetrics()

        # Setup handlers and middleware
        self._setup_core_handlers()
        self._setup_middleware()

        logger.info("MCP Request Handler initialized")

    def _setup_core_handlers(self) -> None:
        """Setup core MCP protocol handlers"""

        # Register core protocol handlers
        self.router.register_handler(
            RequestMethod.INITIALIZE.value, self._handle_initialize
        )
        self.router.register_handler(RequestMethod.PING.value, self._handle_ping)
        self.router.register_handler(
            RequestMethod.LIST_TOOLS.value, self._handle_list_tools
        )
        self.router.register_handler(
            RequestMethod.CALL_TOOL.value, self._handle_call_tool
        )
        self.router.register_handler(
            RequestMethod.LIST_RESOURCES.value, self._handle_list_resources
        )
        self.router.register_handler(
            RequestMethod.READ_RESOURCE.value, self._handle_read_resource
        )
        self.router.register_handler(
            RequestMethod.LIST_PROMPTS.value, self._handle_list_prompts
        )
        self.router.register_handler(
            RequestMethod.GET_PROMPT.value, self._handle_get_prompt
        )
        self.router.register_handler(
            RequestMethod.COMPLETE.value, self._handle_complete
        )
        self.router.register_handler(
            RequestMethod.SET_LEVEL.value, self._handle_set_log_level
        )

        logger.info("Core MCP handlers registered")

    def _setup_middleware(self) -> None:
        """Setup request processing middleware"""

        async def logging_middleware(
            context: RequestContext, params: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Log request details"""
            logger.debug(
                f"Processing request: {context.method} (ID: {context.request_id})"
            )
            return params

        async def metrics_middleware(
            context: RequestContext, params: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Update request metrics"""
            self.metrics.requests_by_method[context.method] += 1
            return params

        # Add middleware
        self.router.add_middleware(logging_middleware)
        self.router.add_middleware(metrics_middleware)

    async def process_request(
        self, request_data: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Process an MCP request"""

        start_time = time.time()
        request_id = request_data.get("id", str(uuid.uuid4()))
        method = request_data.get("method", "unknown")

        # Update metrics
        self.metrics.total_requests += 1
        self.metrics.active_requests += 1

        try:
            # Validate request format
            is_valid, error_message = self.validator.validate_request(request_data)
            if not is_valid:
                self.metrics.failed_requests += 1
                self.metrics.errors_by_type["validation_error"] += 1
                return self.formatter.error_response(
                    request_id, -32600, f"Invalid Request: {error_message}"
                )

            # Extract parameters
            params = request_data.get("params", {})

            # Validate method-specific parameters
            is_valid, error_message = self.validator.validate_params(method, params)
            if not is_valid:
                self.metrics.failed_requests += 1
                self.metrics.errors_by_type["parameter_error"] += 1
                return self.formatter.error_response(
                    request_id, -32602, f"Invalid params: {error_message}"
                )

            # Create request context
            context = RequestContext(
                request_id=str(request_id),
                method=method,
                timestamp=start_time,
                client_ip=kwargs.get("client_ip", "127.0.0.1"),
                user_id=kwargs.get("user_id"),
                session_id=kwargs.get("session_id"),
                metadata=kwargs,
            )

            # Create processing request
            processing_request = ProcessingRequest(
                request_id=str(request_id),
                method=method,
                params=params,
                context=context,
                start_time=start_time,
                timeout=kwargs.get("timeout", 30.0),
            )

            # Track active request
            self.active_requests[str(request_id)] = processing_request

            try:
                # Process request
                result = await self._process_request_internal(processing_request)

                # Update request status
                processing_request.status = RequestStatus.COMPLETED
                processing_request.result = result

                # Update metrics
                self.metrics.successful_requests += 1
                response_time = time.time() - start_time
                self._update_average_response_time(response_time)

                # Add to history
                self._add_to_history(processing_request)

                return self.formatter.success_response(request_id, result)

            except asyncio.TimeoutError:
                processing_request.status = RequestStatus.TIMEOUT
                self.metrics.timeout_requests += 1
                self.metrics.errors_by_type["timeout"] += 1
                return self.formatter.error_response(
                    request_id, -32000, "Request timeout"
                )

            except Exception as e:
                processing_request.status = RequestStatus.FAILED
                processing_request.error = str(e)
                self.metrics.failed_requests += 1
                self.metrics.errors_by_type["internal_error"] += 1

                logger.error(f"Request processing failed: {e}")
                logger.debug(
                    f"Request processing error details: {traceback.format_exc()}"
                )

                return self.formatter.error_response(
                    request_id, -32603, f"Internal error: {str(e)}"
                )

        finally:
            # Clean up active request
            if str(request_id) in self.active_requests:
                del self.active_requests[str(request_id)]

            self.metrics.active_requests -= 1

    async def _process_request_internal(
        self, processing_request: ProcessingRequest
    ) -> Any:
        """Internal request processing with timeout"""

        processing_request.status = RequestStatus.PROCESSING

        # Apply timeout if specified
        if processing_request.timeout:
            return await asyncio.wait_for(
                self.router.route_request(
                    processing_request.method,
                    processing_request.params,
                    processing_request.context,
                ),
                timeout=processing_request.timeout,
            )
        else:
            return await self.router.route_request(
                processing_request.method,
                processing_request.params,
                processing_request.context,
            )

    async def _handle_initialize(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle initialize request"""

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
                "logging": {},
            },
            "serverInfo": {
                "name": self.config.server.name,
                "version": self.config.server.version,
            },
        }

    async def _handle_ping(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle ping request"""
        return {}

    async def _handle_list_tools(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle list tools request"""

        tools = [
            {
                "name": "investigate_cloudwatch_logs",
                "description": "CloudWatchログを調査し、指定された条件に基づいてログエントリを分析します",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "調査クエリ（日本語または英語）",
                        },
                        "log_group": {
                            "type": "string",
                            "description": "対象のロググループ名",
                        },
                        "time_range": {
                            "type": "string",
                            "description": "時間範囲（例：1h, 24h, 7d）",
                        },
                        "language": {
                            "type": "string",
                            "enum": ["ja", "en"],
                            "default": "ja",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_available_log_groups",
                "description": "利用可能なCloudWatchロググループの一覧を取得します",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prefix": {
                            "type": "string",
                            "description": "ロググループ名のプレフィックスでフィルタ",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "取得する最大数",
                            "default": 50,
                        },
                    },
                },
            },
            {
                "name": "get_agent_status",
                "description": "エージェントの現在のステータスと設定を取得します",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "test_connection",
                "description": "AWS CloudWatchへの接続をテストします",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "analyze_log_patterns",
                "description": "CloudWatchログの指定されたログ グループ内でパターンと傾向を分析します",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "log_group": {
                            "type": "string",
                            "description": "分析するログ グループ名",
                        },
                        "time_range_hours": {
                            "type": "integer",
                            "description": "分析する時間範囲（時間）",
                            "default": 24,
                        },
                    },
                    "required": ["log_group"],
                },
            },
            {
                "name": "run_direct_investigation",
                "description": "AIエージェントまたはフォールバック メソッドを使用して直接的な調査指示を実行します",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "instruction": {
                            "type": "string",
                            "description": "実行する調査指示",
                        },
                        "use_orchestrator": {
                            "type": "boolean",
                            "description": "オーケストレーターを使用するかどうか",
                            "default": True,
                        },
                    },
                    "required": ["instruction"],
                },
            },
            {
                "name": "get_agent_details",
                "description": "利用可能なエージェントとその機能についての詳細情報を取得します",
            },
        ]

        return {"tools": tools}

    async def _handle_call_tool(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle tool call request"""

        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if not hasattr(self.tools_manager, tool_name):
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_func = getattr(self.tools_manager, tool_name)
        result = await tool_func(**tool_args)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2),
                }
            ]
        }

    async def _handle_list_resources(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle list resources request"""

        # Return empty resources list for now
        return {"resources": []}

    async def _handle_read_resource(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle read resource request"""

        uri = params.get("uri")

        # Basic resource handling
        if uri == "config://current":
            config_data = {
                "server": {
                    "name": self.config.server.name,
                    "version": self.config.server.version,
                },
                "aws": {"region": self.config.aws.region},
            }
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(config_data, indent=2),
                    }
                ]
            }

        raise ValueError(f"Unknown resource: {uri}")

    async def _handle_list_prompts(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle list prompts request"""

        prompts = [
            {
                "name": "investigate_logs",
                "description": "CloudWatchログの調査を支援するプロンプト",
                "arguments": [
                    {
                        "name": "query",
                        "description": "調査したい内容",
                        "required": True,
                    },
                    {
                        "name": "log_group",
                        "description": "対象ロググループ",
                        "required": False,
                    },
                ],
            },
            {
                "name": "analyze_errors",
                "description": "エラーログの分析を支援するプロンプト",
                "arguments": [
                    {
                        "name": "error_type",
                        "description": "エラーの種類",
                        "required": False,
                    }
                ],
            },
        ]

        return {"prompts": prompts}

    async def _handle_get_prompt(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle get prompt request"""

        prompt_name = params.get("name")
        prompt_args = params.get("arguments", {})

        if prompt_name == "investigate_logs":
            query = prompt_args.get("query", "ログを調査してください")
            log_group = prompt_args.get("log_group", "")

            prompt_text = f"""CloudWatchログの調査を行います。

調査内容: {query}
対象ロググループ: {log_group if log_group else '指定なし'}

以下の手順で調査を進めてください：
1. 適切なロググループを選択
2. 時間範囲を設定
3. 関連するログエントリを検索
4. パターンや異常を分析
5. 結果をまとめて報告

investigate_cloudwatch_logsツールを使用して調査を開始してください。"""

            return {
                "description": "CloudWatchログ調査プロンプト",
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": prompt_text}}
                ],
            }

        elif prompt_name == "analyze_errors":
            error_type = prompt_args.get("error_type", "一般的なエラー")

            prompt_text = f"""エラーログの分析を行います。

エラータイプ: {error_type}

以下の観点で分析してください：
1. エラーの発生頻度と傾向
2. エラーメッセージの詳細分析
3. 関連するスタックトレースやコンテキスト
4. 根本原因の特定
5. 対処法の提案

analyze_log_patternsツールを使用してエラーパターンを分析してください。"""

            return {
                "description": "エラーログ分析プロンプト",
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": prompt_text}}
                ],
            }

        raise ValueError(f"Unknown prompt: {prompt_name}")

    async def _handle_complete(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle completion request"""

        # Basic completion support
        ref = params.get("ref", {})
        argument = params.get("argument")

        if (
            ref.get("type") == "ref/tool"
            and ref.get("name") == "investigate_cloudwatch_logs"
        ):
            if argument.get("name") == "log_group":
                # Return available log groups as completions
                try:
                    log_groups_result = (
                        await self.tools_manager.list_available_log_groups()
                    )
                    if log_groups_result.get("success"):
                        log_groups = log_groups_result.get("log_groups", [])
                        completions = [
                            {
                                "values": [
                                    lg.get("logGroupName", "") for lg in log_groups[:10]
                                ],
                                "total": len(log_groups),
                            }
                        ]
                        return {"completion": completions}
                except Exception as e:
                    logger.error(f"Failed to get log groups for completion: {e}")

        return {"completion": {"values": [], "total": 0}}

    async def _handle_set_log_level(
        self, params: Dict[str, Any], context: RequestContext
    ) -> Dict[str, Any]:
        """Handle set log level request"""

        level = params.get("level", "info").upper()

        # Update logging level
        numeric_level = getattr(logging, level, logging.INFO)
        logging.getLogger().setLevel(numeric_level)

        logger.info(f"Log level set to: {level}")

        return {"success": True, "level": level}

    def _update_average_response_time(self, response_time: float) -> None:
        """Update average response time"""
        if self.metrics.successful_requests == 1:
            self.metrics.average_response_time = response_time
        else:
            # Calculate running average
            total_time = self.metrics.average_response_time * (
                self.metrics.successful_requests - 1
            )
            self.metrics.average_response_time = (
                total_time + response_time
            ) / self.metrics.successful_requests

    def _add_to_history(self, request: ProcessingRequest) -> None:
        """Add request to history (keep last 100)"""
        self.request_history.append(request)
        if len(self.request_history) > 100:
            self.request_history.pop(0)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current request metrics"""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "timeout_requests": self.metrics.timeout_requests,
            "active_requests": self.metrics.active_requests,
            "average_response_time": round(self.metrics.average_response_time, 3),
            "requests_by_method": dict(self.metrics.requests_by_method),
            "errors_by_type": dict(self.metrics.errors_by_type),
            "success_rate": round(
                (self.metrics.successful_requests / max(self.metrics.total_requests, 1))
                * 100,
                2,
            ),
        }

    def get_active_requests(self) -> List[Dict[str, Any]]:
        """Get currently active requests"""
        return [
            {
                "request_id": req.request_id,
                "method": req.method,
                "status": req.status.value,
                "start_time": req.start_time,
                "elapsed_time": round(time.time() - req.start_time, 3),
                "progress": req.progress,
            }
            for req in self.active_requests.values()
        ]

    async def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request"""
        if request_id in self.active_requests:
            request = self.active_requests[request_id]
            request.status = RequestStatus.CANCELLED
            return True
        return False

    async def cleanup_stale_requests(self, max_age_seconds: float = 300) -> int:
        """Clean up stale requests older than max_age_seconds"""
        current_time = time.time()
        stale_requests = []

        for request_id, request in self.active_requests.items():
            if current_time - request.start_time > max_age_seconds:
                stale_requests.append(request_id)

        for request_id in stale_requests:
            del self.active_requests[request_id]
            self.metrics.active_requests -= 1

        return len(stale_requests)
