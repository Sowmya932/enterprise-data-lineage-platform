"""
test_api_integration.py
-----------------------
Integration tests for FastAPI endpoints.

Tests cover:
- SQL parsing API
- Lineage relationship management
- Recursive lineage traversal
- Column lineage operations
- Search APIs
- Impact analysis APIs
- Error handling and validation
"""

import pytest
from fastapi import status


class TestLineageParsingAPI:
    """Test SQL lineage parsing endpoints."""
    
    @pytest.mark.integration
    def test_parse_sql_endpoint(self, client, sample_sql_queries):
        """Test POST /parse-sql endpoint."""
        response = client.post(
            "/parse-sql",
            json={
                "sql": sample_sql_queries["simple_select"],
                "dialect": "postgres",
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "lineage" in data
    
    @pytest.mark.integration
    def test_parse_sql_with_join(self, client, sample_sql_queries):
        """Test parsing a JOIN query."""
        response = client.post(
            "/parse-sql",
            json={
                "sql": sample_sql_queries["join_query"],
                "dialect": "postgres",
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        lineage = data.get("lineage", {})
        assert lineage.get("source_tables") is not None
    
    @pytest.mark.integration
    def test_parse_sql_with_cte(self, client, sample_sql_queries):
        """Test parsing a CTE query."""
        response = client.post(
            "/parse-sql",
            json={
                "sql": sample_sql_queries["cte_query"],
                "dialect": "postgres",
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.integration
    def test_parse_sql_invalid_dialect(self, client, sample_sql_queries):
        """Test parsing with unsupported dialect."""
        response = client.post(
            "/parse-sql",
            json={
                "sql": sample_sql_queries["simple_select"],
                "dialect": "unsupported_dialect",
            }
        )
        
        # Should return validation error
        assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]
    
    @pytest.mark.integration
    def test_parse_sql_empty_sql(self, client):
        """Test parsing empty SQL."""
        response = client.post(
            "/parse-sql",
            json={
                "sql": "",
                "dialect": "postgres",
            }
        )
        
        # Should handle gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]


class TestLineageRelationshipAPI:
    """Test lineage relationship endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_create_lineage_relationship(self, client, test_db):
        """Test POST /lineage-relationship endpoint."""
        # First ensure tables exist
        from backend.database.orm_models import TableRecord
        
        test_db.query(TableRecord).filter(TableRecord.name == "source_table").delete()
        test_db.query(TableRecord).filter(TableRecord.name == "target_table").delete()
        test_db.commit()
        
        test_db.add(TableRecord(name="source_table", schema_name="public"))
        test_db.add(TableRecord(name="target_table", schema_name="public"))
        test_db.commit()
        
        response = client.post(
            "/lineage-relationship",
            json={
                "source_table": "source_table",
                "target_table": "target_table",
                "dag_id": "test_dag",
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["source_table"] == "source_table"
        assert data["target_table"] == "target_table"
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_create_lineage_relationship_same_table_error(self, client):
        """Test that same source and target raises error."""
        response = client.post(
            "/lineage-relationship",
            json={
                "source_table": "customers",
                "target_table": "customers",
            }
        )
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRecursiveLineageAPI:
    """Test recursive lineage traversal endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_upstream_lineage(self, client, test_db, sample_lineage_relationships):
        """Test GET /upstream/{table_name} endpoint."""
        response = client.get("/upstream/customer_analytics?max_depth=10")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "upstream_tables" in data
        assert "lineage_chain" in data
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_downstream_lineage(self, client, test_db, sample_lineage_relationships):
        """Test GET /downstream/{table_name} endpoint."""
        response = client.get("/downstream/orders?max_depth=10")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "downstream_tables" in data
        assert "lineage_chain" in data
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_upstream_lineage_nonexistent_table(self, client):
        """Test upstream lineage for nonexistent table."""
        response = client.get("/upstream/nonexistent_table")
        
        # Should return empty or not found
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


class TestLineageGraphAPI:
    """Test full lineage graph endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_full_lineage_graph(self, client, test_db, sample_lineage_relationships):
        """Test GET /lineage-graph endpoint."""
        response = client.get("/lineage-graph")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_lineage_graph_contains_sample_data(self, client, test_db, sample_lineage_relationships):
        """Test that lineage graph contains sample data."""
        response = client.get("/lineage-graph")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should have nodes and edges from sample data
        assert len(data["edges"]) > 0


class TestColumnLineageAPI:
    """Test column-level lineage endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_create_column_lineage(self, client, test_db):
        """Test POST /column-lineage endpoint."""
        # Ensure tables exist
        from backend.database.orm_models import TableRecord
        
        test_db.query(TableRecord).filter(TableRecord.name == "source").delete()
        test_db.query(TableRecord).filter(TableRecord.name == "target").delete()
        test_db.commit()
        
        test_db.add(TableRecord(name="source", schema_name="public"))
        test_db.add(TableRecord(name="target", schema_name="public"))
        test_db.commit()
        
        response = client.post(
            "/column-lineage",
            json={
                "source_table": "source",
                "source_column": "id",
                "target_table": "target",
                "target_column": "source_id",
                "transformation": "DIRECT",
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["source_table"] == "source"
        assert data["target_column"] == "source_id"
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_column_upstream_lineage(self, client, test_db, sample_column_lineage):
        """Test GET /column-upstream/{table}/{column} endpoint."""
        response = client.get(
            "/column-upstream/customer_analytics/customer_id?max_depth=10"
        )
        
        # May return 200 or 404 depending on data
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "upstream_columns" in data
            assert "lineage_chain" in data


class TestSearchAPI:
    """Test metadata search endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_search_tables(self, client, test_db, sample_tables):
        """Test GET /search/tables endpoint."""
        response = client.get("/search/tables?q=customer")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data or "tables" in data
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_search_tables_with_exact_match(self, client, test_db, sample_tables):
        """Test table search with exact match."""
        response = client.get(
            "/search/tables?q=customers&match_type=exact"
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_search_tables_empty_query(self, client):
        """Test table search with empty query."""
        response = client.get("/search/tables?q=")
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestImpactAnalysisAPI:
    """Test impact analysis endpoints."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_table_impact(self, client, test_db, sample_lineage_relationships):
        """Test GET /impact/table/{table_name} endpoint."""
        response = client.get("/impact/table/customers?max_depth=10")
        
        # May return 200 or 404 depending on data
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "affected_tables" in data
            assert "severity" in data
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_get_column_impact(self, client, test_db, sample_column_lineage):
        """Test GET /impact/column/{column_name} endpoint."""
        response = client.get("/impact/column/customer_id?max_depth=10")
        
        # May return 200 or 404
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


class TestErrorHandling:
    """Test API error handling."""
    
    @pytest.mark.integration
    def test_nonexistent_endpoint(self, client):
        """Test requesting nonexistent endpoint."""
        response = client.get("/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error_code" in data or "detail" in data
    
    @pytest.mark.integration
    def test_invalid_json_body(self, client):
        """Test sending invalid JSON body."""
        response = client.post(
            "/parse-sql",
            content="invalid json {",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.integration
    def test_missing_required_field(self, client):
        """Test missing required field in request."""
        response = client.post(
            "/parse-sql",
            json={
                "dialect": "postgres",
                # Missing required 'sql' field
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    @pytest.mark.integration
    def test_health_check(self, client):
        """Test GET /health endpoint."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.integration
    def test_root_endpoint(self, client):
        """Test GET / endpoint."""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "docs" in data


class TestRequestIDTracking:
    """Test request ID tracking and correlation."""
    
    @pytest.mark.integration
    def test_request_id_header_in_response(self, client):
        """Test that request ID is returned in response headers."""
        response = client.get("/health", headers={"x-request-id": "test-123"})
        
        assert response.status_code == status.HTTP_200_OK
        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"] == "test-123"
    
    @pytest.mark.integration
    def test_auto_generated_request_id(self, client):
        """Test that request ID is auto-generated if not provided."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        assert "x-request-id" in response.headers
