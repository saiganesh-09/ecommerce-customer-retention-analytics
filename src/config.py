"""Project configuration: database connections and file paths.

Connection settings are read from environment variables (loaded from .env
when present) so that no credentials are hard-coded or committed.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Project root = directory that contains this file's parent (src/).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
SUMMARY_TABLES_DIR = OUTPUTS_DIR / "summary_tables"

load_dotenv(PROJECT_ROOT / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5434"))
DB_NAME = os.getenv("DB_NAME", "olist_analytics")
DB_USER = os.getenv("DB_USER", "olist")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def db_url() -> str:
    """SQLAlchemy/psycopg2 connection URL built from environment settings."""
    return (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )


def get_engine() -> Engine:
    """Return a SQLAlchemy engine for the analytics database."""
    return create_engine(db_url())


def get_connection():
    """Return a raw psycopg2 connection (autocommit off)."""
    import psycopg2

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


# Order of CSV -> raw table mapping used by the loader.
RAW_TABLE_FILES = {
    "raw.customers": "olist_customers_dataset.csv",
    "raw.orders": "olist_orders_dataset.csv",
    "raw.order_items": "olist_order_items_dataset.csv",
    "raw.order_payments": "olist_order_payments_dataset.csv",
    "raw.order_reviews": "olist_order_reviews_dataset.csv",
    "raw.products": "olist_products_dataset.csv",
    "raw.sellers": "olist_sellers_dataset.csv",
    "raw.geolocation": "olist_geolocation_dataset.csv",
    "raw.category_translation": "product_category_name_translation.csv",
}
