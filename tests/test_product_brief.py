import io
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import main

client = TestClient(main.app)
TORTURE = ROOT / "tests" / "torture_files"


def test_fifteen_file_torture_set_parses_and_returns_honest_result():
    expected = {
        "01_records_sales.csv": "records",
        "02_grouped_tax.csv": "grouped_summary",
        "03_time_series.csv": "time_series",
        "04_wide_table.csv": "wide_table",
        "05_survey.csv": "survey",
        "06_register.csv": "register",
        "07_complaint_text.txt": "text_heavy",
        "08_place_based.csv": "place_based",
        "09_indian_numbers.csv": "records",
        "10_title_rows.csv": "records",
        "11_mixed_dates.csv": "records",
        "12_excel_multi_sheet.xlsx": "place_based",
        "13_nested.json": "place_based",
        "14_html_table.html": "place_based",
        "15_pdf_table.pdf": "place_based",
    }
    files = sorted(TORTURE.iterdir())
    assert len(files) == 15
    for path in files:
        df, meta = main.parse_upload(path.name, path.read_bytes())
        analysis = main.build_analysis(df, path.name, meta)
        assert analysis["headline"].strip(), path.name
        assert analysis["caveat"].strip(), path.name
        assert len(analysis["findings"]) <= 5, path.name
        assert len(analysis["charts"]) <= 3, path.name
        assert analysis["shape"]["shape"] == expected[path.name], path.name


def test_grouped_tax_playbook_uses_totals_not_report_row_counts():
    path = TORTURE / "02_grouped_tax.csv"
    df, meta = main.parse_upload(path.name, path.read_bytes())
    analysis = main.build_analysis(df, path.name, meta)
    assert analysis["excluded_total_rows"]
    assert analysis["weighted_summaries"]
    assert any("Weighted average" in finding["title"] for finding in analysis["findings"])
    assert not any(chart["title"].startswith("Records by") for chart in analysis["charts"])
    assert all("All" not in chart["labels"] for chart in analysis["charts"])
    weighted_finding = next(f for f in analysis["findings"] if "Weighted average" in f["title"])
    assert weighted_finding["rows"], "The weighted calculation must link to its contributing group rows."


def test_time_series_rainfall_gets_chart_and_iso_dates_are_not_called_ambiguous():
    path = TORTURE / "03_time_series.csv"
    df, meta = main.parse_upload(path.name, path.read_bytes())
    analysis = main.build_analysis(df, path.name, meta)
    assert any("rainfall_mm over time" == chart["title"] for chart in analysis["charts"])
    assert analysis["date_notes"] is None
    parsed, note = main.infer_date_format(pd.Series(["2025-01-01", "2025-02-01", "2025-03-01"]))
    assert parsed.notna().all() and note is None


def test_indian_numbering_in_small_file_is_recognised():
    path = TORTURE / "09_indian_numbers.csv"
    df, meta = main.parse_upload(path.name, path.read_bytes())
    shape = main.detect_shape(df)
    assert "Amount" in shape["numeric_columns"]
    assert main.numeric_view(df["Amount"]).tolist() == [150000.0, 200000.0]


def test_numeric_ward_code_is_a_place_dimension_not_a_measure():
    path = TORTURE / "14_html_table.html"
    df, meta = main.parse_upload(path.name, path.read_bytes())
    shape = main.detect_shape(df)
    analysis = main.build_analysis(df, path.name, meta)
    assert "Ward" in shape["dimension_columns"]
    assert "Ward" not in shape["numeric_columns"]
    assert any(chart["title"] == "Complaints by Ward" for chart in analysis["charts"])


def test_survey_charts_show_percentages_and_not_summed_score_labels():
    path = TORTURE / "05_survey.csv"
    df, meta = main.parse_upload(path.name, path.read_bytes())
    analysis = main.build_analysis(df, path.name, meta)
    assert analysis["shape"]["shape"] == "survey"
    assert any(chart["unit"] == "% of responses" for chart in analysis["charts"])
    assert "Average is the largest group" not in analysis["headline"]


