"""Logging Context Management

Provides context managers for maintaining contextual information
throughout the logging lifecycle.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import uuid
from contextlib import contextmanager, asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Generator, AsyncGenerator, Union
import threading

from .structured_logger import LogContext, set_request_context, get_request_context


# Context variables for thread-safe context management
_current_component: ContextVar[Optional[str]] = ContextVar(
    "current_component", default=None
)
_current_operation: ContextVar[Optional[str]] = ContextVar(
    "current_operation", default=None
)
_current_request_id: ContextVar[Optional[str]] = ContextVar(
    "current_request_id", default=None
)
_context_stack: ContextVar[list] = ContextVar("context_stack", default=[])


@dataclass
class LoggingContext:
    """Comprehensive logging context management"""

    request_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=lambda: datetime.utcnow())

    def to_log_context(self) -> LogContext:
        """Convert to LogContext for logging"""
        return LogContext(
            request_id=self.request_id,
            session_id=self.session_id,
            user_id=self.user_id,
            client_ip=self.client_ip,
            component=self.component,
            operation=self.operation,
            trace_id=self.trace_id,
            span_id=self.span_id,
            timestamp=self.start_time,
            extra_data={
                "parent_span_id": self.parent_span_id,
                "tags": self.tags,
                "metadata": self.metadata,
            },
        )

    def copy(self, **updates) -> "LoggingContext":
        """Create a copy with updates"""
        new_context = LoggingContext(
            request_id=self.request_id,
            session_id=self.session_id,
            user_id=self.user_id,
            client_ip=self.client_ip,
            component=self.component,
            operation=self.operation,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            tags=self.tags.copy(),
            metadata=self.metadata.copy(),
            start_time=self.start_time,
        )

        # Apply updates
        for key, value in updates.items():
            if hasattr(new_context, key):
                setattr(new_context, key, value)

        return new_context

    def add_tag(self, key: str, value: str):
        """Add a tag to the context"""
        self.tags[key] = value

    def add_metadata(self, key: str, value: Any):
        """Add metadata to the context"""
        self.metadata[key] = value

    def generate_span_id(self) -> str:
        """Generate a new span ID"""
        return str(uuid.uuid4())[:8]

    def create_child_span(self, operation: Optional[str] = None) -> "LoggingContext":
        """Create a child span context"""
        child_span_id = self.generate_span_id()

        return self.copy(
            span_id=child_span_id,
            parent_span_id=self.span_id,
            operation=operation or self.operation,
            start_time=datetime.utcnow(),
        )


@contextmanager
def request_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    **kwargs
) -> Generator[LoggingContext, None, None]:
    """Context manager for request-level logging context"""

    # Generate request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())

    # Create context
    context = LoggingContext(
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        client_ip=client_ip,
        trace_id=request_id,  # Use request_id as trace_id by default
        span_id=str(uuid.uuid4())[:8],
        **kwargs
    )

    # Set context variables
    request_token = _current_request_id.set(request_id)

    # Set request context for structured logger
    old_request_context = get_request_context()
    set_request_context(**context.to_log_context().to_dict())

    try:
        yield context
    finally:
        # Restore previous context
        _current_request_id.reset(request_token)

        if old_request_context:
            set_request_context(**old_request_context)
        else:
            from .structured_logger import clear_request_context

            clear_request_context()


@contextmanager
def component_context(
    component: str, inherit_request: bool = True, **kwargs
) -> Generator[LoggingContext, None, None]:
    """Context manager for component-level logging context"""

    # Get current request context if inheriting
    base_context = {}
    if inherit_request:
        current_request_context = get_request_context()
        if current_request_context:
            base_context.update(current_request_context)

    # Create context
    context = LoggingContext(component=component, **base_context, **kwargs)

    # If no span_id, generate one
    if not context.span_id:
        context.span_id = context.generate_span_id()

    # Set context variables
    component_token = _current_component.set(component)

    # Update request context
    old_request_context = get_request_context()
    set_request_context(**context.to_log_context().to_dict())

    try:
        yield context
    finally:
        # Restore previous context
        _current_component.reset(component_token)

        if old_request_context:
            set_request_context(**old_request_context)
        else:
            from .structured_logger import clear_request_context

            clear_request_context()


@contextmanager
def operation_context(
    operation: str,
    component: Optional[str] = None,
    inherit_context: bool = True,
    **kwargs
) -> Generator[LoggingContext, None, None]:
    """Context manager for operation-level logging context"""

    # Get current context if inheriting
    base_context = {}
    if inherit_context:
        current_request_context = get_request_context()
        if current_request_context:
            base_context.update(current_request_context)

    # Use current component if not specified
    if component is None:
        component = _current_component.get()

    # Create context
    context = LoggingContext(
        operation=operation, component=component, **base_context, **kwargs
    )

    # Generate span for operation if needed
    if not context.span_id:
        context.span_id = context.generate_span_id()

    # Set context variables
    operation_token = _current_operation.set(operation)
    if component:
        component_token = _current_component.set(component)
    else:
        component_token = None

    # Update request context
    old_request_context = get_request_context()
    set_request_context(**context.to_log_context().to_dict())

    try:
        yield context
    finally:
        # Restore previous context
        _current_operation.reset(operation_token)
        if component_token:
            _current_component.reset(component_token)

        if old_request_context:
            set_request_context(**old_request_context)
        else:
            from .structured_logger import clear_request_context

            clear_request_context()


@asynccontextmanager
async def async_request_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    **kwargs
) -> AsyncGenerator[LoggingContext, None]:
    """Async context manager for request-level logging context"""

    # Generate request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())

    # Create context
    context = LoggingContext(
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        client_ip=client_ip,
        trace_id=request_id,
        span_id=str(uuid.uuid4())[:8],
        **kwargs
    )

    # Set context variables
    request_token = _current_request_id.set(request_id)

    # Set request context for structured logger
    old_request_context = get_request_context()
    set_request_context(**context.to_log_context().to_dict())

    try:
        yield context
    finally:
        # Restore previous context
        _current_request_id.reset(request_token)

        if old_request_context:
            set_request_context(**old_request_context)
        else:
            from .structured_logger import clear_request_context

            clear_request_context()


@asynccontextmanager
async def async_component_context(
    component: str, inherit_request: bool = True, **kwargs
) -> AsyncGenerator[LoggingContext, None]:
    """Async context manager for component-level logging context"""

    # Get current request context if inheriting
    base_context = {}
    if inherit_request:
        current_request_context = get_request_context()
        if current_request_context:
            base_context.update(current_request_context)

    # Create context
    context = LoggingContext(component=component, **base_context, **kwargs)

    # If no span_id, generate one
    if not context.span_id:
        context.span_id = context.generate_span_id()

    # Set context variables
    component_token = _current_component.set(component)

    # Update request context
    old_request_context = get_request_context()
    set_request_context(**context.to_log_context().to_dict())

    try:
        yield context
    finally:
        # Restore previous context
        _current_component.reset(component_token)

        if old_request_context:
            set_request_context(**old_request_context)
        else:
            from .structured_logger import clear_request_context

            clear_request_context()


@asynccontextmanager
async def async_operation_context(
    operation: str,
    component: Optional[str] = None,
    inherit_context: bool = True,
    **kwargs
) -> AsyncGenerator[LoggingContext, None]:
    """Async context manager for operation-level logging context"""

    # Get current context if inheriting
    base_context = {}
    if inherit_context:
        current_request_context = get_request_context()
        if current_request_context:
            base_context.update(current_request_context)

    # Use current component if not specified
    if component is None:
        component = _current_component.get()

    # Create context
    context = LoggingContext(
        operation=operation, component=component, **base_context, **kwargs
    )

    # Generate span for operation if needed
    if not context.span_id:
        context.span_id = context.generate_span_id()

    # Set context variables
    operation_token = _current_operation.set(operation)
    if component:
        component_token = _current_component.set(component)
    else:
        component_token = None

    # Update request context
    old_request_context = get_request_context()
    set_request_context(**context.to_log_context().to_dict())

    try:
        yield context
    finally:
        # Restore previous context
        _current_operation.reset(operation_token)
        if component_token:
            _current_component.reset(component_token)

        if old_request_context:
            set_request_context(**old_request_context)
        else:
            from .structured_logger import clear_request_context

            clear_request_context()


def get_current_context() -> Optional[LoggingContext]:
    """Get the current logging context"""
    current_request_context = get_request_context()
    if not current_request_context:
        return None

    return LoggingContext(
        request_id=current_request_context.get("request_id"),
        session_id=current_request_context.get("session_id"),
        user_id=current_request_context.get("user_id"),
        client_ip=current_request_context.get("client_ip"),
        component=current_request_context.get("component"),
        operation=current_request_context.get("operation"),
        trace_id=current_request_context.get("trace_id"),
        span_id=current_request_context.get("span_id"),
        start_time=datetime.utcnow(),
    )


def get_current_component() -> Optional[str]:
    """Get the current component name"""
    return _current_component.get()


def get_current_operation() -> Optional[str]:
    """Get the current operation name"""
    return _current_operation.get()


def get_current_request_id() -> Optional[str]:
    """Get the current request ID"""
    return _current_request_id.get()
