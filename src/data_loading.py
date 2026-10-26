"""Data loading helpers.

Primary source is the PostgreSQL `staging`/`analytics` schemas built by the
SQL scripts. Each loader validates the required columns and parses date
fields, so downstream code always gets analysis-ready DataFrames.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

from src.config import get_engine

ORDER_DATES = [
    "purchase_ts",
    "purchase_date",
    "purchase_month",
    "delivered_ts",
    "estimated_delivery_ts",
]


def query(sql: str, engine: Engine | None = None) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def load_orders_enriched(engine: Engine | None = None) -> pd.DataFrame:
    """Order-grain fact table (one row per order)."""
    df = query("SELECT * FROM staging.orders_enriched", engine)
    for col in ORDER_DATES:
        df[col] = pd.to_datetime(df[col])
    return df


def load_customer_metrics(engine: Engine | None = None) -> pd.DataFrame:
    """Customer-grain metrics built by sql/03_customer_metrics.sql."""
    df = query("SELECT * FROM analytics.customer_metrics", engine)
    for col in ["first_purchase_ts", "last_purchase_ts"]:
        df[col] = pd.to_datetime(df[col])
    for col in ["first_purchase_date", "last_purchase_date",
                "first_purchase_month", "second_purchase_date"]:
        df[col] = pd.to_datetime(df[col])
    return df


def load_order_items(engine: Engine | None = None) -> pd.DataFrame:
    """Order-item grain staging table."""
    return query("SELECT * FROM staging.order_items", engine)


def load_table(schema_table: str, engine: Engine | None = None) -> pd.DataFrame:
    """Load any schema.table (e.g. 'analytics.cohort_retention')."""
    if "." not in schema_table:
        raise ValueError("Expected 'schema.table'")
    return query(f"SELECT * FROM {schema_table}", engine)


def qualifying_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Filter an orders_enriched frame to qualifying (delivered) orders."""
    return df.loc[df["is_qualifying_order"]].copy()
