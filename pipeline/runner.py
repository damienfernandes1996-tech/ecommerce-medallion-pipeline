"""Orchestrator: download -> bronze -> silver -> gold -> dashboard, with quality gates."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb

from . import bronze, download, gold, quality, silver
from .config import PROJECT_ROOT, RAW_FILES, Paths

STAGES = ("bronze", "silver", "gold", "dashboard")


def _quality_gate(paths: Paths, layer: str) -> list[quality.Check]:
    con = duckdb.connect(str(paths.warehouse), read_only=True)
    try:
        checks = quality.run_checks(con, layer)
    finally:
        con.close()
    quality.print_report(checks)
    quality.assert_no_failures(checks)
    return checks


def run(paths: Paths, stages: tuple[str, ...] = STAGES, skip_download: bool = False) -> dict:
    started = time.perf_counter()
    summary: dict = {"row_counts": {}}
    all_checks: list[quality.Check] = []

    if "bronze" in stages and not skip_download:
        if any(not (paths.raw / f).exists() for f in RAW_FILES.values()):
            print("[0/4] Download Olist data")
            download.download(paths)

    if "bronze" in stages:
        print("[1/4] BRONZE  raw copy of the source files")
        summary["row_counts"]["bronze"] = bronze.run(paths)
        all_checks += _quality_gate(paths, "bronze")

    if "silver" in stages:
        print("[2/4] SILVER  cleaning, typing, de-duplication")
        summary["row_counts"]["silver"] = silver.run(paths)
        all_checks += _quality_gate(paths, "silver")

    if "gold" in stages:
        print("[3/4] GOLD    star schema + KPI tables")
        summary["row_counts"]["gold"] = gold.run(paths)
        all_checks += _quality_gate(paths, "gold")

    if "dashboard" in stages:
        print("[4/4] DASHBOARD  export of the Gold layer for the interactive page")
        from . import dashboard_export

        summary["dashboard"] = dashboard_export.run(paths)

    summary["duration_seconds"] = round(time.perf_counter() - started, 1)
    if all_checks:
        quality.save_report(all_checks, paths.outputs / "quality_report.json")
    paths.outputs.mkdir(parents=True, exist_ok=True)
    (paths.outputs / "pipeline_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nDone in {summary['duration_seconds']}s")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Olist medallion pipeline (Bronze/Silver/Gold)")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="project root (default: repo)")
    parser.add_argument("--stages", default=",".join(STAGES), help=f"comma-separated subset of {STAGES}")
    parser.add_argument("--skip-download", action="store_true", help="never try to download the data")
    args = parser.parse_args(argv)

    stages = tuple(s.strip() for s in args.stages.split(",") if s.strip())
    unknown = set(stages) - set(STAGES)
    if unknown:
        parser.error(f"unknown stage(s): {', '.join(sorted(unknown))}")
    run(Paths(args.root), stages, args.skip_download)
