"""End-to-end tests on the hand-made fixture of conftest.py (expected values computed by hand)."""
from __future__ import annotations

import json

import duckdb
import pytest

from pipeline import quality
from pipeline.config import RAW_FILES


@pytest.fixture()
def con(built):
    c = duckdb.connect(str(built.warehouse), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


# ---------------------------------------------------------------- bronze
def test_bronze_is_an_untouched_copy(con):
    assert one(con, "SELECT count(*) FROM bronze.orders") == 7
    assert one(con, "SELECT count(*) FROM bronze.reviews") == 5          # duplicates kept
    # everything stays text, lineage columns are added
    types = dict(con.execute("SELECT column_name, data_type FROM information_schema.columns "
                             "WHERE table_schema='bronze' AND table_name='orders'").fetchall())
    assert types["order_purchase_timestamp"] == "VARCHAR"
    assert {"_source_file", "_ingested_at"} <= set(types)
    assert one(con, "SELECT DISTINCT _source_file FROM bronze.orders") == RAW_FILES["orders"]


# ---------------------------------------------------------------- silver
def test_silver_deduplicates_reviews_keeping_the_latest(con):
    assert one(con, "SELECT count(*) FROM silver.reviews") == 3          # o2 deduped, invalid score dropped
    assert one(con, "SELECT score FROM silver.reviews WHERE order_id = 'o2'") == 2
    assert one(con, "SELECT count(*) FROM silver.reviews WHERE order_id = 'o5'") == 0


def test_silver_products_translation_and_defaults(con):
    cat = dict(con.execute("SELECT product_id, category FROM silver.products").fetchall())
    assert cat == {"p1": "health_beauty", "p2": "unknown", "p3": "pc_gamer"}


def test_silver_customers_are_normalised(con):
    row = con.execute("SELECT city, state FROM silver.customers WHERE customer_id = 'c1'").fetchone()
    assert row == ("sao paulo", "SP")          # source had ' Sao Paulo ' / 'sp'


def test_silver_delivery_metrics(con):
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT order_id, delivery_days, delay_days, has_date_anomaly FROM silver.orders").fetchall()}
    assert rows["o1"] == (5, -5, False)
    assert rows["o2"] == (18, 5, False)
    assert rows["o3"] == (3, 0, False)
    assert rows["o5"] == (None, None, False)          # not delivered
    assert rows["o7"] == (None, None, True)           # delivered before purchase -> flagged, no metric


# ---------------------------------------------------------------- gold
def test_gold_overview(con):
    cur = con.execute("SELECT * FROM gold.kpi_overview")
    ov = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    assert ov["orders"] == 5                                     # o1 o2 o3 o5 o7 (o4 canceled, o6 unavailable)
    assert ov["total_revenue"] == pytest.approx(480.0)           # 100 + 80 + 200 + 60 + 40
    assert ov["avg_order_value"] == pytest.approx(96.0)
    assert ov["customers"] == 3                                  # u1 u2 u4
    assert ov["repeat_customers"] == 2                           # u1 (o1, o3) and u4 (o5, o7)
    assert ov["repeat_rate"] == pytest.approx(2 / 3)
    assert ov["avg_delivery_days"] == pytest.approx((5 + 18 + 3) / 3)
    assert ov["late_rate"] == pytest.approx(1 / 3)               # only o2 is late
    assert ov["avg_review_score"] == pytest.approx((5 + 2 + 4) / 3)


def test_gold_monthly_with_growth(con):
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT year_month, orders, revenue, revenue_mom_growth FROM gold.kpi_monthly").fetchall()}
    assert rows["2017-01"][:2] == (2, 180.0) and rows["2017-01"][2] is None
    assert rows["2017-02"][:2] == (2, 260.0)
    assert rows["2017-02"][2] == pytest.approx(260 / 180 - 1)
    assert rows["2017-03"][:2] == (1, 40.0)
    assert rows["2017-03"][2] == pytest.approx(40 / 260 - 1)


def test_gold_category_kpis(con):
    rows = {r[0]: r[1:] for r in con.execute("SELECT category, orders, revenue FROM gold.kpi_category").fetchall()}
    assert rows == {"health_beauty": (3, 190.0), "unknown": (2, 90.0), "pc_gamer": (1, 200.0)}


def test_gold_delay_buckets(con):
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT delay_bucket, orders, avg_review_score FROM gold.kpi_delivery_review").fetchall()}
    assert rows == {"early": (1, 5.0), "on_time": (1, 4.0), "late_4_7": (1, 2.0)}


def test_gold_star_schema_grain(con):
    assert one(con, "SELECT count(*) - count(DISTINCT order_id) FROM gold.fact_orders") == 0
    assert one(con, "SELECT count(*) FROM gold.fact_order_items") == 7
    seg = dict(con.execute("SELECT customer_unique_id, segment FROM gold.dim_customers").fetchall())
    assert seg == {"u1": "repeat", "u2": "one_time", "u3": "no_valid_order", "u4": "repeat"}
    # first / second order number of u1
    nums = con.execute("SELECT order_id, customer_order_number FROM gold.fact_orders "
                       "WHERE customer_unique_id = 'u1' ORDER BY purchased_at").fetchall()
    assert nums == [("o1", 1), ("o3", 2)]


# ---------------------------------------------------------------- quality gates
def test_quality_checks_pass_on_clean_data(con):
    for layer in ("silver", "gold"):
        failed = [c for c in quality.run_checks(con, layer) if c.status == "fail"]
        assert not failed, failed


def test_quality_checks_catch_broken_data(built, tmp_path):
    import shutil
    broken = tmp_path / "broken.duckdb"
    shutil.copy(built.warehouse, broken)
    c = duckdb.connect(str(broken))
    c.execute("DELETE FROM silver.customers WHERE customer_id = 'c1'")      # orphan order o1
    c.execute("INSERT INTO silver.order_items SELECT * FROM silver.order_items LIMIT 1")  # duplicate key
    failed = {x.name for x in quality.run_checks(c, "silver") if x.status == "fail"}
    c.close()
    assert "foreign key orders.customer_id -> customers.customer_id" in failed
    assert "unique key order_items(order_id, order_item_id)" in failed
    with pytest.raises(RuntimeError):
        quality.assert_no_failures([quality.Check("silver", "x", "fail", "boom")])


# ---------------------------------------------------------------- outputs
def test_outputs_are_written(built):
    for layer in ("bronze", "silver", "gold"):
        assert any(getattr(built, layer).glob("*.parquet")), layer
    assert (built.outputs / "kpi_overview.csv").exists()
    assert (built.powerbi_export / "fact_orders.csv").exists()
    report = json.loads((built.outputs / "quality_report.json").read_text())
    assert report["summary"]["failed"] == 0


def test_dashboard_export_is_consistent(built):
    text = (built.dashboard / "data.js").read_text(encoding="utf-8")
    data = json.loads(text.removeprefix("window.OLIST_DATA = ").rstrip().removesuffix(";"))
    o, it = data["orders"], data["items"]
    n = len(o["m"])
    assert n == 5 and all(len(v) == n for v in o.values())
    assert it["o"] == sorted(it["o"])                              # items sorted by order (needed by the JS)
    assert sum(o["rev"]) == pytest.approx(data["meta"]["total_revenue"])
    assert sum(it["p"]) == pytest.approx(data["meta"]["total_revenue"])
    assert data["months"] == ["2017-01", "2017-02", "2017-03"]
    assert data["meta"]["default_range"] == ["2017-01", "2017-03"]
