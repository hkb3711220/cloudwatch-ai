"""
AWS CloudWatch MCP Tools - Wrapper Module for AI Agents

This module serves as the MCP (Model Context Protocol) interface layer for CloudWatch operations,
providing JSON-formatted responses optimized for AI consumption. It acts as a wrapper around
the core CloudWatch functionality implemented in cloudwatch_logs_tools.py and cloudwatch_metrics_tools.py.

Key Features:
- MCP-compatible JSON responses for all CloudWatch operations
- Simplified error handling with structured error messages
- Time-based filtering and data aggregation for log analysis
- Automatic timestamp conversion to human-readable formats
- Pattern analysis for error detection and health monitoring

Architecture:
- This module delegates actual AWS operations to specialized tool modules
- cloudwatch_logs_tools.py: Core CloudWatch Logs functionality for AutoGen agents
- cloudwatch_metrics_tools.py: Core CloudWatch Metrics functionality for AutoGen agents
- All functions return JSON strings suitable for MCP protocol consumption

Usage:
This module is primarily intended for use by MCP servers and AI agents that need
structured CloudWatch data. For direct programmatic access, use the underlying
tool modules directly.

Example:
    >>> result = list_log_groups(limit=10)
    >>> print(json.loads(result)['total_found'])
    5
"""

import json
import logging
from datetime import datetime, timezone, timedelta

# Configure logging
logger = logging.getLogger(__name__)

# Import new CloudWatch logs module
try:
    from .cloudwatch_logs_tools import (
        list_log_groups as _list_log_groups,
        list_log_streams as _list_log_streams,
        search_log_events as _search_log_events,
        get_log_events as _get_log_events,
    )

    LOGS_AVAILABLE = True
except ImportError:
    LOGS_AVAILABLE = False
    logger.warning("CloudWatch logs module not available")

