"""Parameter Validation for MCP Tools

Provides comprehensive validation for all MCP tool parameters with
detailed error messages in Japanese.
"""

import re
import time
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Validation error with code and message"""

    code: str
    message: str
    field: str
    value: Any


class MCPValidationException(Exception):
    """Exception raised when parameter validation fails"""

    def __init__(self, errors: List[ValidationError]):
        self.errors = errors
        messages = [f"{error.field}: {error.message}" for error in errors]
        super().__init__(f"パラメータ検証エラー: {'; '.join(messages)}")


class TimeValidator:
    """Validator for time-related parameters"""

    @staticmethod
    def validate_start_time(start_time: str) -> List[ValidationError]:
        """Validate start time format"""
        errors = []

        if not isinstance(start_time, str):
            errors.append(
                ValidationError(
                    code="START_TIME_INVALID_TYPE",
                    message="開始時刻は文字列である必要があります",
                    field="start_time",
                    value=start_time,
                )
            )
        else:
            # Try to parse the time to check validity
            try:
                # Basic ISO format check
                if (
                    start_time.endswith("Z")
                    or "+" in start_time
                    or "-" in start_time[-6:]
                ):
                    # Looks like ISO format, try parsing
                    import datetime

                    datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                else:
                    # Check other common formats
                    import datetime

                    # Try common formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d_%H%M%S"]:
                        try:
                            datetime.datetime.strptime(start_time, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError("Invalid format")
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        code="START_TIME_INVALID_FORMAT",
                        message="開始時刻の形式が無効です（ISO形式またはYYYY-MM-DD HH:MM:SSを使用してください）",
                        field="start_time",
                        value=start_time,
                    )
                )

        return errors

    @staticmethod
    def validate_end_time(end_time: str) -> List[ValidationError]:
        """Validate end time format (similar to start_time)"""
        errors = []

        if not isinstance(end_time, str):
            errors.append(
                ValidationError(
                    code="END_TIME_INVALID_TYPE",
                    message="終了時刻は文字列である必要があります",
                    field="end_time",
                    value=end_time,
                )
            )
        else:
            # Try to parse the time to check validity
            try:
                # Basic ISO format check
                if end_time.endswith("Z") or "+" in end_time or "-" in end_time[-6:]:
                    # Looks like ISO format, try parsing
                    import datetime

                    datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                else:
                    # Check other common formats
                    import datetime

                    # Try common formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d_%H%M%S"]:
                        try:
                            datetime.datetime.strptime(end_time, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError("Invalid format")
            except (ValueError, TypeError):
                errors.append(
                    ValidationError(
                        code="END_TIME_INVALID_FORMAT",
                        message="終了時刻の形式が無効です（ISO形式またはYYYY-MM-DD HH:MM:SSを使用してください）",
                        field="end_time",
                        value=end_time,
                    )
                )

        return errors


class ParameterValidator:
    """Comprehensive parameter validator for MCP tools"""

    @staticmethod
    def validate_query(query: str) -> List[ValidationError]:
        """Validate investigation query parameter"""
        errors = []

        if not query:
            errors.append(
                ValidationError(
                    code="QUERY_EMPTY",
                    message="クエリが空です",
                    field="query",
                    value=query,
                )
            )
        elif not isinstance(query, str):
            errors.append(
                ValidationError(
                    code="QUERY_INVALID_TYPE",
                    message="クエリは文字列である必要があります",
                    field="query",
                    value=query,
                )
            )
        elif len(query.strip()) < 3:
            errors.append(
                ValidationError(
                    code="QUERY_TOO_SHORT",
                    message="クエリは最低3文字以上である必要があります",
                    field="query",
                    value=query,
                )
            )
        elif len(query) > 1000:
            errors.append(
                ValidationError(
                    code="QUERY_TOO_LONG",
                    message="クエリは1000文字以下である必要があります",
                    field="query",
                    value=query,
                )
            )

        return errors

    @staticmethod
    def validate_log_group(log_group: Optional[str]) -> List[ValidationError]:
        """Validate log group parameter"""
        errors = []

        if log_group is not None:
            if not isinstance(log_group, str):
                errors.append(
                    ValidationError(
                        code="LOG_GROUP_INVALID_TYPE",
                        message="ロググループ名は文字列である必要があります",
                        field="log_group",
                        value=log_group,
                    )
                )
            elif not log_group.strip():
                errors.append(
                    ValidationError(
                        code="LOG_GROUP_EMPTY",
                        message="ロググループ名が空です",
                        field="log_group",
                        value=log_group,
                    )
                )
            elif len(log_group) > 512:
                errors.append(
                    ValidationError(
                        code="LOG_GROUP_TOO_LONG",
                        message="ロググループ名は512文字以下である必要があります",
                        field="log_group",
                        value=log_group,
                    )
                )
            elif not re.match(r"^[a-zA-Z0-9._/\-]+$", log_group):
                errors.append(
                    ValidationError(
                        code="LOG_GROUP_INVALID_FORMAT",
                        message="ロググループ名に無効な文字が含まれています",
                        field="log_group",
                        value=log_group,
                    )
                )

        return errors

    @staticmethod
    def validate_time_range(
        start_time: Optional[str], end_time: Optional[str]
    ) -> List[ValidationError]:
        """Validate time range parameters"""
        errors = []

        start_dt = None
        end_dt = None

        # Validate start_time
        if start_time is not None:
            errors.extend(TimeValidator.validate_start_time(start_time))

        # Validate end_time
        if end_time is not None:
            errors.extend(TimeValidator.validate_end_time(end_time))

        # Validate time range logic
        if start_dt and end_dt:
            if start_dt >= end_dt:
                errors.append(
                    ValidationError(
                        code="TIME_RANGE_INVALID",
                        message="開始時間は終了時間より前である必要があります",
                        field="time_range",
                        value=f"{start_time} - {end_time}",
                    )
                )

            # Check if range is too large (more than 30 days)
            if (end_dt - start_dt).days > 30:
                errors.append(
                    ValidationError(
                        code="TIME_RANGE_TOO_LARGE",
                        message="時間範囲は30日以下である必要があります",
                        field="time_range",
                        value=f"{start_time} - {end_time}",
                    )
                )

        # Check if times are not too far in the future
        now = datetime.now(timezone.utc)
        if start_dt and start_dt > now:
            errors.append(
                ValidationError(
                    code="START_TIME_FUTURE",
                    message="開始時間は現在時刻より前である必要があります",
                    field="start_time",
                    value=start_time,
                )
            )

        if end_dt and end_dt > now:
            errors.append(
                ValidationError(
                    code="END_TIME_FUTURE",
                    message="終了時間は現在時刻より前である必要があります",
                    field="end_time",
                    value=end_time,
                )
            )

        return errors

    @staticmethod
    def validate_max_results(max_results: int) -> List[ValidationError]:
        """Validate max_results parameter"""
        errors = []

        if not isinstance(max_results, int):
            errors.append(
                ValidationError(
                    code="MAX_RESULTS_INVALID_TYPE",
                    message="最大結果数は整数である必要があります",
                    field="max_results",
                    value=max_results,
                )
            )
        elif max_results <= 0:
            errors.append(
                ValidationError(
                    code="MAX_RESULTS_TOO_SMALL",
                    message="最大結果数は1以上である必要があります",
                    field="max_results",
                    value=max_results,
                )
            )
        elif max_results > 10000:
            errors.append(
                ValidationError(
                    code="MAX_RESULTS_TOO_LARGE",
                    message="最大結果数は10000以下である必要があります",
                    field="max_results",
                    value=max_results,
                )
            )

        return errors

    @staticmethod
    def validate_pattern(pattern: Optional[str]) -> List[ValidationError]:
        """Validate pattern parameter for log group filtering"""
        errors = []

        if pattern is not None:
            if not isinstance(pattern, str):
                errors.append(
                    ValidationError(
                        code="PATTERN_INVALID_TYPE",
                        message="パターンは文字列である必要があります",
                        field="pattern",
                        value=pattern,
                    )
                )
            elif len(pattern) > 256:
                errors.append(
                    ValidationError(
                        code="PATTERN_TOO_LONG",
                        message="パターンは256文字以下である必要があります",
                        field="pattern",
                        value=pattern,
                    )
                )
            elif pattern.strip() == "":
                errors.append(
                    ValidationError(
                        code="PATTERN_EMPTY",
                        message="パターンが空です",
                        field="pattern",
                        value=pattern,
                    )
                )

        return errors

    @classmethod
    def validate_investigate_params(
        cls,
        query: str,
        log_group: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: int = 100,
    ) -> None:
        """Validate all parameters for investigate_cloudwatch_logs"""
        errors = []

        errors.extend(cls.validate_query(query))
        errors.extend(cls.validate_log_group(log_group))
        errors.extend(cls.validate_time_range(start_time, end_time))
        errors.extend(cls.validate_max_results(max_results))

        if errors:
            raise MCPValidationException(errors)

    @classmethod
    def validate_list_log_groups_params(cls, pattern: Optional[str] = None) -> None:
        """Validate parameters for list_available_log_groups"""
        errors = []

        errors.extend(cls.validate_pattern(pattern))

        if errors:
            raise MCPValidationException(errors)
