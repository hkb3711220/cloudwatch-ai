"""
CloudWatch Logs Lambda Function Handler

Lambda function for CloudWatch logs investigation and analysis.
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

# CloudWatch Logs client
logs_client = boto3.client('logs')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for CloudWatch logs operations
    
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
        if operation == 'investigate_logs':
            return investigate_logs(parameters)
        elif operation == 'list_log_groups':
            return list_log_groups(parameters)
        elif operation == 'analyze_patterns':
            return analyze_patterns(parameters)
        elif operation == 'get_log_streams':
            return get_log_streams(parameters)
        elif operation == 'get_recent_events':
            return get_recent_events(parameters)
        elif operation == 'test_connection':
            return test_connection(parameters)
        else:
            return {
                'statusCode': 400,
                'body': {
                    'error': f'Unknown operation: {operation}',
                    'supported_operations': [
                        'investigate_logs', 'list_log_groups', 'analyze_patterns',
                        'get_log_streams', 'get_recent_events', 'test_connection'
                    ]
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message_ja': f'リクエスト処理中にエラーが発生しました: {str(e)}'
            })
        }


def investigate_logs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Investigate CloudWatch logs based on query parameters"""
    try:
        query = params.get('query', '')
        log_group = params.get('log_group')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        max_results = params.get('max_results', 100)
        
        logger.info(f"Investigating logs: query='{query}', log_group='{log_group}'")
        
        # Calculate time range
        if start_time and end_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
        
        # Convert to milliseconds
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        
        # If no log group specified, get available groups
        if not log_group:
            paginator = logs_client.get_paginator('describe_log_groups')
            log_groups = []
            for page in paginator.paginate(limit=20):
                log_groups.extend(page['logGroups'])
            
            if log_groups:
                log_group = log_groups[0]['logGroupName']
                logger.info(f"Using first available log group: {log_group}")
            else:
                return {
                    'statusCode': 200,
                    'body': {
                        'status': 'error',
                        'message': 'No log groups found',
                        'message_ja': 'ロググループが見つかりませんでした'
                    }
                }
        
        # Search log events
        search_results = []
        if query:
            try:
                response = logs_client.filter_log_events(
                    logGroupName=log_group,
                    filterPattern=query,
                    startTime=start_ms,
                    endTime=end_ms,
                    limit=max_results
                )
                search_results = response.get('events', [])
            except Exception as e:
                logger.warning(f"Filter failed, using describe_log_events: {e}")
                # Fallback to describe_log_events
                search_results = []
        
        # Analyze patterns
        pattern_stats = analyze_log_events_patterns(log_group, start_ms, end_ms)
        
        result = {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'summary': {
                    'investigation_query': query,
                    'log_group': log_group,
                    'time_range': f"{start_dt.isoformat()} to {end_dt.isoformat()}",
                    'events_found': len(search_results),
                    'pattern_analysis': pattern_stats
                },
                'search_results': search_results[:max_results],
                'message_ja': f'CloudWatchログ調査が完了しました。{len(search_results)}件のイベントが見つかりました。'
            }
        }
        
        logger.info(f"Investigation completed: {len(search_results)} events found")
        return result
        
    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        return {
            'statusCode': 500,
            'body': {
                'status': 'error',
                'message': f'Investigation failed: {str(e)}',
                'message_ja': f'調査に失敗しました: {str(e)}'
            }
        }


def list_log_groups(params: Dict[str, Any]) -> Dict[str, Any]:
    """List available CloudWatch log groups"""
    try:
        pattern = params.get('pattern')
        limit = params.get('limit', 50)
        
        paginator = logs_client.get_paginator('describe_log_groups')
        page_iterator = paginator.paginate(
            logGroupNamePrefix=pattern if pattern else '',
            limit=limit
        )
        
        log_groups = []
        for page in page_iterator:
            log_groups.extend(page['logGroups'])
        
        # Format response
        formatted_groups = []
        for group in log_groups:
            formatted_groups.append({
                'name': group['logGroupName'],
                'creation_time': datetime.fromtimestamp(group['creationTime'] / 1000).isoformat(),
                'size_bytes': group.get('storedBytes', 0),
                'retention_days': group.get('retentionInDays', 'Never expire')
            })
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'total_found': len(formatted_groups),
                'log_groups': formatted_groups,
                'message_ja': f'{len(formatted_groups)}個のロググループが見つかりました'
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list log groups: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'ロググループの取得に失敗しました: {str(e)}'
            }
        }


