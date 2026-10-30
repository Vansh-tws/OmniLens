from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import main

client = TestClient(main.app)


def test_three_samples_are_full_workflows_with_distinct_analyses():
    expected_shapes = {"shop": "records", "expenses": "records", "tax": "grouped_summary"}
    expected_rows = {"shop": 290, "expenses": 271, "tax": 209}
    for sample_id, expected_shape in expected_shapes.items():
        response = client.post(f"/api/sample/{sample_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        analysis = payload["analysis"]
        assert analysis["shape"]["shape"] == expected_shape
        assert analysis["row_count"] == expected_rows[sample_id]
        assert len(analysis["charts"]) == 3
        assert analysis["findings"]
        assert analysis["actions"]
        assert analysis["caveat"]
        assert "fictional" in payload["import_report"]["note"].lower()
        assert len(payload["suggested_questions"]) == 3


def test_shop_sample_shows_sales_story_cleanup_privacy_and_indian_format_check():
    df = main.SAMPLES["shop"]
    shape = main.detect_shape(df)
    analysis = main.build_analysis(df, "shop.csv", {"method": "synthetic"})
    assert "Groceries" in analysis["headline"]
    assert "decreased from 2025-05 to 2025-06" in analysis["headline"]
    assert [c["title"] for c in analysis["charts"]] == [
        "sales_amount_inr by category", "sales_amount_inr over time", "quantity by product"
    ]
    change_ids = {c["id"] for c in main.prepare_cleaning(df)["changes"]}
    assert {"trim_spaces", "normalise_spelling", "standardise_dates", "remove_exact_duplicates"}.issubset(change_ids)
    assert any(x["format"] == "Phone number" for x in analysis["indian_checks"]["checks"])
    assert "customer_phone" in main.detect_pii_columns(df)
    assert "supplier_gstin" in main.detect_pii_columns(df)
    assert "Which category has the highest sales?" in main.get_suggested_questions(df, shape)


def test_personal_expenses_sample_asks_category_and_incoming_payment_questions_correctly():
    df = main.SAMPLES["expenses"]
    shape = main.detect_shape(df)
    food = main.answer_question(df, shape, "How much did I spend on Food?")
    expected = df[
        df["category"].astype(str).str.strip().str.casefold().eq("food")
        & df["direction"].eq("Money out")
        & df["status"].eq("Completed")
    ]["amount_inr"].sum()
    assert f"{expected:,.2f}" in food["answer"]
    assert "Outgoing transactions only" in food["answer"]
    assert food["chart"] is not None
    expense_analysis = main.build_analysis(df, "expenses.csv", {"method": "synthetic"})
    assert [c["title"] for c in expense_analysis["charts"]] == [
        "Money out by category", "Money out over time", "Completed money in vs money out"
    ]
    assert expense_analysis["charts"][2]["values"][0] > expense_analysis["charts"][2]["values"][1]

    received = main.answer_question(df, shape, "Which merchant received the most money?")
    assert "Employer Payroll" in received["answer"]
    assert "Incoming transactions only" in received["answer"]
    assert received["chart"] is not None
    assert any(x["format"] == "IFSC" for x in main.detect_indian_formats(df)["checks"])
    assert "phone_number" in main.detect_pii_columns(df)
    assert "email" in main.detect_pii_columns(df)
    assert "bank_ifsc" in main.detect_pii_columns(df)
    headline = main.build_analysis(df, "expenses.csv", {"method": "synthetic"})["headline"]
    assert "Failed or pending attempts are kept out" in headline


def test_tax_sample_uses_weighted_averages_and_excludes_report_totals():
    df = main.SAMPLES["tax"]
    shape = main.detect_shape(df)
    analysis = main.build_analysis(df, "tax.csv", {"method": "synthetic"})
    working, excluded = main.exclude_total_rows(df, shape)
    assert len(excluded) == 17
    assert len(working) == 192
    assert len(analysis["weighted_summaries"]) == 3
    assert [x["title"] for x in analysis["charts"]] == [
        "Income (Sum) by District",
        "Income (Average) across Income Band",
        "Tax Paid (Sum) by Taxpayer Type",
    ]
    # The income-by-band chart must be count-weighted, not a simple average
    # of the per-row averages (the bands have different taxpayer counts).
    income_bands = working.groupby("Income Band").agg(
        income_sum=("Income (Sum)", "sum"),
        income_count=("Income (Count)", "sum"),
    )
    income_bands["weighted_average"] = income_bands["income_sum"] / income_bands["income_count"]
    average_chart = next(c for c in analysis["charts"] if c["title"] == "Income (Average) across Income Band")
    assert "Count-weighted" in average_chart["explanation"]
    for label, value in zip(average_chart["labels"], average_chart["values"]):
        assert value == pytest.approx(income_bands.loc[label, "weighted_average"], abs=0.01)
    questions = main.get_suggested_questions(df, shape)
    assert questions == [
        "Which district has the highest total income?",
        "What is the weighted average income?",
        "How much tax was paid in total?",
    ]
    ranked = main.answer_question(df, shape, questions[0])
    assert "Mumbai Suburban" in ranked["answer"]
    weighted = main.answer_question(df, shape, questions[1])
    expected_weighted = working["Income (Sum)"].sum() / working["Income (Count)"].sum()
    assert f"{expected_weighted:,.2f}" in weighted["answer"]
    total_tax = main.answer_question(df, shape, questions[2])
    expected_tax = working["Tax Paid (Sum)"].sum()
    assert f"{expected_tax:,.2f}" in total_tax["answer"]
    assert "Tax Paid (Sum)" in total_tax["answer"]
    assert analysis["actions"], "Grouped reports should also produce useful next steps."
    neighbour = next(f for f in analysis["findings"] if "neighbouring groups in Income Band" in f["title"])
    assert "combining rows within each band" in neighbour["happened"]
    assert len(neighbour["rows"]) == len(working)
    assert neighbour["happened"].count("adjacent change(s)") == 1


def test_sample_csv_assets_match_in_app_datasets_and_download_route():
    sample_files = {
        "shop": "shop_sales.csv",
        "expenses": "personal_expenses.csv",
        "tax": "tax_summary.csv",
    }
    for sample_id, filename in sample_files.items():
        path = ROOT / "samples" / filename
        assert path.exists()
        df, _ = main.parse_upload(filename, path.read_bytes())
        assert df.shape == main.SAMPLES[sample_id].shape
        response = client.get(f"/api/sample-file/{sample_id}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert response.content.startswith(b"\xef\xbb\xbf")


def test_ready_made_compare_pair_uses_sales_value_not_quantity():
    earlier = client.get("/api/sample-file/shop_earlier")
    later = client.get("/api/sample-file/shop_later")
    assert earlier.status_code == later.status_code == 200
    response = client.post("/api/compare", files={
        "file_a": ("shop_sales_earlier_period.csv", earlier.content, "text/csv"),
        "file_b": ("shop_sales_later_period.csv", later.content, "text/csv"),
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["measure"] == "sales_amount_inr"
    assert "decreased" in result["headline"]


def test_sample_evidence_and_share_exports_keep_the_source_rows_and_caveat():
    sample = client.post("/api/sample/shop").json()
    sid = sample["session_id"]
    analysis = sample["analysis"]
    finding = next(f for f in analysis["findings"] if f["title"] == "Some rows appear more than once")
    evidence = client.get(f"/api/evidence/{sid}/{finding['id']}")
    assert evidence.status_code == 200
    assert evidence.json()["count"] >= 2
    share = client.get(f"/api/share-text/{sid}").json()["text"]
    assert "OmniLens" in share
    assert "What to check next" in share
    assert "What this file cannot tell us" in share
