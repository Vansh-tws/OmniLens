import io
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import main

client = TestClient(main.app)


def upload_csv(text: str, name="sample.csv"):
    return client.post("/api/analyze", files={"file": (name, text.encode("utf-8"), "text/csv")})


def test_health_and_home():
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/").json()["version"] == main.APP_VERSION


def test_csv_delimiters_and_indian_numbers():
    df, meta = main.parse_upload("indian.csv", "Name;Amount\nA;1,50,000\nB;₹2,00,000\n".encode())
    assert len(df.columns) == 2
    assert main.parse_indian_number(df.loc[0, "Amount"]) == 150000
    assert main.parse_indian_number(df.loc[1, "Amount"]) == 200000


def test_title_row_header_detection():
    df, meta = main.parse_upload("title.csv", b"Monthly report\nPrepared by office\nName,Amount\nA,10\nB,20\n")
    assert "Name" in df.columns
    assert len(df) == 2


def test_grouped_summary_excludes_all_and_weighted_average():
    df = pd.DataFrame({
        "Group": ["A", "B", "All"],
        "Income (Count)": [10, 30, 40],
        "Income (Sum)": [100, 600, 700],
        "Income (Average)": [10, 20, 17.5],
    })
    shape = main.detect_shape(df)
    assert shape["shape"] == "grouped_summary"
    working, removed = main.exclude_total_rows(df, shape)
    assert len(working) == 2 and removed == [2]
    weighted = main.weighted_summary_columns(working)[0]
    assert weighted["weighted_average"] == 17.5


def test_record_transactions_are_not_mistaken_for_time_series():
    df = pd.DataFrame({"transaction_date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                       "description": ["Tea", "Food", "Bus"], "amount": [10, 20, 30],
                       "direction": ["Money out"] * 3})
    assert main.detect_shape(df)["shape"] == "records"


def test_time_series_shape():
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=15, freq="MS").strftime("%Y-%m-%d"),
                       "rainfall_mm": range(15)})
    assert main.detect_shape(df)["shape"] == "time_series"


def test_text_heavy_shape():
    df = pd.DataFrame({"complaint_description": ["Water supply is not working in my area and it has been three days."] * 15})
    assert main.detect_shape(df)["shape"] == "text_heavy"


def test_wide_table_shape():
    df = pd.DataFrame({"district": ["A", "B"], "Jan": [10, 12], "Feb": [11, 13], "Mar": [9, 12], "Apr": [12, 14], "May": [15, 16]})
    assert main.detect_shape(df)["shape"] == "wide_table"


def test_indian_format_checks():
    df = pd.DataFrame({"phone_number": ["9876543210", "123456789", "9123456780"],
                       "pin_code": ["411001", "1234", "400001"]})
    result = main.detect_indian_formats(df)
    assert any(x["format"] == "Phone number" and x["invalid_count"] == 1 for x in result["checks"])
    assert any(x["format"] == "PIN code" and x["invalid_count"] == 1 for x in result["checks"])


def test_cleaning_preview_and_apply_approval():
    df = pd.DataFrame({"city": ["pune", "Pune ", "PUNE"], "date": ["01/02/2025", "02/02/2025", "03/02/2025"]})
    preview = main.prepare_cleaning(df)
    ids = {x["id"] for x in preview["changes"]}
    assert "trim_spaces" in ids and "normalise_spelling" in ids and "standardise_dates" in ids
    # No mutation of the source; only selected clean steps apply.
    cleaned, log = main.apply_cleaning(df, ["trim_spaces", "standardise_dates"], {})
    assert df.loc[1, "city"] == "Pune "
    assert cleaned.loc[1, "city"] == "Pune"
    assert cleaned.loc[0, "date"] == "2025-02-01"


def test_upload_ask_evidence_and_whatsapp():
    content = "date,category,amount,direction,status\n2025-01-01,Food,100,Money out,Completed\n2025-01-02,Travel,50,Money out,Completed\n2025-01-03,Food,200,Money out,Completed\n"
    response = upload_csv(content)
    assert response.status_code == 200, response.text
    payload = response.json(); sid = payload["session_id"]
    answer = client.post("/api/ask", json={"session_id": sid, "question": "How much did I spend on food?"}).json()
    assert "300.00" in answer["answer"]
    assert answer["evidence_indices"]
    share = client.get(f"/api/share-text/{sid}").json()["text"]
    assert "OmniLens" in share
    finding = payload["analysis"]["findings"][0]
    evidence = client.get(f"/api/evidence/{sid}/{finding['id']}")
    assert evidence.status_code == 200


def test_pending_cases_count_by_district():
    content = "district,status,case_id\nA,Pending,1\nA,Pending,2\nB,Closed,3\nB,Pending,4\n"
    p = upload_csv(content).json()
    answer = client.post("/api/ask", json={"session_id": p["session_id"], "question": "Which district has the most pending cases?"}).json()
    assert "A" in answer["answer"]
    assert "2" in answer["answer"]


def test_pdf_and_docx_report_exports():
    payload = client.post("/api/sample/shop").json(); sid = payload["session_id"]
    assert client.get(f"/api/report/{sid}?format=pdf").status_code == 200
    assert client.get(f"/api/report/{sid}?format=docx").status_code == 200


def test_compare_two_files_autodetects_sales_measure():
    a = b"area,sales_amount\nPune,100\nNashik,50\n"
    b = b"area,sales_amount\nPune,80\nNashik,70\n"
    response = client.post("/api/compare", files={"file_a": ("a.csv", a, "text/csv"), "file_b": ("b.csv", b, "text/csv")})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["measure"] == "sales_amount"
    assert data["differences"][0]["file_a"] == 150.0


def test_three_sample_files():
    for sample in ("shop", "tax", "expenses"):
        response = client.post(f"/api/sample/{sample}")
        assert response.status_code == 200
        assert response.json()["analysis"]["headline"]


def test_purge_session_and_privacy_audit():
    # 1. Create a session
    res = client.post("/api/sample/shop")
    assert res.status_code == 200
    sid = res.json()["session_id"]

    # 2. Check session exists
    status_res = client.get(f"/api/session/{sid}")
    assert status_res.status_code == 200
    assert status_res.json()["active"] is True

    # 3. Privacy audit endpoint
    audit_res = client.get("/api/privacy-audit")
    assert audit_res.status_code == 200
    assert audit_res.json()["storage_mode"] == "in_memory_ram_only"
    assert audit_res.json()["persistent_disk_writes"] is False

    # 4. Purge the session
    purge_res = client.delete(f"/api/session/{sid}")
    assert purge_res.status_code == 200
    assert purge_res.json()["status"] == "purged"

    # 5. Verify it is gone from memory
    gone_res = client.get(f"/api/session/{sid}")
    assert gone_res.status_code == 404
