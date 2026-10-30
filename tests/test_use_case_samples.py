from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import main

client = TestClient(main.app)


def test_crime_sample_is_a_full_fictional_government_workflow():
    response = client.post("/api/sample/crime")
    assert response.status_code == 200, response.text
    payload = response.json()
    analysis = payload["analysis"]
    assert analysis["shape"]["shape"] == "records"
    assert analysis["row_count"] == 300
    assert analysis["charts"]
    assert len(analysis["charts"]) == 3
    assert analysis["findings"]
    assert analysis["actions"]
    assert analysis["caveat"]
    assert "fictional" in payload["sample_description"].lower()
    assert "not official" in payload["sample_description"].lower()
    assert len(payload["suggested_questions"]) == 3
    assert not any("name" in c.lower() for c in main.SAMPLES["crime"].columns)


def test_crime_sample_csv_matches_api_dataset():
    path = ROOT / "samples" / "crime_statistics.csv"
    assert path.exists()
    frame, _ = main.parse_upload(path.name, path.read_bytes())
    assert frame.shape == main.SAMPLES["crime"].shape
    response = client.get("/api/sample-file/crime")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.startswith(b"\xef\xbb\xbf")


def test_investigation_days_are_not_mistaken_for_calendar_dates():
    import pandas as pd

    frame = pd.DataFrame({
        "Case ID": ["A", "B", "C"],
        "Incident Date": ["2025-01-01", "02/01/2025", "03-01-2025"],
        "Investigation Days": [3, 12, 28],
    })
    shape = main.detect_shape(frame)
    assert shape["date_column"] == "Incident Date"
    changes = main.prepare_cleaning(frame)["changes"]
    date_change = next((x for x in changes if x["id"] == "standardise_dates"), None)
    assert date_change is not None
    assert [item["field"] for item in date_change["fields"]] == ["Incident Date"]