# Import new CloudWatch metrics module
try:
    from .cloudwatch_metrics_tools import (
        get_cloudwatch_metrics_tools,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("CloudWatch metrics module not available")


def list_log_groups(name_prefix: str = "", limit: int = 50) -> str:
    """
    List CloudWatch log groups (MCP wrapper).

    Args:
        name_prefix: Filter log groups by name prefix (optional)
        limit: Maximum number of log groups to return (default: 50)

    Returns:
        JSON string containing list of log groups with their details
    """
    if not LOGS_AVAILABLE:
        return json.dumps(
            {"error": "CloudWatch logs module not available"}, ensure_ascii=False
        )

    try:
        # Use cloudwatch_logs_tools function
        result = _list_log_groups(limit=limit, prefix=name_prefix)

        # Convert to MCP format (simplified for AI consumption)
        if isinstance(result, list) and result and "error" not in result[0]:
            simplified_groups = []
            for group in result:
                simplified_groups.append(
                    {
                        "name": group["logGroupName"],
                        "creation_time": datetime.fromtimestamp(
                            group["creationTime"] / 1000
                        ).isoformat(),
                        "retention_days": group.get("retentionInDays", "Never expire"),
                        "size_bytes": group.get("storedBytes", 0),
                    }
                )

            mcp_result = {
                "total_found": len(simplified_groups),
                "log_groups": simplified_groups,
            }
            return json.dumps(mcp_result, ensure_ascii=False, indent=2)
        else:
            return json.dumps(
                {"error": "Failed to retrieve log groups"}, ensure_ascii=False
            )

    except Exception as e:
        error_msg = f"Error listing log groups: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def list_log_streams(
    log_group_name: str, limit: int = 20, order_by: str = "LastEventTime"
) -> str:
    """
    List log streams within a log group (MCP wrapper).

    Args:
        log_group_name: Name of the log group
        limit: Maximum number of streams to return (default: 20)
        order_by: Order by 'LogStreamName' or 'LastEventTime' (default: LastEventTime)

    Returns:
        JSON string containing list of log streams
    """
    if not LOGS_AVAILABLE:
        return json.dumps(
            {"error": "CloudWatch logs module not available"}, ensure_ascii=False
        )

    try:
        # Use cloudwatch_logs_tools function
        result = _list_log_streams(log_group_name=log_group_name, limit=limit)

        # Convert to MCP format
        if isinstance(result, list) and result and "error" not in result[0]:
            simplified_streams = []
            for stream in result:
                simplified_streams.append(
                    {
                        "name": stream["logStreamName"],
                        "creation_time": datetime.fromtimestamp(
                            stream["creationTime"] / 1000
                        ).isoformat(),
                        "last_event_time": (
                            datetime.fromtimestamp(
                                stream.get("lastEventTime", 0) / 1000
                            ).isoformat()
                            if stream.get("lastEventTime")
                            else None
                        ),
                        "last_ingestion_time": (
                            datetime.fromtimestamp(
                                stream.get("lastIngestionTime", 0) / 1000
                            ).isoformat()
                            if stream.get("lastIngestionTime")
                            else None
                        ),
                    }
                )

            mcp_result = {
                "log_group": log_group_name,
                "total_found": len(simplified_streams),
                "streams": simplified_streams,
            }
            return json.dumps(mcp_result, ensure_ascii=False, indent=2)
        else:
            return json.dumps(
                {"error": f"Failed to retrieve streams for {log_group_name}"},
                ensure_ascii=False,
            )

    except Exception as e:
        error_msg = f"Error listing streams in {log_group_name}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def search_log_events(
    log_group_name: str,
    filter_pattern: str = "",
    hours_back: int = 24,
    max_events: int = 100,
) -> str:
    """
    Search for log events across streams in a log group (MCP wrapper).

    Args:
        log_group_name: Name of the log group to search
        filter_pattern: CloudWatch Logs filter pattern (optional)
        hours_back: How many hours back to search (default: 24)
        max_events: Maximum number of events to return (default: 100)

    Returns:
        JSON string containing matching log events
    """
    if not LOGS_AVAILABLE:
        return json.dumps(
            {"error": "CloudWatch logs module not available"}, ensure_ascii=False
        )

    try:
        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        # Use cloudwatch_logs_tools function
        result = _search_log_events(
            log_group_name=log_group_name,
            filter_pattern=filter_pattern,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            limit=max_events,
        )

        # Convert to MCP format
        if isinstance(result, list) and result and "error" not in result[0]:
            simplified_events = []
            for event in result:
                simplified_events.append(
                    {
                        "timestamp": datetime.fromtimestamp(
                            event["timestamp"] / 1000
                        ).isoformat(),
                        "log_stream": event["logStreamName"],
                        "message": event["message"].strip(),
                    }
                )

            mcp_result = {
                "log_group": log_group_name,
                "search_period": f"{hours_back} hours",
                "filter_pattern": filter_pattern or "No filter",
                "total_found": len(simplified_events),
                "events": simplified_events,
            }
            return json.dumps(mcp_result, ensure_ascii=False, indent=2)
        else:
            return json.dumps(
                {"error": f"Failed to search logs in {log_group_name}"},
                ensure_ascii=False,
            )

    except Exception as e:
        error_msg = f"Error searching logs in {log_group_name}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def get_recent_log_events(
    log_group_name: str, log_stream_name: str, hours_back: int = 1, max_events: int = 50
) -> str:
    """
    Get recent log events from a specific log stream (MCP wrapper).

    Args:
        log_group_name: Name of the log group
        log_stream_name: Name of the log stream
        hours_back: How many hours back to retrieve (default: 1)
        max_events: Maximum number of events to return (default: 50)

    Returns:
        JSON string containing log events
    """
    if not LOGS_AVAILABLE:
        return json.dumps(
            {"error": "CloudWatch logs module not available"}, ensure_ascii=False
        )

    try:
        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        # Use cloudwatch_logs_tools function
        result = _get_log_events(
            log_group_name=log_group_name,
            log_stream_name=log_stream_name,
            limit=max_events,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )

        # Convert to MCP format
        if isinstance(result, list) and result and "error" not in result[0]:
            simplified_events = []
            for event in result:
                simplified_events.append(
                    {
                        "timestamp": datetime.fromtimestamp(
                            event["timestamp"] / 1000
                        ).isoformat(),
                        "message": event["message"].strip(),
                    }
                )

            mcp_result = {
                "log_group": log_group_name,
                "log_stream": log_stream_name,
                "period": f"{hours_back} hours",
                "total_found": len(simplified_events),
                "events": simplified_events,
            }
            return json.dumps(mcp_result, ensure_ascii=False, indent=2)
        else:
            return json.dumps(
                {
                    "error": f"Failed to get events from {log_group_name}/{log_stream_name}"
                },
                ensure_ascii=False,
            )

    except Exception as e:
        error_msg = (
            f"Error getting events from {log_group_name}/{log_stream_name}: {str(e)}"
        )
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def analyze_log_patterns(log_group_name: str, hours_back: int = 24) -> str:
    """
    Analyze log patterns and statistics for a log group to identify health issues.

    This function performs intelligent pattern analysis on CloudWatch logs to detect
    error patterns, warning trends, and overall system health. It samples events from
    the most recent log streams and categorizes them by severity.

    Features:
    - Samples up to 500 events from the 5 most recent log streams
    - Identifies error patterns (error, exception, failed keywords)
    - Tracks warning patterns for early issue detection
    - Provides health status assessment (HEALTHY/WARNING/ERROR)
    - Returns frequency counts for top error and warning patterns

    Args:
        log_group_name: Name of the CloudWatch log group to analyze
        hours_back: Time window in hours for analysis (default: 24)

    Returns:
        JSON string containing:
        - health_status: Overall health assessment
        - total_events_sampled: Number of log events analyzed
        - active_streams: Number of log streams with recent activity
        - top_error_patterns: Most frequent error-related terms with counts
        - top_warning_patterns: Most frequent warning-related terms with counts
        - analysis_period: Time range covered by the analysis

    Example:
        >>> result = analyze_log_patterns("/aws/lambda/my-function", hours_back=12)
        >>> data = json.loads(result)
        >>> print(f"Health: {data['health_status']}")
        Health: ERROR
    """
    if not LOGS_AVAILABLE:
        return json.dumps(
            {"error": "CloudWatch logs module not available"}, ensure_ascii=False
        )

    try:
        # This function remains in aws_utils.py as it's MCP-specific
        from .cloudwatch_logs_tools import _get_cloudwatch_logs_client

        client = _get_cloudwatch_logs_client()

        # Get recent streams
        streams_response = client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy="LastEventTime",
            limit=10,
            descending=True,
        )

        streams = streams_response.get("logStreams", [])

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        # Sample events from multiple streams
        total_events = 0
        error_patterns = {}
        warning_patterns = {}
        active_streams = 0

        for stream in streams[:5]:  # Analyze top 5 most recent streams
            try:
                events_response = client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream["logStreamName"],
                    startTime=int(start_time.timestamp() * 1000),
                    endTime=int(end_time.timestamp() * 1000),
                    limit=100,
                )

                events = events_response.get("events", [])
                if events:
                    active_streams += 1
                    total_events += len(events)

                    # Simple pattern analysis
                    for event in events:
                        message = event["message"].lower()
                        if (
                            "error" in message
                            or "exception" in message
                            or "failed" in message
                        ):
                            for word in message.split():
                                if "error" in word or "exception" in word:
                                    error_patterns[word] = (
                                        error_patterns.get(word, 0) + 1
                                    )
                        elif "warn" in message:
                            for word in message.split():
                                if "warn" in word:
                                    warning_patterns[word] = (
                                        warning_patterns.get(word, 0) + 1
                                    )

            except Exception:
                continue  # Skip problematic streams

        # Compile analysis
        analysis = {
            "log_group": log_group_name,
            "analysis_period": f"{hours_back} hours",
            "total_events_sampled": total_events,
            "active_streams": active_streams,
            "top_error_patterns": dict(
                sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "top_warning_patterns": dict(
                sorted(warning_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "health_status": (
                "ERROR"
                if error_patterns
                else ("WARNING" if warning_patterns else "HEALTHY")
            ),
        }

        logger.info(f"Analyzed {total_events} events from {log_group_name}")
        return json.dumps(analysis, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"Error analyzing patterns in {log_group_name}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


# Tool function list for easy import by agents
CLOUDWATCH_TOOLS = [
    list_log_groups,
    list_log_streams,
    search_log_events,
    get_recent_log_events,
    analyze_log_patterns,
]

# Add metrics tools if available
if METRICS_AVAILABLE:
    from .cloudwatch_metrics_tools import get_metric_statistics, list_available_metrics

    CLOUDWATCH_TOOLS.extend([get_metric_statistics, list_available_metrics])


def get_cloudwatch_tools():
    """
    Get all available CloudWatch tool functions for AutoGen agents.

    Returns a list of function references that can be used directly by AutoGen
    agents for CloudWatch operations. These functions return structured data
    optimized for AI consumption.

    Returns:
        List of CloudWatch tool functions including:
        - Log group and stream listing
        - Log event searching and retrieval
        - Pattern analysis for health monitoring
        - Metrics retrieval (if metrics module available)
    """
    return CLOUDWATCH_TOOLS


def get_all_cloudwatch_tools():
    """
    Get comprehensive list of all CloudWatch tools (logs + metrics).

    Returns:
        Dictionary with logs and metrics tools
    """
    tools = {
        "logs": [
            list_log_groups,
            list_log_streams,
            search_log_events,
            get_recent_log_events,
            analyze_log_patterns,
        ]
    }

    if METRICS_AVAILABLE:
        tools["metrics"] = get_cloudwatch_metrics_tools()

    return tools
