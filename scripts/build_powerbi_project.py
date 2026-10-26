"""Generate a Power BI Project (.pbip) for the Olist retention report.

Produces:
  powerbi/project/OlistRetention.pbip                      (open this)
  powerbi/project/OlistRetention.SemanticModel/            (TMDL model)
  powerbi/project/OlistRetention.Report/                   (PBIR report)

The semantic model loads the CSVs exported by
scripts/export_powerbi_data.py via Power Query (Csv.Document). A
`DataFolder` expression holds the absolute path to data/processed.

Regenerate after data changes:
    python scripts/export_powerbi_data.py
    python scripts/build_powerbi_project.py
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "powerbi" / "project"
DATA_DIR = PROJECT_ROOT / "data" / "processed"
# Forward slashes keep M/TMDL strings free of escaping issues.
DATA_DIR_M = DATA_DIR.as_posix()

PBIR_SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/item/"
               "report/definition/visualContainer/2.2.0/schema.json")
PAGE_SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/item/"
               "report/definition/page/2.0.0/schema.json")


def uid() -> str:
    return uuid.uuid4().hex[:20]


def guid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Field helpers (PBIR projections)
# ---------------------------------------------------------------------------

def col(table: str, prop: str) -> dict:
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": table}},
                                 "Property": prop}},
            "queryRef": f"{table}.{prop}"}


def meas(table: str, prop: str, display: str | None = None) -> dict:
    p = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": table}},
                               "Property": prop}},
         "queryRef": f"{table}.{prop}"}
    if display:
        p["displayName"] = display
    return p


def agg(table: str, prop: str, func: int) -> dict:
    """Function codes: 0=Sum, 1=Avg, 2=Count, 3=Min, 4=Max."""
    name = {0: "Sum", 1: "Average", 2: "Count", 3: "Min", 4: "Max"}[func]
    return {"field": {"Aggregation": {
                "Expression": {"Column": {"Expression": {
                    "SourceRef": {"Entity": table}}, "Property": prop}},
                "Function": func}},
            "queryRef": f"{name}({table}.{prop})"}


def cat_filter(table: str, prop: str, values: list[str]) -> dict:
    """Categorical IN filter for visual.filterConfig."""
    return {
        "name": f"f{uid()[:8]}",
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}},
                             "Property": prop}},
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {
                    "SourceRef": {"Source": "f"}}, "Property": prop}}],
                "Values": [[{"Literal": {"Value": v}}] for v in values]}}}],
        },
        "howCreated": "User",
    }


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def title_obj(text: str) -> dict:
    return {"title": [{"properties": {
        "show": lit("true"),
        "text": lit(f"'{text}'"),
        "fontSize": lit("'10'"),
    }}]}


_Z = [0]


def visual(vtype: str, x: float, y: float, w: float, h: float, z: int,
           roles: dict[str, list[dict]] | None = None,
           title: str | None = None,
           objects: dict | None = None,
           filters: list[dict] | None = None,
           name: str | None = None) -> tuple[str, dict]:
    name = name or uid()
    _Z[0] += 1
    vis: dict = {"visualType": vtype}
    if roles:
        vis["query"] = {"queryState": {
            role: {"projections": projs} for role, projs in roles.items()}}
    if title:
        vis["visualContainerObjects"] = title_obj(title)
    if objects:
        vis["objects"] = objects
    doc = {"$schema": PBIR_SCHEMA, "name": name,
           "position": {"x": x, "y": y, "z": _Z[0] * 1000, "height": h,
                        "width": w, "tabOrder": _Z[0] * 1000},
           "visual": vis}
    if filters:
        doc["filterConfig"] = {"filters": filters}
    return name, doc


def textbox(x, y, w, h, z, paragraphs: list[list[dict]],
            name: str | None = None) -> tuple[str, dict]:
    """paragraphs: list of paragraphs; each paragraph = list of textRuns."""
    name = name or uid()
    return name, {
        "$schema": PBIR_SCHEMA, "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {
                "paragraphs": [{"textRuns": r} for r in paragraphs]}}]},
        },
    }


def run(text: str, size: str = "10pt", bold: bool = False,
        color: str | None = None) -> dict:
    style: dict = {"fontSize": size}
    if bold:
        style["fontWeight"] = "bold"
    if color:
        style["color"] = color
    return {"value": text, "textStyle": style}


def page(name: str, display: str) -> dict:
    return {"$schema": PAGE_SCHEMA, "name": name,
            "displayName": display, "displayOption": "FitToPage",
            "height": 720, "width": 1280}


# ---------------------------------------------------------------------------
# Semantic-model table specs
# T = text, I = Int64, N = number, D = date, B = logical
# ---------------------------------------------------------------------------

T, I, N, D, B = "type text", "Int64.Type", "type number", "type date", "type logical"
M2T = {T: "string", I: "int64", N: "double", D: "dateTime", B: "boolean"}

TABLES: dict[str, dict] = {
    "fact_orders": {
        "csv": "fact_orders.csv",
        "cols": [("order_id", T), ("customer_unique_id", T),
                 ("purchase_date", D), ("purchase_month", D),
                 ("order_status", T), ("is_qualifying_order", B),
                 ("item_count", I), ("items_value", N),
                 ("freight_value", N), ("order_total_value", N),
                 ("payment_total", N), ("payment_types", T),
                 ("max_installments", I), ("delivered_date", D),
                 ("estimated_delivery_date", D), ("delivery_days", I),
                 ("delivery_delay_days", I), ("is_late_delivery", B),
                 ("review_score", I), ("primary_category", T),
                 ("customer_state", T), ("customer_city", T)],
        "measures": [
            ("Total Orders", "COUNTROWS(fact_orders)", "0"),
            ("Qualifying Orders",
             "CALCULATE([Total Orders],fact_orders[is_qualifying_order]=TRUE())", "0"),
            ("Unique Customers",
             "CALCULATE(DISTINCTCOUNT(fact_orders[customer_unique_id]),"
             "fact_orders[is_qualifying_order]=TRUE())", "0"),
            ("Total Revenue (BRL)",
             "CALCULATE(SUM(fact_orders[order_total_value]),"
             "fact_orders[is_qualifying_order]=TRUE())", "#,##0.00"),
            ("Avg Order Value (BRL)",
             "DIVIDE([Total Revenue (BRL)],[Qualifying Orders])", "#,##0.00"),
            ("Delivered With Timestamps",
             "CALCULATE([Total Orders],fact_orders[order_status]=\"delivered\","
             "NOT ISBLANK(fact_orders[delivered_date]),"
             "NOT ISBLANK(fact_orders[estimated_delivery_date]))", "0"),
            ("Late Orders",
             "CALCULATE([Total Orders],fact_orders[is_late_delivery]=TRUE())", "0"),
            ("Late Delivery %",
             "DIVIDE([Late Orders],[Delivered With Timestamps])*100", "0.00"),
            ("Avg Delivery Days",
             "CALCULATE(AVERAGE(fact_orders[delivery_days]),"
             "fact_orders[order_status]=\"delivered\","
             "NOT ISBLANK(fact_orders[delivery_days]))", "0.0"),
            ("Avg Review Score",
             "CALCULATE(AVERAGE(fact_orders[review_score]),"
             "fact_orders[order_status]=\"delivered\")", "0.00"),
        ],
        "hidden_cols": ["order_id", "customer_unique_id"],
    },
    "dim_customers": {
        "csv": "dim_customers.csv",
        "cols": [("customer_unique_id", T), ("order_count", I),
                 ("first_purchase_date", D), ("last_purchase_date", D),
                 ("first_purchase_month", D), ("recency_days", I),
                 ("frequency", I), ("monetary_brl", N),
                 ("r_score", I), ("f_score", I), ("m_score", I),
                 ("rfm_score", I), ("rfm_segment", T),
                 ("avg_review_score", N), ("late_deliveries", I),
                 ("is_repeat_customer", B), ("days_to_second_order", I),
                 ("customer_lifetime_days", I)],
        "measures": [
            ("Customers", "COUNTROWS(dim_customers)", "0"),
            ("Repeat Customers",
             "CALCULATE([Customers],dim_customers[is_repeat_customer]=TRUE())", "0"),
            ("Repeat Purchase Rate %",
             "DIVIDE([Repeat Customers],[Customers])*100", "0.00"),
            ("Avg Customer Spend (BRL)",
             "AVERAGE(dim_customers[monetary_brl])", "#,##0.00"),
        ],
        "hidden_cols": ["customer_unique_id"],
    },
    "dim_date": {
        "csv": "dim_date.csv",
        "cols": [("date", D), ("year", I), ("month", I),
                 ("month_name", T), ("year_month", T), ("quarter", I),
                 ("year_quarter", T), ("day_of_week", T)],
    },
    "cohort_retention": {
        "csv": "cohort_retention.csv",
        "cols": [("cohort_month", D), ("cohort_size", I),
                 ("months_since_first", I), ("activity_month", D),
                 ("active_customers", I), ("retention_pct", N),
                 ("is_observed", B)],
        "measures": [
            ("Retention %", "AVERAGE(cohort_retention[retention_pct])", "0.00"),
        ],
    },
    "cohort_sizes": {
        "csv": "cohort_sizes.csv",
        "cols": [("cohort_month", D), ("cohort_size", I),
                 ("cumulative_customers", N)],
    },
    "cohort_summary": {
        "csv": "cohort_summary.csv",
        "cols": [("months_since_first", I), ("cohorts_observed", I),
                 ("returning_customers", I), ("customers_in_window", I),
                 ("avg_retention_pct", N)],
    },
    "rfm_segments": {
        "csv": "rfm_segments.csv",
        "cols": [("rfm_segment", T), ("customers", I),
                 ("pct_customers", N), ("total_revenue_brl", N),
                 ("pct_revenue", N), ("avg_spend_brl", N),
                 ("avg_recency_days", N), ("avg_frequency", N),
                 ("avg_review_score", N), ("late_delivery_pct", N)],
    },
    "segment_opportunity": {
        "csv": "segment_opportunity.csv",
        "cols": [("rfm_segment", T), ("customers", I),
                 ("pct_customers", N), ("total_revenue_brl", N),
                 ("pct_revenue", N), ("avg_spend_brl", N),
                 ("avg_recency_days", N), ("avg_frequency", N),
                 ("avg_review_score", N), ("late_delivery_pct", N),
                 ("avg_value_per_order_brl", N),
                 ("indicative_order_value_pool", I)],
    },
    "review_by_delivery": {
        "csv": "review_by_delivery.csv",
        "cols": [("delivery_outcome", T), ("orders_with_review", I),
                 ("avg_review_score", N), ("pct_score_1_2", N),
                 ("pct_score_5", N), ("avg_delivery_days", N),
                 ("avg_delay_days", N)],
    },
    "review_distribution_by_delivery": {
        "csv": "review_distribution_by_delivery.csv",
        "cols": [("delivery_outcome", T), ("review_score", I),
                 ("orders", I), ("pct", N)],
    },
    "repeat_by_first_delivery": {
        "csv": "repeat_by_first_delivery.csv",
        "cols": [("cohort_label", T), ("customers", I),
                 ("repeat_customers", I), ("repeat_rate_pct", N),
                 ("customers_180d_window", I), ("repeat_rate_pct_180d", N)],
    },
    "late_by_state": {
        "csv": "late_by_state.csv",
        "cols": [("customer_state", T), ("delivered_orders", I),
                 ("avg_delivery_days", N), ("late_pct", N),
                 ("avg_review_score", N)],
    },
    "late_by_category": {
        "csv": "late_by_category.csv",
        "cols": [("primary_category", T), ("delivered_orders", I),
                 ("avg_delivery_days", N), ("late_pct", N),
                 ("avg_review_score", N)],
    },
    "monthly_orders": {
        "csv": "monthly_orders.csv",
        "cols": [("purchase_month", D), ("orders", I),
                 ("active_customers", I), ("revenue_brl", N),
                 ("avg_order_value_brl", N), ("avg_delivery_days", N)],
    },
    "revenue_by_category": {
        "csv": "revenue_by_category.csv",
        "cols": [("product_category", T), ("orders", I), ("items", I),
                 ("revenue_brl", N), ("pct_revenue", N),
                 ("avg_item_value_brl", N)],
    },
    "customer_purchase_frequency": {
        "csv": "customer_purchase_frequency.csv",
        "cols": [("order_count", I), ("customers", I),
                 ("pct_of_customers", N), ("revenue_brl", N),
                 ("pct_of_revenue", N)],
    },
}

RELATIONSHIPS = [
    ("fact_orders", "customer_unique_id",
     "dim_customers", "customer_unique_id"),
    ("fact_orders", "purchase_date", "dim_date", "date"),
]


# ---------------------------------------------------------------------------
# TMDL emitters
# ---------------------------------------------------------------------------

def tmdl_table(name: str, spec: dict) -> str:
    lines = [f"table {name}", f"\tlineageTag: {guid()}", ""]
    for cname, mtype in spec["cols"]:
        lines += [f"\tcolumn {cname}",
                  f"\t\tdataType: {M2T[mtype]}",
                  f"\t\tsourceColumn: {cname}",
                  f"\t\tlineageTag: {guid()}"]
        if cname in spec.get("hidden_cols", []):
            lines.append("\t\tisHidden")
        lines.append("\t\tsummarizeBy: none")
        lines.append("")
    for mname, dax, fmt in spec.get("measures", []):
        lines += [f"\tmeasure '{mname}' = ```",
                  f"\t\t\t{dax}",
                  "\t\t\t```",
                  f"\t\tlineageTag: {guid()}",
                  f"\t\tformatString: {fmt}",
                  ""]
    type_pairs = ",".join(
        f'{{"{c}", {m}}}' for c, m in spec["cols"])
    lines += [
        f"\tpartition {name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "/{spec["csv"]}"),[Delimiter=",",Encoding=65001,QuoteStyle=QuoteStyle.Csv]),',
        "\t\t\t\t    PromotedHeaders = Table.PromoteHeaders(Source,[PromoteAllScalars=true]),",
        f"\t\t\t\t    ChangedType = Table.TransformColumnTypes(PromotedHeaders,{{{type_pairs}}})",
        "\t\t\t\tin",
        "\t\t\t\t    ChangedType",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(lines)


def platform_file(item_type: str, display: str) -> str:
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": item_type, "displayName": display},
        "config": {"version": "2.0", "logicalId": guid()},
    }, indent=2)


def build_semantic_model() -> Path:
    sm = OUT / "OlistRetention.SemanticModel"
    tables_dir = sm / "definition" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    (sm / ".platform").write_text(
        platform_file("SemanticModel", "OlistRetention"), encoding="utf-8")
    (sm / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {},
    }, indent=2), encoding="utf-8")

    d = sm / "definition"
    (d / "database.tmdl").write_text(
        "database\n\tcompatibilityLevel: 1567\n", encoding="utf-8")

    refs = "\n".join(f"ref table {t}" for t in TABLES)
    (d / "model.tmdl").write_text(
        "model Model\n"
        "\tculture: en-US\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        f"{refs}\n\nref cultureInfo en-US\n",
        encoding="utf-8")

    (d / "expressions.tmdl").write_text(
        f'expression DataFolder = "{DATA_DIR_M}" '
        'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {guid()}\n\n"
        "\tannotation PBI_ResultType = Text\n",
        encoding="utf-8")

    (d / "relationships.tmdl").write_text(
        "\n".join(
            f"relationship {guid()}\n"
            f"\tfromColumn: {fk}.{fkc}\n"
            f"\ttoColumn: {pk}.{pkc}\n"
            for fk, fkc, pk, pkc in RELATIONSHIPS),
        encoding="utf-8")

    for tname, spec in TABLES.items():
        (tables_dir / f"{tname}.tmdl").write_text(
            tmdl_table(tname, spec), encoding="utf-8")
    return sm


# ---------------------------------------------------------------------------
# Report emitters
# ---------------------------------------------------------------------------

NAVY, ACCENT = "#1F4E79", "#E07B39"


def page_title(text: str, z: int = 40000) -> tuple[str, dict]:
    return textbox(24, 10, 1232, 44, z,
                   [[run(text, "16pt", bold=True, color=NAVY)]])


def build_pages() -> dict[str, tuple[str, list[tuple[str, dict]]]]:
    pages: dict[str, tuple[str, list[tuple[str, dict]]]] = {}
    z = 1000

    # ------------------------- Page 1: Executive Overview ------------------
    p1 = "p" + uid()
    v: list[tuple[str, dict]] = [page_title(
        "Executive Overview - Olist Customer Retention & Revenue")]

    kpis = [
        ("Unique Customers", meas("fact_orders", "Unique Customers")),
        ("Qualifying Orders", meas("fact_orders", "Qualifying Orders")),
        ("Repeat Rate %",
         meas("dim_customers", "Repeat Purchase Rate %", "Repeat Rate %")),
        ("Avg Order Value",
         meas("fact_orders", "Avg Order Value (BRL)", "Avg Order Value")),
        ("Total Revenue",
         meas("fact_orders", "Total Revenue (BRL)", "Total Revenue")),
    ]
    x = 24
    for title, proj in kpis:
        v.append(visual("card", x, 70, 240, 92, z,
                        roles={"Values": [proj]}, title=title))
        x += 248

    v.append(visual(
        "lineChart", 24, 178, 760, 250, z,
        roles={"Category": [col("monthly_orders", "purchase_month")],
               "Y": [agg("monthly_orders", "revenue_brl", 0)]},
        title="Monthly revenue (delivered orders)"))
    v.append(visual(
        "donutChart", 800, 178, 456, 250, z,
        roles={"Category": [col("dim_customers", "is_repeat_customer")],
               "Y": [meas("dim_customers", "Customers")]},
        title="One-time vs repeat customers"))
    top10 = ["health_beauty", "watches_gifts", "bed_bath_table",
             "sports_leisure", "computers_accessories", "furniture_decor",
             "housewares", "cool_stuff", "auto", "garden_tools"]
    v.append(visual(
        "clusteredBarChart", 24, 440, 620, 264, z,
        roles={"Category": [col("revenue_by_category", "product_category")],
               "Y": [agg("revenue_by_category", "revenue_brl", 0)]},
        title="Top 10 categories by revenue (R$)"))
    v.append(visual(
        "lineChart", 660, 440, 596, 120, z,
        roles={"Category": [col("monthly_orders", "purchase_month")],
               "Y": [agg("monthly_orders", "orders", 0)]},
        title="Monthly delivered orders"))
    v.append(textbox(
        660, 570, 596, 134, z,
        [[run("Key message", "10pt", bold=True, color=NAVY)],
         [run("97% of customers order exactly once (repeat rate 3.0%). "
              "Repeat buyers return within ~29 days when they do. Delivery "
              "experience is the clearest satisfaction signal: late orders "
              "score 2.27 vs 4.29 on-time.", "9pt")],
         [run("Population: delivered orders, Sep-2016 - Oct-2018. Revenue = "
              "items + freight.", "9pt", color="#666666")]]))
    pages["page1"] = (p1, v)

    # ------------------------- Page 2: Customer Retention ------------------
    p2 = "p" + uid()
    v = [page_title("Customer Retention - Monthly Cohorts")]
    v.append(visual(
        "pivotTable", 24, 70, 700, 500, z,
        roles={"Rows": [col("cohort_retention", "cohort_month")],
               "Columns": [col("cohort_retention", "months_since_first")],
               "Values": [meas("cohort_retention", "Retention %")]},
        title="Cohort retention matrix (% ordering in month N)"))
    v.append(visual(
        "clusteredColumnChart", 740, 70, 516, 240, z,
        roles={"Category": [col("cohort_sizes", "cohort_month")],
               "Y": [agg("cohort_sizes", "cohort_size", 0)]},
        title="Customers acquired per cohort"))
    v.append(visual(
        "lineChart", 740, 322, 516, 248, z,
        roles={"Category": [col("cohort_summary", "months_since_first")],
               "Y": [agg("cohort_summary", "avg_retention_pct", 1)]},
        title="Avg % of cohort ordering in month N (observed only)"))
    v.append(visual(
        "card", 24, 582, 300, 92, z,
        roles={"Values": [meas("dim_customers", "Repeat Purchase Rate %")]},
        title="Overall repeat purchase rate"))
    v.append(textbox(
        340, 582, 916, 100, z,
        [[run("How to read", "10pt", bold=True, color=NAVY)],
         [run("Month 0 = 100% by construction. Retention averages 0.48% in "
              "month 1 and decays to ~0.2% by month 6 across observed "
              "cohorts - no cohort 'warms up'. Incomplete windows are "
              "excluded, not zero-filled.", "9pt")]]))
    pages["page2"] = (p2, v)

    # ------------------------- Page 3: RFM Segmentation --------------------
    p3 = "p" + uid()
    v = [page_title("RFM Customer Segmentation")]
    v.append(visual(
        "slicer", 24, 64, 220, 110, z,
        roles={"Values": [col("dim_customers", "rfm_segment")]}))
    v.append(visual(
        "clusteredBarChart", 24, 190, 600, 240, z,
        roles={"Category": [col("rfm_segments", "rfm_segment")],
               "Y": [agg("rfm_segments", "customers", 0)]},
        title="Customers per segment"))
    v.append(visual(
        "clusteredBarChart", 640, 64, 616, 366, z,
        roles={"Category": [col("rfm_segments", "rfm_segment")],
               "Y": [agg("rfm_segments", "total_revenue_brl", 0)]},
        title="Historical revenue per segment (R$)"))
    v.append(visual(
        "tableEx", 24, 442, 1232, 262, z,
        roles={"Values": [
            col("segment_opportunity", "rfm_segment"),
            col("segment_opportunity", "customers"),
            col("segment_opportunity", "pct_customers"),
            col("segment_opportunity", "total_revenue_brl"),
            col("segment_opportunity", "avg_spend_brl"),
            col("segment_opportunity", "avg_recency_days"),
            col("segment_opportunity", "avg_frequency"),
            col("segment_opportunity", "late_delivery_pct")]},
        title="Segment opportunity detail"))
    pages["page3"] = (p3, v)

    # ------------------- Page 4: Delivery & Experience ---------------------
    p4 = "p" + uid()
    v = [page_title("Delivery Performance & Customer Experience")]
    v.append(visual(
        "slicer", 24, 64, 160, 150, z,
        roles={"Values": [col("fact_orders", "customer_state")]}))
    cards4 = [("Late Delivery %", meas("fact_orders", "Late Delivery %")),
              ("Avg Delivery Days", meas("fact_orders", "Avg Delivery Days")),
              ("Avg Review Score", meas("fact_orders", "Avg Review Score"))]
    x = 200
    for t, proj in cards4:
        v.append(visual("card", x, 64, 260, 92, z,
                        roles={"Values": [proj]}, title=t))
        x += 270
    v.append(visual(
        "clusteredColumnChart", 24, 230, 600, 230, z,
        roles={"Category": [col("review_distribution_by_delivery",
                                "review_score")],
               "Series": [col("review_distribution_by_delivery",
                              "delivery_outcome")],
               "Y": [agg("review_distribution_by_delivery", "pct", 0)]},
        title="Review-score distribution: late vs on-time (%)"))
    v.append(visual(
        "clusteredColumnChart", 640, 170, 300, 140, z,
        roles={"Category": [col("review_by_delivery", "delivery_outcome")],
               "Y": [agg("review_by_delivery", "avg_review_score", 1)]},
        title="Avg review score"))
    v.append(visual(
        "clusteredColumnChart", 956, 170, 300, 140, z,
        roles={"Category": [col("repeat_by_first_delivery", "cohort_label")],
               "Y": [agg("repeat_by_first_delivery",
                         "repeat_rate_pct_180d", 1)]},
        title="Repeat rate, 180-day window"))
    v.append(visual(
        "clusteredBarChart", 640, 322, 616, 240, z,
        roles={"Category": [col("late_by_state", "customer_state")],
               "Y": [agg("late_by_state", "late_pct", 1)]},
        title="Late delivery % by customer state"))
    v.append(textbox(
        24, 574, 1232, 120, z,
        [[run("Reading the evidence", "10pt", bold=True, color=NAVY)],
         [run("Only 6.77% of orders arrive late - but they average 10.6 "
              "days late and a 2.27 review score. Repeat purchasing after a "
              "late first order is ~24% lower (windowed). Lateness is "
              "concentrated in North/North-East states - a logistics "
              "effect, and a confounder: these are associations, not "
              "proven causes.", "9pt")]]))
    pages["page4"] = (p4, v)
    return pages


def build_report() -> Path:
    rep = OUT / "OlistRetention.Report"
    d = rep / "definition"
    (d / "pages").mkdir(parents=True, exist_ok=True)

    (rep / ".platform").write_text(
        platform_file("Report", "OlistRetention"), encoding="utf-8")

    # Copy the bundled base theme that report.json references.
    import shutil
    theme_dst = (rep / "StaticResources" / "SharedResources"
                 / "BaseThemes" / "CY20SU09.json")
    theme_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(PROJECT_ROOT / "powerbi" / "theme" / "CY20SU09.json",
                theme_dst)
    (rep / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {
            "path": "../OlistRetention.SemanticModel"}},
    }, indent=2), encoding="utf-8")

    (d / "version.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    }, indent=2), encoding="utf-8")

    # Full report.json skeleton matching a real Desktop-saved project:
    # themeCollection + objects + resourcePackages + settings are present
    # in every Desktop-produced file; omitting them breaks page loading
    # on some Desktop versions.
    (d / "report.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY20SU09",
                "reportVersionAtImport": {
                    "visual": "1.8.53", "report": "2.0.53", "page": "1.3.53"},
                "type": "SharedResources"}},
        "objects": {"section": [{"properties": {
            "verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
        "resourcePackages": [{
            "name": "SharedResources",
            "type": "SharedResources",
            "items": [{"name": "CY20SU09",
                       "path": "BaseThemes/CY20SU09.json",
                       "type": "BaseTheme"}]}],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "useEnhancedTooltips": True},
        "slowDataSourceSettings": {
            "isCrossHighlightingDisabled": False,
            "isSlicerSelectionsButtonEnabled": False,
            "isFilterSelectionsButtonEnabled": False,
            "isFieldWellButtonEnabled": False,
            "isApplyAllButtonEnabled": False},
    }, indent=2), encoding="utf-8")

    pages = build_pages()
    order = list(pages)
    display = {"page1": "Executive Overview", "page2": "Customer Retention",
               "page3": "RFM Segmentation", "page4": "Delivery & Experience"}
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [pages[k][0] for k in order],
        "activePageName": pages["page1"][0],
    }, indent=2), encoding="utf-8")

    for key in order:
        pname, visuals = pages[key]
        pdir = d / "pages" / pname
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        (pdir / "page.json").write_text(
            json.dumps(page(pname, display[key]), indent=2),
            encoding="utf-8")
        for vname, vdoc in visuals:
            (pdir / "visuals" / vname).mkdir(exist_ok=True)
            (pdir / "visuals" / vname / "visual.json").write_text(
                json.dumps(vdoc, indent=2), encoding="utf-8")
    return rep


def main() -> None:
    # Wipe and regenerate everything: page/visual ids are random per run,
    # so stale folders would otherwise accumulate inside the project.
    # If Power BI Desktop has the project open its files are locked -
    # close the report first or we fall back to overwriting in place.
    if OUT.exists():
        import shutil
        try:
            shutil.rmtree(OUT)
        except PermissionError:
            print("warning: project files locked (Desktop open?) - "
                  "overwriting in place")
            shutil.rmtree(OUT / "OlistRetention.Report" / "definition"
                          / "pages", ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "OlistRetention.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/"
                   "pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": "OlistRetention.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2), encoding="utf-8")

    sm = build_semantic_model()
    rep = build_report()
    n_visuals = len(list(rep.rglob("visual.json")))
    n_tmdl = len(list(sm.rglob("*.tmdl")))
    print(f"Wrote {OUT}")
    print(f"  semantic model: {n_tmdl} TMDL files, {len(TABLES)} tables")
    print(f"  report        : {n_visuals} visuals across 4 pages")
    print("Open powerbi/project/OlistRetention.pbip in Power BI Desktop.")


if __name__ == "__main__":
    main()
