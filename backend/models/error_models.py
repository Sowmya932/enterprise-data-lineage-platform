"""
error_models.py
---------------
Centralized error response models for consistent API error handling and documentation.

All API errors follow a standard error response format for better error handling
in clients and clearer error documentation in Swagger UI.
"""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ErrorCode(str, Enum):
    """Standardized error codes for common failure scenarios."""
    # Validation errors
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_TABLE_NAME = "INVALID_TABLE_NAME"
    INVALID_COLUMN_NAME = "INVALID_COLUMN_NAME"
    INVALID_SQL_DIALECT = "INVALID_SQL_DIALECT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Parsing errors
    SQL_PARSE_ERROR = "SQL_PARSE_ERROR"
    DAG_PARSE_ERROR = "DAG_PARSE_ERROR"
    INVALID_SQL_SYNTAX = "INVALID_SQL_SYNTAX"
    
    # Data errors
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    LINEAGE_NOT_FOUND = "LINEAGE_NOT_FOUND"
    CIRCULAR_DEPENDENCY_DETECTED = "CIRCULAR_DEPENDENCY_DETECTED"
    
    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    
    # File errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_READ_ERROR = "FILE_READ_ERROR"
    
    # General errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"


class ErrorDetail(BaseModel):
    """Detailed error information for structured error responses."""
    
    field: Optional[str] = Field(None, description="Field name that caused the error (for validation errors)")
    message: str = Field(..., description="Detailed error message")
    value: Optional[Any] = Field(None, description="The problematic value")


class ErrorResponse(BaseModel):
    """Standard error response format for all API endpoints."""
    
    success: bool = Field(False, description="Always False for error responses")
    error_code: ErrorCode = Field(..., description="Machine-readable error code")
    error_message: str = Field(..., description="Human-readable error message")
    severity: ErrorSeverity = Field(ErrorSeverity.MEDIUM, description="Error severity level")
    details: Optional[list[ErrorDetail]] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Correlation ID for debugging")
    timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp of the error")


class ValidationErrorResponse(ErrorResponse):
    """Error response for validation failures."""
    
    error_code: ErrorCode = Field(ErrorCode.INVALID_INPUT, description="Validation error code")
    severity: ErrorSeverity = Field(ErrorSeverity.LOW, description="Validation errors are low severity")


class DatabaseErrorResponse(ErrorResponse):
    """Error response for database operation failures."""
    
    error_code: ErrorCode = Field(ErrorCode.DATABASE_ERROR, description="Database error code")
    severity: ErrorSeverity = Field(ErrorSeverity.HIGH, description="Database errors are high severity")


class NotFoundErrorResponse(ErrorResponse):
    """Error response for resource not found scenarios."""
    
    error_code: ErrorCode = Field(ErrorCode.TABLE_NOT_FOUND, description="Resource not found error code")
    severity: ErrorSeverity = Field(ErrorSeverity.MEDIUM, description="Not found errors are medium severity")


class CircularDependencyErrorResponse(ErrorResponse):
    """Error response for circular dependency detection."""
    
    error_code: ErrorCode = Field(ErrorCode.CIRCULAR_DEPENDENCY_DETECTED, description="Circular dependency error")
    severity: ErrorSeverity = Field(ErrorSeverity.CRITICAL, description="Circular dependencies are critical")
    cycle_path: Optional[list[str]] = Field(None, description="Tables involved in the circular dependency")


class ParseErrorResponse(ErrorResponse):
    """Error response for SQL/DAG parsing failures."""
    
    error_code: ErrorCode = Field(ErrorCode.SQL_PARSE_ERROR, description="Parse error code")
    severity: ErrorSeverity = Field(ErrorSeverity.MEDIUM, description="Parse errors are medium severity")
    snippet: Optional[str] = Field(None, description="Code snippet that failed to parse")
    line_number: Optional[int] = Field(None, description="Line number where parsing failed")
    column_number: Optional[int] = Field(None, description="Column number where parsing failed")
