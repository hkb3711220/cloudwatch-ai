"""AWS-related Exception Classes

Provides exception classes for AWS, CloudWatch, and CloudWatch Logs
specific errors with Japanese message support.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

from typing import Optional, Dict, Any
from .base import AgentError, ErrorContext


class AWSError(AgentError):
    """Base exception class for AWS-related errors"""

    def __init__(
        self,
        message: str,
        aws_error_code: Optional[str] = None,
        aws_error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        region: Optional[str] = None,
        **kwargs
    ):
        """Initialize AWS error

        Args:
            message: Error message
            aws_error_code: AWS error code from the service
            aws_error_message: AWS error message from the service
            request_id: AWS request ID for tracking
            region: AWS region where the error occurred
            **kwargs: Additional AgentError arguments
        """
        super().__init__(message, **kwargs)
        self.aws_error_code = aws_error_code
        self.aws_error_message = aws_error_message
        self.aws_request_id = request_id
        self.region = region

    def _get_default_japanese_message(self) -> str:
        return "AWSサービスでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "AWS_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with AWS-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "aws_error_code": self.aws_error_code,
                "aws_error_message": self.aws_error_message,
                "aws_request_id": self.aws_request_id,
                "region": self.region,
            }
        )
        return result


class CloudWatchError(AWSError):
    """Exception class for CloudWatch service errors"""

    def _get_default_japanese_message(self) -> str:
        return "CloudWatchサービスでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "CLOUDWATCH_ERROR"


class CloudWatchLogsError(CloudWatchError):
    """Exception class for CloudWatch Logs service errors"""

    def __init__(
        self,
        message: str,
        log_group_name: Optional[str] = None,
        log_stream_name: Optional[str] = None,
        **kwargs
    ):
        """Initialize CloudWatch Logs error

        Args:
            message: Error message
            log_group_name: Log group name associated with the error
            log_stream_name: Log stream name associated with the error
            **kwargs: Additional AWSError arguments
        """
        super().__init__(message, **kwargs)
        self.log_group_name = log_group_name
        self.log_stream_name = log_stream_name

    def _get_default_japanese_message(self) -> str:
        return "CloudWatch Logsでエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "CLOUDWATCH_LOGS_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with CloudWatch Logs specific fields"""
        result = super().to_dict()
        result.update(
            {
                "log_group_name": self.log_group_name,
                "log_stream_name": self.log_stream_name,
            }
        )
        return result


class CredentialsError(AWSError):
    """Exception class for AWS credentials-related errors"""

    def __init__(self, message: str, credential_type: Optional[str] = None, **kwargs):
        """Initialize credentials error

        Args:
            message: Error message
            credential_type: Type of credentials that failed (e.g., 'IAM_ROLE', 'ACCESS_KEY')
            **kwargs: Additional AWSError arguments
        """
        super().__init__(message, **kwargs)
        self.credential_type = credential_type

    def _get_default_japanese_message(self) -> str:
        return "AWS認証情報でエラーが発生しました"

    def _get_default_error_code(self) -> str:
        return "CREDENTIALS_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with credentials-specific fields"""
        result = super().to_dict()
        result["credential_type"] = self.credential_type
        return result


class RegionError(AWSError):
    """Exception class for AWS region-related errors"""

    def __init__(
        self,
        message: str,
        invalid_region: Optional[str] = None,
        valid_regions: Optional[list] = None,
        **kwargs
    ):
        """Initialize region error

        Args:
            message: Error message
            invalid_region: Invalid region that was provided
            valid_regions: List of valid regions
            **kwargs: Additional AWSError arguments
        """
        super().__init__(message, **kwargs)
        self.invalid_region = invalid_region
        self.valid_regions = valid_regions or []

    def _get_default_japanese_message(self) -> str:
        return "AWSリージョンが無効です"

    def _get_default_error_code(self) -> str:
        return "REGION_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with region-specific fields"""
        result = super().to_dict()
        result.update(
            {"invalid_region": self.invalid_region, "valid_regions": self.valid_regions}
        )
        return result


class ResourceNotFoundError(AWSError):
    """Exception class for AWS resource not found errors"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_identifier: Optional[str] = None,
        **kwargs
    ):
        """Initialize resource not found error

        Args:
            message: Error message
            resource_type: Type of resource that was not found
            resource_identifier: Identifier of the resource that was not found
            **kwargs: Additional AWSError arguments
        """
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_identifier = resource_identifier

    def _get_default_japanese_message(self) -> str:
        if self.resource_type == "LOG_GROUP":
            return "指定されたログ グループが見つかりません"
        elif self.resource_type == "LOG_STREAM":
            return "指定されたログ ストリームが見つかりません"
        else:
            return "指定されたAWSリソースが見つかりません"

    def _get_default_error_code(self) -> str:
        return "RESOURCE_NOT_FOUND"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary with resource-specific fields"""
        result = super().to_dict()
        result.update(
            {
                "resource_type": self.resource_type,
                "resource_identifier": self.resource_identifier,
            }
        )
        return result
