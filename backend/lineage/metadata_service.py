"""
metadata_service.py
-------------------
Unified metadata service for the Enterprise Data Lineage Platform.

Combines SQL lineage metadata, column lineage metadata, and Airflow DAG
metadata into a single centralized view.

Public API
----------
    service = MetadataService()
    result  = service.get_unified_metadata(db)
    # {
    #   "tables":       [...],
    #   "columns":      [...],
    #   "dags":         [...],
    #   "dependencies": [...]
    # }
"""

import logging
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.database.orm_models import (
    ColumnRecord,
    DAGRecord,
    LineageRelationship,
    TableRecord,
    TaskDependency,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """
    Centralises access to all persisted lineage metadata.

    Every public method accepts a SQLAlchemy ``Session`` and returns plain
    Python dicts that are safe to serialise with Pydantic / FastAPI.
    """

    # ------------------------------------------------------------------
    # Unified endpoint
    # ------------------------------------------------------------------

    def get_unified_metadata(self, db: Session) -> Dict:
        """
        Return a single dict combining tables, columns, DAGs, and
        lineage / task-dependency edges.
        """
        logger.info("Fetching unified metadata")
        try:
            return {
                "tables": self.get_tables(db),
                "columns": self.get_columns(db),
                "dags": self.get_dags(db),
                "dependencies": self.get_dependencies(db),
            }
        except Exception:
            logger.exception("Failed to fetch unified metadata")
            raise

    # ------------------------------------------------------------------
    # Individual getters
    # ------------------------------------------------------------------

    def get_tables(self, db: Session) -> List[Dict]:
        """Return all catalogued table records."""
        logger.debug("Fetching all table records")
        try:
            records = db.query(TableRecord).order_by(TableRecord.name).all()
            return [r.to_dict() for r in records]
        except Exception:
            logger.exception("Failed to fetch table records")
            raise

    def get_columns(self, db: Session) -> List[Dict]:
        """Return all column records."""
        logger.debug("Fetching all column records")
        try:
            records = db.query(ColumnRecord).order_by(ColumnRecord.table_id, ColumnRecord.name).all()
            return [r.to_dict() for r in records]
        except Exception:
            logger.exception("Failed to fetch column records")
            raise

    def get_dags(self, db: Session) -> List[Dict]:
        """Return all DAG records with their task lists."""
        logger.debug("Fetching all DAG records")
        try:
            records = db.query(DAGRecord).order_by(DAGRecord.dag_id).all()
            return [r.to_dict() for r in records]
        except Exception:
            logger.exception("Failed to fetch DAG records")
            raise

    def get_dependencies(self, db: Session) -> List[Dict]:
        """Return all lineage relationships and task dependency edges."""
        logger.debug("Fetching all dependency records")
        try:
            lineage = db.query(LineageRelationship).order_by(
                LineageRelationship.source_table,
                LineageRelationship.target_table,
            ).all()
            task_deps = db.query(TaskDependency).order_by(
                TaskDependency.dag_record_id,
                TaskDependency.upstream_task,
            ).all()
            return {
                "lineage_edges": [r.to_dict() for r in lineage],
                "task_edges": [r.to_dict() for r in task_deps],
            }
        except Exception:
            logger.exception("Failed to fetch dependency records")
            raise
