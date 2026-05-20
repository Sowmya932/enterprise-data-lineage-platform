"""
dag_service.py
--------------
Reusable service functions for persisting and fetching Airflow DAG metadata.

Functions
---------
    save_dag_metadata    – persist parsed DAG result to PostgreSQL
    fetch_dag_metadata   – retrieve all DAG records from PostgreSQL
    fetch_dependencies   – retrieve task dependency edges from PostgreSQL
"""

import logging
from typing import Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.orm_models import DAGRecord, TaskDependency, TaskRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_dag_metadata(
    db: Session,
    *,
    dag_id: str,
    tasks: List[str],
    dependencies: List[List[str]],
) -> Dict:
    """
    Persist a parsed Airflow DAG result to PostgreSQL.

    If a DAG with the same ``dag_id`` already exists the record is reused
    and tasks / dependencies are appended (duplicates are skipped).

    Parameters
    ----------
    db           : active SQLAlchemy session
    dag_id       : Airflow DAG identifier string
    tasks        : list of task_id strings
    dependencies : list of [upstream_task_id, downstream_task_id] pairs

    Returns
    -------
    dict with keys ``dag_id``, ``tasks_saved``, ``dependencies_saved``
    """
    logger.info("Saving DAG metadata | dag_id=%s tasks=%d", dag_id, len(tasks))

    try:
        # Upsert DAG record
        dag_record = db.query(DAGRecord).filter(DAGRecord.dag_id == dag_id).first()
        if dag_record is None:
            dag_record = DAGRecord(dag_id=dag_id)
            db.add(dag_record)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                dag_record = db.query(DAGRecord).filter(DAGRecord.dag_id == dag_id).first()

        # Existing task ids to avoid duplicates
        existing_task_ids = {t.task_id for t in dag_record.tasks}
        tasks_saved: List[str] = []
        for task_id in tasks:
            if task_id not in existing_task_ids:
                db.add(TaskRecord(dag_id=dag_record.id, task_id=task_id))
                tasks_saved.append(task_id)

        # Existing dependency pairs
        existing_deps = {
            (d.upstream_task, d.downstream_task) for d in dag_record.task_dependencies
        }
        deps_saved: int = 0
        for pair in dependencies:
            if len(pair) != 2:
                logger.warning("Skipping malformed dependency pair: %s", pair)
                continue
            upstream, downstream = pair[0], pair[1]
            if (upstream, downstream) not in existing_deps:
                db.add(
                    TaskDependency(
                        dag_record_id=dag_record.id,
                        upstream_task=upstream,
                        downstream_task=downstream,
                    )
                )
                deps_saved += 1

        db.commit()
        logger.info(
            "DAG saved | dag_id=%s tasks_saved=%d deps_saved=%d",
            dag_id,
            len(tasks_saved),
            deps_saved,
        )
        return {
            "dag_id": dag_id,
            "tasks_saved": tasks_saved,
            "dependencies_saved": deps_saved,
        }

    except Exception:
        db.rollback()
        logger.exception("Failed to save DAG metadata for dag_id=%s", dag_id)
        raise


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_dag_metadata(db: Session) -> List[Dict]:
    """
    Retrieve all persisted DAG records with their task lists.

    Returns a list of dicts: ``{id, dag_id, tasks, created_at}``.
    """
    logger.debug("Fetching all DAG records")
    try:
        records = db.query(DAGRecord).order_by(DAGRecord.dag_id).all()
        return [r.to_dict() for r in records]
    except Exception:
        logger.exception("Failed to fetch DAG metadata")
        raise


def fetch_dependencies(db: Session) -> Dict:
    """
    Retrieve all task dependency edges grouped by DAG.

    Returns ``{"task_edges": [{dag_record_id, upstream_task, downstream_task, ...}]}``.
    """
    logger.debug("Fetching all task dependencies")
    try:
        records = (
            db.query(TaskDependency)
            .order_by(TaskDependency.dag_record_id, TaskDependency.upstream_task)
            .all()
        )
        return {"task_edges": [r.to_dict() for r in records]}
    except Exception:
        logger.exception("Failed to fetch task dependencies")
        raise
