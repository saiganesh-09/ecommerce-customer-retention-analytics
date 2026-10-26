// cohort_retention — Power Query (M) script
// Prerequisites: parameter `DataFolder` -> <repo>\data\processed
let
    Source = Csv.Document(
        File.Contents(DataFolder & "\cohort_retention.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"cohort_month", type date},
        {"cohort_size", Int64.Type},
        {"months_since_first", Int64.Type},
        {"activity_month", type date},
        {"active_customers", Int64.Type},
        {"retention_pct", type number},
        {"is_observed", type logical}
    })
in
    Typed
