"""Small DuckDB helpers: connection, SQL-file runner, schema export."""
from __future__ import annotations

import time
from pathlib import Path

import duckdb

from .config import Paths


def connect(paths: Paths) -> duckdb.DuckDBPyConnection:
    paths.warehouse.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(paths.warehouse))


def sql_literal(value: str | Path) -> str:
    """Quote a string as a SQL literal (doubles single quotes)."""
    return "'" + str(value).replace("'", "''") + "'"


def run_sql_dir(con: duckdb.DuckDBPyConnection, directory: Path) -> list[str]:
    """Execute every *.sql file of a folder in alphabetical order."""
    executed = []
    for sql_file in sorted(directory.glob("*.sql")):
        started = time.perf_counter()
        con.execute(sql_file.read_text(encoding="utf-8"))
        print(f"    {sql_file.name:<32} {time.perf_counter() - started:5.1f}s")
        executed.append(sql_file.name)
    return executed


def list_tables(con: duckdb.DuckDBPyConnection, schema: str) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = ? ORDER BY table_name",
        [schema],
    ).fetchall()
    return [r[0] for r in rows]


def count_rows(con: duckdb.DuckDBPyConnection, schema: str) -> dict[str, int]:
    return {
        t: con.execute(f"SELECT count(*) FROM {schema}.{t}").fetchone()[0]
        for t in list_tables(con, schema)
    }


def export_schema(
    con: duckdb.DuckDBPyConnection, schema: str, out_dir: Path, fmt: str = "parquet"
) -> None:
    """Write every table of a schema to a folder (parquet or csv)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in list_tables(con, schema):
        target = out_dir / f"{table}.{fmt}"
        options = "(FORMAT parquet, COMPRESSION zstd)" if fmt == "parquet" else "(FORMAT csv, HEADER)"
        con.execute(f"COPY {schema}.{table} TO {sql_literal(target)} {options}")
