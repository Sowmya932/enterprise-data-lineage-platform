"""
lineage_service.py
------------------
Reusable service functions for persisting and fetching SQL lineage metadata.

Functions
---------
    save_lineage_metadata      – persist a parsed lineage result to PostgreSQL
    save_lineage_relationship  – persist a single validated lineage edge
    fetch_lineage_metadata     – retrieve all lineage relationships from PostgreSQL
    fetch_relationships_for_table – direct relationships for a specific table
    fetch_tables               – retrieve all catalogued table records
"""

import logging
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.orm_models import (
    ColumnRecord,
    ColumnLineage,
    LineageRelationship,
    TableRecord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_lineage_metadata(
    db: Session,
    *,
    target_table: Optional[str],
    source_tables: List[str],
    column_lineage: Optional[Dict[str, List[str]]] = None,
) -> Dict:
    """
    Persist a parsed SQL lineage result to PostgreSQL.

    Parameters
    ----------
    db             : active SQLAlchemy session
    target_table   : name of the table being written to
    source_tables  : names of tables being read
    column_lineage : mapping of {output_column: [source_table.column, ...]}

    Returns
    -------
    dict with keys ``tables_saved``, ``columns_saved``, ``edges_saved``
    """
    logger.info(
        "Saving lineage metadata | target=%s sources=%s",
        target_table,
        source_tables,
    )

    tables_saved: List[str] = []
    columns_saved: int = 0
    edges_saved: int = 0

    try:
        # Upsert all involved table names
        all_table_names = list(source_tables)
        if target_table:
            all_table_names.append(target_table)

        table_map: Dict[str, TableRecord] = {}
        for raw_name in all_table_names:
            schema_name, name = _split_table_name(raw_name)
            record = (
                db.query(TableRecord)
                .filter(TableRecord.name == name, TableRecord.schema_name == schema_name)
                .first()
            )
            if record is None:
                record = TableRecord(name=name, schema_name=schema_name)
                db.add(record)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    record = (
                        db.query(TableRecord)
                        .filter(TableRecord.name == name, TableRecord.schema_name == schema_name)
                        .first()
                    )
            table_map[raw_name] = record
            tables_saved.append(raw_name)

        # Persist column lineage
        if column_lineage and target_table and target_table in table_map:
            target_record = table_map[target_table]
            for output_col, source_refs in column_lineage.items():
                source_expr = ", ".join(source_refs) if source_refs else None
                col_record = ColumnRecord(
                    table_id=target_record.id,
                    name=output_col,
                    source_expression=source_expr,
                )
                db.add(col_record)
                columns_saved += 1

        # Persist lineage edges (source → target)
        if target_table:
            for src in source_tables:
                edge = LineageRelationship(
                    source_table=src,
                    target_table=target_table,
                )
                db.add(edge)
                edges_saved += 1

        db.commit()
        logger.info(
            "Lineage saved | tables=%d columns=%d edges=%d",
            len(tables_saved),
            columns_saved,
            edges_saved,
        )
        return {
            "tables_saved": tables_saved,
            "columns_saved": columns_saved,
            "edges_saved": edges_saved,
        }

    except Exception:
        db.rollback()
        logger.exception("Failed to save lineage metadata")
        raise


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_lineage_metadata(db: Session) -> List[Dict]:
    """
    Retrieve all persisted lineage relationships.

    Returns a list of dicts: ``{source_table, target_table, column_name, source_column}``.
    """
    logger.debug("Fetching all lineage relationships")
    try:
        records = (
            db.query(LineageRelationship)
            .order_by(LineageRelationship.source_table, LineageRelationship.target_table)
            .all()
        )
        return [r.to_dict() for r in records]
    except Exception:
        logger.exception("Failed to fetch lineage metadata")
        raise


def fetch_tables(db: Session) -> List[Dict]:
    """Retrieve all catalogued table records."""
    logger.debug("Fetching all tables")
    try:
        records = db.query(TableRecord).order_by(TableRecord.name).all()
        return [r.to_dict() for r in records]
    except Exception:
        logger.exception("Failed to fetch tables")
        raise


# ---------------------------------------------------------------------------
# Single relationship save  (with circular dependency protection)
# ---------------------------------------------------------------------------

def save_lineage_relationship(
    db: Session,
    *,
    source_table: str,
    target_table: str,
    column_name: Optional[str] = None,
    source_column: Optional[str] = None,
    dag_id: Optional[str] = None,
) -> Dict:
    """
    Persist a single lineage edge after validating it will not create a cycle.

    Parameters
    ----------
    db            : active SQLAlchemy session
    source_table  : data origin table name
    target_table  : data destination table name
    column_name   : target column name (optional)
    source_column : source column name (optional)
    dag_id        : DAG identifier that produced this lineage (optional)

    Returns
    -------
    dict representation of the saved ``LineageRelationship`` row.

    Raises
    ------
    HTTPException 400  – if source_table == target_table
    HTTPException 409  – if the edge would create a circular dependency
    """
    logger.info(
        "Saving lineage relationship | %s → %s (dag=%s)",
        source_table,
        target_table,
        dag_id,
    )

    # ------------------------------------------------------------------
    # Validation: identical tables
    # ------------------------------------------------------------------
    if source_table.strip().lower() == target_table.strip().lower():
        raise HTTPException(
            status_code=400,
            detail=f"source_table and target_table must differ (both are '{source_table}').",
        )

    # ------------------------------------------------------------------
    # Validation: circular dependency check (WITH RECURSIVE)
    # ------------------------------------------------------------------
    try:
        from backend.lineage.graph_service import LineageGraphService

        if LineageGraphService().has_circular_dependency(db, source_table, target_table):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Adding {source_table} → {target_table} would create a "
                    "circular dependency in the lineage graph."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Circular dependency check failed | %s → %s", source_table, target_table
        )
        raise

    # ------------------------------------------------------------------
    # Persist the edge
    # ------------------------------------------------------------------
    try:
        edge = LineageRelationship(
            source_table=source_table,
            target_table=target_table,
            column_name=column_name,
            source_column=source_column,
            dag_id=dag_id,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        logger.info(
            "Lineage relationship saved | id=%d %s → %s",
            edge.id,
            source_table,
            target_table,
        )
        return edge.to_dict()

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to save lineage relationship | %s → %s", source_table, target_table
        )
        raise


