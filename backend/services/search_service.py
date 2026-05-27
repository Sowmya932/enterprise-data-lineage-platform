"""
search_service.py
-----------------
Metadata search and discovery service.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.database.orm_models import (
    ColumnLineage,
    ColumnRecord,
    DAGRecord,
    LineageRelationship,
    TableRecord,
    TaskDependency,
    TaskRecord,
)
from backend.impact_analysis.impact_service import ImpactAnalysisService
from backend.lineage.graph_service import LineageGraphService
from backend.models.search_models import MatchType

logger = logging.getLogger(__name__)


class SearchService:
    """Service layer for metadata search/discovery and detail retrieval."""

    def __init__(self) -> None:
        self._graph = LineageGraphService()
        self._impact = ImpactAnalysisService()

    @staticmethod
    def _apply_text_match(column, q: str, match_type: MatchType):
        if match_type == MatchType.exact:
            return func.lower(column) == q.lower()
        return column.ilike(f"%{q}%")

    @staticmethod
    def _pagination(total: int, limit: int, offset: int) -> Dict[str, Any]:
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": (offset + limit) < total,
        }

    def search_tables(
        self,
        db: Session,
        *,
        q: str,
        match_type: MatchType,
        schema_name: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        logger.info(
            "Searching tables | q=%s match=%s schema=%s limit=%d offset=%d",
            q,
            match_type.value,
            schema_name,
            limit,
            offset,
        )
        query = db.query(TableRecord).filter(
            self._apply_text_match(TableRecord.name, q, match_type)
        )

        if schema_name:
            query = query.filter(func.lower(TableRecord.schema_name) == schema_name.lower())

        total = query.count()
        rows = (
            query.order_by(TableRecord.schema_name, TableRecord.name)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "query": q,
            "match_type": match_type,
            "filters": {"schema_name": schema_name},
            "pagination": self._pagination(total, limit, offset),
            "items": [r.to_dict() for r in rows],
        }

    def search_columns(
        self,
        db: Session,
        *,
        q: str,
        match_type: MatchType,
        table_name: Optional[str],
        schema_name: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        logger.info(
            "Searching columns | q=%s match=%s table=%s schema=%s limit=%d offset=%d",
            q,
            match_type.value,
            table_name,
            schema_name,
            limit,
            offset,
        )

        query = (
            db.query(ColumnRecord, TableRecord)
            .join(TableRecord, ColumnRecord.table_id == TableRecord.id)
            .filter(self._apply_text_match(ColumnRecord.name, q, match_type))
        )

        if table_name:
            query = query.filter(func.lower(TableRecord.name) == table_name.lower())
        if schema_name:
            query = query.filter(func.lower(TableRecord.schema_name) == schema_name.lower())

        total = query.count()
        rows = (
            query
            .order_by(TableRecord.schema_name, TableRecord.name, ColumnRecord.name)
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = []
        for col, table in rows:
            payload = col.to_dict()
            payload["table_name"] = table.name
            payload["schema_name"] = table.schema_name
            items.append(payload)

        return {
            "query": q,
            "match_type": match_type,
            "filters": {"table_name": table_name, "schema_name": schema_name},
            "pagination": self._pagination(total, limit, offset),
            "items": items,
        }

    def search_dags(
        self,
        db: Session,
        *,
        q: str,
        match_type: MatchType,
        task_name: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        logger.info(
            "Searching DAGs | q=%s match=%s task_name=%s limit=%d offset=%d",
            q,
            match_type.value,
            task_name,
            limit,
            offset,
        )

        query = db.query(DAGRecord).filter(
            self._apply_text_match(DAGRecord.dag_id, q, match_type)
        )

        if task_name:
            query = query.join(TaskRecord, TaskRecord.dag_id == DAGRecord.id).filter(
                TaskRecord.task_id.ilike(f"%{task_name}%")
            )

        total = query.distinct(DAGRecord.id).count()
        rows = (
            query
            .distinct(DAGRecord.id)
            .order_by(DAGRecord.dag_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = []
        for dag in rows:
            payload = dag.to_dict()
            payload["task_count"] = len(dag.tasks)
            items.append(payload)

        return {
            "query": q,
            "match_type": match_type,
            "filters": {"task_name": task_name},
            "pagination": self._pagination(total, limit, offset),
            "items": items,
        }

    def search_lineage_relationships(
        self,
        db: Session,
        *,
        q: str,
        match_type: MatchType,
        source_table: Optional[str],
        target_table: Optional[str],
        dag_id: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        logger.info(
            "Searching lineage relationships | q=%s match=%s source=%s target=%s dag=%s",
            q,
            match_type.value,
            source_table,
            target_table,
            dag_id,
        )

        match = self._apply_text_match
        query = db.query(LineageRelationship).filter(
            or_(
                match(LineageRelationship.source_table, q, match_type),
                match(LineageRelationship.target_table, q, match_type),
                match(LineageRelationship.column_name, q, match_type),
                match(LineageRelationship.source_column, q, match_type),
                match(LineageRelationship.dag_id, q, match_type),
            )
        )

        if source_table:
            query = query.filter(
                func.lower(LineageRelationship.source_table) == source_table.lower()
            )
        if target_table:
            query = query.filter(
                func.lower(LineageRelationship.target_table) == target_table.lower()
            )
        if dag_id:
            query = query.filter(func.lower(LineageRelationship.dag_id) == dag_id.lower())

        total = query.count()
        rows = (
            query
            .order_by(LineageRelationship.source_table, LineageRelationship.target_table)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "query": q,
            "match_type": match_type,
            "filters": {
                "source_table": source_table,
                "target_table": target_table,
                "dag_id": dag_id,
            },
            "pagination": self._pagination(total, limit, offset),
            "items": [r.to_dict() for r in rows],
        }

    def get_table_details(self, db: Session, table_name: str, max_depth: int = 10) -> Dict[str, Any]:
        logger.info("Fetching table metadata details | table=%s", table_name)

        table_record = (
            db.query(TableRecord)
            .filter(func.lower(TableRecord.name) == table_name.lower())
            .first()
        )
        if not table_record:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

        normalized_table_name = table_record.name

        columns = (
            db.query(ColumnRecord)
            .filter(ColumnRecord.table_id == table_record.id)
            .order_by(ColumnRecord.name)
            .all()
        )

        lineage_rels = (
            db.query(LineageRelationship)
            .filter(
                or_(
                    func.lower(LineageRelationship.source_table) == normalized_table_name.lower(),
                    func.lower(LineageRelationship.target_table) == normalized_table_name.lower(),
                )
            )
            .order_by(LineageRelationship.source_table, LineageRelationship.target_table)
            .all()
        )

        related_dag_ids = sorted({r.dag_id for r in lineage_rels if r.dag_id})
        related_dags = (
            db.query(DAGRecord)
            .filter(DAGRecord.dag_id.in_(related_dag_ids))
            .order_by(DAGRecord.dag_id)
            .all()
            if related_dag_ids
            else []
        )

        upstream = self._graph.fetch_upstream_lineage(db, normalized_table_name, max_depth=max_depth)
        downstream = self._graph.fetch_downstream_lineage(db, normalized_table_name, max_depth=max_depth)
        impact = self._impact.analyze_table_impact(db, normalized_table_name, max_depth=max_depth)

        return {
            "table": table_record.to_dict(),
            "columns": [c.to_dict() for c in columns],
            "lineage_relationships": [r.to_dict() for r in lineage_rels],
            "dependencies": {
                "upstream": upstream,
                "downstream": downstream,
            },
            "related_dags": [d.to_dict() for d in related_dags],
            "impact_metadata": impact,
        }

    def get_column_details(
        self,
        db: Session,
        column_name: str,
        table_name: Optional[str] = None,
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        logger.info(
            "Fetching column metadata details | table=%s column=%s",
            table_name,
            column_name,
        )

        query = (
            db.query(ColumnRecord, TableRecord)
            .join(TableRecord, ColumnRecord.table_id == TableRecord.id)
            .filter(func.lower(ColumnRecord.name) == column_name.lower())
        )
        if table_name:
            query = query.filter(func.lower(TableRecord.name) == table_name.lower())

        rows = query.order_by(TableRecord.name).all()
        if not rows:
            if table_name:
                raise HTTPException(
                    status_code=404,
                    detail=f"Column '{column_name}' not found in table '{table_name}'.",
                )
            raise HTTPException(status_code=404, detail=f"Column '{column_name}' not found.")

        table_names = {t.name for _, t in rows}
        seed_table = table_name or rows[0][1].name

        col_lineage = db.query(ColumnLineage).filter(
            or_(
                func.lower(ColumnLineage.source_column) == column_name.lower(),
                func.lower(ColumnLineage.target_column) == column_name.lower(),
            )
        )
        if table_name:
            col_lineage = col_lineage.filter(
                or_(
                    func.lower(ColumnLineage.source_table) == table_name.lower(),
                    func.lower(ColumnLineage.target_table) == table_name.lower(),
                )
            )
        col_lineage_rows = col_lineage.order_by(
            ColumnLineage.source_table,
            ColumnLineage.source_column,
            ColumnLineage.target_table,
            ColumnLineage.target_column,
        ).all()

        related_dag_ids = sorted({r.dag_id for r in col_lineage_rows if r.dag_id})
        related_dags = (
            db.query(DAGRecord)
            .filter(DAGRecord.dag_id.in_(related_dag_ids))
            .order_by(DAGRecord.dag_id)
            .all()
            if related_dag_ids
            else []
        )

        dependencies: Dict[str, Any] = {
            "upstream": self._graph.fetch_column_upstream(
                db, seed_table, column_name, max_depth=max_depth
            ),
            "downstream": self._graph.fetch_column_downstream(
                db, seed_table, column_name, max_depth=max_depth
            ),
        }

        if table_name:
            impact = self._impact.analyze_column_impact(
                db, table_name, column_name, max_depth=max_depth
            )
        else:
            impact = self._impact.analyze_column_impact_by_name(
                db, column_name, max_depth=max_depth
            )

        return {
            "column_name": column_name,
            "table_filter": table_name,
            "matched_tables": sorted(table_names),
            "column_records": [
                {
                    **col.to_dict(),
                    "table_name": table.name,
                    "schema_name": table.schema_name,
                }
                for col, table in rows
            ],
            "lineage_relationships": [r.to_dict() for r in col_lineage_rows],
            "dependencies": dependencies,
            "related_dags": [d.to_dict() for d in related_dags],
            "impact_metadata": impact,
        }

    def get_dag_details(self, db: Session, dag_name: str) -> Dict[str, Any]:
        logger.info("Fetching DAG metadata details | dag=%s", dag_name)

        dag = (
            db.query(DAGRecord)
            .filter(func.lower(DAGRecord.dag_id) == dag_name.lower())
            .first()
        )
        if not dag:
            raise HTTPException(status_code=404, detail=f"DAG '{dag_name}' not found.")

        tasks = (
            db.query(TaskRecord)
            .filter(TaskRecord.dag_id == dag.id)
            .order_by(TaskRecord.task_id)
            .all()
        )
        task_dependencies = (
            db.query(TaskDependency)
            .filter(TaskDependency.dag_record_id == dag.id)
            .order_by(TaskDependency.upstream_task, TaskDependency.downstream_task)
            .all()
        )
        table_rels = (
            db.query(LineageRelationship)
            .filter(func.lower(LineageRelationship.dag_id) == dag.dag_id.lower())
            .order_by(LineageRelationship.source_table, LineageRelationship.target_table)
            .all()
        )
        col_rels = (
            db.query(ColumnLineage)
            .filter(func.lower(ColumnLineage.dag_id) == dag.dag_id.lower())
            .order_by(
                ColumnLineage.source_table,
                ColumnLineage.source_column,
                ColumnLineage.target_table,
                ColumnLineage.target_column,
            )
            .all()
        )

        related_tables = sorted(
            {r.source_table for r in table_rels}
            | {r.target_table for r in table_rels}
            | {r.source_table for r in col_rels}
            | {r.target_table for r in col_rels}
        )
        per_table_impact = {
            table_name: self._impact.analyze_table_impact(db, table_name, max_depth=10)
            for table_name in related_tables
        }

        return {
            "dag": dag.to_dict(),
            "tasks": [t.to_dict() for t in tasks],
            "task_dependencies": [d.to_dict() for d in task_dependencies],
            "lineage_relationships": {
                "table_level": [r.to_dict() for r in table_rels],
                "column_level": [r.to_dict() for r in col_rels],
            },
            "dependencies": {
                "task_dependency_count": len(task_dependencies),
                "related_table_count": len(related_tables),
                "related_tables": related_tables,
            },
            "related_dags": [dag.to_dict()],
            "impact_metadata": {
                "related_table_impacts": per_table_impact,
                "total_related_tables": len(related_tables),
            },
        }
