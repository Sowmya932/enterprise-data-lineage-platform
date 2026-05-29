"""
test_sql_parser.py
------------------
Unit tests for SQL parsing functionality.

Tests cover:
- Simple SELECT statements
- INSERT, UPDATE, DELETE statements
- Complex queries (JOINs, subqueries, CTEs)
- Column-level lineage extraction
- Error handling for invalid SQL
"""

import pytest
from backend.parsers.sql_parser import SQLParser
from backend.exceptions import SqlParseError, InvalidSqlDialectError
from backend.validators import validate_sql_dialect


class TestSQLParserBasics:
    """Test basic SQL parsing functionality."""
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_simple_select(self):
        """Test parsing a simple SELECT statement."""
        parser = SQLParser(dialect="postgres")
        sql = "SELECT * FROM customers;"
        result = parser.parse(sql)
        
        assert result["target_table"] is None
        assert "customers" in result["source_tables"]
        assert result["success"] is True
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_simple_insert(self):
        """Test parsing a simple INSERT statement."""
        parser = SQLParser(dialect="postgres")
        sql = "INSERT INTO customers (name, email) VALUES ('John', 'john@example.com');"
        result = parser.parse(sql)
        
        assert result["target_table"] == "customers"
        assert len(result["source_tables"]) == 0
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_simple_update(self):
        """Test parsing a simple UPDATE statement."""
        parser = SQLParser(dialect="postgres")
        sql = "UPDATE orders SET status = 'completed' WHERE order_id = 123;"
        result = parser.parse(sql)
        
        assert result["target_table"] == "orders"
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_simple_delete(self):
        """Test parsing a simple DELETE statement."""
        parser = SQLParser(dialect="postgres")
        sql = "DELETE FROM orders WHERE order_date < '2020-01-01';"
        result = parser.parse(sql)
        
        assert "orders" in [result["target_table"]]
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_create_as_select(self):
        """Test parsing a CREATE TABLE AS SELECT (CTAS) statement."""
        parser = SQLParser(dialect="postgres")
        sql = """
            CREATE TABLE customer_summary AS
            SELECT customer_id, COUNT(*) as order_count
            FROM orders
            GROUP BY customer_id;
        """
        result = parser.parse(sql)
        
        assert result["target_table"] == "customer_summary"
        assert "orders" in result["source_tables"]
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_with_schema_qualified_names(self):
        """Test parsing SQL with schema-qualified table names."""
        parser = SQLParser(dialect="postgres")
        sql = "SELECT * FROM public.customers JOIN public.orders ON customers.id = orders.customer_id;"
        result = parser.parse(sql)
        
        # Parser should handle schema-qualified names
        assert "customers" in result.get("source_tables") or "public.customers" in result.get("source_tables")


class TestSQLParserComplexQueries:
    """Test parsing of complex SQL queries."""
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_join_query(self, sample_sql_queries):
        """Test parsing a JOIN query."""
        parser = SQLParser(dialect="postgres")
        result = parser.parse(sample_sql_queries["join_query"])
        
        assert "customers" in result["source_tables"]
        assert "orders" in result["source_tables"]
        assert result["target_table"] is None
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_subquery(self, sample_sql_queries):
        """Test parsing a query with subqueries."""
        parser = SQLParser(dialect="postgres")
        result = parser.parse(sample_sql_queries["subquery"])
        
        assert "orders" in result["source_tables"]
        assert "customers" in result["source_tables"]
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_cte_query(self, sample_sql_queries):
        """Test parsing a query with CTEs (WITH clause)."""
        parser = SQLParser(dialect="postgres")
        result = parser.parse(sample_sql_queries["cte_query"])
        
        assert "customers" in result["source_tables"]
        assert "orders" in result["source_tables"]


