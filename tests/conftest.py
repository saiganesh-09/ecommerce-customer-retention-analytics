"""Shared pytest fixtures.

DB-dependent tests are skipped automatically when the PostgreSQL container
is unreachable so the unit suite still runs anywhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _db_available() -> bool:
    try:
        from src.config import get_connection
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL database is not reachable")


@pytest.fixture(scope="session")
def engine():
    from src.config import get_engine
    return get_engine()


@pytest.fixture()
def synthetic_orders() -> pd.DataFrame:
    """Small deterministic orders frame for unit tests.

    5 customers, mixed statuses, two late deliveries, one repeat buyer.
    """
    rows = [
        # order_id, cust, status, purchase, delivered, estimate, total, review
        ("o1", "c1", "delivered", "2018-01-01", "2018-01-05", "2018-01-10", 100.0, 5),
        ("o2", "c1", "delivered", "2018-02-01", "2018-02-03", "2018-02-08", 50.0, 4),
        ("o3", "c2", "delivered", "2018-01-10", "2018-01-25", "2018-01-20", 200.0, 1),  # late
        ("o4", "c3", "delivered", "2018-02-15", "2018-02-20", "2018-02-25", 80.0, 4),
        ("o5", "c4", "delivered", "2018-03-01", None, "2018-03-10", 60.0, None),       # no ts
        ("o6", "c5", "canceled",  "2018-03-05", None, "2018-03-15", 70.0, None),       # not qualifying
        ("o7", "c2", "delivered", "2018-04-02", "2018-04-05", "2018-04-03", 40.0, 2),  # late (5>3)
    ]
    df = pd.DataFrame(rows, columns=[
        "order_id", "customer_unique_id", "order_status", "purchase_ts",
        "delivered_ts", "estimated_delivery_ts", "order_total_value",
        "review_score",
    ])
    for c in ["purchase_ts", "delivered_ts", "estimated_delivery_ts"]:
        df[c] = pd.to_datetime(df[c])
    df["purchase_date"] = df["purchase_ts"].dt.normalize()
    df["purchase_month"] = df["purchase_ts"].values.astype("datetime64[M]")
    df["delivery_days"] = (df["delivered_ts"].dt.normalize()
                           - df["purchase_date"]).dt.days
    df["delivery_delay_days"] = (df["delivered_ts"].dt.normalize()
                                 - df["estimated_delivery_ts"].dt.normalize()).dt.days
    df["is_late_delivery"] = (
        df["order_status"].eq("delivered")
        & df["delivered_ts"].notna()
        & (df["delivered_ts"].dt.normalize()
           > df["estimated_delivery_ts"].dt.normalize()))
    df["is_qualifying_order"] = df["order_status"].eq("delivered")
    return df
