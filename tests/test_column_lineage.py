"""
test_column_lineage.py
----------------------
Unit tests for column-level lineage functionality.

Tests cover:
- Column lineage creation
- Recursive column upstream/downstream traversal
- Column transformation tracking
- Error handling for invalid columns/tables
"""

import pytest
from sqlalchemy.orm import Session
from backend.exceptions import (
    InvalidColumnNameError,
    InvalidTableNameError,
    ColumnNotFoundError,
)
from backend.validators import (
    validate_column_name,
    validate_table_name,
    extract_table_and_schema,
)


class TestColumnNameValidation:
    """Test column name validation."""
    
    @pytest.mark.unit
    def test_validate_simple_column_name(self):
        """Test validation of a simple column name."""
        name = validate_column_name("customer_id")
        assert name == "customer_id"
    
    @pytest.mark.unit
    def test_validate_column_name_with_uppercase(self):
        """Test validation of column name with uppercase letters."""
        name = validate_column_name("CustomerID")
        assert name == "CustomerID"
    
    @pytest.mark.unit
    def test_validate_column_name_with_numbers(self):
        """Test validation of column name with numbers."""
        name = validate_column_name("column_123")
        assert name == "column_123"
    
    @pytest.mark.unit
    def test_validate_column_name_with_leading_underscore(self):
        """Test validation of column name starting with underscore."""
        name = validate_column_name("_internal_id")
        assert name == "_internal_id"
    
    @pytest.mark.unit
    def test_validate_column_name_empty(self):
        """Test that empty column name raises error."""
        with pytest.raises(InvalidColumnNameError):
            validate_column_name("")
    
    @pytest.mark.unit
    def test_validate_column_name_whitespace_only(self):
        """Test that whitespace-only column name raises error."""
        with pytest.raises(InvalidColumnNameError):
            validate_column_name("   ")
    
    @pytest.mark.unit
    def test_validate_column_name_leading_number(self):
        """Test that column name starting with number raises error."""
        with pytest.raises(InvalidColumnNameError):
            validate_column_name("123column")
    
    @pytest.mark.unit
    def test_validate_column_name_special_characters(self):
        """Test that special characters in column name raise error."""
        with pytest.raises(InvalidColumnNameError):
            validate_column_name("column-name")
    
    @pytest.mark.unit
    def test_validate_column_name_sql_injection(self):
        """Test that SQL injection patterns in column name raise error."""
        with pytest.raises(InvalidColumnNameError):
            validate_column_name("column; DROP TABLE")
    
    @pytest.mark.unit
    def test_validate_column_name_too_long(self):
        """Test that overly long column names raise error."""
        long_name = "a" * 256
        with pytest.raises(InvalidColumnNameError):
            validate_column_name(long_name)
    
    @pytest.mark.unit
    def test_validate_column_name_with_context(self):
        """Test column name validation with table context."""
        name = validate_column_name("order_id", table_name="orders")
        assert name == "order_id"
    
    @pytest.mark.unit
    def test_validate_column_name_with_context_error(self):
        """Test that invalid column name with context shows context."""
        with pytest.raises(InvalidColumnNameError) as exc_info:
            validate_column_name("", table_name="customers")
        
        exc = exc_info.value
        assert exc.table_name == "customers"


class TestTableNameValidation:
    """Test table name validation."""
    
    @pytest.mark.unit
    def test_validate_simple_table_name(self):
        """Test validation of a simple table name."""
        name = validate_table_name("customers")
        assert name == "customers"
    
    @pytest.mark.unit
    def test_validate_schema_qualified_table_name(self):
        """Test validation of schema-qualified table name."""
        name = validate_table_name("public.customers")
        assert name == "public.customers"
    
    @pytest.mark.unit
    def test_validate_table_name_with_underscore(self):
        """Test validation of table name with underscores."""
        name = validate_table_name("customer_orders")
        assert name == "customer_orders"
    
    @pytest.mark.unit
    def test_validate_table_name_empty(self):
        """Test that empty table name raises error."""
        with pytest.raises(InvalidTableNameError):
            validate_table_name("")
    
    @pytest.mark.unit
    def test_validate_table_name_special_characters(self):
        """Test that special characters in table name raise error."""
        with pytest.raises(InvalidTableNameError):
            validate_table_name("customer-orders")
    
    @pytest.mark.unit
    def test_validate_table_name_sql_injection(self):
        """Test that SQL injection patterns in table name raise error."""
        with pytest.raises(InvalidTableNameError):
            validate_table_name("customers; DROP TABLE")
    
    @pytest.mark.unit
    def test_validate_table_name_too_many_dots(self):
        """Test that table names with too many dots raise error."""
        with pytest.raises(InvalidTableNameError):
            validate_table_name("db.schema.public.customers")
    
    @pytest.mark.unit
    def test_extract_table_and_schema_simple(self):
        """Test extracting table name and schema."""
        table, schema = extract_table_and_schema("customers")
        assert table == "customers"
        assert schema is None
    
    @pytest.mark.unit
    def test_extract_table_and_schema_qualified(self):
        """Test extracting from schema-qualified name."""
        table, schema = extract_table_and_schema("public.customers")
        assert table == "customers"
        assert schema == "public"


