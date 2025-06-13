"""
AWS CloudWatch Logs tools for AutoGen agents.

This module provides simple, focused functions that can be used as tools
by AutoGen agents for CloudWatch Logs investigation.
"""

import boto3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Union
from botocore.exceptions import ClientError, NoCredentialsError
import os

# Import new settings system
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


# Configure logging
logger = logging.getLogger(__name__)

# Import new CloudWatch metrics module
try:
    from .cloudwatch_metrics_tools import (
        create_cloudwatch_metrics_client,
        get_cloudwatch_metrics_tools,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("CloudWatch metrics module not available")

# Global client instance (initialized when first used)
_logs_client = None

# Global CloudWatch metrics client instance
_cloudwatch_metrics_client = None


def _get_logs_client():
    """Get or create CloudWatch Logs client using new settings system."""
    global _logs_client
    if _logs_client is None:
        try:
            # Get settings from new configuration system
            settings = get_settings()

            # Create session with settings
            session_kwargs = {}
            if settings.aws.profile_name:
                session_kwargs["profile_name"] = settings.aws.profile_name
            if settings.aws.region_name:
                session_kwargs["region_name"] = settings.aws.region_name

            session = boto3.Session(**session_kwargs)
            _logs_client = session.client("logs")

            # Test connection
            _logs_client.describe_log_groups(limit=1)
            logger.info(
                f"Connected to CloudWatch Logs in region: {_logs_client.meta.region_name}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch Logs client: {e}")
            raise

    return _logs_client


def create_cloudwatch_client(
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
        # Get settings if parameters not provided
        if region_name is None or profile_name is None:
            settings = get_settings()
            region_name = region_name or settings.aws.region_name
            profile_name = profile_name or settings.aws.profile_name

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
        logger.error(f"Failed to create CloudWatch client: {e}")
        raise


def list_log_groups(name_prefix: str = "", limit: int = 50) -> str:
    """
    List CloudWatch log groups.

    Args:
        name_prefix: Filter log groups by name prefix (optional)
        limit: Maximum number of log groups to return (default: 50)

    Returns:
        JSON string containing list of log groups with their details
    """
    try:
        client = _get_logs_client()

        kwargs = {"limit": limit}
        if name_prefix:
            kwargs["logGroupNamePrefix"] = name_prefix

        response = client.describe_log_groups(**kwargs)
        log_groups = response.get("logGroups", [])

        # Simplify the response for AI agent consumption
        simplified_groups = []
        for group in log_groups:
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

        result = {
            "total_found": len(simplified_groups),
            "log_groups": simplified_groups,
        }

        logger.info(f"Found {len(simplified_groups)} log groups")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"Error listing log groups: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def list_log_streams(
    log_group_name: str, limit: int = 20, order_by: str = "LastEventTime"
) -> str:
    """
    List log streams within a log group.

    Args:
        log_group_name: Name of the log group
        limit: Maximum number of streams to return (default: 20)
        order_by: Order by 'LogStreamName' or 'LastEventTime' (default: LastEventTime)

    Returns:
        JSON string containing list of log streams
    """
    try:
        client = _get_logs_client()

        response = client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy=order_by,
            limit=limit,
            descending=True,  # Most recent first for LastEventTime
        )

        streams = response.get("logStreams", [])

        # Simplify for AI consumption
        simplified_streams = []
        for stream in streams:
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

        result = {
            "log_group": log_group_name,
            "total_found": len(simplified_streams),
            "streams": simplified_streams,
        }

        logger.info(f"Found {len(simplified_streams)} streams in {log_group_name}")
        return json.dumps(result, ensure_ascii=False, indent=2)

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
    Search for log events across streams in a log group.

    Args:
        log_group_name: Name of the log group to search
        filter_pattern: CloudWatch Logs filter pattern (optional)
        hours_back: How many hours back to search (default: 24)
        max_events: Maximum number of events to return (default: 100)

    Returns:
        JSON string containing matching log events
    """
    try:
        client = _get_logs_client()

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        kwargs = {
            "logGroupName": log_group_name,
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000),
            "limit": max_events,
        }

        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern

        response = client.filter_log_events(**kwargs)
        events = response.get("events", [])

        # Simplify events for AI consumption
        simplified_events = []
        for event in events:
            simplified_events.append(
                {
                    "timestamp": datetime.fromtimestamp(
                        event["timestamp"] / 1000
                    ).isoformat(),
                    "log_stream": event["logStreamName"],
                    "message": event["message"].strip(),
                }
            )

        result = {
            "log_group": log_group_name,
            "search_period": f"{hours_back} hours",
            "filter_pattern": filter_pattern or "No filter",
            "total_found": len(simplified_events),
            "events": simplified_events,
        }

        logger.info(f"Found {len(simplified_events)} events in {log_group_name}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"Error searching logs in {log_group_name}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def get_recent_log_events(
    log_group_name: str, log_stream_name: str, hours_back: int = 1, max_events: int = 50
) -> str:
    """
    Get recent log events from a specific log stream.

    Args:
        log_group_name: Name of the log group
        log_stream_name: Name of the log stream
        hours_back: How many hours back to retrieve (default: 1)
        max_events: Maximum number of events to return (default: 50)

    Returns:
        JSON string containing log events
    """
    try:
        client = _get_logs_client()

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        response = client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            startTime=int(start_time.timestamp() * 1000),
            endTime=int(end_time.timestamp() * 1000),
            limit=max_events,
            startFromHead=False,  # Get most recent first
        )

        events = response.get("events", [])

        # Simplify for AI consumption
        simplified_events = []
        for event in events:
            simplified_events.append(
                {
                    "timestamp": datetime.fromtimestamp(
                        event["timestamp"] / 1000
                    ).isoformat(),
                    "message": event["message"].strip(),
                }
            )

        result = {
            "log_group": log_group_name,
            "log_stream": log_stream_name,
            "period": f"{hours_back} hours",
            "total_found": len(simplified_events),
            "events": simplified_events,
        }

        logger.info(
            f"Retrieved {len(simplified_events)} events from {log_group_name}/{log_stream_name}"
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = (
            f"Error getting events from {log_group_name}/{log_stream_name}: {str(e)}"
        )
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def analyze_log_patterns(log_group_name: str, hours_back: int = 24) -> str:
    """
    Analyze log patterns and statistics for a log group.

    Args:
        log_group_name: Name of the log group to analyze
        hours_back: How many hours back to analyze (default: 24)

    Returns:
        JSON string containing pattern analysis
    """
    try:
        client = _get_logs_client()

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


def _get_cloudwatch_metrics_client():
    """Get or create CloudWatch metrics client using settings system."""
    global _cloudwatch_metrics_client
    if _cloudwatch_metrics_client is None:
        try:
            # Get settings from configuration system
            settings = get_settings()

            # Create session with settings
            session_kwargs = {}
            if settings.aws.profile_name:
                session_kwargs["profile_name"] = settings.aws.profile_name
            if settings.aws.region_name:
                session_kwargs["region_name"] = settings.aws.region_name

            session = boto3.Session(**session_kwargs)
            _cloudwatch_metrics_client = session.client("cloudwatch")

            # Test connection
            _cloudwatch_metrics_client.list_metrics(MaxRecords=1)
            logger.info(
                f"Connected to CloudWatch Metrics in region: {_cloudwatch_metrics_client.meta.region_name}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch Metrics client: {e}")
            raise

    return _cloudwatch_metrics_client


def get_cloudwatch_metrics_client():
    """
    Get CloudWatch metrics client for direct use.

    Returns:
        CloudWatch client for metrics operations
    """
    return _get_cloudwatch_metrics_client()


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
    """Return list of all CloudWatch tool functions for AutoGen agents."""
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
