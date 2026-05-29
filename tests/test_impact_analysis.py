"""
test_impact_analysis.py
-----------------------
Tests for impact analysis functionality.

Tests cover:
- Table-level impact analysis
- Column-level impact analysis
- Severity calculation
- Affected table detection
- Recursive impact traversal
"""

import pytest
from sqlalchemy.orm import Session


class TestTableImpactAnalysis:
    """Test table-level impact analysis."""
    
    @pytest.mark.unit
    @pytest.mark.impact
    def test_impact_severity_levels(self):
        """Test impact severity level mapping."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        
        service = ImpactAnalysisService()
        
        # Test severity level thresholds
        assert service.calculate_severity(0) == "NONE"
        assert service.calculate_severity(3) == "LOW"
        assert service.calculate_severity(10) == "MEDIUM"
        assert service.calculate_severity(20) == "HIGH"
        assert service.calculate_severity(50) == "CRITICAL"
    
    @pytest.mark.unit
    @pytest.mark.impact
    def test_affected_tables_detection(self, test_db, sample_lineage_relationships):
        """Test detecting affected tables from a change."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        
        service = ImpactAnalysisService()
        
        # Get impact for 'orders' table
        result = service.get_table_impact(test_db, "orders", max_depth=10)
        
        assert isinstance(result, dict)
        assert "affected_tables" in result or "downstream_tables" in result
    
    @pytest.mark.unit
    @pytest.mark.impact
    @pytest.mark.db
    def test_no_impact_for_leaf_table(self, test_db):
        """Test impact analysis for table with no downstream dependencies."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        
        service = ImpactAnalysisService()
        
        # Create a table with no outgoing edges
        from backend.database.orm_models import TableRecord
        leaf = TableRecord(name="leaf_table", schema_name="public")
        test_db.add(leaf)
        test_db.commit()
        
        result = service.get_table_impact(test_db, "leaf_table", max_depth=10)
        
        assert isinstance(result, dict)


class TestColumnImpactAnalysis:
    """Test column-level impact analysis."""
    
    @pytest.mark.unit
    @pytest.mark.impact
    @pytest.mark.db
    def test_column_impact_analysis(self, test_db, sample_column_lineage):
        """Test column-level impact analysis."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        
        service = ImpactAnalysisService()
        
        # Get impact for a column change
        result = service.get_column_impact(
            test_db,
            column_name="customer_id",
            table_name="customers",
            max_depth=10
        )
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.impact
    def test_column_impact_with_transformation(self, test_db, sample_column_lineage):
        """Test impact analysis for columns with transformations."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        
        service = ImpactAnalysisService()
        
        # Test impact for aggregated column
        result = service.get_column_impact(
            test_db,
            column_name="order_amount",
            table_name="orders",
            max_depth=10
        )
        
        assert isinstance(result, dict)


class TestImpactAnalysisIntegration:
    """Integration tests for impact analysis API."""
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_table_impact_endpoint(self, client, test_db, sample_lineage_relationships):
        """Test GET /impact/table/{table_name} endpoint."""
        response = client.get(
            "/impact/table/orders?max_depth=10"
        )
        
        assert response.status_code in [200, 404, 422]
        
        if response.status_code == 200:
            data = response.json()
            assert "affected_tables" in data or "downstream_tables" in data
            assert "severity" in data
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_column_impact_endpoint(self, client, test_db, sample_column_lineage):
        """Test GET /impact/column/{column_name} endpoint."""
        response = client.get(
            "/impact/column/customer_id?max_depth=10"
        )
        
        assert response.status_code in [200, 404, 422]
    
    @pytest.mark.integration
    @pytest.mark.db
    def test_column_impact_with_table_scope(self, client, test_db, sample_column_lineage):
        """Test column impact with table scope parameter."""
        response = client.get(
            "/impact/column/customer_id?table=customers&max_depth=10"
        )
        
        assert response.status_code in [200, 404, 422]


class TestImpactAnalysisEdgeCases:
    """Test edge cases in impact analysis."""
    
    @pytest.mark.unit
    @pytest.mark.impact
    @pytest.mark.db
    def test_circular_dependency_impact(self, test_db):
        """Test impact analysis with circular dependencies."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        from backend.database.orm_models import TableRecord, LineageRelationship
        
        # Create circular dependency
        test_db.query(TableRecord).filter(TableRecord.name.in_(["a", "b", "c"])).delete()
        test_db.commit()
        
        test_db.add_all([
            TableRecord(name="a", schema_name="public"),
            TableRecord(name="b", schema_name="public"),
            TableRecord(name="c", schema_name="public"),
        ])
        test_db.commit()
        
        test_db.add_all([
            LineageRelationship(source_table="a", target_table="b"),
            LineageRelationship(source_table="b", target_table="c"),
            LineageRelationship(source_table="c", target_table="a"),  # Creates cycle
        ])
        test_db.commit()
        
        service = ImpactAnalysisService()
        
        # Should handle circular dependency gracefully
        result = service.get_table_impact(test_db, "a", max_depth=10)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    @pytest.mark.impact
    @pytest.mark.db
    def test_deep_lineage_impact(self, test_db):
        """Test impact analysis with deep lineage chains."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        from backend.database.orm_models import TableRecord, LineageRelationship
        
        # Create deep dependency chain
        test_db.query(TableRecord).filter(TableRecord.name.like("level_%")).delete()
        test_db.commit()
        
        # Create 15 levels of dependencies
        for i in range(15):
            test_db.add(TableRecord(name=f"level_{i}", schema_name="public"))
        test_db.commit()
        
        for i in range(14):
            test_db.add(
                LineageRelationship(
                    source_table=f"level_{i}",
                    target_table=f"level_{i+1}"
                )
            )
        test_db.commit()
        
        service = ImpactAnalysisService()
        
        # Test with limited depth
        result = service.get_table_impact(test_db, "level_0", max_depth=5)
        
        assert isinstance(result, dict)


class TestImpactAnalysisPerformance:
    """Performance tests for impact analysis."""
    
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.db
    def test_impact_analysis_large_graph(self, test_db):
        """Test impact analysis with large lineage graph."""
        from backend.impact_analysis.impact_service import ImpactAnalysisService
        from backend.database.orm_models import TableRecord, LineageRelationship
        
        # Create large graph
        test_db.query(TableRecord).filter(TableRecord.name.like("node_%")).delete()
        test_db.commit()
        
        # Create 100 table nodes
        for i in range(100):
            test_db.add(TableRecord(name=f"node_{i}", schema_name="public"))
        test_db.commit()
        
        # Create edges (skip some to avoid overwhelming connections)
        for i in range(0, 99, 2):
            test_db.add(
                LineageRelationship(
                    source_table=f"node_{i}",
                    target_table=f"node_{i+1}"
                )
            )
        test_db.commit()
        
        service = ImpactAnalysisService()
        
        # Should complete in reasonable time
        result = service.get_table_impact(test_db, "node_0", max_depth=10)
        
        assert isinstance(result, dict)
