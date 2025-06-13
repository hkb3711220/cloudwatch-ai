"""
CloudWatch Logs Tools for AutoGen Agents

This module provides comprehensive CloudWatch Logs functionality specifically designed
for AutoGen agents and AI-driven log analysis. It offers direct access to AWS CloudWatch
Logs with intelligent data formatting and error handling optimized for AI consumption.

Core Capabilities:
- Log group and stream discovery with metadata enrichment
- Event retrieval with flexible time-based filtering
- Advanced log searching using CloudWatch filter patterns
- CloudWatch Logs Insights query execution and result retrieval
- Automatic timestamp conversion and data normalization
- Robust error handling with detailed error context

Key Features:
- **AI-Optimized Responses**: All functions return List[Dict] structures that are
  easily consumable by AI agents for further analysis
- **Flexible Time Handling**: Supports both Unix timestamps and ISO format strings
- **Intelligent Defaults**: Sensible default values for common use cases
- **Connection Management**: Automatic AWS client creation with settings integration
- **Error Resilience**: Graceful error handling with informative error messages

Architecture:
This module serves as the core implementation layer for CloudWatch Logs operations.
It's designed to be used directly by AutoGen agents or wrapped by MCP interface
layers (like aws_utils.py) for different consumption patterns.

Usage Examples:
    # List log groups
    groups = list_log_groups(limit=10, prefix="/aws/lambda")

    # Search for errors in the last hour
    errors = search_log_events(
        "/aws/lambda/my-function",
        "ERROR",
        start_time="2023-01-01T10:00:00Z"
    )

    # Run Logs Insights query
    query_result = start_logs_insights_query(
        ["/aws/lambda/my-function"],
        "fields @timestamp, @message | filter @message like /ERROR/"
    )

Dependencies:
- boto3: AWS SDK for Python
- AWS credentials configured via environment, IAM roles, or AWS profiles
- Appropriate CloudWatch Logs permissions (logs:DescribeLogGroups, logs:FilterLogEvents, etc.)
"""

import boto3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
import logging
import os

# Import settings system
try:
    from ..config.settings import get_settings
except ImportError:
    try:
        from src.config.settings import get_settings
    except ImportError:
        print("Warning: Could not import settings. Using default configuration.")

        def get_settings():
            class DefaultSettings:
                class aws:
                    region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                    profile_name = os.getenv("AWS_PROFILE")

            return DefaultSettings()


logger = logging.getLogger(__name__)

# Global client instance (initialized when first used)
_cloudwatch_logs_client = None


def _get_cloudwatch_logs_client():
    """Get or create CloudWatch Logs client using settings configuration."""
    global _cloudwatch_logs_client
    if _cloudwatch_logs_client is None:
        try:
            settings = get_settings()

            # Create session with settings configuration
            session_kwargs = {}
            if settings.aws.profile_name:
                session_kwargs["profile_name"] = settings.aws.profile_name
            if settings.aws.region_name:
                session_kwargs["region_name"] = settings.aws.region_name

            session = boto3.Session(**session_kwargs)
            _cloudwatch_logs_client = session.client("logs")

            # Test connection
            _cloudwatch_logs_client.describe_log_groups(limit=1)
            logger.info(
                f"Connected to CloudWatch Logs in region: {_cloudwatch_logs_client.meta.region_name}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch Logs client: {e}")
            raise

    return _cloudwatch_logs_client


def create_cloudwatch_logs_client(
    region_name: Optional[str] = None, profile_name: Optional[str] = None
):
    """
    Create a CloudWatch Logs client with specified or default configuration.

    Args:
        region_name: AWS region name (optional, uses settings if not provided)
        profile_name: AWS profile name (optional, uses settings if not provided)

    Returns:
        CloudWatch Logs client
    """
    try:
        settings = get_settings()

        # Use provided parameters or fall back to settings
        if region_name is None:
            region_name = settings.aws.region_name
        if profile_name is None:
            profile_name = settings.aws.profile_name

        # Create session
        session_kwargs = {}
        if profile_name:
            session_kwargs["profile_name"] = profile_name
        if region_name:
            session_kwargs["region_name"] = region_name

        session = boto3.Session(**session_kwargs)
        client = session.client("logs")

        # Test connection
        client.describe_log_groups(limit=1)

        return client

    except Exception as e:
        logger.error(f"Failed to create CloudWatch Logs client: {e}")
        raise


