"""Data-quality checks, run after each layer.

status: pass | warn | fail
A `fail` stops the pipeline (the layer below must not be built on broken data).
A `warn` is a known data issue that is documented but does not block.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb

from .config import EXPECTED_BRONZE_ROWS


@dataclass
class Check:
    layer: str
    name: str
    status: str
    detail: str


def _scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]


def _zero_check(con, layer: str, name: str, sql: str, fail_status: str = "fail") -> Check:
    """Pass when the query (which counts offending rows) returns 0."""
    n = _scalar(con, sql)
    return Check(layer, name, "pass" if n == 0 else fail_status, f"{n:,} offending rows")


def _equal_check(layer: str, name: str, left: float, right: float, tol: float = 0.01) -> Check:
    ok = abs((left or 0) - (right or 0)) <= tol
    return Check(layer, name, "pass" if ok else "fail", f"{left:,.2f} vs {right:,.2f}")


def bronze_checks(con) -> list[Check]:
    checks = []
    for table, expected in EXPECTED_BRONZE_ROWS.items():
        n = _scalar(con, f"SELECT count(*) FROM bronze.{table}")
        checks.append(
            Check(
                "bronze",
                f"row count {table}",
                "pass" if n == expected else "warn",
                f"{n:,} rows (official release: {expected:,})",
            )
        )
    return checks


def silver_checks(con) -> list[Check]:
    s = "silver"
    c = []
    # --- unique keys
    for table, key in [
        ("orders", "order_id"),
        ("customers", "customer_id"),
        ("products", "product_id"),
        ("sellers", "seller_id"),
        ("reviews", "order_id"),
        ("order_items", "order_id, order_item_id"),
    ]:
        c.append(_zero_check(
            con, s, f"unique key {table}({key})",
            f"SELECT count(*) - count(DISTINCT ({key})) FROM silver.{table}",
        ))
    # --- mandatory columns
    for table, col in [
        ("orders", "customer_id"), ("orders", "purchased_at"),
        ("order_items", "price"), ("payments", "payment_value"),
    ]:
        c.append(_zero_check(
            con, s, f"not null {table}.{col}",
            f"SELECT count(*) FROM silver.{table} WHERE {col} IS NULL",
        ))
    # --- referential integrity
    for child, fk, parent, pk in [
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id", "sellers", "seller_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
    ]:
        c.append(_zero_check(
            con, s, f"foreign key {child}.{fk} -> {parent}.{pk}",
            f"SELECT count(*) FROM silver.{child} ch "
            f"WHERE NOT EXISTS (SELECT 1 FROM silver.{parent} p WHERE p.{pk} = ch.{fk})",
        ))
    # --- value ranges
    c.append(_zero_check(con, s, "price >= 0",
                         "SELECT count(*) FROM silver.order_items WHERE price < 0"))
    c.append(_zero_check(con, s, "freight_value >= 0",
                         "SELECT count(*) FROM silver.order_items WHERE freight_value < 0"))
    c.append(_zero_check(con, s, "review score between 1 and 5",
                         "SELECT count(*) FROM silver.reviews WHERE score NOT BETWEEN 1 AND 5"))
    # --- known data issues (documented, not blocking)
    c.append(_zero_check(con, s, "delivered before purchase",
                         "SELECT count(*) FROM silver.orders WHERE has_date_anomaly", "warn"))
    c.append(_zero_check(con, s, "status 'delivered' without delivery date",
                         "SELECT count(*) FROM silver.orders "
                         "WHERE status = 'delivered' AND delivered_at IS NULL", "warn"))
    # --- bronze -> silver reconciliation
    removed = _scalar(con, "SELECT (SELECT count(*) FROM bronze.reviews) - (SELECT count(*) FROM silver.reviews)")
    c.append(Check(s, "reviews removed by de-duplication", "pass",
                   f"{removed:,} rows (duplicate reviews per order / invalid scores)"))
    c.append(_zero_check(
        con, s, "orders bronze == silver",
        "SELECT abs((SELECT count(*) FROM bronze.orders) - (SELECT count(*) FROM silver.orders))"))
    return c


def gold_checks(con) -> list[Check]:
    g = "gold"
    c = []
    c.append(_zero_check(
        con, g, "fact_orders rows == silver.orders rows",
        "SELECT abs((SELECT count(*) FROM gold.fact_orders) - (SELECT count(*) FROM silver.orders))"))
    c.append(_zero_check(
        con, g, "fact_order_items rows == silver.order_items rows",
        "SELECT abs((SELECT count(*) FROM gold.fact_order_items) - (SELECT count(*) FROM silver.order_items))"))
    c.append(_equal_check(
        g, "revenue silver.order_items == gold.fact_orders",
        _scalar(con, "SELECT sum(price) FROM silver.order_items"),
        _scalar(con, "SELECT sum(items_revenue) FROM gold.fact_orders")))

    total = _scalar(con, "SELECT total_revenue FROM gold.kpi_overview")
    for table in ("kpi_monthly", "kpi_state", "kpi_category", "kpi_payment"):
        c.append(_equal_check(g, f"{table} revenue == kpi_overview", _scalar(con, f"SELECT sum(revenue) FROM gold.{table}"), total))
    c.append(_equal_check(
        g, "kpi_monthly orders == kpi_overview",
        _scalar(con, "SELECT sum(orders) FROM gold.kpi_monthly"),
        _scalar(con, "SELECT orders FROM gold.kpi_overview"), tol=0))
    c.append(_equal_check(
        g, "dim_customers orders == valid orders",
        _scalar(con, "SELECT sum(orders_count) FROM gold.dim_customers"),
        _scalar(con, "SELECT count(*) FROM gold.fact_orders WHERE is_valid_sale"), tol=0))
    c.append(_zero_check(
        con, g, "unique key dim_customers",
        "SELECT count(*) - count(DISTINCT customer_unique_id) FROM gold.dim_customers"))
    c.append(_zero_check(
        con, g, "fact_order_items -> dim_products",
        "SELECT count(*) FROM gold.fact_order_items i "
        "WHERE NOT EXISTS (SELECT 1 FROM gold.dim_products p WHERE p.product_id = i.product_id)"))
    c.append(_zero_check(
        con, g, "fact_orders -> dim_date",
        "SELECT count(*) FROM gold.fact_orders o "
        "WHERE NOT EXISTS (SELECT 1 FROM gold.dim_date d WHERE d.date_key = o.purchase_date_key)"))
    return c


CHECKS = {"bronze": bronze_checks, "silver": silver_checks, "gold": gold_checks}


def run_checks(con: duckdb.DuckDBPyConnection, layer: str) -> list[Check]:
    return CHECKS[layer](con)


def print_report(checks: list[Check]) -> None:
    icons = {"pass": "OK  ", "warn": "WARN", "fail": "FAIL"}
    for chk in checks:
        print(f"    [{icons[chk.status]}] {chk.name:<58} {chk.detail}")


def assert_no_failures(checks: list[Check]) -> None:
    failed = [c for c in checks if c.status == "fail"]
    if failed:
        names = "; ".join(f"{c.layer}: {c.name} ({c.detail})" for c in failed)
        raise RuntimeError(f"Data-quality checks failed -> {names}")


def save_report(checks: list[Check], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "passed": sum(c.status == "pass" for c in checks),
        "warnings": sum(c.status == "warn" for c in checks),
        "failed": sum(c.status == "fail" for c in checks),
    }
    path.write_text(
        json.dumps({"summary": summary, "checks": [asdict(c) for c in checks]}, indent=2),
        encoding="utf-8",
    )
