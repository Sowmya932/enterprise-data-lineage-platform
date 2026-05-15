import sqlglot
from sqlglot import exp, parse_one
from typing import Dict, List, Optional, Tuple


class SQLParser:
    def __init__(self, dialect: str = "postgres"):
        self.dialect = dialect

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
