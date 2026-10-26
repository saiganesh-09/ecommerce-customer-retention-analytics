// fact_orders — Power Query (M) script
// Load: Get Data > Blank Query > Advanced Editor > paste this.
// Prerequisites: create a text parameter `DataFolder` pointing at
//   <repo>\data\processed  (e.g. "C:\...\data\processed")
let
    Source = Csv.Document(
        File.Contents(DataFolder & "\fact_orders.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"order_id", type text},
        {"customer_unique_id", type text},
        {"purchase_date", type date},
        {"purchase_month", type date},
        {"order_status", type text},
        {"is_qualifying_order", type logical},
        {"item_count", Int64.Type},
        {"items_value", type number},
        {"freight_value", type number},
        {"order_total_value", type number},
        {"payment_total", type number},
        {"payment_types", type text},
        {"max_installments", Int64.Type},
        {"delivered_date", type date},
        {"estimated_delivery_date", type date},
        {"delivery_days", Int64.Type},
        {"delivery_delay_days", Int64.Type},
        {"is_late_delivery", type logical},
        {"review_score", Int64.Type},
        {"primary_category", type text},
        {"customer_state", type text},
        {"customer_city", type text}
    })
in
    Typed
