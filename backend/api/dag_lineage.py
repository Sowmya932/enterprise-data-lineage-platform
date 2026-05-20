"""
dag_lineage.py
--------------
FastAPI router for Airflow DAG parsing and DAG → SQL lineage endpoints.

Endpoints
---------
POST /parse-dag
    Parse a DAG from a server-side file path or inline source code.
    Returns DAGMetadata (dag_id, tasks, dependencies).

POST /parse-dag/upload
    Upload a .py DAG file and receive the same DAGMetadata response.

POST /dag-sql-lineage
    Parse a DAG and enrich each task with SQL lineage information.
    Returns DAGFullLineage (DAG → SQL transformations → source/target tables).
"""

import ast as _ast
import logging
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.models.lineage_models import (
    DAGFullLineage,
    DAGLineageNode,
    DAGMetadata,
    DAGParseRequest,
    DAGParseResponse,
)
from backend.parsers.dag_parser import DAGParser
from backend.parsers.sql_parser import SQLParser
from backend.services.dag_service import save_dag_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["DAG Lineage"])

_dag_parser = DAGParser()
_sql_parser = SQLParser()


# ============================================================
# POST /parse-dag  – parse from path or inline source
# ============================================================

@router.post(
    "/parse-dag",
    response_model=DAGParseResponse,
    summary="Parse an Airflow DAG file",
    description=(
        "Extract DAG metadata from an Airflow DAG Python file. "
        "Provide either a server-side **dag_file_path** or the raw "
        "**dag_content** (Python source code)."
    ),
)
def parse_dag(request: DAGParseRequest, db: Session = Depends(get_db)) -> DAGParseResponse:
    try:
        if request.dag_file_path:
            result = _dag_parser.parse_file(request.dag_file_path)
        else:
            result = _dag_parser.parse_source(request.dag_content)  # type: ignore[arg-type]

        # Persist to PostgreSQL
        if result.get("dag"):
            try:
                save_dag_metadata(
                    db,
                    dag_id=result["dag"],
                    tasks=result.get("tasks") or [],
                    dependencies=result.get("dependencies") or [],
                )
            except Exception:
                logger.warning("Could not persist DAG metadata to database", exc_info=True)

        return DAGParseResponse(success=True, metadata=DAGMetadata(**result))

    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc


# ============================================================
# POST /parse-dag/upload  – upload a .py file
# ============================================================

@router.post(
    "/parse-dag/upload",
    response_model=DAGParseResponse,
    summary="Upload and parse an Airflow DAG file",
    description=(
        "Upload a `.py` Airflow DAG file as a multipart form-data request. "
        "The server parses the file and returns DAG metadata."
    ),
)
async def parse_dag_upload(file: UploadFile = File(...), db: Session = Depends(get_db)) -> DAGParseResponse:
    if not (file.filename or "").endswith(".py"):
        raise HTTPException(
            status_code=400,
            detail="Only .py files are accepted.",
        )

    try:
        raw_bytes = await file.read()
        source = raw_bytes.decode("utf-8")
        result = _dag_parser.parse_source(source, source_name=file.filename or "<upload>")

        # Persist to PostgreSQL
        if result.get("dag"):
            try:
                save_dag_metadata(
                    db,
                    dag_id=result["dag"],
                    tasks=result.get("tasks") or [],
                    dependencies=result.get("dependencies") or [],
                )
            except Exception:
                logger.warning("Could not persist uploaded DAG metadata to database", exc_info=True)

        return DAGParseResponse(success=True, metadata=DAGMetadata(**result))

    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="File must be UTF-8 encoded Python source.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc


# ============================================================
# POST /dag-sql-lineage  – DAG → SQL transformation → tables
# ============================================================

