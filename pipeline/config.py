"""Paths and constants shared by every stage of the pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"

# Public mirror of the Olist dataset (the original lives on Kaggle and needs an account).
MIRROR_URL = (
    "https://raw.githubusercontent.com/spdrio/"
    "Brazilian-E-Commerce-Public-Dataset-by-Olist/master/files"
)
KAGGLE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"

# Bronze table name -> raw CSV file name
RAW_FILES: dict[str, str] = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Row counts of the official Olist release (used as an informational check only).
EXPECTED_BRONZE_ROWS: dict[str, int] = {
    "orders": 99_441,
    "order_items": 112_650,
    "payments": 103_886,
    "customers": 99_441,
    "products": 32_951,
    "sellers": 3_095,
    "category_translation": 71,
}


@dataclass(frozen=True)
class Paths:
    """All locations are derived from one root so tests can run in a temp folder."""

    root: Path = PROJECT_ROOT

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def bronze(self) -> Path:
        return self.root / "data" / "bronze"

    @property
    def silver(self) -> Path:
        return self.root / "data" / "silver"

    @property
    def gold(self) -> Path:
        return self.root / "data" / "gold"

    @property
    def warehouse(self) -> Path:
        return self.root / "data" / "warehouse.duckdb"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def powerbi_export(self) -> Path:
        return self.root / "outputs" / "powerbi"

    @property
    def dashboard(self) -> Path:
        return self.root / "dashboard"
