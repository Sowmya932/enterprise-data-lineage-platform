"""
dag_parser.py
-------------
Parse Airflow DAG Python files using Python's built-in AST module.

No Airflow installation is required – the parser only does static analysis,
so it is safe to run in any environment.

Public API
----------
    parser = DAGParser()

    # From a file on disk
    result = parser.parse_file("airflow_dags/etl_pipeline_dag.py")

    # From raw source code
    result = parser.parse_source(source_code)

    # result:
    # {
    #   "dag":          "daily_etl_pipeline",
    #   "tasks":        ["extract", "transform", "load"],
    #   "dependencies": [["extract", "transform"], ["transform", "load"]]
    # }
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional


class DAGParser:
    """
    Static-analysis parser for Airflow DAG Python files.

    Extracts:
        - dag_id  (from the DAG(...) constructor)
        - task_ids (from *Operator(task_id=...) constructors)
        - dependencies (from >> operator chains)
    """

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def parse_file(self, file_path: str) -> Dict:
        """
        Parse an Airflow DAG file from disk and return metadata.

        Parameters
        ----------
        file_path : str
            Absolute or relative path to a `.py` DAG file.

        Returns
        -------
        dict with keys: dag, tasks, dependencies

        Raises
        ------
        FileNotFoundError  if the file does not exist.
        ValueError         if the file is not a .py file or contains syntax errors.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"DAG file not found: {file_path}")
        if path.suffix.lower() != ".py":
            raise ValueError(f"Expected a .py file, got: {file_path}")

        source = path.read_text(encoding="utf-8")
        return self.parse_source(source, source_name=path.name)

    def parse_source(self, source: str, source_name: str = "<dag_source>") -> Dict:
        """
        Parse raw Airflow DAG Python source code and return metadata.

        Parameters
        ----------
        source      : str  – Python source code of the DAG module.
        source_name : str  – Filename label used in error messages.

        Returns
        -------
        dict with keys: dag, tasks, dependencies
        """
        if not source or not source.strip():
            raise ValueError("DAG source code is empty.")

        try:
            tree = ast.parse(source, filename=source_name)
        except SyntaxError as exc:
            raise ValueError(f"Syntax error in DAG source '{source_name}': {exc}") from exc

        dag_name = self._extract_dag_name(tree)
        tasks = self._extract_tasks(tree)
        dependencies = self._extract_dependencies(tree)

        return {
            "dag": dag_name,
            "tasks": tasks,
            "dependencies": dependencies,
        }

    # ------------------------------------------------------------------ #
    # DAG name extraction
    # ------------------------------------------------------------------ #

    def _extract_dag_name(self, tree: ast.AST) -> Optional[str]:
        """
        Locate the DAG id from either:
            with DAG("name", ...) as dag:   — context manager style
            dag = DAG("name", ...)          — assignment style
        """
        for node in ast.walk(tree):
            # Context manager: `with DAG(...) as dag:`
            if isinstance(node, ast.With):
                for item in node.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and self._is_dag_call(call):
                        name = self._get_dag_id(call)
                        if name:
                            return name

            # Assignment: `dag = DAG(...)`
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call) and self._is_dag_call(node.value):
                    name = self._get_dag_id(node.value)
                    if name:
                        return name

        return None

    def _is_dag_call(self, call: ast.Call) -> bool:
        """Return True if the call is `DAG(...)` or `module.DAG(...)`."""
        func = call.func
        if isinstance(func, ast.Name):
            return func.id == "DAG"
        if isinstance(func, ast.Attribute):
            return func.attr == "DAG"
        return False

    def _get_dag_id(self, call: ast.Call) -> Optional[str]:
        """
        Extract the dag_id value from a DAG(...) call.
        Checks:
            DAG("my_dag", ...)
            DAG(dag_id="my_dag", ...)
        """
        # First positional argument
        if call.args:
            first = call.args[0]
            if isinstance(first, ast.Constant):
                return str(first.value)

        # Keyword argument dag_id=
        for kw in call.keywords:
            if kw.arg == "dag_id" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)

        return None

    # ------------------------------------------------------------------ #
    # Task extraction
    # ------------------------------------------------------------------ #

    def _extract_tasks(self, tree: ast.AST) -> List[str]:
        """
        Collect all task_id values from *Operator(task_id="...") calls.
        Returns task ids in definition order, deduplicated.
        """
        task_ids: List[str] = []
        seen: set = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value if isinstance(node, ast.Assign) else node.value
                if value and isinstance(value, ast.Call):
                    tid = self._get_task_id(value)
                    if tid and tid not in seen:
                        task_ids.append(tid)
                        seen.add(tid)

        return task_ids

    def _get_task_id(self, call: ast.Call) -> Optional[str]:
        """Extract task_id keyword argument from an Operator call."""
        for kw in call.keywords:
            if kw.arg == "task_id" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
        return None

    # ------------------------------------------------------------------ #
    # Dependency extraction
    # ------------------------------------------------------------------ #

    def _extract_dependencies(self, tree: ast.AST) -> List[List[str]]:
        """
        Walk all top-level expression statements for `>>` chains.

        Examples handled:
            extract >> transform >> load
            [extract, validate] >> transform
        """
        deps: List[List[str]] = []
        seen_pairs: set = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.BinOp):
                chain = self._flatten_rshift_chain(node.value)
                for i in range(len(chain) - 1):
                    pair = (chain[i], chain[i + 1])
                    if pair not in seen_pairs:
                        deps.append(list(pair))
                        seen_pairs.add(pair)

        return deps

    def _flatten_rshift_chain(self, node: ast.expr) -> List[str]:
        """
        Recursively flatten a `>>` chain into an ordered list of names.

        `a >> b >> c`  →  ast.BinOp(BinOp(a, >>, b), >>, c)
                       →  ["a", "b", "c"]
        """
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
            left_chain = self._flatten_rshift_chain(node.left)
            right_chain = self._flatten_rshift_chain(node.right)
            return left_chain + right_chain

        # Leaf node
        return [self._node_to_name(node)]

    def _node_to_name(self, node: ast.AST) -> str:
        """Convert a leaf AST node to a string label."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Constant):
            return str(node.value)
        # Fallback: dump the node type for visibility
        return type(node).__name__
