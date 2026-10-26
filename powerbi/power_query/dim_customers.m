// dim_customers — Power Query (M) script
// Prerequisites: parameter `DataFolder` -> <repo>\data\processed
let
    Source = Csv.Document(
        File.Contents(DataFolder & "\dim_customers.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"customer_unique_id", type text},
        {"order_count", Int64.Type},
        {"first_purchase_date", type date},
        {"last_purchase_date", type date},
        {"first_purchase_month", type date},
        {"recency_days", Int64.Type},
        {"frequency", Int64.Type},
        {"monetary_brl", type number},
        {"r_score", Int64.Type},
        {"f_score", Int64.Type},
        {"m_score", Int64.Type},
        {"rfm_score", Int64.Type},
        {"rfm_segment", type text},
        {"avg_review_score", type number},
        {"late_deliveries", Int64.Type},
        {"is_repeat_customer", type logical},
        {"days_to_second_order", Int64.Type},
        {"customer_lifetime_days", Int64.Type}
    })
in
    Typed
