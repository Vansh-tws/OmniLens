# OmniLens sample datasets

All included sample data is fictional and created only to demonstrate OmniLens. It is not official government information or real customer/tax/payment/crime data.

## Government & public services
- `tax_summary.csv`: district tax summary with detail rows, subtotals and a grand total. Tests weighted averages and exclusion of totals.
- `crime_statistics.csv`: fictional district-level incident register covering 2025, crime categories, severity, case status, reporting channel, investigation duration and estimated property loss. It contains no personal names and must not be cited as official crime statistics.

## Business
- `shop_sales.csv`: six months of product sales and shop transactions, with useful cleanup examples.
- `shop_sales_earlier_period.csv` and `shop_sales_later_period.csv`: matching first-half/second-half comparison files.

## Personal
- `personal_expenses.csv`: synthetic incoming and outgoing payments, categories, statuses and masked-identifier demonstrations.

Regenerate all files with `python scripts/generate_sample_data.py`.
