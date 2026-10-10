"""Gold layer: star schema + business KPI tables (SQL lives in sql/gold)."""
from __future__ import annotations

from .config import SQL_DIR, Paths
from .db import connect, count_rows, export_schema, list_tables, run_sql_dir, sql_literal


def run(paths: Paths) -> dict[str, int]:
    con = connect(paths)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")
        run_sql_dir(con, SQL_DIR / "gold")
        counts = count_rows(con, "gold")
        export_schema(con, "gold", paths.gold)
        # Small KPI tables are versioned (GitHub renders CSV); the full model is for Power BI.
        paths.outputs.mkdir(parents=True, exist_ok=True)
        for table in list_tables(con, "gold"):
            if table.startswith("kpi_"):
                target = paths.outputs / f"{table}.csv"
                con.execute(f"COPY gold.{table} TO {sql_literal(target)} (FORMAT csv, HEADER)")
        export_schema(con, "gold", paths.powerbi_export, fmt="csv")
        return counts
    finally:
        con.close()