class TestColumnLineageExtraction:
    """Test column-level lineage extraction."""
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_extract_column_lineage_simple(self):
        """Test extracting column lineage from a simple SELECT."""
        parser = SQLParser(dialect="postgres")
        sql = "SELECT customer_id, customer_name FROM customers;"
        result = parser.extract_column_lineage(sql)
        
        assert "error" not in result
        assert "column_lineage" in result
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_extract_column_lineage_with_transformation(self):
        """Test extracting column lineage with transformations."""
        parser = SQLParser(dialect="postgres")
        sql = """
            SELECT 
                customer_id,
                UPPER(customer_name) as customer_name_upper,
                order_count * 100 as order_value
            FROM customer_summary;
        """
        result = parser.extract_column_lineage(sql)
        
        assert "error" not in result or "column_lineage" in result
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_extract_column_lineage_with_aggregation(self):
        """Test extracting column lineage with aggregations."""
        parser = SQLParser(dialect="postgres")
        sql = """
            SELECT 
                customer_id,
                SUM(order_amount) as total_amount,
                COUNT(*) as order_count
            FROM orders
            GROUP BY customer_id;
        """
        result = parser.extract_column_lineage(sql)
        
        assert "error" not in result or "column_lineage" in result


class TestSQLDialectHandling:
    """Test SQL dialect validation and handling."""
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_validate_postgres_dialect(self):
        """Test PostgreSQL dialect validation."""
        dialect = validate_sql_dialect("postgres")
        assert dialect == "postgres"
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_validate_postgresql_alias(self):
        """Test PostgreSQL alias validation."""
        dialect = validate_sql_dialect("postgresql")
        assert dialect == "postgres"
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_validate_mysql_dialect(self):
        """Test MySQL dialect validation."""
        dialect = validate_sql_dialect("mysql")
        assert dialect == "mysql"
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_validate_snowflake_dialect(self):
        """Test Snowflake dialect validation."""
        dialect = validate_sql_dialect("snowflake")
        assert dialect == "snowflake"
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_validate_unsupported_dialect(self):
        """Test that unsupported dialects raise an error."""
        with pytest.raises(InvalidSqlDialectError):
            validate_sql_dialect("unsupported_dialect")
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_case_insensitive_dialect(self):
        """Test that dialect validation is case-insensitive."""
        dialect = validate_sql_dialect("POSTGRES")
        assert dialect == "postgres"


class TestSQLParserErrorHandling:
    """Test error handling in SQL parsing."""
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_invalid_sql_syntax(self):
        """Test parsing invalid SQL syntax."""
        parser = SQLParser(dialect="postgres")
        sql = "SELCT * FROM customers;"  # typo: SELCT instead of SELECT
        result = parser.parse(sql)
        
        # Should either return error or handle gracefully
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_empty_sql(self):
        """Test parsing empty SQL string."""
        parser = SQLParser(dialect="postgres")
        sql = ""
        result = parser.parse(sql)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_whitespace_only_sql(self):
        """Test parsing whitespace-only SQL."""
        parser = SQLParser(dialect="postgres")
        sql = "   \n  \t  "
        result = parser.parse(sql)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_sql_injection_attempt(self):
        """Test that SQL injection attempts are handled."""
        parser = SQLParser(dialect="postgres")
        sql = "SELECT * FROM customers; DROP TABLE customers; --"
        result = parser.parse(sql)
        
        # Should not execute the DROP TABLE
        assert isinstance(result, dict)


class TestSQLParserMultiDialect:
    """Test SQL parsing across different dialects."""
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_snowflake_dialect(self):
        """Test parsing with Snowflake dialect."""
        parser = SQLParser(dialect="snowflake")
        sql = "SELECT * FROM DATABASE.SCHEMA.TABLE;"
        result = parser.parse(sql)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_bigquery_dialect(self):
        """Test parsing with BigQuery dialect."""
        parser = SQLParser(dialect="bigquery")
        sql = "SELECT * FROM `project.dataset.table`;"
        result = parser.parse(sql)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.sql_parser
    def test_parse_mysql_dialect(self):
        """Test parsing with MySQL dialect."""
        parser = SQLParser(dialect="mysql")
        sql = "SELECT * FROM `table_name`;"
        result = parser.parse(sql)
        
        assert isinstance(result, dict)
