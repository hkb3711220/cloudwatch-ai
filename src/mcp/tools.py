"""Simplified MCP Tools Manager

Direct CloudWatch integration without AI Agent complexity.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError

# Import aws_utils CloudWatch tools directly
from ..tools.aws_utils import (
    list_log_groups,
    list_log_streams,
    search_log_events,
    get_recent_log_events,
    analyze_log_patterns,
    # Add CloudWatch metrics imports
    get_metric_statistics,
    list_available_metrics,
    METRICS_AVAILABLE,
)

# Import new configuration system
from .config import MCPConfig

logger = logging.getLogger(__name__)


class MCPToolsManager:
    """Simplified MCP Tools Manager with direct CloudWatch integration"""

    def __init__(self, config: Optional[MCPConfig] = None):
        """Initialize tools manager with configuration

        Args:
            config: MCPConfig instance, will load from environment if None
        """
        # Store configuration
        if config is None:
            from .config import load_config

            self.config = load_config()
        else:
            self.config = config

        logger.info("Initializing MCP Tools Manager")
        logger.debug(f"AWS Region: {self.config.aws.region}")

        # Connection status
        self._aws_connected = False

        logger.info("MCP Tools Manager initialized")

    async def investigate_cloudwatch_logs(
        self,
        query: str,
        log_group: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: int = 100,
    ) -> str:
        """CloudWatchログの詳細調査を実行します（直接aws_utils使用）"""

        try:
            logger.info(f"Starting CloudWatch investigation: {query}")

            # Determine time range
            hours_back = 24  # Default
            if start_time and end_time:
                # Parse time strings and calculate hours_back
                try:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    hours_back = int((end_dt - start_dt).total_seconds() / 3600)
                    # Limit to 1-168 hours
                    hours_back = max(1, min(hours_back, 168))
                except Exception as e:
                    logger.warning(
                        f"Failed to parse time range: {e}, using default 24 hours"
                    )

            investigation_results = {}

            # If no log group specified, list available groups
            if not log_group:
                logger.info("No log group specified, listing available groups")
                groups_result = list_log_groups(limit=20)
                investigation_results["available_log_groups"] = json.loads(
                    groups_result
                )

                # Get first group for demonstration
                groups_data = json.loads(groups_result)
                if groups_data.get("log_groups"):
                    log_group = groups_data["log_groups"][0]["name"]
                    logger.info(f"Using first available log group: {log_group}")
                else:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": "No log groups found",
                            "investigation_results": investigation_results,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )

            # Search for log events based on query
            logger.info(f"Searching log events in {log_group}")
            search_result = search_log_events(
                log_group_name=log_group,
                filter_pattern=query,
                hours_back=hours_back,
                max_events=max_results,
            )
            investigation_results["search_results"] = json.loads(search_result)

            # Analyze patterns in the log group
            logger.info(f"Analyzing patterns in {log_group}")
            pattern_result = analyze_log_patterns(
                log_group_name=log_group, hours_back=hours_back
            )
            investigation_results["pattern_analysis"] = json.loads(pattern_result)

            # Compile investigation summary
            search_data = json.loads(search_result)
            pattern_data = json.loads(pattern_result)

            summary = {
                "investigation_query": query,
                "log_group": log_group,
                "time_range": f"{hours_back} hours",
                "events_found": search_data.get("total_found", 0),
                "health_status": pattern_data.get("health_status", "UNKNOWN"),
                "error_patterns": pattern_data.get("top_error_patterns", {}),
                "warning_patterns": pattern_data.get("top_warning_patterns", {}),
            }

            result = {
                "status": "success",
                "summary": summary,
                "detailed_results": investigation_results,
                "message_ja": f"CloudWatchログ調査が完了しました。{search_data.get('total_found', 0)}件のイベントが見つかりました。",
            }

            logger.info(
                f"Investigation completed: {search_data.get('total_found', 0)} events found"
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Investigation failed: {e}")
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Investigation failed: {str(e)}",
                    "message_ja": f"調査に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
                indent=2,
            )

    async def list_available_log_groups(self, pattern: Optional[str] = None) -> str:
        """List available CloudWatch log groups with optional pattern filtering"""

        try:
            logger.info(f"Listing log groups with pattern: {pattern}")

            result = list_log_groups(name_prefix=pattern or "", limit=50)

            # Add Japanese message
            data = json.loads(result)
            if "error" not in data:
                data["message_ja"] = (
                    f"{data.get('total_found', 0)}個のロググループが見つかりました"
                )

            logger.info(f"Found {data.get('total_found', 0)} log groups")
            return json.dumps(data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to list log groups: {e}")
            return json.dumps(
                {
                    "error": str(e),
                    "message_ja": f"ロググループの取得に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
            )

    async def analyze_log_patterns(
        self, log_group: str, time_range_hours: int = 24
    ) -> str:
        """Analyze patterns and trends in the specified log group over time"""

        try:
            logger.info(
                f"Analyzing patterns in {log_group} for {time_range_hours} hours"
            )

            result = analyze_log_patterns(
                log_group_name=log_group, hours_back=time_range_hours
            )

            # Add Japanese message
            data = json.loads(result)
            if "error" not in data:
                status = data.get("health_status", "UNKNOWN")
                status_ja = {
                    "HEALTHY": "正常",
                    "WARNING": "警告",
                    "ERROR": "エラー",
                    "UNKNOWN": "不明",
                }.get(status, status)
                data["message_ja"] = (
                    f"ログパターン分析が完了しました。ステータス: {status_ja}"
                )

            logger.info(f"Pattern analysis completed for {log_group}")
            return json.dumps(data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to analyze patterns: {e}")
            return json.dumps(
                {
                    "error": str(e),
                    "message_ja": f"パターン分析に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
            )

    async def test_connection(self) -> str:
        """Test connection to CloudWatch"""

        try:
            logger.info("Testing CloudWatch connection")

            # Test connection by listing log groups
            result = list_log_groups(limit=1)
            data = json.loads(result)

            if "error" in data:
                self._aws_connected = False
                return json.dumps(
                    {
                        "status": "error",
                        "connection": "failed",
                        "error": data["error"],
                        "message_ja": "CloudWatchへの接続に失敗しました",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                self._aws_connected = True
                return json.dumps(
                    {
                        "status": "success",
                        "connection": "connected",
                        "aws_region": self.config.aws.region,
                        "aws_profile": self.config.aws.profile,
                        "message_ja": "CloudWatchへの接続が成功しました",
                    },
                    ensure_ascii=False,
                    indent=2,
                )

        except Exception as e:
            self._aws_connected = False
            logger.error(f"Connection test failed: {e}")
            return json.dumps(
                {
                    "status": "error",
                    "connection": "failed",
                    "error": str(e),
                    "message_ja": f"接続テストに失敗しました: {str(e)}",
                },
                ensure_ascii=False,
                indent=2,
            )

    async def get_log_streams(self, log_group: str, limit: int = 20) -> str:
        """Get log streams for a specific log group"""

        try:
            logger.info(f"Getting log streams for {log_group}")

            result = list_log_streams(log_group_name=log_group, limit=limit)

            # Add Japanese message
            data = json.loads(result)
            if "error" not in data:
                data["message_ja"] = (
                    f"{data.get('total_found', 0)}個のログストリームが見つかりました"
                )

            return json.dumps(data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to get log streams: {e}")
            return json.dumps(
                {
                    "error": str(e),
                    "message_ja": f"ログストリームの取得に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
            )

    async def get_recent_events(
        self, log_group: str, log_stream: str, hours_back: int = 1
    ) -> str:
        """Get recent log events from a specific stream"""

        try:
            logger.info(f"Getting recent events from {log_group}/{log_stream}")

            result = get_recent_log_events(
                log_group_name=log_group,
                log_stream_name=log_stream,
                hours_back=hours_back,
            )

            # Add Japanese message
            data = json.loads(result)
            if "error" not in data:
                data["message_ja"] = (
                    f"{data.get('total_found', 0)}個のログイベントが見つかりました"
                )

            return json.dumps(data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return json.dumps(
                {
                    "error": str(e),
                    "message_ja": f"最新イベントの取得に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
            )

    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            logger.info("Cleaning up MCP Tools Manager")
            # No complex cleanup needed for direct integration
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def investigate_cloudwatch_metrics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        period: int = 300,
        statistics: Optional[str] = None,
    ) -> str:
        """CloudWatchメトリクスの詳細調査を実行します（直接aws_utils使用）"""

        try:
            logger.info(
                f"Starting CloudWatch metrics investigation: {namespace}/{metric_name}"
            )

            if not METRICS_AVAILABLE:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "CloudWatch metrics functionality is not available",
                        "message_ja": "CloudWatchメトリクス機能が利用できません",
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            # Parse dimensions if provided
            parsed_dimensions = []
            if dimensions:
                try:
                    # Expect format like "InstanceId=i-1234567890abcdef0,Name=Value"
                    for dim_pair in dimensions.split(","):
                        if "=" in dim_pair:
                            name, value = dim_pair.strip().split("=", 1)
                            parsed_dimensions.append(
                                {"Name": name.strip(), "Value": value.strip()}
                            )
                except Exception as e:
                    logger.warning(f"Failed to parse dimensions: {e}")

            # Parse statistics if provided
            parsed_statistics = None
            if statistics:
                parsed_statistics = [stat.strip() for stat in statistics.split(",")]

            # Parse time range
            parsed_start_time = None
            parsed_end_time = None
            if start_time:
                try:
                    parsed_start_time = datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse start_time: {e}")
            if end_time:
                try:
                    parsed_end_time = datetime.fromisoformat(
                        end_time.replace("Z", "+00:00")
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse end_time: {e}")

            # Get metric statistics
            logger.info(f"Retrieving metrics for {namespace}/{metric_name}")
            metrics_result = get_metric_statistics(
                namespace=namespace,
                metric_name=metric_name,
                dimensions=parsed_dimensions,
                start_time=parsed_start_time,
                end_time=parsed_end_time,
                period=period,
                statistics=parsed_statistics,
            )

            metrics_data = json.loads(metrics_result)

            # Check for errors
            if "error" in metrics_data:
                return json.dumps(
                    {
                        "status": "error",
                        "message": metrics_data["error"],
                        "message_ja": f"メトリクス取得に失敗しました: {metrics_data['error']}",
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            # Compile investigation summary
            datapoints_count = metrics_data.get("total_datapoints", 0)
            time_range = f"{metrics_data.get('start_time', 'N/A')} to {metrics_data.get('end_time', 'N/A')}"

            summary = {
                "namespace": namespace,
                "metric_name": metric_name,
                "dimensions": parsed_dimensions,
                "time_range": time_range,
                "period_seconds": period,
                "statistics": parsed_statistics or ["Average", "Maximum", "Minimum"],
                "datapoints_found": datapoints_count,
            }

            result = {
                "status": "success",
                "summary": summary,
                "metrics_data": metrics_data,
                "message_ja": f"CloudWatchメトリクス調査が完了しました。{datapoints_count}個のデータポイントが見つかりました。",
            }

            logger.info(
                f"Metrics investigation completed: {datapoints_count} datapoints found"
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Metrics investigation failed: {e}")
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Metrics investigation failed: {str(e)}",
                    "message_ja": f"メトリクス調査に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
                indent=2,
            )

    async def list_available_metrics(self, namespace: Optional[str] = None) -> str:
        """List available CloudWatch metrics with optional namespace filtering"""

        try:
            logger.info(f"Listing available metrics for namespace: {namespace}")

            if not METRICS_AVAILABLE:
                return json.dumps(
                    {
                        "error": "CloudWatch metrics functionality is not available",
                        "message_ja": "CloudWatchメトリクス機能が利用できません",
                    },
                    ensure_ascii=False,
                )

            result = list_available_metrics(namespace=namespace)

            # Add Japanese message
            data = json.loads(result)
            if "error" not in data:
                data["message_ja"] = (
                    f"{data.get('total_metrics', 0)}個のメトリクスが見つかりました"
                )

            logger.info(f"Found {data.get('total_metrics', 0)} available metrics")
            return json.dumps(data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to list available metrics: {e}")
            return json.dumps(
                {
                    "error": str(e),
                    "message_ja": f"利用可能メトリクスの取得に失敗しました: {str(e)}",
                },
                ensure_ascii=False,
            )