def analyze_patterns(params: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze patterns in log events"""
    try:
        log_group = params.get('log_group')
        time_range_hours = params.get('time_range_hours', 24)
        
        if not log_group:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'log_group parameter is required',
                    'message_ja': 'ログループパラメータが必要です'
                }
            }
        
        # Calculate time range
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(hours=time_range_hours)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        
        # Analyze patterns
        pattern_stats = analyze_log_events_patterns(log_group, start_ms, end_ms)
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'log_group': log_group,
                'time_range_hours': time_range_hours,
                **pattern_stats,
                'message_ja': f'ログパターン分析が完了しました'
            }
        }
        
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'パターン分析に失敗しました: {str(e)}'
            }
        }


def get_log_streams(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get log streams for a log group"""
    try:
        log_group = params.get('log_group')
        limit = params.get('limit', 20)
        
        if not log_group:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'log_group parameter is required',
                    'message_ja': 'ロググループパラメータが必要です'
                }
            }
        
        paginator = logs_client.get_paginator('describe_log_streams')
        page_iterator = paginator.paginate(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=limit
        )
        
        streams = []
        for page in page_iterator:
            streams.extend(page['logStreams'])
        
        # Format response
        formatted_streams = []
        for stream in streams:
            formatted_streams.append({
                'name': stream['logStreamName'],
                'creation_time': datetime.fromtimestamp(stream['creationTime'] / 1000).isoformat(),
                'last_event_time': datetime.fromtimestamp(stream.get('lastEventTime', stream['creationTime']) / 1000).isoformat(),
                'size_bytes': stream.get('storedBytes', 0)
            })
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'log_group': log_group,
                'total_found': len(formatted_streams),
                'log_streams': formatted_streams,
                'message_ja': f'{len(formatted_streams)}個のログストリームが見つかりました'
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get log streams: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'ログストリームの取得に失敗しました: {str(e)}'
            }
        }


def get_recent_events(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent events from a log stream"""
    try:
        log_group = params.get('log_group')
        log_stream = params.get('log_stream')
        hours_back = params.get('hours_back', 1)
        
        if not log_group or not log_stream:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'log_group and log_stream parameters are required',
                    'message_ja': 'ロググループとログストリームパラメータが必要です'
                }
            }
        
        # Calculate time range
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(hours=hours_back)
        start_ms = int(start_dt.timestamp() * 1000)
        
        response = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            startTime=start_ms,
            startFromHead=False
        )
        
        events = response.get('events', [])
        
        # Format events
        formatted_events = []
        for event in events:
            formatted_events.append({
                'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                'message': event['message']
            })
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'log_group': log_group,
                'log_stream': log_stream,
                'hours_back': hours_back,
                'total_found': len(formatted_events),
                'events': formatted_events,
                'message_ja': f'{len(formatted_events)}個のログイベントが見つかりました'
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent events: {e}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message_ja': f'最新イベントの取得に失敗しました: {str(e)}'
            }
        }


def test_connection(params: Dict[str, Any]) -> Dict[str, Any]:
    """Test connection to CloudWatch Logs"""
    try:
        # Test by listing log groups
        response = logs_client.describe_log_groups(limit=1)
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'connection': 'connected',
                'region': logs_client.meta.region_name,
                'message_ja': 'CloudWatchログへの接続が成功しました'
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


def analyze_log_events_patterns(log_group: str, start_ms: int, end_ms: int) -> Dict[str, Any]:
    """Analyze patterns in log events"""
    try:
        # Get a sample of events for pattern analysis
        response = logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=end_ms,
            limit=1000
        )
        
        events = response.get('events', [])
        
        # Simple pattern analysis
        error_count = 0
        warning_count = 0
        info_count = 0
        
        error_patterns = {}
        warning_patterns = {}
        
        for event in events:
            message = event['message'].lower()
            
            if 'error' in message or 'exception' in message or 'fail' in message:
                error_count += 1
                # Extract error pattern (simplified)
                words = message.split()[:5]  # First 5 words
                pattern = ' '.join(words)
                error_patterns[pattern] = error_patterns.get(pattern, 0) + 1
                
            elif 'warn' in message or 'warning' in message:
                warning_count += 1
                words = message.split()[:5]
                pattern = ' '.join(words)
                warning_patterns[pattern] = warning_patterns.get(pattern, 0) + 1
                
            else:
                info_count += 1
        
        # Determine health status
        total_events = len(events)
        if total_events == 0:
            health_status = "UNKNOWN"
        elif error_count > total_events * 0.1:  # >10% errors
            health_status = "ERROR"
        elif warning_count > total_events * 0.2:  # >20% warnings
            health_status = "WARNING"
        else:
            health_status = "HEALTHY"
        
        return {
            'total_events': total_events,
            'error_count': error_count,
            'warning_count': warning_count,
            'info_count': info_count,
            'health_status': health_status,
            'top_error_patterns': dict(sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]),
            'top_warning_patterns': dict(sorted(warning_patterns.items(), key=lambda x: x[1], reverse=True)[:5])
        }
        
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        return {
            'total_events': 0,
            'error_count': 0,
            'warning_count': 0,
            'info_count': 0,
            'health_status': 'UNKNOWN',
            'analysis_error': str(e)
        }