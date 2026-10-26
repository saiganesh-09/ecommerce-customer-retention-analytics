// dim_date — Power Query (M) script
// Prerequisites: parameter `DataFolder` -> <repo>\data\processed
// After loading: right-click the table > "Mark as date table" > choose `date`.
let
    Source = Csv.Document(
        File.Contents(DataFolder & "\dim_date.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"date", type date},
        {"year", Int64.Type},
        {"month", Int64.Type},
        {"month_name", type text},
        {"year_month", type text},
        {"quarter", Int64.Type},
        {"year_quarter", type text},
        {"day_of_week", type text}
    })
in
    Typed
