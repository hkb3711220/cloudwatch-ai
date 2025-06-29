"""
CloudWatch Metrics Lambda Function Handler

Lambda function for CloudWatch metrics investigation and analysis.
This function is designed to work with the Lambda MCP Server architecture.
"""

import json
import logging
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CloudWatch client
cloudwatch_client = boto3.client('cloudwatch')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for CloudWatch metrics operations
    
    Args:
        event: Lambda event containing the operation and parameters
        context: Lambda context
        
    Returns:
        Dict containing the result of the operation
    """
    try:
        # Extract operation and parameters from event
        operation = event.get('operation')
        parameters = event.get('parameters', {})
        
        logger.info(f"Processing operation: {operation} with parameters: {parameters}")
        
        # Route to appropriate handler function
        if operation == 'investigate_metrics':
            return investigate_metrics(parameters)
        elif operation == 'list_metrics':
            return list_metrics(parameters)
        elif operation == 'get_metric_statistics':
            return get_metric_statistics(parameters)
        elif operation == 'list_namespaces':
            return list_namespaces(parameters)
        elif operation == 'analyze_metric_trends':
            return analyze_metric_trends(parameters)
        elif operation == 'test_connection':
            return test_connection(parameters)
        else:
            return {
                'statusCode': 400,
                'body': {
                    'error': f'Unknown operation: {operation}',
                    'supported_operations': [
                        'investigate_metrics', 'list_metrics', 'get_metric_statistics',
                        'list_namespaces', 'analyze_metric_trends', 'test_connection'
                    ]
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'リクエスト処理中にエラーが発生しました: {str(e)}'
            }
        }


def investigate_metrics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Investigate CloudWatch metrics based on parameters"""
    try:
        namespace = params.get('namespace')
        metric_name = params.get('metric_name')
        dimensions = params.get('dimensions', [])
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        period = params.get('period', 300)
        statistics = params.get('statistics', ['Average', 'Maximum', 'Minimum'])
        
        logger.info(f"Investigating metrics: {namespace}/{metric_name}")
        
        if not namespace or not metric_name:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'namespace and metric_name parameters are required',
                    'message_ja': 'ネームスペースとメトリクス名パラメータが必要です'
                }
            }
        
        # Parse time range
        if start_time and end_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
        
        # Parse dimensions if string format
        if isinstance(dimensions, str):
            parsed_dimensions = []
            for dim_pair in dimensions.split(','):
                if '=' in dim_pair:
                    name, value = dim_pair.strip().split('=', 1)
                    parsed_dimensions.append({'Name': name.strip(), 'Value': value.strip()})
            dimensions = parsed_dimensions
        
        # Get metric statistics
        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_dt,
            EndTime=end_dt,
            Period=period,
            Statistics=statistics
        )
        
        datapoints = response.get('Datapoints', [])
        
        # Sort datapoints by timestamp
        datapoints.sort(key=lambda x: x['Timestamp'])
        
        # Format datapoints
        formatted_datapoints = []
        for dp in datapoints:
            formatted_dp = {
                'timestamp': dp['Timestamp'].isoformat(),
                'unit': dp.get('Unit', 'None')
            }
            for stat in statistics:
                if stat in dp:
                    formatted_dp[stat.lower()] = dp[stat]
            formatted_datapoints.append(formatted_dp)
        
        # Calculate summary statistics
        if datapoints:
            values = [dp.get('Average', dp.get('Value', 0)) for dp in datapoints if 'Average' in dp or 'Value' in dp]
            if values:
                summary_stats = {
                    'min_value': min(values),
                    'max_value': max(values),
                    'avg_value': sum(values) / len(values),
                    'total_datapoints': len(values)
                }
            else:
                summary_stats = {'total_datapoints': len(datapoints)}
        else:
            summary_stats = {'total_datapoints': 0}
        
        result = {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'summary': {
                    'namespace': namespace,
                    'metric_name': metric_name,
                    'dimensions': dimensions,
                    'time_range': f"{start_dt.isoformat()} to {end_dt.isoformat()}",
                    'period_seconds': period,
                    'statistics': statistics,
                    **summary_stats
                },
                'datapoints': formatted_datapoints,
                'message_ja': f'CloudWatchメトリクス調査が完了しました。{len(datapoints)}個のデータポイントが見つかりました。'
            }
        }
        
        logger.info(f"Metrics investigation completed: {len(datapoints)} datapoints found")
        return result
        
    except Exception as e:
        logger.error(f"Metrics investigation failed: {e}")
        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'message': f'Metrics investigation failed: {str(e)}',
                'message_ja': f'メトリクス調査に失敗しました: {str(e)}'
            }
        }


