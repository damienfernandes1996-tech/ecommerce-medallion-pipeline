"""Silver layer: cleaned, typed, de-duplicated tables (SQL lives in sql/silver)."""
from __future__ import annotations

from .config import SQL_DIR, Paths
from .db import connect, count_rows, export_schema, run_sql_dir


def run(paths: Paths) -> dict[str, int]:
    con = connect(paths)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        run_sql_dir(con, SQL_DIR / "silver")
        counts = count_rows(con, "silver")
        export_schema(con, "silver", paths.silver)
        return counts
    finally:
        con.close()
