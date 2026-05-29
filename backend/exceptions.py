"""
exceptions.py
-------------
Custom exception classes for consistent error handling throughout the application.

These exceptions are caught by FastAPI exception handlers and converted to
standardized HTTP responses using error_models.
"""

from typing import Optional, List
from backend.models.error_models import ErrorCode, ErrorSeverity


class LineageError(Exception):
    """Base exception for all lineage-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[List[dict]] = None,
        **kwargs
    ):
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.details = details or []
        self.extra = kwargs
        super().__init__(self.message)


class ValidationError(LineageError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, details: Optional[List[dict]] = None, **kwargs):
        super().__init__(
            message,
            error_code=ErrorCode.INVALID_INPUT,
            severity=ErrorSeverity.LOW,
            details=details,
            **kwargs
        )


class InvalidTableNameError(ValidationError):
    """Raised when a provided table name is invalid."""
    
    def __init__(self, table_name: str, reason: str = "", **kwargs):
        message = f"Invalid table name: '{table_name}'"
        if reason:
            message += f" ({reason})"
        super().__init__(
            message,
            details=[{"field": "table_name", "message": reason or "Table name is invalid", "value": table_name}],
            **kwargs
        )
        self.error_code = ErrorCode.INVALID_TABLE_NAME


class InvalidColumnNameError(ValidationError):
    """Raised when a provided column name is invalid."""
    
    def __init__(self, column_name: str, table_name: Optional[str] = None, reason: str = "", **kwargs):
        message = f"Invalid column name: '{column_name}'"
        if table_name:
            message += f" in table '{table_name}'"
        if reason:
            message += f" ({reason})"
        super().__init__(
            message,
            details=[{"field": "column_name", "message": reason or "Column name is invalid", "value": column_name}],
            **kwargs
        )
        self.error_code = ErrorCode.INVALID_COLUMN_NAME


class InvalidSqlDialectError(ValidationError):
    """Raised when an unsupported SQL dialect is provided."""
    
    def __init__(self, dialect: str, supported: List[str], **kwargs):
        message = f"Unsupported SQL dialect: '{dialect}'. Supported: {', '.join(supported)}"
        super().__init__(
            message,
            details=[{"field": "dialect", "message": "Unsupported SQL dialect", "value": dialect}],
            **kwargs
        )
        self.error_code = ErrorCode.INVALID_SQL_DIALECT


class SqlParseError(LineageError):
    """Raised when SQL parsing fails."""
    
    def __init__(
        self,
        message: str,
        sql_snippet: Optional[str] = None,
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code=ErrorCode.SQL_PARSE_ERROR,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.sql_snippet = sql_snippet
        self.line_number = line_number
        self.column_number = column_number


class DagParseError(LineageError):
    """Raised when DAG parsing fails."""
    
    def __init__(
        self,
        message: str,
        dag_snippet: Optional[str] = None,
        line_number: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code=ErrorCode.DAG_PARSE_ERROR,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.dag_snippet = dag_snippet
        self.line_number = line_number


class TableNotFoundError(LineageError):
    """Raised when a referenced table does not exist in the database."""
    
    def __init__(self, table_name: str, **kwargs):
        super().__init__(
            f"Table not found: '{table_name}'",
            error_code=ErrorCode.TABLE_NOT_FOUND,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.table_name = table_name


class ColumnNotFoundError(LineageError):
    """Raised when a referenced column does not exist."""
    
    def __init__(self, column_name: str, table_name: Optional[str] = None, **kwargs):
        if table_name:
            message = f"Column not found: '{table_name}'.'{column_name}'"
        else:
            message = f"Column not found: '{column_name}'"
        super().__init__(
            message,
            error_code=ErrorCode.COLUMN_NOT_FOUND,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.column_name = column_name
        self.table_name = table_name


class LineageNotFoundError(LineageError):
    """Raised when no lineage exists for a given table or column."""
    
    def __init__(self, entity_name: str, entity_type: str = "table", **kwargs):
        super().__init__(
            f"No lineage found for {entity_type}: '{entity_name}'",
            error_code=ErrorCode.LINEAGE_NOT_FOUND,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.entity_name = entity_name
        self.entity_type = entity_type


class CircularDependencyError(LineageError):
    """Raised when a circular dependency is detected in lineage."""
    
    def __init__(self, cycle_path: Optional[List[str]] = None, **kwargs):
        message = "Circular dependency detected in lineage"
        if cycle_path:
            message += f": {' -> '.join(cycle_path)} -> {cycle_path[0]}"
        super().__init__(
            message,
            error_code=ErrorCode.CIRCULAR_DEPENDENCY_DETECTED,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.cycle_path = cycle_path


class DatabaseError(LineageError):
    """Raised when a database operation fails."""
    
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        full_message = message
        if operation:
            full_message += f" (operation: {operation})"
        super().__init__(
            full_message,
            error_code=ErrorCode.DATABASE_ERROR,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.operation = operation


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    
    def __init__(self, message: str = "Failed to connect to database", **kwargs):
        super().__init__(
            message,
            operation="connect",
            **kwargs
        )
        self.error_code = ErrorCode.CONNECTION_ERROR
        self.severity = ErrorSeverity.CRITICAL


class DuplicateEntryError(DatabaseError):
    """Raised when attempting to create a duplicate entry."""
    
    def __init__(self, entity_type: str, unique_field: str, value: str, **kwargs):
        message = f"Duplicate {entity_type}: {unique_field}='{value}' already exists"
        super().__init__(message, **kwargs)
        self.error_code = ErrorCode.DUPLICATE_ENTRY
        self.entity_type = entity_type
        self.unique_field = unique_field
        self.value = value


class FileNotFoundError(LineageError):
    """Raised when a required file is not found."""
    
    def __init__(self, file_path: str, **kwargs):
        super().__init__(
            f"File not found: '{file_path}'",
            error_code=ErrorCode.FILE_NOT_FOUND,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.file_path = file_path


class FileReadError(LineageError):
    """Raised when a file cannot be read."""
    
    def __init__(self, file_path: str, reason: str = "", **kwargs):
        message = f"Error reading file: '{file_path}'"
        if reason:
            message += f" ({reason})"
        super().__init__(
            message,
            error_code=ErrorCode.FILE_READ_ERROR,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.file_path = file_path
        self.reason = reason