def test_cleaning_preview_updates_after_approved_selection_and_preserves_source():
    csv = b"city,date\npune,01/02/2025\nPune ,02/02/2025\nPUNE,03/02/2025\n"
    upload = client.post("/api/analyze", files={"file": ("cities.csv", csv, "text/csv")})
    assert upload.status_code == 200, upload.text
    sid = upload.json()["session_id"]
    before = client.get(f"/api/clean/preview/{sid}").json()
    assert any(x["id"] == "normalise_spelling" for x in before["changes"])
    mapping = {"city::pune": "Pune", "city::PUNE": "Pune", "city::Pune ": "Pune"}
    preview = client.post("/api/clean/preview-approved", json={
        "session_id": sid,
        "approved": ["trim_spaces", "standardise_dates", "normalise_spelling"],
        "fuzzy_mappings": mapping,
    })
    assert preview.status_code == 200, preview.text
    result = preview.json()
    assert result["rows_before"] == result["rows_after"] == 3
    assert {r["city"] for r in result["after"]} == {"Pune"}
    assert all(r["date"].startswith("2025-") for r in result["after"])
    # Uploaded session remains unchanged; cleaning returns a separate copy.
    stored = main.SESSIONS[sid]["df"]
    assert stored.loc[0, "city"] == "pune"
    assert stored.loc[0, "date"] == "01/02/2025"


def test_grouped_compare_prefers_sum_and_excludes_all_rows():
    header = "Taxpayer Type,Income (Count),Income (Sum),Income (Average)\n"
    a = (header + "Individual,10,1000,100\nCompany,5,2000,400\nAll,15,3000,200\n").encode()
    b = (header + "Individual,10,1200,120\nCompany,5,1800,360\nAll,15,3000,200\n").encode()
    response = client.post("/api/compare", files={
        "file_a": ("a.csv", a, "text/csv"),
        "file_b": ("b.csv", b, "text/csv"),
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["measure"] == "Income (Sum)"
    assert data["differences"][0]["file_a"] == 3000.0
    assert data["differences"][0]["file_b"] == 3000.0


def test_ask_food_question_returns_filtered_total_and_chart():
    csv = b"date,category,amount,direction,status\n2025-01-01,Food,100,Money out,Completed\n2025-01-02,Travel,50,Money out,Completed\n2025-01-03,Food,200,Money out,Completed\n2025-01-04,Food,900,Money out,Failed\n"
    upload = client.post("/api/analyze", files={"file": ("spend.csv", csv, "text/csv")})
    assert upload.status_code == 200
    sid = upload.json()["session_id"]
    answer = client.post("/api/ask", json={"session_id": sid, "question": "How much did I spend on food?"})
    assert answer.status_code == 200
    body = answer.json()
    assert "300.00" in body["answer"]
    assert body["chart"] is not None
    assert body["what_this_cannot_tell_us"]


def test_pdf_report_has_chart_content_and_caveat():
    sample = client.post("/api/sample/shop")
    assert sample.status_code == 200
    sid = sample.json()["session_id"]
    response = client.get(f"/api/report/{sid}?format=pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 2000


def test_cleaned_csv_export_masks_personal_fields_by_default():
    csv = (
        b"name,phone_number,amount\n"
        b"A,9876543210,100\n"
        b"B,9876543211,200\n"
    )
    upload = client.post("/api/analyze", files={"file": ("contacts.csv", csv, "text/csv")})
    assert upload.status_code == 200, upload.text
    sid = upload.json()["session_id"]
    response = client.post("/api/clean/apply", json={
        "session_id": sid,
        "approved": [],
        "fuzzy_mappings": {},
        "output_format": "csv",
    })
    assert response.status_code == 200, response.text
    body = response.content.decode("utf-8-sig")
    assert "9876543210" not in body
    assert "98****10" in body


def test_sample_headline_leads_with_business_result_and_time_change():
    data = main.SAMPLES["shop"]
    analysis = main.build_analysis(data, "shop.csv", {"method": "Synthetic sample"})
    assert "Groceries had the highest recorded sales_amount" in analysis["headline"]
    assert "decreased from" in analysis["headline"]
    assert "sales_amount_inr by category" in [c["title"] for c in analysis["charts"]]
    assert "quantity by product" in [c["title"] for c in analysis["charts"]]


def test_personal_sample_totals_keep_failed_attempts_out_of_plain_language_headline():
    data = main.SAMPLES["expenses"]
    analysis = main.build_analysis(data, "expenses.csv", {"method": "Synthetic sample"})
    assert "went out" in analysis["headline"] and "came in" in analysis["headline"]
    assert "Failed or pending attempts are kept out" in analysis["headline"]
    assert "Money out by category" in [c["title"] for c in analysis["charts"]]
    finding = next(f for f in analysis["findings"] if f["title"] == "Some payment attempts were not completed")
    assert len(finding["rows"]) > 0
