"""
lineage_service.py
------------------
Reusable service functions for persisting and fetching SQL lineage metadata.

Functions
---------
    save_lineage_metadata  – persist a parsed lineage result to PostgreSQL
    fetch_lineage_metadata – retrieve all lineage relationships from PostgreSQL
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.orm_models import (
    ColumnRecord,
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
# Helpers
# ---------------------------------------------------------------------------

def _split_table_name(raw: str):
    """Split 'schema.table' into (schema, table). Returns (None, raw) if no dot."""
    if "." in raw:
        parts = raw.split(".", 1)
        return parts[0], parts[1]
    return None, raw
