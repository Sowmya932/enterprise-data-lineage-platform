"""
test_lineage_graph.py
---------------------
Unit / integration tests for Week 2 Day 1 features:

  * LineageGraphService  (graph_service.py)
  * save_lineage_relationship  (lineage_service.py)
  * GET /upstream/{table_name}
  * GET /downstream/{table_name}
  * POST /lineage-relationship
  * GET /lineage-graph

All database operations run against an in-memory SQLite database so no
live PostgreSQL instance is required.  SQLite in-memory databases are
per-connection, so StaticPool is used to guarantee every engine access
reuses the same connection and therefore sees the same schema/data.

The startup event (which would try to connect to PostgreSQL) is patched
out so TestClient can start without a live database server.
"""

import os
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Must set DATABASE_URL before any backend import so db.py does not crash
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from backend.database.db import Base, get_db          # noqa: E402
from backend.database.orm_models import LineageRelationship, TableRecord  # noqa: E402
from backend.main import app                           # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """
    Single-connection SQLite engine.  StaticPool ensures create_all and all
    subsequent ORM queries share the same in-memory connection.
    """
    engine = create_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Clean SQLAlchemy session backed by the test SQLite engine."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    TestClient wired to SQLite via FastAPI dependency override.
    The startup event is patched out to avoid a PostgreSQL connection attempt.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with patch.object(app.router, "on_startup", []):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _seed(session, edges):
    """Insert TableRecord + LineageRelationship rows from (src, tgt) pairs."""
    table_names = {name for pair in edges for name in pair}
    for name in table_names:
        if not session.query(TableRecord).filter_by(name=name).first():
            session.add(TableRecord(name=name, schema_name="public"))
    for src, tgt in edges:
        session.add(LineageRelationship(source_table=src, target_table=tgt))
    session.commit()


# ===========================================================================
# ORM model tests
# ===========================================================================

class TestLineageRelationshipModel:
    def test_dag_id_field_exists(self, db_session):
        edge = LineageRelationship(
            source_table="orders",
            target_table="sales_summary",
            dag_id="etl_pipeline",
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(edge)
        assert edge.dag_id == "etl_pipeline"
        d = edge.to_dict()
        assert d["dag_id"] == "etl_pipeline"
        assert d["source_table"] == "orders"
        assert d["target_table"] == "sales_summary"

    def test_dag_id_nullable(self, db_session):
        edge = LineageRelationship(source_table="a", target_table="b")
        db_session.add(edge)
        db_session.commit()
        assert edge.dag_id is None


# ===========================================================================
# POST /lineage-relationship
# ===========================================================================

class TestCreateLineageRelationship:
    def test_create_basic(self, client):
        resp = client.post(
            "/lineage-relationship",
            json={"source_table": "orders", "target_table": "sales_summary"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_table"] == "orders"
        assert body["target_table"] == "sales_summary"
        assert body["id"] is not None

    def test_create_with_column_and_dag(self, client):
        resp = client.post(
            "/lineage-relationship",
            json={
                "source_table": "customers",
                "target_table": "orders",
                "column_name": "customer_id",
                "source_column": "id",
                "dag_id": "etl_pipeline",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["column_name"] == "customer_id"
        assert body["source_column"] == "id"
        assert body["dag_id"] == "etl_pipeline"

    def test_self_loop_rejected(self, client):
        resp = client.post(
            "/lineage-relationship",
            json={"source_table": "orders", "target_table": "orders"},
        )
        assert resp.status_code == 422

    def test_same_table_service_rejected(self, client, monkeypatch):
        from fastapi import HTTPException

        def _mock_save(db, *, source_table, target_table, **kw):
            raise HTTPException(status_code=400, detail="must differ")

        monkeypatch.setattr("backend.api.lineage.save_lineage_relationship", _mock_save)
        resp = client.post(
            "/lineage-relationship",
            json={"source_table": "orders", "target_table": "orders_dup"},
        )
        assert resp.status_code == 400


# ===========================================================================
# GET /upstream/{table_name}
# ===========================================================================

class TestUpstreamLineage:
    def test_empty_upstream(self, client, db_session):
        db_session.add(TableRecord(name="raw_events", schema_name="public"))
        db_session.commit()
        resp = client.get("/upstream/raw_events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["table"] == "raw_events"
        assert body["direction"] == "upstream"
        assert body["lineage_chain"] == []
        assert body["upstream_tables"] == []

    def test_single_hop_upstream(self, client, db_session):
        _seed(db_session, [("orders", "sales_summary")])
        resp = client.get("/upstream/sales_summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_edges"] == 1
        assert "orders" in body["upstream_tables"]
        assert body["lineage_chain"][0]["source_table"] == "orders"
        assert body["lineage_chain"][0]["depth"] == 1

    def test_multi_hop_upstream(self, client, db_session):
        _seed(db_session, [("raw", "orders"), ("orders", "sales_summary")])
        resp = client.get("/upstream/sales_summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "orders" in body["upstream_tables"]
        assert "raw" in body["upstream_tables"]
        depths = {e["source_table"]: e["depth"] for e in body["lineage_chain"]}
        assert depths["orders"] == 1
        assert depths["raw"] == 2

    def test_max_depth_respected(self, client, db_session):
        _seed(db_session, [("raw", "orders"), ("orders", "sales_summary")])
        resp = client.get("/upstream/sales_summary?max_depth=1")
        assert resp.status_code == 200
        body = resp.json()
        assert all(e["depth"] == 1 for e in body["lineage_chain"])
        assert "raw" not in body["upstream_tables"]


# ===========================================================================
# GET /downstream/{table_name}
# ===========================================================================

class TestDownstreamLineage:
    def test_empty_downstream(self, client, db_session):
        db_session.add(TableRecord(name="leaf_table", schema_name="public"))
        db_session.commit()
        resp = client.get("/downstream/leaf_table")
        assert resp.status_code == 200
        body = resp.json()
        assert body["lineage_chain"] == []
        assert body["downstream_tables"] == []

    def test_single_hop_downstream(self, client, db_session):
        _seed(db_session, [("orders", "sales_summary")])
        resp = client.get("/downstream/orders")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_edges"] == 1
        assert "sales_summary" in body["downstream_tables"]
        assert body["lineage_chain"][0]["target_table"] == "sales_summary"
        assert body["lineage_chain"][0]["depth"] == 1

    def test_multi_hop_downstream(self, client, db_session):
        _seed(
            db_session,
            [("orders", "sales_summary"), ("sales_summary", "monthly_report")],
        )
        resp = client.get("/downstream/orders")
        assert resp.status_code == 200
        body = resp.json()
        assert "sales_summary" in body["downstream_tables"]
        assert "monthly_report" in body["downstream_tables"]
        depths = {e["target_table"]: e["depth"] for e in body["lineage_chain"]}
        assert depths["sales_summary"] == 1
        assert depths["monthly_report"] == 2


# ===========================================================================
# GET /lineage-graph
# ===========================================================================

class TestLineageGraph:
    def test_empty_graph(self, client):
        resp = client.get("/lineage-graph")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "edges" in body

    def test_graph_contains_seeded_data(self, client, db_session):
        _seed(db_session, [("orders", "sales_summary")])
        resp = client.get("/lineage-graph")
        assert resp.status_code == 200
        body = resp.json()
        assert "orders" in [e["source"] for e in body["edges"]]


# ===========================================================================
# Circular dependency protection
# ===========================================================================

class TestCircularDependencyGuard:
    def test_circular_dependency_rejected(self, client, monkeypatch):
        from fastapi import HTTPException

        def _patched_save(db, *, source_table, target_table, **kw):
            if source_table == "b" and target_table == "a":
                raise HTTPException(status_code=409, detail="Circular dependency detected.")
            return {"id": 1, "source_table": source_table, "target_table": target_table,
                    "column_name": None, "source_column": None, "dag_id": None, "created_at": None}

        monkeypatch.setattr("backend.api.lineage.save_lineage_relationship", _patched_save)
        resp = client.post(
            "/lineage-relationship",
            json={"source_table": "b", "target_table": "a"},
        )
        assert resp.status_code == 409
        assert "circular" in resp.json()["detail"].lower()

    def test_non_circular_edge_accepted(self, client, monkeypatch):
        def _patched_save(db, *, source_table, target_table, **kw):
            return {"id": 99, "source_table": source_table, "target_table": target_table,
                    "column_name": None, "source_column": None, "dag_id": None,
                    "created_at": "2026-05-21T00:00:00"}

        monkeypatch.setattr("backend.api.lineage.save_lineage_relationship", _patched_save)
        resp = client.post(
            "/lineage-relationship",
            json={"source_table": "a", "target_table": "b"},
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == 99

    def test_real_circular_detection_python(self, db_session):
        """Python BFS cycle detector: A->B->C exists, so C->A is circular."""
        from backend.lineage.graph_service import LineageGraphService
        _seed(db_session, [("a", "b"), ("b", "c")])
        service = LineageGraphService()
        assert service.has_circular_dependency(db_session, "c", "a") is True
        assert service.has_circular_dependency(db_session, "d", "a") is False


# ===========================================================================
# Health check
# ===========================================================================

def test_home(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["docs"] == "/docs"
