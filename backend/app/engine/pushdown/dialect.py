from typing import Optional, Dict, Any
from backend.app.engine.pushdown.models import SQLDialect


class DialectFormatter:
    """
    Renders identifiers, literal values, and DDL/DML clauses according to
    database-specific SQL syntax rules.
    """

    @classmethod
    def quote_identifier(cls, name: str, dialect: SQLDialect = SQLDialect.ANSI) -> str:
        """Quotes SQL identifiers using dialect-appropriate delimiter."""
        clean = name.strip()
        if dialect == SQLDialect.MYSQL:
            clean_escaped = clean.replace("`", "``")
            return f"`{clean_escaped}`"
        else:
            clean_escaped = clean.replace('"', '""')
            return f'"{clean_escaped}"'

    @classmethod
    def qualify_table(
        cls,
        table: str,
        schema: Optional[str] = None,
        dialect: SQLDialect = SQLDialect.ANSI
    ) -> str:
        """Formats fully qualified table identifier schema.table."""
        tbl_q = cls.quote_identifier(table, dialect)
        if schema and schema.strip():
            sch_q = cls.quote_identifier(schema, dialect)
            return f"{sch_q}.{tbl_q}"
        return tbl_q

    @classmethod
    def format_literal(cls, val: Any) -> str:
        """Formats a Python literal value into standard SQL literal."""
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if isinstance(val, (int, float)):
            return str(val)
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'"

    @classmethod
    def render_ctas(
        cls,
        table: str,
        select_query: str,
        schema: Optional[str] = None,
        dialect: SQLDialect = SQLDialect.ANSI,
        if_not_exists: bool = False
    ) -> str:
        """Generates CREATE TABLE AS SELECT statement."""
        tbl = cls.qualify_table(table, schema, dialect)
        ine = "IF NOT EXISTS " if if_not_exists else ""
        return f"CREATE TABLE {ine}{tbl} AS\n{select_query};"

    @classmethod
    def render_insert_into(
        cls,
        table: str,
        select_query: str,
        columns: Optional[list] = None,
        schema: Optional[str] = None,
        dialect: SQLDialect = SQLDialect.ANSI
    ) -> str:
        """Generates INSERT INTO target SELECT statement."""
        tbl = cls.qualify_table(table, schema, dialect)
        cols_clause = ""
        if columns:
            cols_clause = f" ({', '.join(cls.quote_identifier(c, dialect) for c in columns)})"
        return f"INSERT INTO {tbl}{cols_clause}\n{select_query};"