class TestColumnLineageOperations:
    """Test column lineage operations in database."""
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_create_column_lineage_record(self, test_db, sample_column_lineage):
        """Test creating a column lineage record."""
        from backend.database.orm_models import ColumnLineage
        
        columns = test_db.query(ColumnLineage).all()
        assert len(columns) > 0
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_column_lineage_with_transformation(self, test_db):
        """Test column lineage with transformation."""
        from backend.database.orm_models import ColumnLineage
        
        col = ColumnLineage(
            source_table="orders",
            source_column="order_amount",
            target_table="analytics",
            target_column="total_value",
            transformation="ROUND(order_amount, 2)",
            transformation_type="FUNCTION",
        )
        
        test_db.add(col)
        test_db.commit()
        test_db.refresh(col)
        
        assert col.transformation == "ROUND(order_amount, 2)"
        assert col.transformation_type == "FUNCTION"
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_column_lineage_aggregation(self, test_db):
        """Test column lineage with aggregation transformation."""
        from backend.database.orm_models import ColumnLineage
        
        col = ColumnLineage(
            source_table="transactions",
            source_column="amount",
            target_table="summary",
            target_column="total_amount",
            transformation="SUM(amount)",
            transformation_type="AGGREGATION",
        )
        
        test_db.add(col)
        test_db.commit()
        test_db.refresh(col)
        
        assert col.transformation_type == "AGGREGATION"


class TestColumnLineageValidation:
    """Test column lineage validation rules."""
    
    @pytest.mark.unit
    def test_column_not_self_referential(self):
        """Test that self-referential column lineage is rejected."""
        from backend.models.lineage_models import ColumnLineageCreate
        
        with pytest.raises(ValueError):
            ColumnLineageCreate(
                source_table="customers",
                source_column="id",
                target_table="customers",
                target_column="id",
            )
    
    @pytest.mark.unit
    def test_column_lineage_with_dag_id(self):
        """Test column lineage with DAG identifier."""
        from backend.models.lineage_models import ColumnLineageCreate
        
        lineage = ColumnLineageCreate(
            source_table="raw_data",
            source_column="customer_id",
            target_table="processed_data",
            target_column="customer_id",
            dag_id="etl_pipeline",
        )
        
        assert lineage.dag_id == "etl_pipeline"
    
    @pytest.mark.unit
    def test_column_lineage_request_model(self):
        """Test ColumnLineageCreate request model validation."""
        from backend.models.lineage_models import ColumnLineageCreate
        
        lineage = ColumnLineageCreate(
            source_table="source_table",
            source_column="source_col",
            target_table="target_table",
            target_column="target_col",
            transformation="UPPER(source_col)",
        )
        
        assert lineage.source_table == "source_table"
        assert lineage.transformation == "UPPER(source_col)"


class TestColumnLineageTraversal:
    """Test column lineage traversal operations."""
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_query_column_lineage_by_table_column(self, test_db, sample_column_lineage):
        """Test querying column lineage by table and column."""
        from backend.database.orm_models import ColumnLineage
        
        col = test_db.query(ColumnLineage).filter(
            ColumnLineage.source_table == "customers",
            ColumnLineage.source_column == "customer_id"
        ).first()
        
        assert col is not None
        assert col.source_table == "customers"
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_count_column_lineage_by_transformation_type(self, test_db, sample_column_lineage):
        """Test counting column lineage by transformation type."""
        from backend.database.orm_models import ColumnLineage
        
        aggregations = test_db.query(ColumnLineage).filter(
            ColumnLineage.transformation_type == "AGGREGATION"
        ).all()
        
        assert len(aggregations) > 0
    
    @pytest.mark.unit
    @pytest.mark.db
    def test_find_all_downstream_columns(self, test_db, sample_column_lineage):
        """Test finding all downstream columns for a given source column."""
        from backend.database.orm_models import ColumnLineage
        
        # Find all columns that depend on customers.customer_id
        downstream = test_db.query(ColumnLineage).filter(
            ColumnLineage.source_table == "customers",
            ColumnLineage.source_column == "customer_id"
        ).all()
        
        assert len(downstream) > 0
