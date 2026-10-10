"""A tiny hand-made dataset in the Olist format, with every edge case the pipeline must handle.

Expected results are computed by hand in tests/test_pipeline.py.

Orders
  o1  delivered   u1  5 days, 5 days early      item 100        review 5
  o2  delivered   u2  18 days, 5 days late       items 50 + 30   two reviews (1 then 2 -> keep 2)
  o3  delivered   u1  on the estimated day       item 200        review 4   (u1 is a repeat customer)
  o4  canceled    u3                             item 80         -> not a valid sale
  o5  shipped     u4  not delivered              item 60         review with an invalid score (9)
  o6  unavailable u3  no item                                    -> not a valid sale
  o7  delivered   u4  delivered BEFORE purchase  item 40         -> date anomaly, no delivery metric
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.config import RAW_FILES, Paths


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_fixture(raw: Path) -> None:
    f = RAW_FILES
    _write(raw / f["customers"],
           ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
           [["c1", "u1", "01000", " Sao Paulo ", "sp"],
            ["c2", "u2", "20000", "rio de janeiro", "RJ"],
            ["c3", "u1", "01000", "sao paulo", "SP"],
            ["c4", "u3", "30000", "belo horizonte", "MG"],
            ["c5", "u4", "01000", "sao paulo", "SP"]])
    _write(raw / f["orders"],
           ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
           [["o1", "c1", "delivered", "2017-01-10 10:00:00", "2017-01-10 11:00:00", "2017-01-11 09:00:00", "2017-01-15 12:00:00", "2017-01-20 00:00:00"],
            ["o2", "c2", "delivered", "2017-01-12 08:00:00", "2017-01-12 09:00:00", "2017-01-13 09:00:00", "2017-01-30 12:00:00", "2017-01-25 00:00:00"],
            ["o3", "c3", "delivered", "2017-02-05 08:00:00", "2017-02-05 09:00:00", "2017-02-06 09:00:00", "2017-02-08 12:00:00", "2017-02-08 00:00:00"],
            ["o4", "c4", "canceled", "2017-02-10 08:00:00", "", "", "", "2017-02-25 00:00:00"],
            ["o5", "c5", "shipped", "2017-02-15 08:00:00", "2017-02-15 09:00:00", "2017-02-16 09:00:00", "", "2017-03-01 00:00:00"],
            ["o6", "c4", "unavailable", "2017-02-20 08:00:00", "", "", "", "2017-03-05 00:00:00"],
            ["o7", "c5", "delivered", "2017-03-10 08:00:00", "2017-03-10 09:00:00", "2017-03-11 09:00:00", "2017-03-05 12:00:00", "2017-03-20 00:00:00"]])
    _write(raw / f["order_items"],
           ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
           [["o1", 1, "p1", "s1", "2017-01-12 00:00:00", "100.00", "10.00"],
            ["o2", 1, "p1", "s1", "2017-01-14 00:00:00", "50.00", "5.00"],
            ["o2", 2, "p2", "s1", "2017-01-14 00:00:00", "30.00", "5.00"],
            ["o3", 1, "p3", "s1", "2017-02-07 00:00:00", "200.00", "20.00"],
            ["o4", 1, "p1", "s1", "2017-02-12 00:00:00", "80.00", "8.00"],
            ["o5", 1, "p2", "s1", "2017-02-17 00:00:00", "60.00", "6.00"],
            ["o7", 1, "p1", "s1", "2017-03-12 00:00:00", "40.00", "4.00"]])
    _write(raw / f["payments"],
           ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
           [["o1", 1, "credit_card", 3, "110.00"], ["o2", 1, "boleto", 1, "90.00"],
            ["o3", 1, "credit_card", 1, "220.00"], ["o4", 1, "credit_card", 1, "88.00"],
            ["o5", 1, "voucher", 1, "66.00"], ["o7", 1, "credit_card", 2, "44.00"]])
    _write(raw / f["reviews"],
           ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
            "review_creation_date", "review_answer_timestamp"],
           [["r1", "o1", 5, "", "great", "2017-01-16 00:00:00", "2017-01-17 10:00:00"],
            ["r2a", "o2", 1, "", "late", "2017-01-31 00:00:00", "2017-02-01 10:00:00"],
            ["r2b", "o2", 2, "", "still late", "2017-02-02 00:00:00", "2017-02-03 10:00:00"],
            ["r3", "o3", 4, "", "", "2017-02-09 00:00:00", "2017-02-10 10:00:00"],
            ["r5", "o5", 9, "", "invalid score", "2017-03-02 00:00:00", "2017-03-03 10:00:00"]])
    _write(raw / f["products"],
           ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
            "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
           [["p1", "beleza_saude", 40, 500, 2, 300, 20, 10, 15],
            ["p2", "", "", "", "", 100, 10, 10, 10],
            ["p3", "pc_gamer", 30, 400, 1, 2000, 40, 30, 30]])
    _write(raw / f["sellers"],
           ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
           [["s1", "01000", "sao paulo", "SP"]])
    _write(raw / f["category_translation"],
           ["product_category_name", "product_category_name_english"],
           [["beleza_saude", "health_beauty"]])


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Run the whole pipeline once on the fixture; return its Paths."""
    from pipeline import runner

    root = tmp_path_factory.mktemp("olist")
    paths = Paths(root)
    write_fixture(paths.raw)
    runner.run(paths, stages=runner.STAGES, skip_download=True)
    return paths