# CloudWatch Logs tool functions
def list_log_groups(
    limit: int = 50, prefix: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List CloudWatch log groups with optional filtering.

    Args:
        limit: Maximum number of log groups to return (default: 50)
        prefix: Optional prefix to filter log group names

    Returns:
        List of log group dictionaries with metadata

    Example:
        >>> list_log_groups(limit=10, prefix="/aws/lambda")
        [{"logGroupName": "/aws/lambda/my-function", "creationTime": 1234567890, ...}]
    """
    try:
        client = _get_cloudwatch_logs_client()
        kwargs = {"limit": limit}

        if prefix:
            kwargs["logGroupNamePrefix"] = prefix

        response = client.describe_log_groups(**kwargs)
        log_groups = response.get("logGroups", [])

        # Simplify the response for better agent consumption
        simplified_groups = []
        for group in log_groups:
            simplified_groups.append(
                {
                    "logGroupName": group.get("logGroupName"),
                    "creationTime": group.get("creationTime"),
                    "retentionInDays": group.get("retentionInDays"),
                    "storedBytes": group.get("storedBytes", 0),
                    "metricFilterCount": group.get("metricFilterCount", 0),
                }
            )

        logger.info(f"Retrieved {len(simplified_groups)} log groups")
        return simplified_groups

    except Exception as e:
        logger.error(f"Error listing log groups: {str(e)}")
        return [{"error": f"Failed to list log groups: {str(e)}"}]


def list_log_streams(
    log_group_name: str, limit: int = 50, prefix: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List log streams within a log group.

    Args:
        log_group_name: Name of the log group
        limit: Maximum number of log streams to return (default: 50)
        prefix: Optional prefix to filter log stream names

    Returns:
        List of log stream dictionaries with metadata

    Example:
        >>> list_log_streams("/aws/lambda/my-function", limit=10)
        [{"logStreamName": "2023/01/01/[$LATEST]abcd1234", "creationTime": 1234567890, ...}]
    """
    try:
        client = _get_cloudwatch_logs_client()
        kwargs = {
            "logGroupName": log_group_name,
            "limit": limit,
            "orderBy": "LastEventTime",
            "descending": True,
        }

        if prefix:
            kwargs["logStreamNamePrefix"] = prefix

        response = client.describe_log_streams(**kwargs)
        log_streams = response.get("logStreams", [])

        # Simplify the response
        simplified_streams = []
        for stream in log_streams:
            simplified_streams.append(
                {
                    "logStreamName": stream.get("logStreamName"),
                    "creationTime": stream.get("creationTime"),
                    "firstEventTime": stream.get("firstEventTime"),
                    "lastEventTime": stream.get("lastEventTime"),
                    "lastIngestionTime": stream.get("lastIngestionTime"),
                    "uploadSequenceToken": stream.get("uploadSequenceToken"),
                    "storedBytes": stream.get("storedBytes", 0),
                }
            )

        logger.info(
            f"Retrieved {len(simplified_streams)} log streams from {log_group_name}"
        )
        return simplified_streams

    except Exception as e:
        logger.error(f"Error listing log streams for {log_group_name}: {str(e)}")
        return [{"error": f"Failed to list log streams for {log_group_name}: {str(e)}"}]


def get_log_events(
    log_group_name: str,
    log_stream_name: str,
    limit: int = 100,
    start_time: Optional[Union[int, str]] = None,
    end_time: Optional[Union[int, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Get log events from a specific log stream.

    Args:
        log_group_name: Name of the log group
        log_stream_name: Name of the log stream
        limit: Maximum number of events to return (default: 100)
        start_time: Start time (Unix timestamp in milliseconds or ISO string)
        end_time: End time (Unix timestamp in milliseconds or ISO string)

    Returns:
        List of log event dictionaries

    Example:
        >>> get_log_events("/aws/lambda/my-function", "2023/01/01/[$LATEST]abcd1234", limit=50)
        [{"timestamp": 1234567890000, "message": "START RequestId: ...", "ingestionTime": 1234567891000}]
    """
    try:
        client = _get_cloudwatch_logs_client()
        kwargs = {
            "logGroupName": log_group_name,
            "logStreamName": log_stream_name,
            "limit": limit,
            "startFromHead": False,  # Get newest events first
        }

        # Handle time parameters
        if start_time:
            if isinstance(start_time, str):
                start_time = int(
                    datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    ).timestamp()
                    * 1000
                )
            kwargs["startTime"] = start_time

        if end_time:
            if isinstance(end_time, str):
                end_time = int(
                    datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp()
                    * 1000
                )
            kwargs["endTime"] = end_time

        response = client.get_log_events(**kwargs)
        events = response.get("events", [])

        # Convert timestamps to readable format for agents
        for event in events:
            event["timestamp_readable"] = datetime.fromtimestamp(
                event["timestamp"] / 1000
            ).isoformat()
            event["ingestionTime_readable"] = datetime.fromtimestamp(
                event["ingestionTime"] / 1000
            ).isoformat()

        logger.info(
            f"Retrieved {len(events)} log events from {log_group_name}/{log_stream_name}"
        )
        return events

    except Exception as e:
        logger.error(
            f"Error getting log events from {log_group_name}/{log_stream_name}: {str(e)}"
        )
        return [
            {
                "error": f"Failed to get log events from {log_group_name}/{log_stream_name}: {str(e)}"
            }
        ]


def search_log_events(
    log_group_name: str,
    filter_pattern: str,
    start_time: Optional[Union[int, str]] = None,
    end_time: Optional[Union[int, str]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Search log events using CloudWatch Logs filter patterns.

    Args:
        log_group_name: Name of the log group to search
        filter_pattern: CloudWatch Logs filter pattern (e.g., "ERROR", "[timestamp,request_id=\"ERROR\"]")
        start_time: Start time (Unix timestamp in milliseconds or ISO string, defaults to 24 hours ago)
        end_time: End time (Unix timestamp in milliseconds or ISO string, defaults to now)
        limit: Maximum number of events to return (default: 100)

    Returns:
        List of matching log event dictionaries

    Example:
        >>> search_log_events("/aws/lambda/my-function", "ERROR", limit=50)
        [{"timestamp": 1234567890000, "message": "ERROR: Something went wrong", ...}]
    """
    try:
        client = _get_cloudwatch_logs_client()

        # Set default time range if not provided (last 24 hours)
        if not start_time:
            start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
        elif isinstance(start_time, str):
            start_time = int(
                datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp()
                * 1000
            )

        if not end_time:
            end_time = int(datetime.now().timestamp() * 1000)
        elif isinstance(end_time, str):
            end_time = int(
                datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp()
                * 1000
            )

        response = client.filter_log_events(
            logGroupName=log_group_name,
            filterPattern=filter_pattern,
            startTime=start_time,
            endTime=end_time,
            limit=limit,
        )

        events = response.get("events", [])

        # Add readable timestamps and enrich with metadata
        for event in events:
            event["timestamp_readable"] = datetime.fromtimestamp(
                event["timestamp"] / 1000
            ).isoformat()
            event["ingestionTime_readable"] = datetime.fromtimestamp(
                event["ingestionTime"] / 1000
            ).isoformat()
            # Add search metadata
            event["search_filter"] = filter_pattern
            event["log_group"] = log_group_name

        logger.info(
            f"Found {len(events)} matching events in {log_group_name} with pattern '{filter_pattern}'"
        )
        return events

    except Exception as e:
        logger.error(
            f"Error searching log events in {log_group_name} with pattern '{filter_pattern}': {str(e)}"
        )
        return [{"error": f"Failed to search log events in {log_group_name}: {str(e)}"}]


def start_logs_insights_query(
    log_group_names: List[str],
    query_string: str,
    start_time: Optional[Union[int, str]] = None,
    end_time: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """
    Start a CloudWatch Logs Insights query.

    Args:
        log_group_names: List of log group names to query
        query_string: CloudWatch Logs Insights query string
        start_time: Start time (Unix timestamp in seconds or ISO string, defaults to 24 hours ago)
        end_time: End time (Unix timestamp in seconds or ISO string, defaults to now)

    Returns:
        Dictionary with query ID and status

    Example:
        >>> start_logs_insights_query(["/aws/lambda/my-function"], "fields @timestamp, @message | filter @message like /ERROR/")
        {"queryId": "abcd-1234-efgh-5678", "status": "Running"}
    """
    try:
        client = _get_cloudwatch_logs_client()

        # Set default time range if not provided (last 24 hours)
        if not start_time:
            start_time = int((datetime.now() - timedelta(hours=24)).timestamp())
        elif isinstance(start_time, str):
            start_time = int(
                datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp()
            )

        if not end_time:
            end_time = int(datetime.now().timestamp())
        elif isinstance(end_time, str):
            end_time = int(
                datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp()
            )

        response = client.start_query(
            logGroupNames=log_group_names,
            startTime=start_time,
            endTime=end_time,
            queryString=query_string,
        )

        result = {
            "queryId": response["queryId"],
            "status": "Running",
            "log_groups": log_group_names,
            "query": query_string,
            "start_time": start_time,
            "end_time": end_time,
        }

        logger.info(
            f"Started Logs Insights query {response['queryId']} for {len(log_group_names)} log groups"
        )
        return result

    except Exception as e:
        logger.error(f"Error starting Logs Insights query: {str(e)}")
        return {"error": f"Failed to start Logs Insights query: {str(e)}"}


def get_logs_insights_results(query_id: str) -> Dict[str, Any]:
    """
    Get results from a CloudWatch Logs Insights query.

    Args:
        query_id: Query ID returned from start_logs_insights_query

    Returns:
        Dictionary with query results and metadata

    Example:
        >>> get_logs_insights_results("abcd-1234-efgh-5678")
        {"status": "Complete", "results": [...], "statistics": {...}}
    """
    try:
        client = _get_cloudwatch_logs_client()

        response = client.get_query_results(queryId=query_id)

        result = {
            "queryId": query_id,
            "status": response["status"],
            "results": response.get("results", []),
            "statistics": response.get("statistics", {}),
            "encrypted": response.get("encryptionKey") is not None,
        }

        # Add readable format for results
        if result["results"]:
            result["result_count"] = len(result["results"])

        logger.info(f"Retrieved results for query {query_id}: {result['status']}")
        return result

    except Exception as e:
        logger.error(f"Error getting results for query {query_id}: {str(e)}")
        return {"error": f"Failed to get results for query {query_id}: {str(e)}"}


# Create AutoGen FunctionTools
cloudwatch_logs_tools = [
    list_log_groups,
    list_log_streams,
    get_log_events,
    search_log_events,
    start_logs_insights_query,
    get_logs_insights_results,
]


def get_cloudwatch_logs_tools():
    """Get all CloudWatch Logs tools for use with AutoGen agents."""
    return cloudwatch_logs_tools