def list_metrics(params: Dict[str, Any]) -> Dict[str, Any]:
    """List available CloudWatch metrics"""
    try:
        namespace = params.get('namespace')
        metric_name = params.get('metric_name')
        limit = params.get('limit', 100)
        
        # Build list_metrics parameters
        list_params = {}
        if namespace:
            list_params['Namespace'] = namespace
        if metric_name:
            list_params['MetricName'] = metric_name
        
        paginator = cloudwatch_client.get_paginator('list_metrics')
        page_iterator = paginator.paginate(**list_params)
        
        metrics = []
        count = 0
        for page in page_iterator:
            for metric in page['Metrics']:
                if count >= limit:
                    break
                metrics.append({
                    'namespace': metric['Namespace'],
                    'metric_name': metric['MetricName'],
                    'dimensions': metric.get('Dimensions', [])
                })
                count += 1
            if count >= limit:
                break
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'total_metrics': len(metrics),
                'metrics': metrics,
                'message_ja': f'{len(metrics)}個のメトリクスが見つかりました'
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list metrics: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'メトリクスの取得に失敗しました: {str(e)}'
            }
        }


def get_metric_statistics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get statistics for a specific metric"""
    try:
        namespace = params.get('namespace')
        metric_name = params.get('metric_name')
        dimensions = params.get('dimensions', [])
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        period = params.get('period', 300)
        statistics = params.get('statistics', ['Average'])
        
        if not namespace or not metric_name:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'namespace and metric_name parameters are required',
                    'message_ja': 'ネームスペースとメトリクス名パラメータが必要です'
                }
            }
        
        # Parse time range
        if start_time and end_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=1)
        
        # Parse dimensions if string format
        if isinstance(dimensions, str):
            parsed_dimensions = []
            for dim_pair in dimensions.split(','):
                if '=' in dim_pair:
                    name, value = dim_pair.strip().split('=', 1)
                    parsed_dimensions.append({'Name': name.strip(), 'Value': value.strip()})
            dimensions = parsed_dimensions
        
        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_dt,
            EndTime=end_dt,
            Period=period,
            Statistics=statistics
        )
        
        datapoints = response.get('Datapoints', [])
        datapoints.sort(key=lambda x: x['Timestamp'])
        
        # Format datapoints
        formatted_datapoints = []
        for dp in datapoints:
            formatted_dp = {
                'timestamp': dp['Timestamp'].isoformat(),
                'unit': dp.get('Unit', 'None')
            }
            for stat in statistics:
                if stat in dp:
                    formatted_dp[stat.lower()] = dp[stat]
            formatted_datapoints.append(formatted_dp)
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'namespace': namespace,
                'metric_name': metric_name,
                'dimensions': dimensions,
                'start_time': start_dt.isoformat(),
                'end_time': end_dt.isoformat(),
                'period': period,
                'statistics': statistics,
                'total_datapoints': len(datapoints),
                'datapoints': formatted_datapoints,
                'message_ja': f'{len(datapoints)}個のデータポイントを取得しました'
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get metric statistics: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'メトリクス統計の取得に失敗しました: {str(e)}'
            }
        }


def list_namespaces(params: Dict[str, Any]) -> Dict[str, Any]:
    """List available CloudWatch namespaces"""
    try:
        # Get unique namespaces from metrics
        paginator = cloudwatch_client.get_paginator('list_metrics')
        page_iterator = paginator.paginate()
        
        namespaces = set()
        for page in page_iterator:
            for metric in page['Metrics']:
                namespaces.add(metric['Namespace'])
        
        sorted_namespaces = sorted(list(namespaces))
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'total_namespaces': len(sorted_namespaces),
                'namespaces': sorted_namespaces,
                'message_ja': f'{len(sorted_namespaces)}個のネームスペースが見つかりました'
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list namespaces: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'ネームスペースの取得に失敗しました: {str(e)}'
            }
        }


def analyze_metric_trends(params: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze trends in metric data"""
    try:
        namespace = params.get('namespace')
        metric_name = params.get('metric_name')
        dimensions = params.get('dimensions', [])
        hours_back = params.get('hours_back', 24)
        
        if not namespace or not metric_name:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'namespace and metric_name parameters are required',
                    'message_ja': 'ネームスペースとメトリクス名パラメータが必要です'
                }
            }
        
        # Calculate time range
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(hours=hours_back)
        
        # Parse dimensions if string format
        if isinstance(dimensions, str):
            parsed_dimensions = []
            for dim_pair in dimensions.split(','):
                if '=' in dim_pair:
                    name, value = dim_pair.strip().split('=', 1)
                    parsed_dimensions.append({'Name': name.strip(), 'Value': value.strip()})
            dimensions = parsed_dimensions
        
        # Get metric statistics
        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_dt,
            EndTime=end_dt,
            Period=3600,  # 1 hour periods for trend analysis
            Statistics=['Average', 'Maximum', 'Minimum']
        )
        
        datapoints = response.get('Datapoints', [])
        datapoints.sort(key=lambda x: x['Timestamp'])
        
        if not datapoints:
            return {
                'statusCode': 200,
                'body': {
                    'status': 'success',
                    'message': 'No data points found for trend analysis',
                    'message_ja': 'トレンド分析のためのデータポイントが見つかりませんでした'
                }
            }
        
        # Analyze trends
        averages = [dp['Average'] for dp in datapoints if 'Average' in dp]
        if len(averages) < 2:
            trend = 'insufficient_data'
        else:
            # Simple trend analysis: compare first half with second half
            mid_point = len(averages) // 2
            first_half_avg = sum(averages[:mid_point]) / mid_point if mid_point > 0 else 0
            second_half_avg = sum(averages[mid_point:]) / (len(averages) - mid_point)
            
            change_percent = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
            
            if abs(change_percent) < 5:
                trend = 'stable'
            elif change_percent > 0:
                trend = 'increasing'
            else:
                trend = 'decreasing'
        
        # Calculate statistics
        all_values = [dp.get('Average', 0) for dp in datapoints if 'Average' in dp]
        stats = {
            'min_value': min(all_values) if all_values else 0,
            'max_value': max(all_values) if all_values else 0,
            'avg_value': sum(all_values) / len(all_values) if all_values else 0,
            'trend': trend,
            'total_datapoints': len(datapoints)
        }
        
        if len(averages) >= 2:
            stats['change_percent'] = change_percent
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'namespace': namespace,
                'metric_name': metric_name,
                'dimensions': dimensions,
                'analysis_period_hours': hours_back,
                'trend_analysis': stats,
                'recent_datapoints': [
                    {
                        'timestamp': dp['Timestamp'].isoformat(),
                        'average': dp.get('Average'),
                        'maximum': dp.get('Maximum'),
                        'minimum': dp.get('Minimum')
                    }
                    for dp in datapoints[-10:]  # Last 10 data points
                ],
                'message_ja': f'メトリクストレンド分析が完了しました。トレンド: {trend}'
            }
        }
        
    except Exception as e:
        logger.error(f"Trend analysis failed: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'トレンド分析に失敗しました: {str(e)}'
            }
        }


def test_connection(params: Dict[str, Any]) -> Dict[str, Any]:
    """Test connection to CloudWatch"""
    try:
        # Test by listing metrics
        response = cloudwatch_client.list_metrics(MaxRecords=1)
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'connection': 'connected',
                'region': cloudwatch_client.meta.region_name,
                'message_ja': 'CloudWatchメトリクスへの接続が成功しました'
            }
        }
        
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'connection': 'failed',
                'error': str(e),
                'message_ja': f'接続テストに失敗しました: {str(e)}'
            }
        }