# ---------------------------------------------------------------------------
# Fetch relationships for a specific table
# ---------------------------------------------------------------------------

def fetch_relationships_for_table(db: Session, table_name: str) -> List[Dict]:
    """
    Retrieve all direct lineage relationships where *table_name* appears as
    either source or target.

    Parameters
    ----------
    db         : active SQLAlchemy session
    table_name : table to look up

    Returns
    -------
    List of dicts from ``LineageRelationship.to_dict()``.
    """
    logger.debug("Fetching relationships for table=%s", table_name)
    try:
        records = (
            db.query(LineageRelationship)
            .filter(
                (LineageRelationship.source_table == table_name)
                | (LineageRelationship.target_table == table_name)
            )
            .order_by(
                LineageRelationship.source_table,
                LineageRelationship.target_table,
            )
            .all()
        )
        return [r.to_dict() for r in records]
    except Exception:
        logger.exception(
            "Failed to fetch relationships for table=%s", table_name
        )
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_table_name(raw: str):
    """Split 'schema.table' into (schema, table). Returns (None, raw) if no dot."""
    if "." in raw:
        parts = raw.split(".", 1)
        return parts[0], parts[1]
    return None, raw


# ---------------------------------------------------------------------------
# Column-level lineage
# ---------------------------------------------------------------------------

def save_column_lineage(
    db: Session,
    *,
    source_table: str,
    source_column: str,
    target_table: str,
    target_column: str,
    transformation: Optional[str] = None,
    dag_id: Optional[str] = None,
) -> Dict:
    """
    Persist a single column-level lineage edge.

    Parameters
    ----------
    db                : active SQLAlchemy session
    source_table      : data-origin table
    source_column     : data-origin column
    target_table      : data-destination table
    target_column     : data-destination column
    transformation    : SQL expression that derives target_column (optional)
    dag_id            : DAG identifier that produces this lineage (optional)

    Returns
    -------
    dict representation of the saved ``ColumnLineage`` row.

    Raises
    ------
    HTTPException 400 – if source == target (both table and column identical)
    HTTPException 409 – if the edge already exists (unique constraint violation)
    """
    logger.info(
        "Saving column lineage | %s.%s → %s.%s (dag=%s)",
        source_table, source_column, target_table, target_column, dag_id,
    )

    if (
        source_table.strip().lower() == target_table.strip().lower()
        and source_column.strip().lower() == target_column.strip().lower()
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"source and target must differ "
                f"(both are '{source_table}.{source_column}')."
            ),
        )

    try:
        edge = ColumnLineage(
            source_table=source_table,
            source_column=source_column,
            target_table=target_table,
            target_column=target_column,
            transformation=transformation,
            dag_id=dag_id,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        logger.info(
            "Column lineage saved | id=%d %s.%s → %s.%s",
            edge.id, source_table, source_column, target_table, target_column,
        )
        return edge.to_dict()
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Column lineage edge {source_table}.{source_column} → "
                f"{target_table}.{target_column} already exists."
            ),
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to save column lineage | %s.%s → %s.%s",
            source_table, source_column, target_table, target_column,
        )
        raise