@router.post(
    "/dag-sql-lineage",
    response_model=DAGFullLineage,
    summary="Full DAG → SQL → table lineage",
    description=(
        "Parse a DAG and enrich every task with the SQL transformations it executes "
        "and the source/target tables those queries touch. "
        "Produces an end-to-end lineage view: **DAG task → SQL → table**."
    ),
)
def dag_sql_lineage(request: DAGParseRequest, db: Session = Depends(get_db)) -> DAGFullLineage:
    # ── 1. Parse the DAG ─────────────────────────────────────────────
    try:
        if request.dag_file_path:
            dag_meta = _dag_parser.parse_file(request.dag_file_path)
        else:
            dag_meta = _dag_parser.parse_source(request.dag_content)  # type: ignore[arg-type]
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    # ── 2. Persist DAG to PostgreSQL ──────────────────────────────────
    if dag_meta.get("dag"):
        try:
            save_dag_metadata(
                db,
                dag_id=dag_meta["dag"],
                tasks=dag_meta.get("tasks") or [],
                dependencies=dag_meta.get("dependencies") or [],
            )
        except Exception:
            logger.warning("Could not persist DAG-SQL lineage metadata to database", exc_info=True)

    # ── 3. Read source text for SQL snippet extraction ────────────────
    source_text = _read_source(request)

    # ── 4. Map task_id → SQL snippets found inside the DAG source ─────
    task_sql_map: Dict[str, List[str]] = _extract_task_sql_snippets(source_text)

    # ── 5. For each task, run SQLParser to get source/target tables ───
    lineage_nodes: List[DAGLineageNode] = []
    for task_id in dag_meta.get("tasks", []):
        sql_queries = task_sql_map.get(task_id, [])
        source_tables: List[str] = []
        target_tables: List[str] = []

        for sql in sql_queries:
            sql_result = _sql_parser.parse(sql)
            if "error" not in sql_result:
                source_tables.extend(sql_result.get("source_tables") or [])
                if sql_result.get("target_table"):
                    target_tables.append(sql_result["target_table"])

        lineage_nodes.append(
            DAGLineageNode(
                task_id=task_id,
                sql_transformations=sql_queries,
                source_tables=_dedupe(source_tables),
                target_tables=_dedupe(target_tables),
            )
        )

    return DAGFullLineage(
        dag=dag_meta.get("dag"),
        lineage_nodes=lineage_nodes,
        task_dependencies=dag_meta.get("dependencies", []),
    )


# ============================================================
# Internal helpers
# ============================================================

def _read_source(request: DAGParseRequest) -> str:
    """Return the DAG Python source text from either the path or inline content."""
    if request.dag_file_path:
        try:
            return Path(request.dag_file_path).read_text(encoding="utf-8")
        except Exception:
            return ""
    return request.dag_content or ""


def _extract_task_sql_snippets(source: str) -> Dict[str, List[str]]:
    """
    Walk the DAG AST and extract SQL strings associated with each task.

    Handles two forms of the ``sql=`` keyword argument inside *Operator calls:

    1. Inline string literal  – ``sql="SELECT ..."``
    2. Variable reference     – ``sql=MY_SQL_VARIABLE``
       (resolved from module-level ``MY_SQL_VARIABLE = "..."`` assignments)

    Returns { task_id: [sql_string, ...] }.
    """
    task_sql: Dict[str, List[str]] = {}
    if not source:
        return task_sql

    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return task_sql

    # ── Pass 1: collect module-level name → string value assignments ──────────
    str_vars: Dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, _ast.Assign) and isinstance(node.value, _ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, _ast.Name):
                        str_vars[target.id] = node.value.value

    # ── Pass 2: find Operator(...) calls and extract task_id + sql ───────────
    for node in _ast.walk(tree):
        if not isinstance(node, (_ast.Assign, _ast.AnnAssign)):
            continue

        value = node.value if isinstance(node, _ast.Assign) else node.value
        if not (value and isinstance(value, _ast.Call)):
            continue

        # Variable names this call is assigned to
        var_names: List[str] = (
            [t.id for t in node.targets if isinstance(t, _ast.Name)]
            if isinstance(node, _ast.Assign)
            else []
        )

        task_id_val: str = ""
        sql_val: str = ""
        for kw in value.keywords:
            if kw.arg == "task_id" and isinstance(kw.value, _ast.Constant):
                task_id_val = str(kw.value.value)
            if kw.arg == "sql":
                if isinstance(kw.value, _ast.Constant):
                    # Inline literal: sql="SELECT ..."
                    sql_val = str(kw.value.value).strip()
                elif isinstance(kw.value, _ast.Name) and kw.value.id in str_vars:
                    # Variable reference: sql=MY_SQL_VAR
                    sql_val = str_vars[kw.value.id].strip()

        if not sql_val:
            continue

        # Index by task_id (preferred key) and by Python variable name
        keys: set = set()
        if task_id_val:
            keys.add(task_id_val)
        keys.update(var_names)

        for key in keys:
            task_sql.setdefault(key, [])
            if sql_val not in task_sql[key]:
                task_sql[key].append(sql_val)

    return task_sql


def _dedupe(items: List[str]) -> List[str]:
    """Return a list with duplicates removed, preserving order."""
    seen: set = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
