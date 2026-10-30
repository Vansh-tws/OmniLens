# OmniLens 5.0.3 — 15-file test set

All files in `tests/torture_files/` are synthetic. Run them with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

| File | Intended shape | Edge case being tested |
|---|---|---|
| `01_records_sales.csv` | Records | Transaction-style rows, categories, amounts and quantity |
| `02_grouped_tax.csv` | Grouped summary | Count/Sum/Average, income bands and All/Total rows |
| `03_time_series.csv` | Time series | Monthly measurement series with a non-sales measure |
| `04_wide_table.csv` | Wide table | Periods stored in columns |
| `05_survey.csv` | Survey | Categorical response shares and rating scores |
| `06_register.csv` | Register | Contact/list-style data with locations |
| `07_complaint_text.txt` | Text-heavy | Written comments and common terms |
| `08_place_based.csv` | Place-based | Geographic codes and case measures |
| `09_indian_numbers.csv` | Records | Indian digit grouping such as `1,50,000` |
| `10_title_rows.csv` | Records | Title rows above the real header |
| `11_mixed_dates.csv` | Records | Mixed date formats |
| `12_excel_multi_sheet.xlsx` | Place-based | Multiple sheets and table-like sheet selection |
| `13_nested.json` | Place-based | Nested JSON list of records |
| `14_html_table.html` | Place-based | HTML table parsing and numeric ward code |
| `15_pdf_table.pdf` | Place-based | Text-selectable PDF table extraction |

A passing classification is not enough on its own. Review the headline, the measure selected, total-row handling, chart units, evidence rows, and the caveat. The test suite asserts the current expected shape and key guardrails; it is not a guarantee that every arbitrary file will be interpreted correctly.
