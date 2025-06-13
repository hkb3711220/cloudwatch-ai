"""
AWS CloudWatch Metrics tools for AutoGen agents.

This module provides functions to retrieve CloudWatch metrics data
in AI-friendly formats for analysis by AutoGen agents.
"""

import boto3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Union
from botocore.exceptions import ClientError, NoCredentialsError
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


# Configure logging
logger = logging.getLogger(__name__)

# Global client instance (initialized when first used)
_cloudwatch_client = None


def _get_cloudwatch_client():
    """Get or create CloudWatch client using settings system."""
    global _cloudwatch_client
    if _cloudwatch_client is None:
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
            _cloudwatch_client = session.client("cloudwatch")

            # Test connection
            _cloudwatch_client.list_metrics(MaxRecords=1)
            logger.info(
                f"Connected to CloudWatch in region: {_cloudwatch_client.meta.region_name}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
            raise

    return _cloudwatch_client


def create_cloudwatch_metrics_client(
    region_name: Optional[str] = None, profile_name: Optional[str] = None
):
    """
    Create a CloudWatch client with specified or default configuration.

    Args:
        region_name: AWS region name (optional, uses settings if not provided)
        profile_name: AWS profile name (optional, uses settings if not provided)

    Returns:
        CloudWatch client
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
        client = session.client("cloudwatch")

        # Test connection
        client.list_metrics(MaxRecords=1)

        return client

    except Exception as e:
        logger.error(f"Failed to create CloudWatch metrics client: {e}")
        raise


def get_metric_statistics(
    namespace: str,
    metric_name: str,
    dimensions: List[Dict[str, str]] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    period: int = 300,
    statistics: List[str] = None,
) -> str:
    """
    Retrieve CloudWatch metric statistics for a specified metric.

    Args:
        namespace: AWS service namespace (e.g., 'AWS/EC2', 'AWS/Lambda')
        metric_name: Name of the metric (e.g., 'CPUUtilization', 'Duration')
        dimensions: List of dimension dictionaries [{'Name': 'InstanceId', 'Value': 'i-1234567890abcdef0'}]
        start_time: Start time for metrics (default: 24 hours ago)
        end_time: End time for metrics (default: now)
        period: Period in seconds for data points (default: 300 = 5 minutes)
        statistics: List of statistics to retrieve (default: ['Average', 'Maximum', 'Minimum'])

    Returns:
        JSON string containing metric data in AI-friendly format
    """
    try:
        client = _get_cloudwatch_client()

        # Set default time range (last 24 hours)
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(hours=24)

        # Set default statistics
        if statistics is None:
            statistics = ["Average", "Maximum", "Minimum"]

        # Set default dimensions
        if dimensions is None:
            dimensions = []

        # Get metric statistics
        response = client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=statistics,
        )

        # Sort datapoints by timestamp
        datapoints = sorted(
            response.get("Datapoints", []), key=lambda x: x["Timestamp"]
        )

        # Convert to AI-friendly format
        formatted_datapoints = []
        for point in datapoints:
            formatted_point = {
                "timestamp": point["Timestamp"].isoformat(),
                "unit": point.get("Unit", "None"),
            }

            # Add all available statistics
            for stat in statistics:
                if stat in point:
                    formatted_point[stat.lower()] = point[stat]

            formatted_datapoints.append(formatted_point)

        result = {
            "namespace": namespace,
            "metric_name": metric_name,
            "dimensions": dimensions,
            "period_seconds": period,
            "statistics": statistics,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_datapoints": len(formatted_datapoints),
            "datapoints": formatted_datapoints,
        }

        logger.info(
            f"Retrieved {len(formatted_datapoints)} datapoints for {namespace}/{metric_name}"
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"Error retrieving metric statistics for {namespace}/{metric_name}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def list_available_metrics(
    namespace: str = None,
    metric_name: str = None,
    dimensions: List[Dict[str, str]] = None,
) -> str:
    """
    List available CloudWatch metrics, optionally filtered by namespace, metric name, or dimensions.

    Args:
        namespace: AWS service namespace to filter by (optional)
        metric_name: Metric name to filter by (optional)
        dimensions: Dimensions to filter by (optional)

    Returns:
        JSON string containing list of available metrics
    """
    try:
        client = _get_cloudwatch_client()

        kwargs = {}
        if namespace:
            kwargs["Namespace"] = namespace
        if metric_name:
            kwargs["MetricName"] = metric_name
        if dimensions:
            kwargs["Dimensions"] = dimensions

        response = client.list_metrics(**kwargs)
        metrics = response.get("Metrics", [])

        # Format for AI consumption
        formatted_metrics = []
        for metric in metrics:
            formatted_metric = {
                "namespace": metric["Namespace"],
                "metric_name": metric["MetricName"],
                "dimensions": metric.get("Dimensions", []),
            }
            formatted_metrics.append(formatted_metric)

        result = {"total_metrics": len(formatted_metrics), "metrics": formatted_metrics}

        logger.info(f"Found {len(formatted_metrics)} available metrics")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"Error listing available metrics: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


def get_cloudwatch_metrics_tools():
    """
    Get list of available CloudWatch metrics tools for AutoGen agents.

    Returns:
        List of tool dictionaries for AutoGen FunctionTool
    """
    return [
        {
            "name": "get_metric_statistics",
            "description": "Retrieve CloudWatch metric statistics for any AWS service",
            "function": get_metric_statistics,
        },
        {
            "name": "list_available_metrics",
            "description": "List available CloudWatch metrics with optional filtering",
            "function": list_available_metrics,
        },
    ]
