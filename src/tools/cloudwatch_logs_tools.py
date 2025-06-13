"""
CloudWatch Logs Tools for AutoGen Agents.

This module provides CloudWatch Logs functionality as AutoGen Tools,
allowing agents to directly access and query CloudWatch Logs.
"""

import boto3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from autogen_core.tools import FunctionTool
import json
import logging

logger = logging.getLogger(__name__)


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
        client = boto3.client("logs")
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
        client = boto3.client("logs")
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
        client = boto3.client("logs")
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
        client = boto3.client("logs")

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
        client = boto3.client("logs")

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
        client = boto3.client("logs")

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
    FunctionTool.from_function(list_log_groups),
    FunctionTool.from_function(list_log_streams),
    FunctionTool.from_function(get_log_events),
    FunctionTool.from_function(search_log_events),
    FunctionTool.from_function(start_logs_insights_query),
    FunctionTool.from_function(get_logs_insights_results),
]


def get_cloudwatch_logs_tools() -> List[FunctionTool]:
    """Get all CloudWatch Logs tools for use with AutoGen agents."""
    return cloudwatch_logs_tools
