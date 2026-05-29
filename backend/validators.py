"""
validators.py
-------------
Reusable validation functions for input validation and data sanitization.

These validators are used by Pydantic models and endpoints to ensure
consistent validation across the entire API.
"""

import re
from typing import List, Optional, Set
from backend.exceptions import (
    InvalidTableNameError,
    InvalidColumnNameError,
    InvalidSqlDialectError,
)


# Supported SQL dialects
SUPPORTED_SQL_DIALECTS = {
    "postgres", "postgresql", "mysql", "snowflake", "bigquery",
    "tsql", "oracle", "redshift", "mariadb", "sqlite"
}

# Regex patterns for validation
TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?$")
COLUMN_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_sql_dialect(dialect: str) -> str:
    """
    Validate and normalize a SQL dialect identifier.
    
    Parameters
    ----------
    dialect : str
        SQL dialect to validate (case-insensitive)
    
    Returns
    -------
    str
        Normalized dialect name
    
    Raises
    ------
    InvalidSqlDialectError
        If the dialect is not supported
    """
    normalized = dialect.lower().strip()
    
    # Handle aliases
    alias_map = {
        "postgresql": "postgres",
        "tsql": "tsql",
        "sql_server": "tsql",
    }
    normalized = alias_map.get(normalized, normalized)
    
    if normalized not in SUPPORTED_SQL_DIALECTS:
        raise InvalidSqlDialectError(dialect, sorted(SUPPORTED_SQL_DIALECTS))
    
    return normalized


def validate_table_name(table_name: str) -> str:
    """
    Validate and normalize a table name.
    
    Accepts:
    - Simple names: 'users', 'customer_orders'
    - Schema-qualified names: 'public.users', 'dbo.customers'
    
    Parameters
    ----------
    table_name : str
        Table name to validate
    
    Returns
    -------
    str
        Normalized table name
    
    Raises
    ------
    InvalidTableNameError
        If the table name is invalid
    """
    if not table_name or not isinstance(table_name, str):
        raise InvalidTableNameError(str(table_name), "Table name must be a non-empty string")
    
    normalized = table_name.strip()
    
    if not normalized:
        raise InvalidTableNameError(table_name, "Table name cannot be empty or whitespace-only")
    
    if len(normalized) > 255:
        raise InvalidTableNameError(normalized, "Table name exceeds 255 characters")
    
    # Check for SQL injection patterns
    if ";" in normalized or "--" in normalized or "/*" in normalized:
        raise InvalidTableNameError(normalized, "Table name contains suspicious SQL patterns")
    
    if not TABLE_NAME_PATTERN.match(normalized):
        raise InvalidTableNameError(
            normalized,
            "Table name must start with letter or underscore and contain only alphanumeric characters and underscores"
        )
    
    return normalized


def validate_column_name(column_name: str, table_name: Optional[str] = None) -> str:
    """
    Validate and normalize a column name.
    
    Parameters
    ----------
    column_name : str
        Column name to validate
    table_name : str, optional
        Table name for context in error messages
    
    Returns
    -------
    str
        Normalized column name
    
    Raises
    ------
    InvalidColumnNameError
        If the column name is invalid
    """
    if not column_name or not isinstance(column_name, str):
        raise InvalidColumnNameError(str(column_name) if column_name else "", table_name, "Column name must be a non-empty string")
    
    normalized = column_name.strip()
    
    if not normalized:
        raise InvalidColumnNameError(column_name, table_name, "Column name cannot be empty or whitespace-only")
    
    if len(normalized) > 255:
        raise InvalidColumnNameError(normalized, table_name, "Column name exceeds 255 characters")
    
    # Check for SQL injection patterns
    if ";" in normalized or "--" in normalized or "/*" in normalized:
        raise InvalidColumnNameError(normalized, table_name, "Column name contains suspicious SQL patterns")
    
    if not COLUMN_NAME_PATTERN.match(normalized):
        raise InvalidColumnNameError(
            normalized,
            table_name,
            "Column name must start with letter or underscore and contain only alphanumeric characters and underscores"
        )
    
    return normalized


def validate_identifier(identifier: str, field_name: str = "identifier") -> str:
    """
    Validate and normalize a generic identifier (DAG ID, schema name, etc.).
    
    Parameters
    ----------
    identifier : str
        Identifier to validate
    field_name : str
        Name of the field for error messages
    
    Returns
    -------
    str
        Normalized identifier
    
    Raises
    ------
    ValueError
        If the identifier is invalid
    """
    if not identifier or not isinstance(identifier, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    
    normalized = identifier.strip()
    
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")
    
    if len(normalized) > 255:
        raise ValueError(f"{field_name} exceeds 255 characters")
    
    if not IDENTIFIER_PATTERN.match(normalized):
        raise ValueError(
            f"{field_name} must start with letter or underscore and contain only alphanumeric characters and underscores"
        )
    
    return normalized


def extract_table_and_schema(table_name: str) -> tuple[str, Optional[str]]:
    """
    Extract schema and table name from a potentially qualified table name.
    
    Parameters
    ----------
    table_name : str
        Table name (possibly schema-qualified)
    
    Returns
    -------
    tuple[str, Optional[str]]
        (table_name, schema_name)
    
    Examples
    --------
    >>> extract_table_and_schema("public.users")
    ('users', 'public')
    >>> extract_table_and_schema("users")
    ('users', None)
    """
    parts = table_name.split(".")
    if len(parts) == 2:
        return parts[1], parts[0]
    elif len(parts) == 1:
        return parts[0], None
    else:
        raise InvalidTableNameError(table_name, "Table name contains too many dots")


def validate_table_list(table_names: List[str], allow_empty: bool = False) -> List[str]:
    """
    Validate a list of table names.
    
    Parameters
    ----------
    table_names : List[str]
        List of table names to validate
    allow_empty : bool
        Whether to allow an empty list
    
    Returns
    -------
    List[str]
        Validated and normalized table names
    
    Raises
    ------
    ValueError
        If validation fails
    """
    if not table_names and not allow_empty:
        raise ValueError("Table list cannot be empty")
    
    return [validate_table_name(t) for t in table_names]


def validate_column_list(column_names: List[str], table_name: Optional[str] = None) -> List[str]:
    """
    Validate a list of column names.
    
    Parameters
    ----------
    column_names : List[str]
        List of column names to validate
    table_name : str, optional
        Table name for context
    
    Returns
    -------
    List[str]
        Validated and normalized column names
    
    Raises
    ------
    ValueError
        If validation fails
    """
    if not column_names:
        raise ValueError("Column list cannot be empty")
    
    return [validate_column_name(c, table_name) for c in column_names]


def sanitize_sql_snippet(sql: str, max_length: int = 1000) -> str:
    """
    Sanitize and truncate SQL for safe display in error messages and logs.
    
    Parameters
    ----------
    sql : str
        SQL to sanitize
    max_length : int
        Maximum length to preserve
    
    Returns
    -------
    str
        Sanitized SQL snippet
    """
    if not sql:
        return ""
    
    # Remove newlines and excess whitespace
    sanitized = " ".join(sql.split())
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length - 3] + "..."
    
    return sanitized


def deduplicate_tables(tables: List[str]) -> List[str]:
    """
    Remove duplicate table names while preserving order.
    
    Parameters
    ----------
    tables : List[str]
        List of table names
    
    Returns
    -------
    List[str]
        Deduplicated table names
    """
    seen: Set[str] = set()
    result = []
    for table in tables:
        if table not in seen:
            seen.add(table)
            result.append(table)
    return result
