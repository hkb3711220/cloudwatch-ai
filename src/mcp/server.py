"""CloudWatch Logs MCP Server

Simple MCP server for direct CloudWatch integration.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import json

from fastmcp import FastMCP
from .config import load_config, MCPConfig
from .tools import MCPToolsManager
from .request_handler import MCPRequestHandler

# Initialize logger
logger = logging.getLogger(__name__)


class CloudWatchMCPServer:
    """CloudWatch MCP Server with Direct Integration"""

    def __init__(self, config: Optional[MCPConfig] = None):
        """Initialize the MCP server with configuration"""

        # Load configuration if not provided
        if config is None:
            self.config = load_config()
        else:
            self.config = config

        # Setup logging based on configuration
        self.config.setup_logging()

        # Initialize tools manager with config
        self.tools_manager = MCPToolsManager(self.config)

        # Initialize request handler
        self.request_handler = MCPRequestHandler(self.config, self.tools_manager)

        # Initialize FastMCP server
        self.app = FastMCP(
            name=self.config.server.name, version=self.config.server.version
        )

        # Register tools
        self._register_tools()

        logger.info(
            f"CloudWatch MCP Server initialized: {self.config.server.name} v{self.config.server.version} (Direct Integration)"
        )

    def _register_tools(self) -> None:
        """Register all MCP tools for direct CloudWatch integration"""

        # Core CloudWatch tools
        @self.app.tool()
        async def investigate_cloudwatch_logs(
            query: str,
            log_group: Optional[str] = None,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
            max_results: int = 100,
        ) -> str:
            """Perform detailed investigation of CloudWatch logs using direct AWS API calls"""
            return await self.tools_manager.investigate_cloudwatch_logs(
                query, log_group, start_time, end_time, max_results
            )

        @self.app.tool()
        async def list_available_log_groups(pattern: Optional[str] = None) -> str:
            """List available CloudWatch log groups with optional pattern filtering"""
            return await self.tools_manager.list_available_log_groups(pattern)

        @self.app.tool()
        async def analyze_log_patterns(
            log_group: str, time_range_hours: int = 24
        ) -> str:
            """Analyze patterns and trends in the specified log group over time"""
            return await self.tools_manager.analyze_log_patterns(
                log_group, time_range_hours
            )

        @self.app.tool()
        async def test_connection() -> str:
            """Test connection to CloudWatch"""
            return await self.tools_manager.test_connection()

        # Additional CloudWatch tools
        @self.app.tool()
        async def get_log_streams(log_group: str, limit: int = 20) -> str:
            """Get log streams for a specific log group"""
            return await self.tools_manager.get_log_streams(log_group, limit)

        @self.app.tool()
        async def get_recent_events(
            log_group: str, log_stream: str, hours_back: int = 1
        ) -> str:
            """Get recent log events from a specific log stream"""
            return await self.tools_manager.get_recent_events(
                log_group, log_stream, hours_back
            )

        # CloudWatch Metrics tools
        @self.app.tool()
        async def investigate_cloudwatch_metrics(
            namespace: str,
            metric_name: str,
            dimensions: Optional[str] = None,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
            period: int = 300,
            statistics: Optional[str] = None,
        ) -> str:
            """Perform detailed investigation of CloudWatch metrics using direct AWS API calls"""
            return await self.tools_manager.investigate_cloudwatch_metrics(
                namespace,
                metric_name,
                dimensions,
                start_time,
                end_time,
                period,
                statistics,
            )

        @self.app.tool()
        async def list_available_metrics(namespace: Optional[str] = None) -> str:
            """List available CloudWatch metrics with optional namespace filtering"""
            return await self.tools_manager.list_available_metrics(namespace)

        # Register request handling tools
        self._register_request_handling_tools()

        logger.info(
            "Registered 10 MCP tools (Direct CloudWatch Integration: 6 Logs + 2 Metrics + 2 Request Handling)"
        )

    def _register_request_handling_tools(self) -> None:
        """Register request handling tools"""

        @self.app.tool()
        async def get_request_metrics() -> Dict[str, Any]:
            """Get comprehensive metrics about request processing and performance"""
            try:
                metrics = self.request_handler.get_metrics()
                return {
                    "success": True,
                    "metrics": metrics,
                    "message_ja": "リクエストメトリクスを取得しました",
                }
            except Exception as e:
                logger.error(f"Failed to get request metrics: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message_ja": "リクエストメトリクスの取得に失敗しました",
                }

        @self.app.tool()
        async def get_active_requests() -> Dict[str, Any]:
            """Get information about currently active and pending requests"""
            try:
                active_requests = self.request_handler.get_active_requests()
                return {
                    "success": True,
                    "active_requests": active_requests,
                    "count": len(active_requests),
                    "message_ja": f"アクティブなリクエスト数: {len(active_requests)}",
                }
            except Exception as e:
                logger.error(f"Failed to get active requests: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message_ja": "アクティブリクエストの取得に失敗しました",
                }

    async def start_server(self) -> None:
        """Start the MCP server"""
        try:
            logger.info("Starting CloudWatch MCP Server (Direct Integration)...")

            # Start the FastMCP server
            await self.app.run()

            logger.info("CloudWatch MCP Server started successfully")

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise

    async def stop_server(self) -> None:
        """Stop the MCP server"""
        try:
            logger.info("Stopping CloudWatch MCP Server...")

            # Cleanup active requests
            if hasattr(self.request_handler, "cleanup_stale_requests"):
                await self.request_handler.cleanup_stale_requests(0)

            logger.info("CloudWatch MCP Server stopped")

        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information"""
        return {
            "name": self.config.server.name,
            "version": self.config.server.version,
            "transport": self.config.server.transport.value,
            "tools_count": 10,
            "integration_type": "direct_cloudwatch",
            "status": "running",
            "config": {
                "log_level": self.config.log_level.value,
                "aws_region": self.config.aws.region,
                "aws_profile": self.config.aws.profile,
            },
        }


async def main():
    """Main entry point for the MCP server"""
    try:
        # Load configuration
        config = load_config()

        # Create and start server
        server = CloudWatchMCPServer(config)
        await server.start_server()

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
