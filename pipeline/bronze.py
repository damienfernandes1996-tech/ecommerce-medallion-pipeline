"""Bronze layer: raw copy of the source files, nothing is cleaned.

Every column stays a string (all_varchar) so no value can be silently altered or lost.
Two lineage columns are added: the source file name and the ingestion timestamp.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import RAW_FILES, Paths
from .db import connect, count_rows, export_schema, sql_literal


def run(paths: Paths) -> dict[str, int]:
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    con = connect(paths)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        for table, filename in RAW_FILES.items():
            source = paths.raw / filename
            if not source.exists():
                raise FileNotFoundError(
                    f"{source} not found. Run `python run_pipeline.py` (it downloads the "
                    "data) or copy the Olist CSV files into data/raw/."
                )
            con.execute(
                f"""
                CREATE OR REPLACE TABLE bronze.{table} AS
                SELECT
                    *,
                    {sql_literal(filename)}                        AS _source_file,
                    CAST({sql_literal(ingested_at)} AS TIMESTAMP)  AS _ingested_at
                FROM read_csv({sql_literal(source)}, header = true, all_varchar = true)
                """
            )
        counts = count_rows(con, "bronze")
        export_schema(con, "bronze", paths.bronze)
        return counts
    finally:
        con.close()
