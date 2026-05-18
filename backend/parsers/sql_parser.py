import sqlglot
from sqlglot import exp, parse_one
from typing import Dict, List, Optional, Tuple


class SQLParser:
    def __init__(self, dialect: str = "postgres"):
        self.dialect = dialect

    # ------------------------------------------------------------------
    # Column-level extraction helpers
    # ------------------------------------------------------------------

    def _resolve_source_table(self, node: exp.Expression, aliases: Dict[str, str]) -> Optional[str]:
        """Walk up to find a Table ancestor, resolving any alias to real name."""
        table_node = node.find_ancestor(exp.Table)
        if table_node:
            raw = f"{table_node.db}.{table_node.name}" if table_node.db else table_node.name
            return aliases.get(raw, raw)
        return None

    def _build_table_aliases(self, parsed: exp.Expression) -> Dict[str, str]:
        """Return mapping of alias -> real table name."""
        mapping: Dict[str, str] = {}
        for table in parsed.find_all(exp.Table):
            if table.alias:
                real = f"{table.db}.{table.name}" if table.db else table.name
                mapping[table.alias] = real
        return mapping

    def extract_columns(self, sql: str) -> Dict:
        """
        Extract selected columns, aliases, aggregates, and derived columns
        from a SELECT statement.

        Returns a dict with keys:
          - selected_columns : plain columns with no alias or aggregate
          - aliases          : {output_name: source_expression}
          - aggregates       : {output_name: {"function": ..., "column": ...}}
          - derived_columns  : expressions that are not plain column refs
        """
        try:
            parsed = parse_one(sql, dialect=self.dialect)
        except Exception as e:
            return {"error": str(e)}

        select = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
        if select is None:
            return {"error": "No SELECT clause found"}

        selected_columns: List[str] = []
        aliases: Dict[str, str] = {}
        aggregates: Dict[str, Dict] = {}
        derived_columns: List[str] = {}

        agg_types = (exp.Sum, exp.Avg, exp.Count, exp.Max, exp.Min,
                     exp.StddevSamp, exp.StddevPop, exp.VarSamp, exp.VarPop,
                     exp.ArrayAgg, exp.GroupConcat)

        for sel in select.expressions:
            alias = sel.alias if sel.alias else None
            inner = sel.this if isinstance(sel, exp.Alias) else sel

            # Aggregate function
            agg_node = inner if isinstance(inner, agg_types) else inner.find(*agg_types)
            if agg_node is not None:
                col_node = agg_node.find(exp.Column)
                col_name = col_node.name if col_node else "*"
                table_prefix = (
                    f"{col_node.table}." if col_node and col_node.table else ""
                )
                output_name = alias or str(sel)
                aggregates[output_name] = {
                    "function": type(agg_node).__name__.upper(),
                    "column": f"{table_prefix}{col_name}",
                }
                continue

            # Plain column reference
            if isinstance(inner, exp.Column):
                col_str = (
                    f"{inner.table}.{inner.name}" if inner.table else inner.name
                )
                if alias:
                    aliases[alias] = col_str
                else:
                    selected_columns.append(col_str)
                continue

            # Star
            if isinstance(inner, exp.Star):
                selected_columns.append("*")
                continue

            # Everything else is a derived / computed expression
            output_name = alias or str(inner)
            if isinstance(derived_columns, list):
                derived_columns = {}
            derived_columns[output_name] = str(inner)

        if isinstance(derived_columns, list):
            derived_columns = {}

        return {
            "selected_columns": selected_columns,
            "aliases": aliases,
            "aggregates": aggregates,
            "derived_columns": derived_columns,
        }

    def extract_column_lineage(self, sql: str) -> Dict:
        """
        Produce a column_lineage mapping of the form:
            { output_column: [source_table.source_column, ...] }

        Example:
            SELECT customer_id, SUM(amount) AS total_sales
            FROM orders GROUP BY customer_id
        ->
            {
              "column_lineage": {
                "customer_id": ["orders.customer_id"],
                "total_sales": ["orders.amount"]
              }
            }
        """
        try:
            parsed = parse_one(sql, dialect=self.dialect)
        except Exception as e:
            return {"error": str(e)}

        select = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
        if select is None:
            return {"error": "No SELECT clause found"}

        table_aliases = self._build_table_aliases(parsed)

        # Build a flat map of table_alias/name -> real table name from FROM clause
        def resolve(tbl_ref: str) -> str:
            return table_aliases.get(tbl_ref, tbl_ref)

        # Determine the primary source tables (FROM + JOINs) in order
        source_tables: List[str] = []
        for tbl in parsed.find_all(exp.Table):
            real = f"{tbl.db}.{tbl.name}" if tbl.db else tbl.name
            canonical = resolve(real)
            if canonical not in source_tables:
                source_tables.append(canonical)

        agg_types = (exp.Sum, exp.Avg, exp.Count, exp.Max, exp.Min,
                     exp.StddevSamp, exp.StddevPop, exp.VarSamp, exp.VarPop,
                     exp.ArrayAgg, exp.GroupConcat)

        lineage: Dict[str, List[str]] = {}

        for sel in select.expressions:
            alias = sel.alias if sel.alias else None
            inner = sel.this if isinstance(sel, exp.Alias) else sel

            # Collect all column references inside this expression.
            # find_all walks the full subtree, so CASE WHEN / CASE ELSE
            # branches and JOIN columns are all captured automatically.
            col_refs = list(inner.find_all(exp.Column))
            if not col_refs and isinstance(inner, exp.Column):
                col_refs = [inner]

            sources: List[str] = []

            if col_refs:
                for col in col_refs:
                    if col.table:
                        tbl = resolve(col.table)
                    else:
                        tbl = source_tables[0] if len(source_tables) == 1 else "unknown"
                    entry = f"{tbl}.{col.name}"
                    if entry not in sources:
                        sources.append(entry)
            else:
                # No column refs (e.g. COUNT(*), literal expressions).
                # Record as table.* so the table dependency is still visible.
                fallback = source_tables[0] if source_tables else "unknown"
                sources = [f"{fallback}.*"]

            # Determine the output name
            if alias:
                output_name = alias
            elif isinstance(inner, exp.Column):
                output_name = inner.name
            elif isinstance(inner, exp.Star):
                output_name = "*"
            else:
                output_name = str(inner)

            lineage[output_name] = sources

        return {"column_lineage": lineage}

    # ------------------------------------------------------------------
    # Original public API (unchanged)
    # ------------------------------------------------------------------

    def parse(self, sql: str) -> Dict:
        """
        Parse a SQL query and return target_table and source_tables.

        Example:
            INSERT INTO sales_summary SELECT * FROM orders;
            -> {"target_table": "sales_summary", "source_tables": ["orders"]}
        """
        try:
            parsed = parse_one(sql, dialect=self.dialect)
            target = self._get_target_table(parsed)
            sources = self._get_source_tables(parsed, exclude=target)
            return {"target_table": target, "source_tables": sources}
        except Exception as e:
            return {"target_table": None, "source_tables": [], "error": str(e)}

    def _get_target_table(self, parsed: exp.Expression) -> Optional[str]:
        """Return the name of the table being written to, or None for SELECT."""
        if isinstance(parsed, (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create)):
            table = parsed.find(exp.Table)
            if table:
                return f"{table.db}.{table.name}" if table.db else table.name
        return None

    def _get_source_tables(self, parsed: exp.Expression, exclude: Optional[str] = None) -> List[str]:
        """Return all tables read by the query, excluding the target table."""
        seen = []
        for table in parsed.find_all(exp.Table):
            name = f"{table.db}.{table.name}" if table.db else table.name
            if name not in seen and name != exclude:
                seen.append(name)
        return seen

    def parse_query(self, sql: str) -> Dict:
        try:
            parsed = parse_one(sql, dialect=self.dialect)
            return {
                "success": True,
                "query_type": type(parsed).__name__,
                "source_tables": self._get_source_tables(parsed),
                "target_tables": ([self._get_target_table(parsed)] if self._get_target_table(parsed) else []),
                "joins": self._extract_joins(parsed),
                "raw_sql": sql,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "raw_sql": sql}

    def _extract_joins(self, parsed: exp.Expression) -> List[Dict]:
        joins = []
        for join in parsed.find_all(exp.Join):
            table = join.find(exp.Table)
            on_cond = join.args.get("on")
            joins.append({
                "type": join.args.get("kind", "INNER"),
                "table": table.name if table else None,
                "on_condition": str(on_cond) if on_cond else None,
            })
        return joins

    def validate_syntax(self, sql: str) -> Tuple[bool, Optional[str]]:
        try:
            parse_one(sql, dialect=self.dialect)
            return True, None
        except Exception as e:
            return False, str(e)

    def format_query(self, sql: str, pretty: bool = True) -> str:
        try:
            return parse_one(sql, dialect=self.dialect).sql(dialect=self.dialect, pretty=pretty)
        except Exception:
            return sql
