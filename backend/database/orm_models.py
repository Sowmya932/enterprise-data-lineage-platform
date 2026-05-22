"""
orm_models.py
-------------
SQLAlchemy ORM models for the Enterprise Data Lineage Platform.

Tables
------
    tables               – catalogued table records
    columns              – column-level records linked to tables
    dags                 – Airflow DAG records
    tasks                – individual DAG task records
    lineage_relationships – source→target column/table lineage edges
    task_dependencies    – upstream→downstream task dependency edges
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.database.db import Base


class TableRecord(Base):
    """A catalogued table extracted from SQL lineage."""

    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("name", "schema_name", name="uq_table_name_schema"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    schema_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    columns = relationship(
        "ColumnRecord", back_populates="table", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "schema_name": self.schema_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ColumnRecord(Base):
    """A column record linked to a parent TableRecord."""

    __tablename__ = "columns"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    source_expression = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    table = relationship("TableRecord", back_populates="columns")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "table_id": self.table_id,
            "name": self.name,
            "source_expression": self.source_expression,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DAGRecord(Base):
    """An Airflow DAG record."""

    __tablename__ = "dags"

    id = Column(Integer, primary_key=True, index=True)
    dag_id = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tasks = relationship(
        "TaskRecord", back_populates="dag", cascade="all, delete-orphan"
    )
    task_dependencies = relationship(
        "TaskDependency", back_populates="dag", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dag_id": self.dag_id,
            "tasks": [t.task_id for t in self.tasks],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TaskRecord(Base):
    """An individual task within an Airflow DAG."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    dag_id = Column(Integer, ForeignKey("dags.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dag = relationship("DAGRecord", back_populates="tasks")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dag_id": self.dag_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LineageRelationship(Base):
    """A directed lineage edge from a source table/column to a target table/column."""

    __tablename__ = "lineage_relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_table = Column(String(255), nullable=False, index=True)
    target_table = Column(String(255), nullable=False, index=True)
    column_name = Column(String(255), nullable=True)
    source_column = Column(String(255), nullable=True)
    # Optional: DAG that produced this lineage edge (string dag_id, not FK)
    dag_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_table": self.source_table,
            "target_table": self.target_table,
            "column_name": self.column_name,
            "source_column": self.source_column,
            "dag_id": self.dag_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TaskDependency(Base):
    """An upstream→downstream task dependency within a DAG."""

    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    dag_record_id = Column(
        Integer, ForeignKey("dags.id", ondelete="CASCADE"), nullable=False
    )
    upstream_task = Column(String(255), nullable=False)
    downstream_task = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dag = relationship("DAGRecord", back_populates="task_dependencies")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dag_record_id": self.dag_record_id,
            "upstream_task": self.upstream_task,
            "downstream_task": self.downstream_task,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ColumnLineage(Base):
    """
    A directed column-level lineage edge.

    Captures the exact column-to-column data flow:
        source_table.source_column  →  target_table.target_column

    The optional ``transformation`` field stores the SQL expression that
    derives the target column (e.g. ``SUM(orders.amount)``, ``COALESCE(a, b)``).

    ``transformation_type`` classifies the derivation:
        DIRECT        – plain column copy / rename
        ALIAS         – column exposed under a different name (AS clause)
        AGGREGATE_SUM – SUM(...)
        AGGREGATE_COUNT – COUNT(...)
        AGGREGATE_AVG – AVG(...)
        AGGREGATE_MAX – MAX(...)
        AGGREGATE_MIN – MIN(...)
        CASE_WHEN     – CASE WHEN ... END expression
        DERIVED       – any other computed expression
    """

    __tablename__ = "column_lineage"
    __table_args__ = (
        UniqueConstraint(
            "source_table", "source_column", "target_table", "target_column",
            name="uq_column_lineage_edge",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_table = Column(String(255), nullable=False, index=True)
    source_column = Column(String(255), nullable=False, index=True)
    target_table = Column(String(255), nullable=False, index=True)
    target_column = Column(String(255), nullable=False, index=True)
    transformation = Column(Text, nullable=True)
    transformation_type = Column(
        String(32), nullable=False, default="DIRECT", server_default="DIRECT"
    )
    dag_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_table": self.source_table,
            "source_column": self.source_column,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "transformation": self.transformation,
            "transformation_type": self.transformation_type,
            "dag_id": self.dag_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
