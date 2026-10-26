"""Python-side data-quality checks that mirror the SQL DQ script.

Each check returns a dict: {area, name, severity, detail}. run_all_checks()
returns the full list so it can be rendered into the data-quality report.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

from src.data_loading import query


def _rows(sql: str, engine: Engine) -> pd.DataFrame:
    return query(sql, engine)


def check_row_counts(engine: Engine) -> list[dict]:
    df = _rows(
        """
        SELECT 'customers' t, COUNT(*) n FROM raw.customers
        UNION ALL SELECT 'orders', COUNT(*) FROM raw.orders
        UNION ALL SELECT 'order_items', COUNT(*) FROM raw.order_items
        UNION ALL SELECT 'order_payments', COUNT(*) FROM raw.order_payments
        UNION ALL SELECT 'order_reviews', COUNT(*) FROM raw.order_reviews
        UNION ALL SELECT 'products', COUNT(*) FROM raw.products
        UNION ALL SELECT 'sellers', COUNT(*) FROM raw.sellers
        UNION ALL SELECT 'geolocation', COUNT(*) FROM raw.geolocation
        UNION ALL SELECT 'category_translation', COUNT(*)
            FROM raw.category_translation
        """,
        engine,
    )
    return [
        {"area": "row_counts", "name": f"raw.{r.t}", "severity": "INFO",
         "detail": f"{r.n:,} rows"}
        for r in df.itertuples()
    ]


def check_orphaned_keys(engine: Engine) -> list[dict]:
    pairs = [
        ("orders -> customers", "raw.orders o", "raw.customers c",
         "c.customer_id = o.customer_id"),
        ("order_items -> orders", "raw.order_items i", "raw.orders o",
         "o.order_id = i.order_id"),
        ("order_payments -> orders", "raw.order_payments p", "raw.orders o",
         "o.order_id = p.order_id"),
        ("order_reviews -> orders", "raw.order_reviews r", "raw.orders o",
         "o.order_id = r.order_id"),
        ("order_items -> sellers", "raw.order_items i", "raw.sellers s",
         "s.seller_id = i.seller_id"),
    ]
    out = []
    for name, left, right, cond in pairs:
        right_key = cond.split("=")[0].strip()
        n = _rows(
            f"SELECT COUNT(*) n FROM {left} "
            f"LEFT JOIN {right} ON {cond} WHERE {right_key} IS NULL",
            engine,
        ).iloc[0, 0]
        out.append({"area": "referential", "name": f"{name} orphans",
                    "severity": "FAIL(0)", "detail": str(n)})
    return out


def check_date_anomalies(engine: Engine) -> list[dict]:
    checks = [
        ("delivered before carrier handover",
         "order_delivered_customer_date < order_delivered_carrier_date"),
        ("status=delivered but no delivery timestamp",
         "order_status = 'delivered' AND order_delivered_customer_date IS NULL"),
        ("non-delivered status with delivery timestamp",
         "order_status <> 'delivered' "
         "AND order_delivered_customer_date IS NOT NULL"),
    ]
    return [
        {"area": "dates", "name": name, "severity": "WARN",
         "detail": str(_rows(
             f"SELECT COUNT(*) n FROM raw.orders WHERE {cond}",
             engine).iloc[0, 0])}
        for name, cond in checks
    ]


def check_reviews(engine: Engine) -> list[dict]:
    dup = _rows(
        "SELECT COUNT(*) n FROM (SELECT review_id FROM raw.order_reviews "
        "GROUP BY review_id HAVING COUNT(*) > 1) d",
        engine,
    ).iloc[0, 0]
    multi = _rows(
        "SELECT COUNT(*) n FROM (SELECT order_id FROM raw.order_reviews "
        "GROUP BY order_id HAVING COUNT(*) > 1) d",
        engine,
    ).iloc[0, 0]
    return [
        {"area": "reviews", "name": "duplicate review_ids",
         "severity": "WARN", "detail": str(dup)},
        {"area": "reviews", "name": "orders with >1 review row",
         "severity": "WARN", "detail": str(multi)},
    ]


def check_money(engine: Engine) -> list[dict]:
    zero_pay = _rows(
        "SELECT COUNT(*) n FROM raw.order_payments WHERE payment_value = 0",
        engine).iloc[0, 0]
    mismatch = _rows(
        """
        SELECT COUNT(*) n FROM (
            SELECT o.order_id
            FROM raw.orders o
            JOIN (SELECT order_id, SUM(price + freight_value) t
                  FROM raw.order_items GROUP BY order_id) i
              ON i.order_id = o.order_id
            JOIN (SELECT order_id, SUM(payment_value) t
                  FROM raw.order_payments GROUP BY order_id) p
              ON p.order_id = o.order_id
            WHERE o.order_status = 'delivered' AND ABS(i.t - p.t) > 1.00
        ) d
        """,
        engine).iloc[0, 0]
    return [
        {"area": "money", "name": "zero-value payment rows",
         "severity": "WARN", "detail": str(zero_pay)},
        {"area": "money",
         "name": "delivered orders where payments != items+freight (>R$1)",
         "severity": "WARN", "detail": str(mismatch)},
    ]


def run_all_checks(engine: Engine) -> pd.DataFrame:
    """Run every check and return a tidy results DataFrame."""
    checks: list[dict] = []
    checks += check_row_counts(engine)
    checks += check_orphaned_keys(engine)
    checks += check_date_anomalies(engine)
    checks += check_reviews(engine)
    checks += check_money(engine)
    return pd.DataFrame(checks)


def render_report(df: pd.DataFrame) -> str:
    """Render the checks DataFrame as a Markdown report string."""
    lines = [
        "# Data Quality Report",
        "",
        "Checks executed by `src/data_validation.py` against `raw.*` and "
        "`staging.*`. Severity: INFO = fact, WARN = handled quirk, "
        "FAIL(0) = hard invariant that must equal zero.",
        "",
        "| Area | Check | Severity | Result |",
        "|---|---|---|---|",
    ]
    for r in df.itertuples():
        lines.append(f"| {r.area} | {r.name} | {r.severity} | {r.detail} |")
    lines.append("")
    return "\n".join(lines)
