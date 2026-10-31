from __future__ import annotations

import asyncio
import csv
import datetime as dt
import difflib
import gc
import html
import io
import json
import math
import os
import re
import secrets
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from backend.sample_data import build_samples

# Optional readers/exporters. The core CSV analysis remains usable if one
# optional package is absent; unsupported formats return an actionable error.
try:
    import pdfplumber
except Exception:  # pragma: no cover - environment dependent
    pdfplumber = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    )
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
except Exception:  # pragma: no cover - environment dependent
    SimpleDocTemplate = None
    Drawing = None
    VerticalBarChart = None

try:
    from docx import Document
except Exception:  # pragma: no cover - environment dependent
    Document = None


APP_VERSION = "5.0.3"
APP_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = APP_DIR / "samples"
MAX_UPLOAD_BYTES = int(os.getenv("OMNILENS_MAX_UPLOAD_MB", "25")) * 1024 * 1024
SESSION_TTL_SECONDS = int(os.getenv("OMNILENS_SESSION_TTL", "1800"))
MAX_SESSIONS = int(os.getenv("OMNILENS_MAX_SESSIONS", "12"))
MAX_EVIDENCE_ROWS = 500

@asynccontextmanager
async def app_lifespan(application):
    # Uploaded data sessions are held in RAM and removed after the configured TTL,
    # even when a user leaves the browser without making another request.
    cleanup_task = asyncio.create_task(_session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="OmniLens",
    version=APP_VERSION,
    description="Private, session-based data understanding and decision support.",
    lifespan=app_lifespan,
)

cors_env = os.getenv("OMNILENS_CORS_ORIGINS", "*")
if cors_env.strip() == "*":
    origins = ["*"]
else:
    origins = [x.strip() for x in cors_env.split(",") if x.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_privacy_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# Uploaded data is held only in this bounded in-memory cache. No upload is
# written to a persistent application directory, database, or object store.
SESSIONS: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------

def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def clean_filename(name: str) -> str:
    base = Path(name or "uploaded_file").name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:100] or "uploaded_file"


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def parse_indian_number(value: Any) -> Any:
    """Parse numbers such as ₹1,50,000 or 1,50,000.50 safely."""
    if is_blank(value):
        return np.nan
    if isinstance(value, (int, float, np.number)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "—", "NA", "N/A", "null", "None"}:
        return np.nan
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"(?i)\b(INR|Rs\.?|rupees?)\b", "", text)
    text = text.replace("₹", "").replace("\u00a0", "").replace(" ", "")
    # Commas are treated as thousands separators only when decimal point is
    # absent or follows a valid 1-2 digit decimal suffix.
    if "," in text:
        if re.fullmatch(r"[-+]?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?", text):
            text = text.replace(",", "")
        else:
            # Remove grouping commas in Indian numbers (1,50,000), never guess
            # when the token contains unrelated characters.
            compact = text.replace(",", "")
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", compact):
                text = compact
    text = text.replace("%", "")
    try:
        number = float(text)
        return -number if negative else number
    except ValueError:
        return np.nan


def numeric_view(series: pd.Series) -> pd.Series:
    return series.map(parse_indian_number).astype(float)


def normalise_header(value: Any) -> str:
    text = str(value).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text or "Unnamed field"


def frame_quality_score(df: pd.DataFrame) -> tuple[float, int]:
    if df is None or df.empty or len(df.columns) == 0:
        return (-1, 0)
    nonempty_cols = sum(not str(c).lower().startswith("unnamed:") for c in df.columns)
    total = max(1, df.size)
    density = float(df.notna().sum().sum()) / total
    unique_headers = len({str(c).strip().lower() for c in df.columns})
    numeric_cols = sum(numeric_view(df[c]).notna().mean() >= 0.65 for c in df.columns)
    score = min(len(df.columns), 30) * 2 + min(len(df), 100) * 0.05
    score += density * 10 + unique_headers / max(1, len(df.columns)) * 5
    score += min(numeric_cols, 10) * 0.3 + nonempty_cols * 0.2
    if len(df.columns) == 1:
        score -= 5
    return score, numeric_cols


def tidy_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame.columns = [normalise_header(c) for c in frame.columns]
    # Make duplicate header names unique while preserving a readable label.
    counts: Counter[str] = Counter()
    new_cols = []
    for col in frame.columns:
        counts[col] += 1
        new_cols.append(col if counts[col] == 1 else f"{col} ({counts[col]})")
    frame.columns = new_cols
    frame = frame.dropna(axis=1, how="all")
    # Drop completely blank rows, but do not remove totals or duplicate rows.
    frame = frame.dropna(axis=0, how="all").reset_index(drop=True)
    return frame


# ---------------------------------------------------------------------------
# File ingestion: CSV, Excel (several sheets/title rows), JSON, text, HTML, PDF
# ---------------------------------------------------------------------------

class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        elif tag.lower() in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"} and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1
        elif tag.lower() in {"p", "div", "li", "tr"} and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def read_csv_flexible(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    best: tuple[float, pd.DataFrame, dict[str, Any]] | None = None
    failures = []
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        for sep in (",", ";", "\t", "|"):
            for skip in range(0, 7):
                try:
                    df = pd.read_csv(
                        io.BytesIO(content), sep=sep, engine="python",
                        encoding=encoding, skiprows=skip,
                        on_bad_lines="error", dtype=object,
                    )
                    df = tidy_frame(df)
                    score, _ = frame_quality_score(df)
                    # Prefer a separator that appears consistently on each
                    # source line. This prevents commas inside Indian amounts
                    # such as 1,50,000 from beating the actual semicolon delimiter.
                    source_lines = [line for line in decode_text(content).splitlines()[:12] if line.strip()]
                    sep_counts = [line.count(sep) for line in source_lines[:8]]
                    nonzero_counts = [x for x in sep_counts if x > 0]
                    if nonzero_counts and len(nonzero_counts) >= max(2, len(sep_counts) - 1):
                        spread = max(nonzero_counts) - min(nonzero_counts)
                        consistency_bonus = 20.0 / (1.0 + spread + (len(sep_counts) - len(nonzero_counts)) * 2)
                        score += consistency_bonus
                    # Reward more than one field, but avoid selecting a
                    # fragmented parse with dozens of mostly-empty columns.
                    if len(df.columns) > 1:
                        score += min(len(df.columns), 20) * 0.2
                    meta = {"method": "CSV delimiter and header detection", "delimiter": "TAB" if sep == "\t" else sep,
                            "encoding": encoding, "title_rows_skipped": skip}
                    if best is None or score > best[0]:
                        best = (score, df, meta)
                except Exception as exc:
                    failures.append(str(exc))
    if best is None:
        raise ValueError("This CSV could not be read. Save it as UTF-8 CSV and try again.")
    _, df, meta = best
    if len(df.columns) == 1:
        meta["warning"] = "Only one column was found. Check whether the file is actually a table or a block of text."
    if meta["title_rows_skipped"]:
        meta["note"] = f"Skipped {meta['title_rows_skipped']} title or introductory row(s) above the table header."
    return df, meta


def read_excel_flexible(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    best: tuple[float, pd.DataFrame, dict[str, Any]] | None = None
    try:
        book = pd.ExcelFile(io.BytesIO(content))
    except Exception as exc:
        raise ValueError("This Excel file could not be opened. Check that it is not password-protected.") from exc
    for sheet in book.sheet_names:
        for header_row in range(0, 7):
            try:
                df = pd.read_excel(book, sheet_name=sheet, header=header_row, dtype=object)
                df = tidy_frame(df)
                score, _ = frame_quality_score(df)
                meta = {"method": "Excel sheet and header detection", "sheet": sheet,
                        "available_sheets": book.sheet_names, "title_rows_skipped": header_row}
                if best is None or score > best[0]:
                    best = (score, df, meta)
            except Exception:
                continue
    if best is None:
        raise ValueError("No usable table was found in the Excel workbook.")
    _, df, meta = best
    if len(book.sheet_names) > 1:
        meta["note"] = f"Selected the most table-like sheet: {meta['sheet']}. Other sheets: {', '.join(x for x in book.sheet_names if x != meta['sheet'])}."
    if meta["title_rows_skipped"]:
        meta["note"] = (meta.get("note", "") + f" Skipped {meta['title_rows_skipped']} title row(s). ").strip()
    return df, meta


def read_json_flexible(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        value = json.loads(decode_text(content))
    except json.JSONDecodeError as exc:
        raise ValueError("This JSON file is not valid. Check brackets and commas.") from exc
    if isinstance(value, list):
        if value and all(isinstance(x, dict) for x in value):
            df = pd.json_normalize(value, sep=".")
        else:
            df = pd.DataFrame({"Value": value})
    elif isinstance(value, dict):
        # Prefer the largest nested list of objects, common in API exports.
        candidates: list[tuple[int, str, list]] = []
        def walk(obj, path=""):
            if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
                candidates.append((len(obj), path, obj))
            elif isinstance(obj, dict):
                for key, child in obj.items():
                    walk(child, f"{path}.{key}" if path else str(key))
        walk(value)
        if candidates:
            _, path, records = max(candidates, key=lambda x: x[0])
            df = pd.json_normalize(records, sep=".")
            return tidy_frame(df), {"method": "JSON records", "records_path": path}
        df = pd.json_normalize(value, sep=".")
    else:
        df = pd.DataFrame({"Value": [value]})
    return tidy_frame(df), {"method": "JSON normalisation"}


def read_html_flexible(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        tables = pd.read_html(io.BytesIO(content))
    except Exception:
        tables = []
    if tables:
        df = max(tables, key=lambda x: x.shape[0] * x.shape[1])
        return tidy_frame(df), {"method": "HTML table extraction", "tables_found": len(tables)}
    parser = VisibleTextParser()
    parser.feed(decode_text(content))
    lines = [x.strip() for x in "\n".join(parser.parts).splitlines() if x.strip()]
    if not lines:
        raise ValueError("No visible table or text was found in this HTML file.")
    return pd.DataFrame({"Text": lines}), {"method": "HTML visible text", "note": "No HTML table was found; text was kept as separate lines."}


def read_pdf_tables(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    if pdfplumber is None:
        raise ValueError("PDF table reading is not installed. Install pdfplumber, or upload an Excel/CSV copy.")
    tables = []
    pages_with_text = 0
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                if page.extract_text():
                    pages_with_text += 1
                page_tables = page.extract_tables() or []
                for table in page_tables:
                    if table and len(table) >= 2:
                        tables.append((page_no, table))
    except Exception as exc:
        raise ValueError("This PDF could not be read. It may be password-protected or damaged.") from exc
    if not tables:
        raise ValueError("No selectable table was found in this PDF. Scanned/image-only PDFs need OCR; for now upload the original Excel/CSV or a text-based PDF with tables.")
    # Choose the table with the most rows and columns. This avoids silently
    # stacking unrelated tables from different report sections.
    page_no, table = max(tables, key=lambda item: len(item[1]) * max(len(r or []) for r in item[1]))
    width = max(len(row or []) for row in table)
    padded = [(row or []) + [None] * (width - len(row or [])) for row in table]
    df = pd.DataFrame(padded[1:], columns=padded[0])
    return tidy_frame(df), {"method": "PDF selectable table extraction", "page": page_no,
                           "tables_found": len(tables), "pages_with_text": pages_with_text,
                           "note": "Extracted the largest table. Check the preview against the PDF before relying on it."}


def read_txt_flexible(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    text = decode_text(content)
    # Detect Google Pay activity exports with repeated transaction sentences.
    entries = parse_gpay_text(text)
    if entries:
        return tidy_frame(pd.DataFrame(entries)), {"method": "Google Pay activity extraction", "transactions_found": len(entries),
               "note": "Payment entries were extracted from text. Review unknown statuses and suggested categories."}
    # Try table-like text files before keeping as prose.
    for sep in ("\t", ";", "|", ","):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python", dtype=object)
            df = tidy_frame(df)
            if len(df.columns) > 1 and len(df) > 0:
                return df, {"method": "Text table detection", "delimiter": "TAB" if sep == "\t" else sep}
        except Exception:
            pass
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("This text file is empty.")
    return pd.DataFrame({"Text": lines}), {"method": "Plain text extraction", "note": "This is text, not a table. OmniLens will count common terms and show representative lines."}


def parse_gpay_text(text: str) -> list[dict[str, Any]]:
    blob = html.unescape(re.sub(r"\s+", " ", text.replace("\xa0", " ")))
    splitter = re.compile(r"(?=Google Pay\s+(?:Paid|Sent|Received)\s+₹\s*[\d,]+(?:\.\d{1,2})?)", re.I)
    pieces = [p.strip() for p in splitter.split(blob) if p.strip()]
    month_map = {m.lower(): i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}
    out = []
    seen = set()
    for piece in pieces:
        m = re.match(r"Google Pay\s+(Paid|Sent|Received)\s+₹\s*([\d,]+(?:\.\d{1,2})?)", piece, re.I)
        if not m:
            continue
        date = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4}),?\s+(\d{1,2}):(\d{2}):(\d{2})\s*(?:IST)?", piece, re.I)
        if not date:
            continue
        day, mon, year, hour, minute, second = date.groups()
        month = month_map.get(mon.lower()) or next((v for k, v in month_map.items() if k.startswith(mon[:3].lower())), None)
        if not month:
            continue
        try:
            stamp = dt.datetime(int(year), month, int(day), int(hour), int(minute), int(second))
        except ValueError:
            continue
        event_type = m.group(1).title()
        amount = float(m.group(2).replace(",", ""))
        merchant_match = re.search(r"\bto\s+(.+?)(?=\s+using\s+(?:Bank Account|Credit Card|UPI|Wallet)\b|\s+\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", piece, re.I)
        merchant = merchant_match.group(1).strip(' ."') if merchant_match else None
        status_match = re.search(r"\b(Completed|Failed|Pending|Successful|Succeeded)\b", piece, re.I)
        status = status_match.group(1).title() if status_match else "Unknown"
        if status in {"Successful", "Succeeded"}:
            status = "Completed"
        method_match = re.search(r"\busing\s+(Bank Account|Credit Card|UPI|Wallet)\b", piece, re.I)
        method = method_match.group(1) if method_match else "Not specified"
        key = (event_type, amount, stamp.isoformat(), (merchant or "").lower(), status)
        if key in seen:
            continue
        seen.add(key)
        direction = "Money in" if event_type == "Received" else "Money out"
        out.append({
            "transaction_date": stamp.date().isoformat(),
            "transaction_time": stamp.time().isoformat(),
            "transaction_type": event_type,
            "direction": direction,
            "amount": amount,
            "recipient_or_merchant": merchant,
            "category_suggestion": suggest_category(merchant or "", event_type),
            "payment_method": method,
            "status": status,
        })
    return out


def suggest_category(text: str, event_type: str = "") -> str:
    t = text.lower()
    patterns = [
        (r"grocery|kirana|super.?market|super.?bazar|general stor|daily needs|zepto|blinkit|bigbasket|mart|bazaar", "Groceries"),
        (r"cafe|coffee|brew|bakery|restaurant|food|pizza|momo|pani puri|chat centre|snack|sweet|hotel", "Food"),
        (r"wellness|medicose|pharmacy|medical|chemist|hospital|clinic", "Health"),
        (r"msrtc|railway|irctc|metro|uber|ola|fuel|petrol|transport", "Travel"),
        (r"hotstar|netflix|spotify|prime video|cinema|movie", "Entertainment"),
        (r"amazon|flipkart|meesho|myntra|zudio|shopping|fashion|retail", "Shopping"),
        (r"academy|college|school|tuition|course|university", "Education"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, t):
            return label
    return "Money received / transfer" if event_type == "Received" else "Other / review"


def parse_upload(filename: str, content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    ext = Path(filename.lower()).suffix
    if ext not in {".csv", ".xlsx", ".xls", ".json", ".txt", ".html", ".htm", ".pdf"}:
        raise ValueError("That file type is not supported yet. Please choose CSV, Excel, JSON, TXT, HTML, or a text-based PDF with tables.")
    if not content:
        raise ValueError("The selected file is empty. Choose another file.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"This file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Please upload a smaller file.")
    if ext == ".csv":
        df, meta = read_csv_flexible(content)
    elif ext in {".xlsx", ".xls"}:
        df, meta = read_excel_flexible(content)
    elif ext == ".json":
        df, meta = read_json_flexible(content)
    elif ext in {".html", ".htm"}:
        df, meta = read_html_flexible(content)
    elif ext == ".pdf":
        df, meta = read_pdf_tables(content)
    else:
        df, meta = read_txt_flexible(content)
    df = tidy_frame(df)
    if df.empty or len(df.columns) == 0:
        raise ValueError("I couldn't find a usable table in this file. Try an Excel or CSV version, or check that the first row contains column names.")
    return df, meta


# ---------------------------------------------------------------------------
# Date and semantic detection
# ---------------------------------------------------------------------------

DATE_NAME_RE = re.compile(r"(?:^|[^a-z])(?:date|day|month|period|timestamp)(?:$|[^a-z])", re.I)
ID_NAME_RE = re.compile(r"(^id$|_id$|\bid\b|code$|pin|pincode|postal|phone|mobile|aadhaar|pan|ifsc|invoice|serial|index|^sr\.?\s*no)", re.I)
MEASURE_WORDS = re.compile(r"amount|sales|revenue|collection|receipt|expense|spend|cost|profit|income|quantity|count|total|sum|balance|value|cases|complaints|population|marks|score|rainfall|temperature|duration|days|rating", re.I)
RATE_RE = re.compile(r"average|avg|mean|median|percentage|percent|pct|ratio|rate|share|margin", re.I)
TOTAL_TOKENS = {"all", "total", "grand total", "overall", "subtotal", "overall total", "all districts", "all wards"}


def infer_date_format(series: pd.Series) -> tuple[pd.Series, str | None]:
    values = series.dropna().astype(str).head(100)
    if values.empty:
        return pd.to_datetime(series, errors="coerce"), None

    dayfirst = True  # India-friendly default for genuinely ambiguous slash dates.
    saw_ambiguous_slash_date = False
    saw_unambiguous_order = False
    for value in values:
        token = value.strip()
        # ISO year-first dates do not need a day/month assumption.
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}(?:[ T].*)?$", token):
            saw_unambiguous_order = True
            continue
        match = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$", token)
        if not match:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12 and second <= 12:
            dayfirst, saw_unambiguous_order = True, True
            break
        if second > 12 and first <= 12:
            dayfirst, saw_unambiguous_order = False, True
            break
        if first <= 12 and second <= 12:
            saw_ambiguous_slash_date = True

    try:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst, format="mixed")
    except (TypeError, ValueError):
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)

    note = None
    if saw_ambiguous_slash_date and not saw_unambiguous_order:
        note = "Some dates could mean either day/month or month/day. OmniLens interpreted them as day-first (DD/MM), commonly used in India. Please check the preview."
    return parsed, note


def numeric_columns(df: pd.DataFrame) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    non_measure_label = re.compile(
        r"^(?:ward|ward name|ward code|ward no|district|district name|district code|"
        r"village|village name|city|city name|town|area|area name|taluka|tehsil|"
        r"state|state name|region|zone|zone name|pincode|pin code|postal code|"
        r"ward number|district number|month|year|quarter|week|day)$", re.I
    )
    required_values = max(2, min(3, int(math.ceil(len(df) * 0.10))))
    for col in df.columns:
        name = str(col).strip()
        if ID_NAME_RE.search(name) or non_measure_label.fullmatch(name):
            continue
        nums = numeric_view(df[col])
        valid_count = int(nums.notna().sum())
        if valid_count >= required_values and nums.notna().mean() >= 0.75:
            result[name] = nums
    return result


def detect_indian_formats(df: pd.DataFrame) -> dict[str, Any]:
    patterns = {
        "PAN": re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.I),
        "GSTIN": re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", re.I),
        "Aadhaar-style number": re.compile(r"^[2-9][0-9]{11}$"),
        "Phone number": re.compile(r"^[6-9][0-9]{9}$"),
        "PIN code": re.compile(r"^[1-9][0-9]{5}$"),
        "IFSC": re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.I),
        "Email": re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I),
    }
    results = []
    for col in df.columns:
        values = df[col].dropna().astype(str).str.strip()
        if values.empty:
            continue
        name = str(col).lower()
        likely = []
        for label in patterns:
            if label == "PAN" and re.search(r"\bpan\b", name): likely.append(label)
            if label == "GSTIN" and re.search(r"gst|gstin", name): likely.append(label)
            if label == "Aadhaar-style number" and re.search(r"aadhaar|aadhar", name): likely.append(label)
            if label == "Phone number" and re.search(r"phone|mobile|contact", name): likely.append(label)
            if label == "PIN code" and re.search(r"pin.?code|postal.?code|zip", name): likely.append(label)
            if label == "IFSC" and re.search(r"ifsc", name): likely.append(label)
            if label == "Email" and re.search(r"email|e.?mail", name): likely.append(label)
        # For unnamed columns do not guess sensitive formats from values alone.
        for label in likely:
            regex = patterns[label]
            invalid = [(int(i), v) for i, v in values.items() if not regex.fullmatch(re.sub(r"[\s-]", "", v) if label in {"Aadhaar-style number", "Phone number"} else v)]
            if invalid:
                results.append({
                    "field": str(col), "format": label,
                    "invalid_count": len(invalid),
                    "examples": [mask_value(v) for _, v in invalid[:3]],
                    "rows": [int(i) for i, _ in invalid[:MAX_EVIDENCE_ROWS]],
                    "note": "Format check only; it does not verify government records or checksum validity.",
                })
    return {"checks": results, "total_invalid_values": sum(x["invalid_count"] for x in results)}


def mask_value(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return text[:2] + "****" + text[-2:]


def detect_shape(df: pd.DataFrame) -> dict[str, Any]:
    rows, cols = df.shape
    nums = numeric_columns(df)
    date_candidates = []
    text_candidates = []
    identifier_cols = []
    dimensions = []
    place_cols = [str(c) for c in df.columns if re.search(r"district|ward|village|city|town|area|taluka|tehsil|state|region|pincode|pin code", str(c), re.I)]
    for col in df.columns:
        s = df[col]
        name = str(col)
        lower = name.lower()
        if ID_NAME_RE.search(lower):
            identifier_cols.append(name)
        if name in place_cols and name not in dimensions:
            dimensions.append(name)
        if DATE_NAME_RE.search(lower):
            parsed, _ = infer_date_format(s)
            if parsed.notna().mean() >= 0.45:
                date_candidates.append(name)
        # CSV/Excel columns are initially loaded as object dtype. Use the
        # numeric parse ratio as well as pandas dtype before calling a field a category.
        if name not in nums and not pd.api.types.is_numeric_dtype(s):
            if name not in dimensions:
                dimensions.append(name)
            lens = s.dropna().astype(str).str.len()
            if len(lens) and lens.mean() >= 35:
                text_candidates.append(name)
    # Data-driven date detection even when the column name is unfamiliar.
    if not date_candidates:
        for col in df.columns:
            if col in identifier_cols:
                continue
            # Never infer a date from numeric IDs, quantities or counts.
            # Pandas can interpret integers as nanoseconds since an epoch.
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            sample = df[col].dropna()
            if sample.empty:
                continue
            parsed, _ = infer_date_format(sample.astype(str))
            if parsed.notna().mean() >= 0.8 and parsed.nunique() >= min(5, max(2, int(rows * .25))):
                date_candidates.append(str(col))
                break
    # grouped summary: measure names have explicit Count/Sum/Average pairs.
    measure_names = [str(c) for c in df.columns if re.search(r"\(\s*(count|sum|average|avg)\s*\)$", str(c), re.I)]
    if len(measure_names) < 3:
        measure_names = [str(c) for c in df.columns if re.search(r"\b(count|sum|average|avg)\b", str(c), re.I)]
    is_grouped = len(measure_names) >= 3 and bool(dimensions) and rows <= 20000
    # wide table: many columns look like months, years, or repeated periods.
    period_cols = [str(c) for c in df.columns if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\b|^(19|20)\d{2}$", str(c), re.I)]
    is_wide = len(period_cols) >= 4 and len(df.columns) >= 5
    is_text_heavy = bool(text_candidates) and len(nums) <= 2
    survey_signal = sum(bool(re.search(r"rating|satisfaction|agree|feedback|response|question|recommend|score", str(c), re.I)) for c in df.columns)
    is_survey = survey_signal >= 2 or (len(dimensions) >= 4 and any("rating" in str(c).lower() for c in df.columns))
    register_signal = sum(bool(re.search(r"name|phone|mobile|email|address|contact|pan|aadhaar|gstin|ifsc", str(c), re.I)) for c in df.columns)
    date_col = date_candidates[0] if date_candidates else None
    date_unique_ratio = 0
    if date_col:
        parsed, _ = infer_date_format(df[date_col])
        date_unique_ratio = parsed.nunique() / max(1, parsed.notna().sum())
    event_signal = any(re.search(r"transaction|invoice|order|payment|merchant|recipient|description|direction|complaint.?id|case.?id|event", str(c), re.I) for c in df.columns)
    if is_grouped:
        shape, confidence = "grouped_summary", "high"
        reason = "The file has group fields and measures labelled as counts, sums or averages."
    elif is_wide:
        shape, confidence = "wide_table", "moderate"
        reason = "Several columns look like repeated periods or subjects."
    elif is_text_heavy or (len(df.columns) == 1 and len(text_candidates) == 1):
        shape, confidence = "text_heavy", "moderate"
        reason = "One or more fields contain longer written descriptions."
    elif is_survey:
        shape, confidence = "survey", "moderate"
        reason = "The fields look like survey questions, responses or ratings."
    elif date_col and event_signal:
        shape, confidence = "records", "high"
        reason = "The file contains dated transaction, service or event records."
    elif date_col and date_unique_ratio >= .6 and len(nums) >= 1 and len(df) >= 8 and not identifier_cols:
        shape, confidence = "time_series", "moderate"
        reason = "The file has a date field and measurements across many dates."
    elif register_signal >= 2 and len(nums) <= 3:
        shape, confidence = "register", "moderate"
        reason = "The file looks like a list of people, organisations or contacts."
    elif place_cols and (len(nums) >= 1 or len(df.columns) <= 8):
        shape, confidence = "place_based", "moderate"
        reason = "The file includes district, ward or area names that can be compared."
    elif date_col or identifier_cols or len(nums) >= 1:
        shape, confidence = "records", "moderate"
        reason = "Rows look like individual entries or events."
    else:
        shape, confidence = "unknown", "low"
        reason = "The file does not clearly match a familiar table type."
    return {
        "shape": shape, "confidence": confidence, "reason": reason,
        "date_column": date_col, "numeric_columns": list(nums.keys()),
        "dimension_columns": dimensions, "identifier_columns": identifier_cols,
        "place_columns": place_cols, "text_columns": text_candidates,
        "period_columns": period_cols, "measure_columns": measure_names,
    }


def exclude_total_rows(df: pd.DataFrame, shape: dict[str, Any]) -> tuple[pd.DataFrame, list[int]]:
    if shape["shape"] != "grouped_summary":
        return df.copy(), []
    dims = shape["dimension_columns"]
    if not dims:
        return df.copy(), []
    mask = pd.Series(False, index=df.index)
    for col in dims:
        s = df[col].astype(str).str.strip().str.lower()
        mask |= s.isin(TOTAL_TOKENS)
    removed = [int(x) for x in df.index[mask].tolist()]
    return df.loc[~mask].copy(), removed


def weighted_summary_columns(df: pd.DataFrame) -> list[dict[str, Any]]:
    cols = [str(c) for c in df.columns]
    result = []
    for avg_col in cols:
        m = re.match(r"^(.*?)\s*\(\s*(?:average|avg|mean)\s*\)$", avg_col, re.I)
        if not m:
            continue
        base = m.group(1).strip()
        count_col = next((c for c in cols if re.fullmatch(re.escape(base) + r"\s*\(\s*count\s*\)", c, re.I)), None)
        sum_col = next((c for c in cols if re.fullmatch(re.escape(base) + r"\s*\(\s*sum\s*\)", c, re.I)), None)
        if count_col and sum_col:
            total_count = numeric_view(df[count_col]).sum(min_count=1)
            total_sum = numeric_view(df[sum_col]).sum(min_count=1)
            weighted = float(total_sum / total_count) if pd.notna(total_count) and total_count else None
            result.append({"measure": base, "count_field": count_col, "sum_field": sum_col,
                           "average_field": avg_col, "weighted_average": weighted,
                           "total_count": json_safe(total_count), "total_sum": json_safe(total_sum)})
    return result


# ---------------------------------------------------------------------------
# Analysis: simple first, evidence attached to every finding
# ---------------------------------------------------------------------------

INDIAN_LABELS = {
    "en": {"missing": "Some entries are blank", "duplicates": "Some rows appear more than once", "unusual": "A few values are much higher or lower than most", "top": "Largest group", "trend": "The total changed over time", "data": "This file contains", "unknown": "I need one detail to read this correctly."},
    "hi": {"missing": "कुछ जगह जानकारी खाली है", "duplicates": "कुछ पंक्तियाँ एक से अधिक बार दिखाई देती हैं", "unusual": "कुछ मान बाकी से बहुत अधिक या कम हैं", "top": "सबसे बड़ा समूह", "trend": "समय के साथ कुल राशि बदली है", "data": "इस फ़ाइल में", "unknown": "इसे सही तरह समझने के लिए मुझे एक जानकारी चाहिए।"},
    "mr": {"missing": "काही ठिकाणी माहिती रिकामी आहे", "duplicates": "काही ओळी एकापेक्षा जास्त वेळा दिसतात", "unusual": "काही मूल्ये इतरांपेक्षा खूप जास्त किंवा कमी आहेत", "top": "सर्वात मोठा गट", "trend": "कालावधीनुसार एकूण रक्कम बदलली आहे", "data": "या फाइलमध्ये", "unknown": "हे योग्यरीत्या समजण्यासाठी मला एक माहिती हवी आहे."},
}


def new_finding(kind: str, title: str, happened: str, evidence: str, next_step: str,
                rows: list[int], priority: int = 50, category: str = "Finding") -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "kind": kind, "title": title,
            "happened": happened, "evidence": evidence, "next_step": next_step,
            "rows": [int(x) for x in rows[:MAX_EVIDENCE_ROWS]], "priority": priority, "category": category}


def transaction_views(df: pd.DataFrame) -> dict[str, Any] | None:
    """Recognise payment-like rows from their fields, without assuming a sector."""
    direction_col = next(
        (str(c) for c in df.columns if re.search(r"direction|transaction.?type|debit.?credit|flow.?type", str(c), re.I)),
        None,
    )
    if not direction_col:
        return None
    measures = numeric_columns(df)
    amount_col = next(
        (c for pattern in (r"amount|spend|expense|payment|transfer|value", r"debit|credit")
         for c in measures if re.search(pattern, c, re.I) and not RATE_RE.search(c)),
        None,
    )
    if not amount_col:
        return None

    direction = df[direction_col].fillna("").astype(str).str.lower().str.strip()
    out_mask = direction.str.contains(r"\bout\b|paid|sent|debit|money out|withdraw", regex=True)
    in_mask = direction.str.contains(r"\bin\b|received|credit|money in|deposit", regex=True)
    if not bool(out_mask.any() or in_mask.any()):
        return None

    status_col = next((str(c) for c in df.columns if re.search(r"^status$|transaction.?status|payment.?status", str(c), re.I)), None)
    success_mask = pd.Series(True, index=df.index)
    status_filtered = False
    if status_col:
        status = df[status_col].fillna("").astype(str).str.lower().str.strip()
        # Only apply a success filter when the field actually looks like a payment result.
        known_results = status.str.contains(r"completed|successful|succeeded|failed|pending|declined", regex=True)
        if bool(known_results.any()):
            success_mask = status.str.contains(r"completed|successful|succeeded", regex=True)
            status_filtered = True

    amounts = numeric_view(df[amount_col])
    outgoing = df.loc[out_mask & success_mask & amounts.notna()].copy()
    incoming = df.loc[in_mask & success_mask & amounts.notna()].copy()
    failed = df.loc[(out_mask | in_mask) & ~success_mask].copy() if status_filtered else df.iloc[0:0].copy()
    if outgoing.empty and incoming.empty:
        return None
    return {
        "direction_column": direction_col,
        "amount_column": amount_col,
        "status_column": status_col,
        "outgoing": outgoing,
        "incoming": incoming,
        "unconfirmed": failed,
        "status_filtered": status_filtered,
    }


def safe_top_groups(df: pd.DataFrame, shape: dict[str, Any], working: pd.DataFrame) -> tuple[str | None, str | None, pd.Series | None, list[int]]:
    dims = [c for c in shape["dimension_columns"] if c not in shape["identifier_columns"] and c != shape.get("date_column") and working[c].nunique(dropna=True) > 1]
    measures = [c for c in shape["numeric_columns"] if not RATE_RE.search(str(c)) and not ID_NAME_RE.search(str(c))]
    # Prefer business outcomes and additive amounts over quantity/sequence fields.
    measure_patterns = [r"sales|revenue|collection|receipt", r"expense|spend|amount|payment|income", r"profit|gross income|cost", r"complaint|case|count|total", r"quantity|items|volume", r"score|rating|marks|rainfall|temperature|duration"]
    measure = next((c for pattern in measure_patterns for c in measures if re.search(pattern, c, re.I)), None)
    if not measure and measures:
        measure = measures[0]
    dimension_patterns = [r"category|district|ward|area|department|branch|city|zone", r"product line|product category", r"type|status|merchant|recipient", r"product"]
    dimension = next((c for pattern in dimension_patterns for c in dims if re.search(pattern, c, re.I)), None)
    if not dimension and dims:
        dimension = dims[0]
    if not dimension:
        return None, measure, None, []
    if shape["shape"] == "grouped_summary":
        # Use additive sum/count fields for rankings; never rank by average.
        measure = next((c for c in shape["measure_columns"] if re.search(r"\(\s*sum\s*\)$", c, re.I)), measure)
        measure = measure or next((c for c in measures if re.search(r"sum|count|total", c, re.I)), None)
    if measure and measure in working.columns:
        vals = numeric_view(working[measure])
        table = pd.DataFrame({"group": working[dimension].astype(str), "value": vals, "row": working.index})
        grouped = table.groupby("group", dropna=False)["value"].sum(min_count=1).sort_values(ascending=False)
        if grouped.empty:
            return dimension, measure, None, []
        top = grouped.head(8)
        row_ids = table[table["group"] == str(top.index[0])].index.tolist()
        return dimension, measure, top, row_ids
    counts = working[dimension].astype(str).value_counts().head(8)
    row_ids = working[working[dimension].astype(str).isin(counts.index)].index.tolist()
    return dimension, None, counts, row_ids


def build_charts(df: pd.DataFrame, shape: dict[str, Any], working: pd.DataFrame, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []

    # Surveys: show response percentages, not sums of category labels.
    if shape["shape"] == "survey":
        text_like = re.compile(r"text|comment|feedback|description|remark|note|message|review", re.I)
        survey_dims = [
            c for c in shape["dimension_columns"]
            if c not in shape["identifier_columns"]
            and not text_like.search(str(c))
            and 2 <= working[c].nunique(dropna=True) <= 12
        ]
        for column in survey_dims[:2]:
            series = working[column].dropna().astype(str)
            if series.empty:
                continue
            counts = series.value_counts().head(8)
            percentages = counts / max(1, len(series)) * 100
            charts.append({
                "title": f"Responses by {column}",
                "explanation": f"Shows the share of non-empty responses in each {column} group.",
                "labels": [str(x) for x in percentages.index],
                "values": [round(float(x), 1) for x in percentages.values],
                "unit": "% of responses",
            })
        rating_col = next((c for c in shape["numeric_columns"] if re.search(r"rating|score|satisfaction|recommend", str(c), re.I)), None)
        if rating_col and len(charts) < 3:
            ratings = numeric_view(working[rating_col]).dropna()
            if not ratings.empty:
                counts = ratings.value_counts().sort_index().head(10)
                pct = counts / max(1, len(ratings)) * 100
                charts.append({
                    "title": f"Responses by {rating_col}",
                    "explanation": "Shows how responses are spread across the recorded score values.",
                    "labels": [str(x) for x in pct.index],
                    "values": [round(float(x), 1) for x in pct.values],
                    "unit": "% of responses",
                })
        return charts[:3]

    # Grouped summaries: compare actual measures, never the number of rows in a report grid.
    if shape["shape"] == "grouped_summary":
        dimension, measure, grouped, _ = safe_top_groups(df, shape, working)
        if grouped is not None and len(grouped):
            charts.append({
                "title": f"{measure or 'Number of records'} by {dimension}",
                "explanation": f"Compares the {'total of ' + measure if measure else 'number of records'} across listed groups. Overall rows such as All/Total are excluded.",
                "labels": [str(x) for x in grouped.index[:8]],
                "values": [round(float(x), 2) for x in grouped.values[:8]],
                "unit": "" if measure else "records",
            })
        # Show an average by another dimension only when paired Sum and Count
        # fields exist. Calculate group Sum / group Count, never mean-of-means.
        avg_col = next((c for c in df.columns if re.search(r"\(\s*(average|avg|mean)\s*\)$", str(c), re.I)), None)
        other_dims = [c for c in shape["dimension_columns"] if c != dimension and c not in shape["identifier_columns"] and working[c].nunique(dropna=True) > 1]
        avg_dim = None
        if avg_col and other_dims:
            avg_base_match = re.match(r"^(.*?)\s*\(\s*(?:average|avg|mean)\s*\)$", str(avg_col), re.I)
            avg_base = avg_base_match.group(1).strip() if avg_base_match else ""
            count_col = next((c for c in df.columns if avg_base and re.fullmatch(re.escape(avg_base) + r"\s*\(\s*count\s*\)", str(c), re.I)), None)
            sum_col = next((c for c in df.columns if avg_base and re.fullmatch(re.escape(avg_base) + r"\s*\(\s*sum\s*\)", str(c), re.I)), None)
            if count_col and sum_col:
                avg_dim = next((c for c in other_dims if re.search(r"range|band|slab|bracket|year|period", str(c), re.I)), other_dims[0])
                temp = pd.DataFrame({
                    "group": working[avg_dim].astype(str),
                    "sum": numeric_view(working[sum_col]),
                    "count": numeric_view(working[count_col]),
                })
                grouped_values = temp.groupby("group").agg(total_sum=("sum", "sum"), total_count=("count", "sum"))
                grouped_values = grouped_values[grouped_values["total_count"] > 0]
                grouped_avg = (grouped_values["total_sum"] / grouped_values["total_count"]).dropna().sort_values(ascending=False).head(8)
                if len(grouped_avg):
                    charts.append({
                        "title": f"{avg_col} across {avg_dim}",
                        "explanation": f"Count-weighted average for each group: combined {sum_col} divided by combined {count_col}. This avoids giving small groups the same weight as large groups.",
                        "labels": grouped_avg.index.astype(str).tolist(),
                        "values": [round(float(x), 2) for x in grouped_avg.values],
                        "unit": "",
                    })
        # If a second additive measure is available, compare it by the second dimension.
        if len(charts) < 3 and other_dims:
            sum_cols = [c for c in shape["measure_columns"] if re.search(r"\(\s*sum\s*\)$", str(c), re.I) and c != measure]
            if not sum_cols:
                sum_cols = [c for c in shape["measure_columns"] if re.search(r"\(\s*count\s*\)$", str(c), re.I) and c != measure]
            if sum_cols:
                second_measure = sum_cols[0]
                second_dim = next((c for c in other_dims if c != (avg_dim if avg_col and other_dims else None)), other_dims[0])
                tmp = pd.DataFrame({"group": working[second_dim].astype(str), "value": numeric_view(working[second_measure])})
                second = tmp.groupby("group")["value"].sum(min_count=1).dropna().sort_values(ascending=False).head(8)
                if len(second):
                    charts.append({
                        "title": f"{second_measure} by {second_dim}",
                        "explanation": "Compares the actual reported totals across groups; it does not count rows in the report layout.",
                        "labels": second.index.astype(str).tolist(),
                        "values": [round(float(x), 2) for x in second.values],
                        "unit": "",
                    })
        return charts[:3]

    # Wide tables: convert period columns into a chart series in memory only.
    if shape["shape"] == "wide_table" and shape["period_columns"]:
        wide_rows = []
        for period_col in shape["period_columns"]:
            values = numeric_view(working[period_col])
            total = values.sum(min_count=1)
            if pd.notna(total):
                wide_rows.append((period_col, float(total)))
        if wide_rows:
            charts.append({
                "title": "Values across the periods",
                "explanation": "Compares the totals in the period columns. Your uploaded table is not changed.",
                "labels": [x[0] for x in wide_rows[:12]],
                "values": [round(x[1], 2) for x in wide_rows[:12]],
                "unit": "",
            })

    # Payment-like record files are charted on completed outgoing amounts first.
    # This avoids mixing money received, failed attempts and spending in one chart.
    ranking_working = working
    tx = transaction_views(df)
    if tx:
        outgoing_indices = tx["outgoing"].index.intersection(working.index)
        if len(outgoing_indices):
            ranking_working = working.loc[outgoing_indices]

    # Most useful ranking for record, place-based and list-shaped tables.
    dimension, measure, grouped, _ = safe_top_groups(df, shape, ranking_working)
    if grouped is not None and len(grouped) and dimension and shape["shape"] not in {"wide_table", "text_heavy"}:
        chart_title = f"{measure or 'Number of records'} by {dimension}"
        chart_explanation = f"Compares the {'total of ' + measure if measure else 'number of records'} across the main groups."
        if tx and measure == tx["amount_column"]:
            chart_title = f"Money out by {dimension}"
            chart_explanation = f"Adds completed outgoing {measure} values within each group. Failed or pending payment attempts are left out."
        charts.append({
            "title": chart_title,
            "explanation": chart_explanation,
            "labels": [str(x) for x in grouped.index[:8]],
            "values": [round(float(x), 2) for x in grouped.values[:8]],
            "unit": "" if measure else "records",
        })

    # Time trend: use the first meaningful numeric measure for time-series files,
    # even when its name is not one of the usual sales/expense words (e.g. rainfall_mm).
    date_col = shape["date_column"]
    measures = shape["numeric_columns"]
    preferred_patterns = [r"sales|revenue|collection|receipt", r"amount|expense|spend|income|cost|profit", r"quantity|count|total|rainfall|temperature|marks|score|rating"]
    trend_measure = next((c for pattern in preferred_patterns for c in measures if re.search(pattern, c, re.I) and not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
    if trend_measure is None and shape["shape"] == "time_series":
        trend_measure = next((c for c in measures if not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
    trend_working = ranking_working if tx and len(ranking_working) else working
    if date_col and trend_measure and shape["shape"] != "grouped_summary":
        dates, _ = infer_date_format(trend_working[date_col])
        temp = pd.DataFrame({"period": dates.dt.to_period("M").astype(str), "value": numeric_view(trend_working[trend_measure])})
        temp = temp[~temp["period"].isin(["NaT", "nan"])]
        monthly = temp.groupby("period")["value"].sum(min_count=1).dropna().sort_index()
        if len(monthly) >= 2:
            charts.append({
                "title": f"{'Money out' if tx and trend_measure == tx['amount_column'] else trend_measure} over time",
                "explanation": "Shows how the recorded total changed from month to month." + (" Only recognised completed outgoing payments are included." if tx and trend_measure == tx["amount_column"] else ""),
                "labels": monthly.index.tolist()[-12:],
                "values": [round(float(x), 2) for x in monthly.values[-12:]],
                "unit": "",
            })

    # Payment ledgers benefit from a direct completed-money-in vs money-out
    # comparison. This is more useful than a chart that merely counts directions.
    if tx and len(charts) < 3 and len(tx["incoming"]) and len(tx["outgoing"]):
        amount_col = tx["amount_column"]
        money_in = float(numeric_view(tx["incoming"][amount_col]).sum())
        money_out = float(numeric_view(tx["outgoing"][amount_col]).sum())
        charts.append({
            "title": "Completed money in vs money out",
            "explanation": "Compares completed incoming and outgoing amounts. Failed or pending attempts are not included; money received is not automatically income.",
            "labels": ["Money out", "Money in"],
            "values": [round(money_out, 2), round(money_in, 2)],
            "unit": "INR",
        })

    # A second category view is useful for record-level files, but is deliberately
    # skipped for grouped summaries because row counts there reflect report layout.
    if shape["shape"] != "wide_table":
        skip = {dimension, date_col}
        second_dim = next((c for c in shape["dimension_columns"] if c not in skip and c not in shape["identifier_columns"] and 2 <= working[c].nunique(dropna=True) <= 12), None)
        if second_dim and len(charts) < 3:
            secondary_measure = next(
                (c for pattern in (r"quantity|items sold|units", r"profit|gross income|cost")
                 for c in measures if c not in {measure, trend_measure} and re.search(pattern, c, re.I) and not RATE_RE.search(c) and not ID_NAME_RE.search(c)),
                None,
            )
            if tx and secondary_measure:
                source_for_second = ranking_working
            else:
                source_for_second = working
            if secondary_measure and len(source_for_second):
                values = numeric_view(source_for_second[secondary_measure])
                grouped_second = values.groupby(source_for_second[second_dim].fillna("(blank)").astype(str)).sum(min_count=1).dropna().sort_values(ascending=False).head(8)
                charts.append({
                    "title": f"{secondary_measure} by {second_dim}",
                    "explanation": f"Adds the recorded {secondary_measure} within each {second_dim} group.",
                    "labels": grouped_second.index.tolist(),
                    "values": [round(float(x), 2) for x in grouped_second.values],
                    "unit": "",
                })
            else:
                counts = source_for_second[second_dim].fillna("(blank)").astype(str).value_counts().head(8)
                charts.append({
                    "title": f"Records by {second_dim}",
                    "explanation": "Shows how the uploaded records are spread across these groups.",
                    "labels": counts.index.tolist(),
                    "values": [int(x) for x in counts.values],
                    "unit": "records",
                })

    # Numeric spread is a last resort for files with too few meaningful groups.
    if len(charts) < 3 and shape["shape"] not in {"grouped_summary", "survey", "wide_table"}:
        skip_numeric = {measure, trend_measure}
        num = next((c for c in measures if c not in skip_numeric and not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
        if num:
            vals = numeric_view(working[num]).dropna()
            if len(vals) >= 3 and vals.nunique() >= 3:
                bins = pd.cut(vals, bins=min(6, max(3, vals.nunique())), duplicates="drop")
                counts = bins.value_counts().sort_index()
                charts.append({
                    "title": f"Spread of {num}",
                    "explanation": "Shows where most recorded values sit.",
                    "labels": [str(x) for x in counts.index],
                    "values": [int(x) for x in counts.values],
                    "unit": "records",
                })
    if shape["shape"] == "wide_table":
        charts.sort(key=lambda c: 0 if c["title"] == "Values across the periods" else 1)
    return charts[:3]


def build_analysis(df: pd.DataFrame, filename: str, meta: dict[str, Any], language: str = "en", confirmed_shape: str | None = None) -> dict[str, Any]:
    shape = detect_shape(df)
    if confirmed_shape in {"records", "grouped_summary", "time_series", "wide_table", "survey", "register", "text_heavy", "place_based"}:
        shape["shape"] = confirmed_shape
        shape["confidence"] = "confirmed by user"
        shape["reason"] = "You confirmed what one row represents; OmniLens uses that choice for this analysis."
    working, excluded_total_rows = exclude_total_rows(df, shape)
    findings: list[dict[str, Any]] = []
    action_candidates: list[tuple[int, str, str, str, list[int]]] = []
    # Missing cells.
    missing_by_col = df.isna().sum()
    missing_cols = missing_by_col[missing_by_col > 0]
    if int(missing_cols.sum()) > 0:
        rows = df.index[df.isna().any(axis=1)].tolist()
        field_names = ", ".join(f"{c} ({int(n)})" for c, n in missing_cols.sort_values(ascending=False).head(4).items())
        findings.append(new_finding("data", "Some entries are blank",
            f"{int(missing_cols.sum()):,} empty cells were found in {len(missing_cols)} field(s).",
            field_names, "Open these rows and decide whether the information is unknown, not needed, or should be added.", rows, 90, "Data to check"))
        action_candidates.append((90, f"Review {int(missing_cols.sum())} blank cells", f"Fields: {field_names}.", "See the rows, then fill only from a reliable source.", rows))
    # Exact duplicates.
    duplicate_mask = df.duplicated(keep=False)
    duplicate_rows = df.index[duplicate_mask].tolist()
    if df.duplicated().sum() > 0:
        findings.append(new_finding("data", "Some rows appear more than once",
            f"{int(df.duplicated().sum()):,} exact repeat row(s) were found.",
            "Every field in the repeated rows matches.", "Check whether these are accidental repeats before removing them.", duplicate_rows, 85, "Data to check"))
        action_candidates.append((85, f"Review {int(df.duplicated().sum())} repeated rows", "They match across every column.", "Preview the repeats before approving removal.", duplicate_rows))
    # Indian formats.
    india = detect_indian_formats(df)
    for check in india["checks"][:3]:
        findings.append(new_finding("data", f"Check {check['format']} in {check['field']}",
            f"{check['invalid_count']} value(s) do not match the expected {check['format']} pattern.",
            "Masked examples: " + ", ".join(check["examples"]),
            "Check the source before changing these values. The check only tests the format, not official validity.", check["rows"], 78, "Format check"))
        action_candidates.append((78, f"Review {check['invalid_count']} {check['format']} value(s)", f"Field: {check['field']}.", "Compare with the original source; do not guess missing digits.", check["rows"]))
    # Grouped summary special playbook.
    if shape["shape"] == "grouped_summary":
        weighted = weighted_summary_columns(working)
        dim = next((c for c in shape["dimension_columns"] if c not in shape["identifier_columns"] and working[c].nunique(dropna=True) > 1), None)
        measure = next((c for c in shape["measure_columns"] if re.search(r"\(\s*sum\s*\)$", c, re.I)), None)
        if dim and measure:
            vals = numeric_view(working[measure])
            valid = vals.notna()
            if valid.any():
                idx = vals[valid].idxmax()
                top_value = float(vals.loc[idx])
                top_group = str(working.loc[idx, dim])
                # Exclude roll-up group values from the rank and evidence.
                group_rows = [int(idx)]
                findings.append(new_finding("group", f"Largest {dim}",
                    f"{top_group} has the largest {measure} among the listed groups.",
                    f"{measure}: {top_value:,.2f}.", "This ranks the groups in this report; it is not necessarily a ranking of individual people or cases.", group_rows, 70, "Group comparison"))
                action_candidates.append((70, f"Review the reported total for {top_group}",
                    f"{top_group} leads the comparison for {measure}.",
                    "Check the reporting period, group definitions and source totals before making a decision.", group_rows))
        if weighted:
            first = weighted[0]
            if first["weighted_average"] is not None:
                findings.append(new_finding("group", f"Weighted average for {first['measure']}",
                    f"The combined average is {first['weighted_average']:,.2f} when calculated as total sum divided by total count.",
                    f"{first['sum_field']} total ÷ {first['count_field']} total. Total count: {first['total_count']}; total sum: {first['total_sum']}.",
                    "This combined average accounts for how many items are in each group. Simply averaging the displayed group averages can give a misleading result.", working.index.astype(int).tolist(), 68, "Correct calculation"))
                action_candidates.append((68, f"Use the combined average for {first['measure']}",
                    f"The count-weighted average is {first['weighted_average']:,.2f}.",
                    "Use this figure when reporting an overall average; do not take a simple average of the group averages.", working.index.astype(int).tolist()))
        if dim and measure:
            group_totals = numeric_view(working[measure]).groupby(working[dim].astype(str)).sum(min_count=1).dropna().sort_values(ascending=False)
            grand = float(group_totals.sum()) if len(group_totals) else 0.0
            if len(group_totals) >= 2 and grand > 0:
                leader = str(group_totals.index[0]); share = float(group_totals.iloc[0]) / grand * 100
                share_rows = working.index[working[dim].astype(str) == leader].tolist()
                findings.append(new_finding("group", f"Share of {leader}",
                    f"{leader} represents {share:.1f}% of the listed {measure} total across the displayed groups.",
                    f"{float(group_totals.iloc[0]):,.2f} out of {grand:,.2f}.",
                    "This is a share of the report's measure, not necessarily a share of all people or cases.",
                    share_rows, 62, "Share of total"))
                action_candidates.append((62, f"Check the {leader} share", f"It represents {share:.1f}% of the listed total.",
                    "Compare the underlying group rows and check whether the concentration is expected.", share_rows))
        order_col = next((c for c in df.columns if re.search(r"range.?order|sort.?order|sequence|rank", str(c), re.I) and c in shape["numeric_columns"]), None)
        range_dim = next((c for c in shape["dimension_columns"] if re.search(r"income band|income range|age band|range|slab|bracket", str(c), re.I) and working[c].nunique(dropna=True) > 2), None)
        if order_col and range_dim and measure:
            ordered_source = pd.DataFrame({
                "group": working[range_dim].astype(str),
                "order": numeric_view(working[order_col]),
                "measure": numeric_view(working[measure]),
            })
            # Reports often contain many rows per band (district, taxpayer
            # type, year). Combine each band before comparing adjacent bands.
            ordered = ordered_source.groupby("group").agg(
                __order=("order", "min"),
                __measure=("measure", lambda values: values.sum(min_count=1)),
            ).dropna(subset=["__order", "__measure"]).sort_values("__order")
            if len(ordered) >= 3:
                diffs = ordered["__measure"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
                if len(diffs):
                    pos = int((diffs > 0).sum()); neg = int((diffs < 0).sum())
                    compared_groups = ordered.index.astype(str).tolist()
                    neighbour_rows = working.index[working[range_dim].astype(str).isin(compared_groups)].tolist()
                    findings.append(new_finding("group", f"Changes between neighbouring groups in {range_dim}",
                        f"After combining rows within each band, the {measure} total rose across {pos} adjacent change(s) and fell across {neg}.",
                        "Each band is compared using its combined total. Bands are ordered using " + order_col + "; this is not a time trend.",
                        "Look at the adjacent bands with the largest difference and confirm their definitions and group sizes in the source report.",
                        neighbour_rows, 58, "Neighbouring groups"))
                    action_candidates.append((58, f"Review differences between {range_dim} groups",
                        f"The combined {measure} total changes across ordered bands.",
                        "Check adjacent ranges and the number of records in each before interpreting the difference.", neighbour_rows))
        if excluded_total_rows:
            findings.append(new_finding("note", "Report totals were kept out of group rankings",
                f"{len(excluded_total_rows)} row(s) labelled All or Total were excluded from group comparisons.",
                "This prevents the overall total from being counted again alongside its component groups.",
                "Use the total row as a check, not as another group in the ranking.", excluded_total_rows, 65, "Calculation note"))
    # Survey playbook: describe response shares and average ratings by group.
    if shape["shape"] == "survey":
        text_like = re.compile(r"text|comment|feedback|description|remark|note|message|review", re.I)
        rating_col = next((c for c in shape["numeric_columns"] if re.search(r"rating|score|satisfaction", str(c), re.I)), None)
        group_col = next((c for c in shape["dimension_columns"] if c not in shape["identifier_columns"] and not text_like.search(str(c)) and 2 <= working[c].nunique(dropna=True) <= 12), None)
        if rating_col and group_col:
            temp = pd.DataFrame({"group": working[group_col].astype(str), "rating": numeric_view(working[rating_col]), "row": working.index})
            summary = temp.groupby("group")["rating"].agg(["mean", "count"]).dropna().sort_values("mean", ascending=False)
            if len(summary):
                leader = str(summary.index[0])
                mean_rating = float(summary.iloc[0]["mean"])
                response_count = int(summary.iloc[0]["count"])
                rows = temp.loc[temp["group"] == leader, "row"].astype(int).tolist()
                findings.append(new_finding("survey", f"Highest average {rating_col}: {leader}",
                    f"The {leader} group has the highest average recorded {rating_col}.",
                    f"Average: {mean_rating:.2f}; responses with a score: {response_count:,}.",
                    "This is a comparison within the responses supplied. It does not explain why people rated the service this way.",
                    rows, 72, "Survey responses"))
                action_candidates.append((72, f"Review feedback from {leader}", f"This group has the highest average {rating_col}.", "Read the comments and compare the number of responses before deciding what to change.", rows))
        elif rating_col:
            values = numeric_view(working[rating_col]).dropna()
            if len(values):
                add_text = f"The average recorded {rating_col} is {values.mean():.2f} across {len(values):,} responses."
                findings.append(new_finding("survey", f"Average {rating_col}", add_text,
                    f"Valid scores: {len(values):,}; minimum: {values.min():.2f}; maximum: {values.max():.2f}.",
                    "This describes the responses in the file; it may not represent people who did not respond.",
                    values.index.tolist(), 65, "Survey responses"))
    elif shape["shape"] in {"records", "place_based", "time_series", "wide_table"}:
        tx = transaction_views(df)
        analysis_working = working
        if tx:
            outgoing_indices = tx["outgoing"].index.intersection(working.index)
            if len(outgoing_indices):
                analysis_working = working.loc[outgoing_indices]
            amount_col = tx["amount_column"]
            out_total = float(numeric_view(tx["outgoing"][amount_col]).sum()) if len(tx["outgoing"]) else 0.0
            in_total = float(numeric_view(tx["incoming"][amount_col]).sum()) if len(tx["incoming"]) else 0.0
            outgoing_rows = tx["outgoing"].index.astype(int).tolist()
            incoming_rows = tx["incoming"].index.astype(int).tolist()
            findings.append(new_finding("transaction", "Money going out and coming in",
                f"Recognised completed outgoing payments total {out_total:,.2f}; incoming payments total {in_total:,.2f}.",
                f"Outgoing records: {len(outgoing_rows):,}; incoming records: {len(incoming_rows):,}; amount field: {amount_col}.",
                "Incoming payments are not automatically income. Outgoing payments may include transfers or wallet top-ups.",
                outgoing_rows + incoming_rows, 82, "Payment summary"))
            action_candidates.append((82, "Review the largest outgoing payments", f"{out_total:,.2f} across {len(outgoing_rows):,} completed outgoing records.", "Check merchant names and separate purchases from transfers before treating the total as spending.", outgoing_rows))
            if tx["status_filtered"] and len(tx["unconfirmed"]):
                unresolved_rows = tx["unconfirmed"].index.astype(int).tolist()
                findings.append(new_finding("transaction", "Some payment attempts were not completed",
                    f"{len(unresolved_rows):,} payment attempt(s) are marked failed or pending and were excluded from completed totals.",
                    f"Status field: {tx['status_column']}.",
                    "Including unsuccessful attempts in money totals could overstate actual payments.",
                    unresolved_rows, 79, "Payment status"))
                action_candidates.append((79, f"Review {len(unresolved_rows)} unsuccessful or pending attempts", "They were excluded from completed payment totals.", "Check the original payment app or bank statement for the final status.", unresolved_rows))
        dimension, measure, grouped, group_rows = safe_top_groups(df, shape, analysis_working)
        if grouped is not None and len(grouped):
            name = str(grouped.index[0]); value = float(grouped.iloc[0])
            findings.append(new_finding("group", f"Largest group: {name}",
                f"{name} has the highest recorded {'total for ' + measure if measure else 'number of rows'}.",
                f"{value:,.2f} {('for ' + measure) if measure else 'records'}.",
                "A high total shows where the records are concentrated; it does not explain why this happened.",
                group_rows, 72, "Group comparison"))
            action_candidates.append((72, f"Look at {name}", f"It leads the {dimension} comparison.", "Compare its trend and the records behind the total.", group_rows))
    # Time trend finding.
    date_col = shape["date_column"]
    trend_patterns = [r"sales|revenue|collection|receipt", r"amount|expense|spend|payment|income", r"profit|gross income|cost", r"quantity|count|total|rainfall|temperature|marks|score|rating"]
    measure = next((c for pattern in trend_patterns for c in shape["numeric_columns"] if re.search(pattern, c, re.I) and not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
    tx_for_trend = transaction_views(df)
    trend_source = tx_for_trend["outgoing"] if tx_for_trend and len(tx_for_trend["outgoing"]) else df
    if date_col and measure and shape["shape"] != "grouped_summary":
        dates, date_note = infer_date_format(trend_source[date_col])
        temp = pd.DataFrame({"date": dates, "value": numeric_view(trend_source[measure]), "row": trend_source.index})
        temp = temp.dropna(subset=["date", "value"])
        monthly = temp.groupby(temp["date"].dt.to_period("M"))["value"].sum(min_count=1).dropna().sort_index()
        if len(monthly) >= 2:
            change = float(monthly.iloc[-1] - monthly.iloc[-2])
            pct = (change / abs(float(monthly.iloc[-2])) * 100) if float(monthly.iloc[-2]) else None
            label = "increased" if change > 0 else "decreased" if change < 0 else "stayed about the same"
            evidence = f"Last two periods: {monthly.index[-2]} = {monthly.iloc[-2]:,.2f}; {monthly.index[-1]} = {monthly.iloc[-1]:,.2f}."
            if pct is not None:
                evidence += f" Change: {pct:+.1f}%."
            trend_rows = temp[temp["date"].dt.to_period("M").isin(monthly.index[-2:])]["row"].astype(int).tolist()
            findings.append(new_finding("trend", f"{measure} {label} in the latest period",
                f"The recorded {measure} {label} compared with the previous period.", evidence,
                "This is a comparison in the uploaded file, not proof of the reason for the change.", trend_rows, 74, "Change over time"))
            action_candidates.append((74, f"Review the latest change in {measure}", evidence, "Check whether the source periods are complete and what changed in the records.", trend_rows))
    # Unusual values only for individual records; no Isolation Forest wording.
    if shape["shape"] in {"records", "place_based", "survey"}:
        for col in shape["numeric_columns"]:
            if RATE_RE.search(col) or ID_NAME_RE.search(col):
                continue
            values = numeric_view(df[col]).dropna()
            if len(values) < 12 or values.nunique() < 5:
                continue
            q1, q3 = values.quantile(.25), values.quantile(.75)
            spread = q3 - q1
            if spread <= 0:
                continue
            low, high = q1 - 1.5 * spread, q3 + 1.5 * spread
            idxs = values.index[(values < low) | (values > high)].tolist()
            if idxs:
                findings.append(new_finding("review", f"Some {col} values are far from most others",
                    f"{len(idxs)} value(s) fall well outside the middle range for this field.",
                    f"Most values fall roughly between {low:,.2f} and {high:,.2f}; highest flagged: {values.loc[idxs].max():,.2f}.",
                    "These records may be genuine. Check the source and context before changing anything.", idxs, 55, "Worth checking"))
                action_candidates.append((55, f"Review {len(idxs)} unusual {col} value(s)", "They sit far from the middle of the other values.", "Open the rows and compare the date, group and source details.", idxs))
                break
    # Text-heavy simple themes.
    if shape["shape"] == "text_heavy" and shape["text_columns"]:
        col = shape["text_columns"][0]
        words = Counter()
        stop = {"this", "that", "with", "from", "have", "were", "will", "your", "they", "there", "their", "then", "when", "what", "where", "which", "the", "and", "for", "are", "was", "has", "had", "but", "not", "you", "our", "this", "into", "out", "about", "have", "been", "because"}
        for value in df[col].dropna().astype(str):
            words.update(w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", value.lower()) if w not in stop)
        common = words.most_common(5)
        if common:
            common_tokens = {w for w, _ in common}
            text_rows = df.index[df[col].fillna("").astype(str).map(lambda x: bool(common_tokens.intersection(re.findall(r"[A-Za-z][A-Za-z'-]{2,}", x.lower()))))].tolist()
            findings.append(new_finding("text", "Common words in the written responses",
                "These words appear most often in the text. They are clues for review, not confirmed themes.",
                ", ".join(f"{w} ({n})" for w, n in common),
                "Frequent words can help you find topics, but their surrounding sentences matter.",
                text_rows, 48, "Text overview"))
    # Keep at most five, ordered by importance. Avoid repeated duplicate-like info.
    findings = sorted(findings, key=lambda f: f["priority"], reverse=True)[:5]
    # Ordered next-step checklist from finding actions.
    actions = []
    for priority, title, detail, action, rows in sorted(action_candidates, key=lambda x: x[0], reverse=True):
        if any(x["title"] == title for x in actions):
            continue
        actions.append({"title": title, "detail": detail, "action": action, "finding_rows": rows[:MAX_EVIDENCE_ROWS], "done": False})
        if len(actions) >= 5:
            break
    if not actions:
        actions = [{"title": "Check whether this file covers the period you need", "detail": "The first checks did not identify a clear issue.", "action": "Confirm the dates and included records with the source.", "finding_rows": [], "done": False}]
    # Headline answer: data story first; do not lead with quality.
    headline = make_headline(df, shape, working)
    caveat = make_limit_note(df, shape)
    charts = build_charts(df, shape, working, findings)
    # If fewer than 3 meaningful charts exist, do not invent charts.
    return {
        "headline": headline,
        "shape": shape,
        "charts": charts,
        "findings": findings,
        "actions": actions,
        "indian_checks": india,
        "caveat": caveat,
        "excluded_total_rows": excluded_total_rows,
        "weighted_summaries": weighted_summary_columns(working) if shape["shape"] == "grouped_summary" else [],
        "date_notes": infer_date_format(df[date_col])[1] if date_col else None,
        "row_count": len(df), "column_count": len(df.columns),
        "preview": masked_records(df.head(8)),
        "technical": {"shape": shape["shape"], "shape_reason": shape["reason"], "numeric_fields": shape["numeric_columns"], "group_fields": shape["dimension_columns"], "excluded_total_rows": len(excluded_total_rows)},
    }


def make_headline(df: pd.DataFrame, shape: dict[str, Any], working: pd.DataFrame) -> str:
    rows, cols = df.shape
    tx = transaction_views(df)
    if tx:
        amount_col = tx["amount_column"]
        out_values = numeric_view(tx["outgoing"][amount_col]).dropna()
        in_values = numeric_view(tx["incoming"][amount_col]).dropna()
        outgoing_total = float(out_values.sum()) if len(out_values) else 0.0
        incoming_total = float(in_values.sum()) if len(in_values) else 0.0
        status_note = " Failed or pending attempts are kept out of these totals." if tx["status_filtered"] else ""
        caveat = " Money received is not necessarily income, and money sent can include transfers."
        return (f"This file contains {len(tx['outgoing']) + len(tx['incoming']):,} recognised completed payment record(s): "
                f"{outgoing_total:,.2f} went out and {incoming_total:,.2f} came in, using {amount_col}."
                f"{status_note}{caveat}")
    if shape["shape"] == "wide_table":
        labels = shape["period_columns"]
        return f"This table compares {rows:,} row(s) across {len(labels)} period or subject columns ({', '.join(labels[:5])}). The first chart shows the totals across those columns; no original columns have been changed."
    if shape["shape"] == "grouped_summary":
        weighted = weighted_summary_columns(working)
        dim, measure, grouped, _ = safe_top_groups(df, shape, working)
        other_dims = [c for c in shape["dimension_columns"] if c != dim and working[c].nunique(dropna=True) > 1]
        if grouped is not None and len(grouped):
            across = f" across {working[other_dims[0]].nunique(dropna=True)} {other_dims[0]} groups" if other_dims else ""
            return (f"This report compares {len(grouped)} {dim} groups{across}. "
                    f"The largest listed group is {grouped.index[0]} for {measure or 'the selected measure'}. "
                    + (f"A weighted average is available for {weighted[0]['measure']}." if weighted else "Overall total rows are kept separate from the group comparison."))
        return f"This looks like a grouped report. Its rows describe groups, not necessarily individual people or transactions. The group totals are analysed separately from any overall total row."
    if shape["shape"] == "survey":
        rating_col = next((c for c in shape["numeric_columns"] if re.search(r"rating|score|satisfaction", str(c), re.I)), None)
        if rating_col:
            values = numeric_view(df[rating_col]).dropna()
            if len(values):
                return (f"This survey contains {rows:,} responses. The average recorded {rating_col} is {values.mean():.2f} "
                        f"across {len(values):,} scored responses. The response charts show how answers are distributed across groups.")
        return f"This survey contains {rows:,} responses. The charts show how people answered the available questions; blank answers are kept separate."
    if shape["shape"] == "time_series":
        date_col = shape.get("date_column")
        measure = next((c for c in shape["numeric_columns"] if not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
        if date_col and measure:
            dates, _ = infer_date_format(df[date_col])
            values = pd.DataFrame({"date": dates, "value": numeric_view(df[measure])}).dropna()
            if len(values):
                monthly = values.groupby(values["date"].dt.to_period("M"))["value"].sum().sort_index()
                if len(monthly) >= 2:
                    return (f"This file contains {len(values):,} dated measurements of {measure}. "
                            f"The highest recorded period is {monthly.idxmax()} ({monthly.max():,.2f}); "
                            f"the latest recorded period is {monthly.index[-1]} ({monthly.iloc[-1]:,.2f}).")
        return f"This file contains {rows:,} dated measurements across {cols} fields. The chart shows how the recorded values move over time."
    if shape["shape"] == "text_heavy":
        return f"This file contains {rows:,} written entries. OmniLens has counted repeated words and can show the original lines behind a finding; it cannot decide the meaning of a comment without reading it in context."
    if shape["shape"] == "register":
        return f"This list contains {rows:,} entries and {cols} fields. It is most useful for checking repeated records, blank details and the format of contact or identity fields."
    dim, measure, grouped, _ = safe_top_groups(df, shape, working)
    if grouped is not None and len(grouped):
        first = grouped.index[0]
        val = float(grouped.iloc[0])
        if measure:
            first_sentence = f"Across {rows:,} records, {first} had the highest recorded {measure}, at {val:,.2f}."
        else:
            first_sentence = f"Across {rows:,} records, {first} appeared most often in {dim}, with {int(val):,} records."
        date_col = shape.get("date_column")
        trend_measure = next((c for pattern in (r"sales|revenue|collection|receipt", r"amount|expense|spend|payment|income", r"profit|gross income|cost", r"quantity|count|total|rainfall|temperature|marks|score|rating") for c in shape["numeric_columns"] if re.search(pattern, c, re.I) and not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
        if date_col and trend_measure:
            dates, _ = infer_date_format(working[date_col])
            temp = pd.DataFrame({"date": dates, "value": numeric_view(working[trend_measure])}).dropna()
            monthly = temp.groupby(temp["date"].dt.to_period("M"))["value"].sum(min_count=1).dropna().sort_index()
            if len(monthly) >= 2:
                previous, latest = float(monthly.iloc[-2]), float(monthly.iloc[-1])
                delta = latest - previous
                change = "increased" if delta > 0 else "decreased" if delta < 0 else "stayed about the same"
                pct = f" ({delta / abs(previous) * 100:+.1f}%)" if previous else ""
                return first_sentence + f" Recorded {trend_measure} {change} from {monthly.index[-2]} to {monthly.index[-1]}{pct}."
        return first_sentence + f" The charts show the comparison across {dim} and the fields that support it."
    return (f"This file contains {rows:,} rows and {cols} fields. "
            "I could not safely choose one headline measure, so the charts and checks below show what can be compared without guessing.")


def make_limit_note(df: pd.DataFrame, shape: dict[str, Any]) -> str:
    if shape["shape"] == "grouped_summary":
        return "This file contains group totals and summary measures, not individual-level records. Do not add averages or percentages. Rows labelled All or Total are excluded from group rankings."
    if shape["shape"] == "text_heavy":
        return "Word counts do not show whether a comment is positive or negative. Read the original lines before drawing a conclusion."
    if shape["shape"] == "register":
        return "A format check cannot confirm whether an ID, phone number or address belongs to a real person. Review sensitive values securely."
    return "This summary covers only the rows in this file. It cannot tell us what is missing from the source or prove why a pattern happened. Check the original source before taking action."


def masked_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    pii_cols = detect_pii_columns(df)
    result = []
    for idx, row in df.iterrows():
        record = {"_row": int(idx) + 1}
        for col, value in row.items():
            if col in pii_cols and not is_blank(value):
                record[str(col)] = mask_value(value)
            else:
                record[str(col)] = json_safe(value)
        result.append(record)
    return result


def detect_pii_columns(df: pd.DataFrame) -> set[str]:
    # Mask fields identified by their label, plus columns where a strong
    # majority of sampled values match a common identifier shape. This is a
    # best-effort screen, not complete detection or anonymisation.
    name_patterns = {
        "PAN": re.compile(r"pan", re.I), "GSTIN": re.compile(r"gstin|gst", re.I),
        "Aadhaar": re.compile(r"aadhaar|aadhar", re.I), "Phone": re.compile(r"phone|mobile|contact", re.I),
        "Email": re.compile(r"email", re.I), "IFSC": re.compile(r"ifsc", re.I),
    }
    value_patterns = [
        re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.I),
        re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", re.I),
        re.compile(r"^[2-9][0-9]{11}$"),
        re.compile(r"^[6-9][0-9]{9}$"),
        re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.I),
        re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I),
    ]
    found = set()
    for c in df.columns:
        if any(p.search(str(c)) for p in name_patterns.values()):
            found.add(str(c)); continue
        sample = df[c].dropna().astype(str).str.strip().head(100)
        if len(sample) >= 4:
            matches = sum(any(p.fullmatch(v) for p in value_patterns) for v in sample)
            if matches / len(sample) >= .25:
                found.add(str(c))
    return found


# ---------------------------------------------------------------------------
# Session cache (RAM only)
# ---------------------------------------------------------------------------

def cleanup_sessions() -> None:
    now = time.time()
    expired = [sid for sid, item in SESSIONS.items() if now - item["created"] > SESSION_TTL_SECONDS]
    for sid in expired:
        SESSIONS.pop(sid, None)
    while len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(SESSIONS, key=lambda k: SESSIONS[k]["created"])
        SESSIONS.pop(oldest, None)


async def _session_cleanup_loop() -> None:
    while True:
        now = time.time()
        expired = [sid for sid, item in SESSIONS.items() if now - item["created"] > SESSION_TTL_SECONDS]
        for sid in expired:
            SESSIONS.pop(sid, None)
        await asyncio.sleep(30)


def put_session(df: pd.DataFrame, filename: str, meta: dict[str, Any], language: str = "en") -> tuple[str, dict[str, Any]]:
    cleanup_sessions()
    sid = secrets.token_urlsafe(24)
    analysis = build_analysis(df, filename, meta, language)
    SESSIONS[sid] = {"created": time.time(), "df": df.copy(deep=True), "filename": filename,
                     "meta": meta, "analysis": analysis, "language": language}
    return sid, analysis


def get_session(sid: str) -> dict[str, Any]:
    cleanup_sessions()
    item = SESSIONS.get(sid)
    if not item:
        raise HTTPException(status_code=404, detail="This result session has expired. Upload the file again to create a fresh result.")
    return item


# ---------------------------------------------------------------------------
# User-facing questions: deterministic, evidence-backed, no invented numbers
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=2, max_length=500)


HINDI_MARATHI_MAP = {
    # Aggregations
    "कुल": "total sum",
    "एकूण": "total sum",
    "सब मिलाकर": "total sum",
    "सब": "total sum",
    "टोटल": "total sum",
    "औसत": "average mean",
    "सरासरी": "average mean",
    "सबसे ज्यादा": "highest max peak top most",
    "सबसे अधिक": "highest max peak top most",
    "सर्वात जास्त": "highest max peak top most",
    "सर्वाधिक": "highest max peak top most",
    "सबसे कम": "lowest min least bottom cheapest",
    "सर्वात कमी": "lowest min least bottom cheapest",
    "कितना": "how much",
    "कितनी": "how much",
    "कितने": "how many count",
    "किती": "how much how many count",
    "संख्या": "count number",
    # Dimensions & Measures
    "बिक्री": "sales",
    "विक्री": "sales",
    "खर्च": "spend expense",
    "व्यय": "spend expense",
    "कमाई": "income received",
    "उत्पन्न": "income",
    "नफा": "profit",
    "फायदा": "profit",
    "तारीख": "date",
    "दिनांक": "date",
    "महीना": "month",
    "महिना": "month",
    "महीने": "month",
    "महिने": "month",
    "साल": "year",
    "वर्ष": "year",
    "उत्पाद": "product",
    "वस्तू": "product",
    "पेंडिंग": "pending",
    "प्रलंबित": "pending",
    "जिल्हा": "district",
    "जिल्हे": "district",
    "स्थान": "area place",
    "रिक्त": "blank missing",
    "खाली": "blank missing",
    "डुप्लिकेट": "duplicate",
    # Common categories
    "भोजन": "food",
    "जेवण": "food",
    "अन्न": "food",
    "किराना": "groceries",
    "यात्रा": "travel",
    "प्रवास": "travel",
}

QA_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "for", "of", "to", "from", "by", "with",
    "is", "are", "was", "were", "what", "which", "where", "how", "who", "whom",
    "did", "do", "does", "have", "has", "had", "show", "give", "tell", "me",
    "us", "this", "that", "these", "those", "my", "our", "all", "any", "some",
    "much", "many", "most", "more", "least", "less", "few", "per", "across",
    "there", "here", "it", "its", "or", "and", "not", "no", "so", "as", "if"
}

def stem_qa_token(w: str) -> str:
    w = w.lower().strip()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and len(w) > 2 and not w.endswith("ss"):
        return w[:-1]
    return w

def normalize_qa_query(question: str) -> str:
    q = question.strip().lower()
    for word, replacement in HINDI_MARATHI_MAP.items():
        if word in q:
            q += " " + replacement
    if re.search(r"\bsabse\s*(?:jyada|jada|bada|badi)\b", q):
        q += " highest most max"
    if re.search(r"\bsabse\s*(?:kam|chhota|chhoti)\b", q):
        q += " lowest min least cheapest"
    if re.search(r"\b(?:kitna|kitne|kitni|kiti)\b", q):
        q += " how much how many count"
    if re.search(r"\b(?:kul|ekun)\b", q):
        q += " total sum"
    if re.search(r"\b(?:ausat|sarasari)\b", q):
        q += " average"
    if re.search(r"\b(?:kharch|kharcha)\b", q):
        q += " spend expense"
    if re.search(r"\b(?:bikri|vikri)\b", q):
        q += " sales"
    return q

def smart_find_measure(df: pd.DataFrame, shape: dict[str, Any], q: str) -> str | None:
    nums = shape.get("numeric_columns", [])
    if not nums:
        return None
    
    if shape.get("shape") == "grouped_summary":
        sum_fields = [c for c in nums if re.search(r"\(\s*sum\s*\)$", str(c), re.I)]
        count_fields = [c for c in nums if re.search(r"\(\s*count\s*\)$", str(c), re.I)]
        avg_fields = [c for c in nums if re.search(r"\(\s*average\s*\)$", str(c), re.I)]
        
        requested_topic = None
        if re.search(r"tax.*paid|paid.*tax|tax.*collected", q):
            requested_topic = "Tax Paid"
        elif "refund" in q:
            requested_topic = "Refund"
        elif re.search(r"taxable income", q):
            requested_topic = "Taxable Income"
        elif "income" in q:
            requested_topic = "Income"
            
        if requested_topic:
            if re.search(r"average|mean", q) and not re.search(r"weighted", q):
                matched = next((c for c in avg_fields if re.search(re.escape(requested_topic), c, re.I)), None)
                if matched: return matched
            elif re.search(r"count|how many", q) and not re.search(r"how much|total|sum", q):
                matched = next((c for c in count_fields if re.search(re.escape(requested_topic), c, re.I)), None)
                if matched: return matched
            else:
                matched = next((c for c in sum_fields if re.search(re.escape(requested_topic), c, re.I)), None)
                if matched: return matched
                
        if sum_fields:
            return sum_fields[0]

    pure_nums = [c for c in nums if not RATE_RE.search(c) and not ID_NAME_RE.search(c) and not re.search(r"order|seq|code|id", c, re.I)]
    if not pure_nums:
        pure_nums = nums

    for col in pure_nums:
        col_clean = re.sub(r"[_\s()]+", " ", str(col)).strip().lower()
        if re.search(r"\b" + re.escape(col_clean) + r"\b", q):
            return col
            
    scores = {}
    tokens = [stem_qa_token(t) for t in re.findall(r"[a-z0-9]+", q)]
    for col in pure_nums:
        col_tokens = {stem_qa_token(t) for t in re.findall(r"[a-z0-9]+", str(col).lower())} - {"inr", "rs", "sum", "average", "count", "id", "no"}
        score = 0
        for t in tokens:
            if t in col_tokens:
                score += 3
        if any(w in q for w in ["profit", "margin", "gain", "gross"]) and any(w in col_tokens for w in ["profit", "margin"]):
            score += 10
        if any(w in q for w in ["cost", "spend", "expenditure"]) and any(w in col_tokens for w in ["cost", "expense", "spend"]):
            score += 10
        if any(w in q for w in ["unit price", "price", "rate", "cheapest"]) and any(w in col_tokens for w in ["price", "rate"]):
            score += 10
        if any(w in q for w in ["quantity", "qty", "units", "volume"]) and any(w in col_tokens for w in ["quantity", "qty", "unit", "volume"]):
            score += 10
        if any(w in q for w in ["sales", "revenue", "collection", "receipt", "bikri", "turnover"]) and any(w in col_tokens for w in ["sales", "revenue", "collection"]):
            score += 10
        if any(w in q for w in ["tax", "tax paid", "gst", "duty"]) and "tax" in col_tokens:
            score += 10
        if "refund" in q and "refund" in col_tokens:
            score += 10
        if "income" in q and "income" in col_tokens:
            score += 10
        if any(w in q for w in ["days", "duration", "resolution", "time"]) and any(w in col_tokens for w in ["days", "duration"]):
            score += 10
        if any(w in q for w in ["rainfall", "rain", "precipitation"]) and any(w in col_tokens for w in ["rainfall", "rain"]):
            score += 10
        if any(w in q for w in ["marks", "score", "rating"]) and any(w in col_tokens for w in ["marks", "score", "rating"]):
            score += 10
        if score > 0:
            scores[col] = score
            
    if scores:
        return max(scores, key=scores.get)
            
    amount_col = next((c for pattern in (r"sales|revenue|collection|receipt", r"amount|spend|expense|payment|income|tax|refund", r"profit|cost", r"quantity|count|total|value")
                       for c in pure_nums if re.search(pattern, c, re.I)), None)
    return amount_col or pure_nums[0]

def smart_find_dimension(df: pd.DataFrame, shape: dict[str, Any], q: str, exclude_filter_cols: set[str] = set()) -> str | None:
    date_col = shape.get("date_column")
    dims = [c for c in shape.get("dimension_columns", []) if c not in shape.get("identifier_columns", []) and c not in exclude_filter_cols and c != date_col]
    if not dims:
        dims = [c for c in df.columns if c not in shape.get("numeric_columns", []) and c not in shape.get("identifier_columns", []) and c not in exclude_filter_cols and c != date_col]
        
    q_stemmed_tokens = [stem_qa_token(t) for t in re.findall(r"[a-z0-9]+", q)]

    for prefix in [r"\bby\s+([a-z0-9_ -]+)", r"\bper\s+([a-z0-9_ -]+)", r"\bacross\s+([a-z0-9_ -]+)", r"\bfor each\s+([a-z0-9_ -]+)", r"\bin each\s+([a-z0-9_ -]+)"]:
        m = re.search(prefix, q)
        if m:
            target = m.group(1).strip()
            target_stem = stem_qa_token(target)
            for col in dims:
                c_clean = re.sub(r"[_\s]+", " ", str(col)).strip().lower()
                c_stem = stem_qa_token(c_clean)
                if c_clean in target or target in c_clean or c_stem in target_stem or target_stem in c_stem:
                    return col

    for col in dims:
        c_clean = re.sub(r"[_\s]+", " ", str(col)).strip().lower()
        if len(c_clean.split()) >= 2 and re.search(r"\b" + re.escape(c_clean) + r"\b", q):
            return col
            
    for col in dims:
        c_clean = re.sub(r"[_\s]+", " ", str(col)).strip().lower()
        c_words = [stem_qa_token(w) for w in re.findall(r"[a-z0-9]+", c_clean) if w not in QA_STOPWORDS]
        if len(c_words) >= 2 and all(w in q_stemmed_tokens for w in c_words):
            return col
            
    for col in dims:
        clow = col.lower()
        if any(k in clow for k in ["payment_method", "payment_mode", "mode", "payment type"]):
            if any(w in q for w in ["payment method", "payment mode", "payment type", "payments", "payment"]):
                return col
        if any(k in clow for k in ["crime category", "incident type", "incident", "crime"]):
            if any(w in q for w in ["incident type", "crime category", "incident", "crime", "type"]):
                return col
        if "category" in clow and any(w in q_stemmed_tokens for w in ["category", "type", "kind", "class"]):
            return col
        if "product" in clow and any(w in q_stemmed_tokens for w in ["product", "item", "goods", "sku"]):
            return col
        if "merchant" in clow and any(w in q_stemmed_tokens for w in ["merchant", "vendor", "payee", "seller"]):
            return col
        if "recipient" in clow and any(w in q_stemmed_tokens for w in ["recipient", "receiver"]):
            return col
        if "department" in clow and any(w in q_stemmed_tokens for w in ["department", "dept"]):
            return col
        if "district" in clow and any(w in q_stemmed_tokens for w in ["district", "jilha"]):
            return col
        if "area" in clow and any(w in q_stemmed_tokens for w in ["area", "branch", "place", "location"]):
            return col
        if "ward" in clow and "ward" in q:
            return col
        if "city" in clow and "city" in q:
            return col
        if "severity" in clow and "severity" in q:
            return col
        if "status" in clow and "status" in q:
            return col
        if "type" in clow and any(w in q_stemmed_tokens for w in ["type"]):
            return col

    for col in dims:
        c_clean = re.sub(r"[_\s]+", " ", str(col)).strip().lower()
        c_words = [stem_qa_token(w) for w in re.findall(r"[a-z0-9]+", c_clean) if w not in QA_STOPWORDS and len(w) > 3]
        if any(w in q_stemmed_tokens for w in c_words):
            return col

    if re.search(r"\b(?:which|compare)\b", q):
        dim_candidates = [c for c in dims if re.search(r"product|item|category|merchant|recipient|district|ward|area|city|zone|department|branch", str(c), re.I)]
        if dim_candidates:
            for dc in dim_candidates:
                dc_words = [stem_qa_token(w) for w in re.findall(r"[a-z]+", dc.lower()) if len(w) > 3]
                if any(w in q_stemmed_tokens for w in dc_words):
                    return dc
            return dim_candidates[0]
            
    return None


def answer_question(df: pd.DataFrame, shape: dict[str, Any], question: str) -> dict[str, Any]:
    raw_q = question.strip()
    q = normalize_qa_query(raw_q)
    nums = shape.get("numeric_columns", [])
    dims = [c for c in shape.get("dimension_columns", []) if c not in shape.get("identifier_columns", [])]
    date_col = shape.get("date_column")
    status_col = next((c for c in df.columns if re.search(r"status|state", str(c), re.I)), None)
    
    # Grouped summary report totals are excluded for all comparisons and calculations.
    if shape.get("shape") == "grouped_summary":
        filtered, _excluded = exclude_total_rows(df, shape)
    else:
        filtered = df.copy()

    # 1. Missing / blank cells
    if re.search(r"\b(?:missing|blank|empty|null|incomplete)\b", q):
        miss = df.isna().sum(); miss = miss[miss > 0]
        rows = df.index[df.isna().any(axis=1)].tolist()
        return answer_payload(
            f"There are {int(miss.sum())} blank cell(s) across {len(miss)} field(s)." if len(miss) else "I did not find any blank cells.",
            "Counted empty cells in each field.",
            [{"field": str(k), "blank_cells": int(v)} for k, v in miss.items()], rows,
            "A blank can mean unknown, not needed, or not recorded. It is not automatically zero."
        )

    # 2. Structure / Overview / Summary question
    if any(w in q for w in ["structure", "one row", "what is this", "describe this file", "overview", "what does this data show"]):
        return answer_payload(
            f"This looks like {shape['shape'].replace('_', ' ')} data. {shape.get('reason', '')}",
            "Detected the likely table shape from its columns, values and row patterns.",
            [{"rows": len(df), "fields": len(df.columns), "likely_type": shape.get("shape")}], [],
            "The shape is an estimate. If it is wrong, tell OmniLens what one row represents."
        )

    # 3. Duplicate rows check
    if re.search(r"\b(?:duplicate|duplicates|redundant|repeat rows|identical rows)\b", q):
        dup_mask = df.duplicated(keep=False)
        dup_count = int(df.duplicated().sum())
        dup_indices = df.index[dup_mask].tolist()
        if dup_count > 0:
            return answer_payload(
                f"I found {dup_count} duplicate row(s) ({len(dup_indices)} total rows involved).",
                "Checked exact matching row contents across all columns.",
                [{"field": "duplicate_rows_count", "value": dup_count}], dup_indices,
                "Duplicate records can occur from multiple submissions or repeated logs."
            )
        else:
            return answer_payload(
                "I did not find any duplicate rows in this file.",
                "Checked exact matching row contents across all columns.",
                [{"field": "duplicate_rows_count", "value": 0}], [],
                "Exact duplicates require every column to match."
            )

    # 4. Date range / time period question
    if date_col and re.search(r"\b(?:date range|time period|time frame|earliest date|latest date|date span|span of time)\b", q):
        dates, _ = infer_date_format(df[date_col])
        valid_dates = dates.dropna()
        if not valid_dates.empty:
            earliest = valid_dates.min().strftime("%Y-%m-%d")
            latest = valid_dates.max().strftime("%Y-%m-%d")
            days_span = (valid_dates.max() - valid_dates.min()).days
            return answer_payload(
                f"The records span from {earliest} to {latest} ({days_span} days across {len(valid_dates):,} dated rows).",
                f"Parsed dates in '{date_col}' to find the earliest and latest entries.",
                [{"earliest_date": earliest, "latest_date": latest, "span_days": days_span, "records": len(valid_dates)}],
                valid_dates.index.tolist(),
                "Dates outside this range may not have been supplied in the uploaded file."
            )

    # 5. Grouped summary report: weighted average
    if shape.get("shape") == "grouped_summary" and re.search(r"weighted average|combined average|weight", q):
        if re.search(r"tax.?paid", q): base = "Tax Paid"
        elif "refund" in q: base = "Refund"
        elif re.search(r"taxable income", q): base = "Taxable Income"
        else: base = "Income"
        count_col = next((c for c in df.columns if re.fullmatch(re.escape(base) + r"\s*\(\s*count\s*\)", str(c), re.I)), None)
        sum_col = next((c for c in df.columns if re.fullmatch(re.escape(base) + r"\s*\(\s*sum\s*\)", str(c), re.I)), None)
        if count_col and sum_col:
            count_total = float(numeric_view(filtered[count_col]).sum())
            sum_total = float(numeric_view(filtered[sum_col]).sum())
            value = sum_total / count_total if count_total else 0.0
            return answer_payload(
                f"The weighted average for {base} is {value:,.2f}, calculated from the combined sum divided by the combined count.",
                f"Added '{sum_col}' and divided it by the total '{count_col}'. Overall rows labelled All or Total were excluded.",
                [{"measure": base, "sum": round(sum_total, 2), "count": int(count_total), "weighted_average": round(value, 2)}],
                filtered.index.tolist(),
                "This is the count-weighted average of the groups supplied. It is only as complete as the source report."
            )

    # --- FILTER EXTRACTION ---
    filter_note = ""
    applied_filter_cols = set()

    # A. Status filter
    if status_col and re.search(r"\b(?:pending|open|unresolved|completed|closed|resolved|failed|succeeded|successful|cancelled)\b", q):
        terms = [x for x in ["pending", "open", "unresolved", "completed", "closed", "resolved", "failed", "succeeded", "successful", "cancelled"] if x in q]
        if terms:
            term = terms[0]
            series = filtered[status_col].astype(str).str.lower()
            if term == "open":
                mask = series.str.contains(r"open|pending|unresolved", regex=True)
            elif term == "unresolved":
                mask = ~series.str.contains(r"resolved|completed|closed", regex=True)
            elif term in ["completed", "successful", "succeeded"]:
                mask = series.str.contains(r"completed|successful|succeeded", regex=True)
            elif term == "closed":
                mask = series.str.contains(r"closed|resolved|completed", regex=True)
            elif term == "resolved":
                mask = series.str.contains(r"resolved|completed|closed", regex=True)
            elif term == "failed":
                mask = series.str.contains(r"failed|declined|rejected", regex=True)
            else:
                mask = series.str.contains(term, regex=False)
            filtered = filtered[mask]
            filter_note += f" Only rows marked {term} in '{status_col}' were included."
            applied_filter_cols.add(status_col)

    # B. Money in/out direction
    direction_col = next((c for c in df.columns if re.search(r"direction|transaction type|^type$", str(c), re.I)), None)
    if direction_col and re.search(r"spend|spent|money out|paid|outgoing|expense|expenses|debit|withdrawal", q):
        filtered = filtered[filtered[direction_col].astype(str).str.lower().str.contains(r"out|paid|sent|debit|expense", regex=True)]
        filter_note += " Outgoing transactions only."
        applied_filter_cols.add(direction_col)
    elif direction_col and re.search(r"received|money in|incoming|credit|deposit|earnings|payroll", q):
        filtered = filtered[filtered[direction_col].astype(str).str.lower().str.contains(r"received|credit|money in|incoming", regex=True)]
        filter_note += " Incoming transactions only."
        applied_filter_cols.add(direction_col)

    if status_col and direction_col and re.search(r"spend|spent|money|received|incoming|outgoing", q):
        filtered = filtered[filtered[status_col].astype(str).str.lower().isin(["completed", "successful", "succeeded", "resolved", "closed"])]

    # C. Dynamic Categorical / Cell-value filters
    filter_term = None
    candidate_filter_cols = [c for c in df.columns if c not in applied_filter_cols and c not in shape.get("numeric_columns", [])]
    for col in candidate_filter_cols:
        uniq_vals = filtered[col].dropna().astype(str).unique()
        if len(uniq_vals) > 150:
            continue
        for val in uniq_vals:
            val_clean = val.strip().lower()
            if len(val_clean) < 3 or val_clean in QA_STOPWORDS:
                continue
            if re.search(r"\b" + re.escape(val_clean) + r"\b", q):
                filtered = filtered[filtered[col].astype(str).str.strip().str.lower() == val_clean]
                filter_term = val
                applied_filter_cols.add(col)
                filter_note += f" Filtered to {col}='{val}'."
                break
        if filter_term:
            break

    # Backward-compatible regex for "on/for/in/at <term>?"
    if not filter_term:
        category_col = next((c for c in dims if re.search(r"category|type|product|merchant", c, re.I)), None)
        if category_col:
            m = re.search(r"\b(?:on|for|in|at)\s+([a-z][a-z &'-]{1,35})\??$", q)
            if m and re.search(r"spend|spent|food|expense|amount|total|much|bikri|sales", q):
                phrase = m.group(1).strip()
                if phrase not in {"this month", "last month", "each month", "this year", "last year"}:
                    vals = filtered[category_col].dropna().astype(str).unique().tolist()
                    chosen = next((v for v in vals if phrase in v.lower()), None)
                    if chosen:
                        filtered = filtered[filtered[category_col].astype(str).str.strip().str.lower() == chosen.strip().lower()]
                        filter_term = chosen
                        applied_filter_cols.add(category_col)

    # Resolve measure and dimension
    measure = smart_find_measure(df, shape, q)
    group = smart_find_dimension(df, shape, q, exclude_filter_cols=applied_filter_cols)

    # 6. Unique / Distinct Count question
    if re.search(r"\b(?:unique|distinct|different)\b", q) and re.search(r"\b(?:how many|count|number of|list of|what are the)\b", q):
        target_dim = group or (dims[0] if dims else None)
        if target_dim:
            uniques = filtered[target_dim].dropna().unique().tolist()
            count = len(uniques)
            val_list_str = ", ".join(map(str, uniques[:8])) + ("..." if count > 8 else "")
            chart = None
            if count <= 15:
                vc = filtered[target_dim].value_counts().head(8)
                chart = {"title": f"Count by {target_dim}", "labels": [str(x) for x in vc.index], "values": [float(x) for x in vc.values]}
            return answer_payload(
                f"There are {count} unique {target_dim} values recorded in this data ({val_list_str}).{filter_note}",
                f"Extracted distinct values in '{target_dim}'.",
                [{"unique_count": count, "field": target_dim, "sample_values": uniques[:10]}],
                filtered.index.tolist(),
                "Unique count reflects only values recorded in the uploaded file.",
                chart
            )

    # 7. Count / How many rows question (when not asking for group ranking)
    is_count_q = bool(re.search(r"\b(?:how many|count of|number of|total rows|total records|how many records|how many transactions|how many incidents|how many cases)\b", q))
    if is_count_q and not group and not re.search(r"which|most|highest|top", q):
        row_count = len(filtered)
        total_rows = len(df)
        pct_str = f" ({row_count / total_rows * 100:.1f}% of all records)" if total_rows > 0 and row_count != total_rows else ""
        return answer_payload(
            f"There are {row_count:,} matching record(s){pct_str}.{filter_note}",
            f"Counted rows after applying matching filters.{filter_note}",
            [{"matching_records": row_count, "total_records": total_rows}],
            filtered.index.tolist(),
            "Counts are based entirely on the provided dataset."
        )

    # 8. Single Extreme Record (Peak / Max / Largest vs Lowest / Min / Cheapest) WITHOUT grouping
    wants_extreme = bool(re.search(r"\b(?:highest|maximum|max|peak|largest|biggest|lowest|minimum|min|smallest|least|cheapest)\b", q))
    if wants_extreme and not group and measure:
        values = numeric_view(filtered[measure]).dropna()
        if not values.empty:
            is_min = bool(re.search(r"\b(?:lowest|minimum|min|smallest|least|cheapest)\b", q))
            target_idx = values.idxmin() if is_min else values.idxmax()
            best_val = float(values.loc[target_idx])
            best_row = filtered.loc[target_idx]
            
            desc_parts = []
            for col in ["product", "category", "merchant", "description", "area", "district", "date", "incident_type"]:
                matching_col = next((c for c in filtered.columns if re.search(r"^" + col, str(c), re.I)), None)
                if matching_col and not pd.isna(best_row[matching_col]):
                    desc_parts.append(f"{matching_col}: {best_row[matching_col]}")
            desc_str = f" ({', '.join(desc_parts[:3])})" if desc_parts else ""
            label = "lowest" if is_min else "highest"
            return answer_payload(
                f"The {label} recorded {measure} is {best_val:,.2f}{desc_str}.{filter_note}",
                f"Found row with {label} numeric value in '{measure}'.{filter_note}",
                [{"field": measure, "value": best_val, "row_index": int(target_idx)}],
                [int(target_idx)],
                "Based on available rows. If earlier or later periods exist, extremes might differ.",
                {"title": f"{label.title()} {measure}", "labels": [desc_parts[0] if desc_parts else "Record"], "values": [round(best_val, 2)]}
            )

    # 9. Ranking / Comparison / Top N / Group Breakdown
    wants_rank = bool(re.search(r"\b(?:which|most|highest|largest|top|lowest|smallest|best|worst|compare|by|breakdown|distribution|per|across|cheapest|least|peak)\b", q))
    if group and wants_rank:
        is_measure_relevant = bool(measure and re.search(r"amount|sales|revenue|collection|spend|spent|expense|profit|cost|price|income|tax|refund|quantity|days|marks|score|rating|rainfall|money|cheapest|unit|rate", q))
        if shape.get("shape") == "grouped_summary":
            is_measure_relevant = True
            
        if is_measure_relevant:
            vals = numeric_view(filtered[measure])
            table = pd.DataFrame({"group": filtered[group].astype(str), "value": vals, "row": filtered.index})
            is_avg = bool(re.search(r"average|mean|avg|cheapest", q))
            if is_avg:
                grouped = table.groupby("group")["value"].mean().dropna().sort_values(ascending=False)
                agg_type = "average" if not re.search(r"cheapest", q) else "average unit price"
                method = f"Calculated average '{measure}' within each '{group}' group."
            else:
                grouped = table.groupby("group")["value"].sum(min_count=1).dropna().sort_values(ascending=False)
                agg_type = "total"
                method = f"Added '{measure}' within each '{group}' group."
            row_ids = table.index.tolist()
        else:
            grouped = filtered[group].fillna("(blank)").astype(str).value_counts()
            agg_type = "number of matching records"
            method = f"Counted matching rows in each '{group}' group."
            row_ids = filtered.index.tolist()

        if not grouped.empty:
            descending = not bool(re.search(r"\b(?:lowest|smallest|worst|least|bottom|cheapest)\b", q))
            if not descending:
                grouped = grouped.sort_values(ascending=True)
            top_key, top_value = grouped.index[0], float(grouped.iloc[0])
            chart = {
                "title": f"{group} comparison",
                "labels": [str(x) for x in grouped.head(8).index],
                "values": [float(x) for x in grouped.head(8).values]
            }
            rank_str = "highest" if descending else "lowest"
            measure_str = f"{agg_type} for {measure}" if is_measure_relevant else "number of matching records"
            unit_str = " in the file's units" if is_measure_relevant else " records"
            return answer_payload(
                f"{top_key} has the {rank_str} {measure_str}{filter_note} The value is {top_value:,.2f}{unit_str}.",
                method + filter_note,
                [{"group": str(k), "value": round(float(v), 2)} for k, v in grouped.head(10).items()],
                row_ids,
                "This tells us where the uploaded records are concentrated. It does not explain the cause.",
                chart
            )

    # 10. Time series question
    if date_col and measure and re.search(r"\b(?:month|trend|over time|by date|monthly|timeline|daily)\b", q):
        dates, _ = infer_date_format(filtered[date_col])
        temp = pd.DataFrame({"period": dates.dt.to_period("M").astype(str), "value": numeric_view(filtered[measure]), "row": filtered.index})
        temp = temp.dropna(subset=["value"])
        monthly = temp.groupby("period")["value"].sum(min_count=1).dropna().sort_index()
        if not monthly.empty:
            chart = {"title": f"{measure} by month", "labels": monthly.index.tolist(), "values": [float(x) for x in monthly.values]}
            return answer_payload(
                f"I found {len(monthly)} month(s) with recorded {measure}.{filter_note}",
                f"Parsed '{date_col}' and summed '{measure}' by month.{filter_note}",
                [{"month": str(k), "value": round(float(v), 2)} for k, v in monthly.items()],
                temp["row"].tolist(),
                "A missing month may mean no records were supplied; it does not always mean zero.",
                chart
            )

    # 11. Totals / Average / Median / General Numeric Query
    if measure and (re.search(r"how much|total|sum|spend|spent|received|average|mean|median|profit|cost|price|quantity|bikri|sales", q) or filter_term):
        values = numeric_view(filtered[measure]).dropna()
        if values.empty:
            return answer_payload("I could not find a usable number in the rows matching that question.", f"Tried the field '{measure}'.", [], [], "Check the field meaning and number format.")
        
        if re.search(r"\b(?:median)\b", q):
            value = float(values.median()); label = "median"
        elif re.search(r"\b(?:average|mean|avg)\b", q):
            value = float(values.mean()); label = "average"
        else:
            value = float(values.sum()); label = "total"

        chart_label = filter_term or (
            "Money received" if re.search(r"received|money in|incoming", q)
            else "Money out" if re.search(r"spend|spent|money out|paid|outgoing", q)
            else "Matching rows"
        )
        chart = {
            "title": f"{label.title()} {measure} in matching rows",
            "labels": [chart_label],
            "values": [round(value, 2)],
        }
        return answer_payload(
            f"The {label} {measure} in the matching rows is {value:,.2f}.{filter_note}",
            f"Converted '{measure}' to numbers and calculated the {label}." + filter_note,
            [{"field": measure, "value": round(value, 2), "rows_used": len(values)}],
            filtered.index.tolist(),
            "Check that all relevant transactions or records are included. The total uses only the uploaded file.",
            chart
        )

    # 12. Smart Informative Fallback
    avail_cols = ", ".join(list(df.columns[:5]))
    return answer_payload(
        f"I couldn't match a specific numeric calculation for that question. This dataset includes fields like: {avail_cols}. Try asking about totals, averages, ranking by a category, or trends over time.",
        "Scanned question for measures, dimensions and filters.",
        [], [],
        "OmniLens calculates exact figures from the data without inventing estimates."
    )


def answer_payload(text: str, method: str, rows: list[dict[str, Any]], evidence_indices: list[int], caveat: str, chart: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"answer": text, "how_calculated": method, "rows": rows[:30], "evidence_indices": [int(x) for x in evidence_indices[:MAX_EVIDENCE_ROWS]], "what_this_cannot_tell_us": caveat, "chart": chart}


# ---------------------------------------------------------------------------
# Clean preview and approval
# ---------------------------------------------------------------------------

class CleanApproval(BaseModel):
    session_id: str
    approved: list[str] = Field(default_factory=list)
    fuzzy_mappings: dict[str, str] = Field(default_factory=dict)
    output_format: str = "xlsx"


class CleanPreviewRequest(BaseModel):
    session_id: str
    approved: list[str] = Field(default_factory=list)
    fuzzy_mappings: dict[str, str] = Field(default_factory=dict)


def prepare_cleaning(df: pd.DataFrame) -> dict[str, Any]:
    proposed: list[dict[str, Any]] = []
    text_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    trim_count = 0
    for col in text_cols:
        s = df[col]
        changed = s.dropna().astype(str).map(lambda x: x != x.strip()).sum()
        if changed:
            trim_count += int(changed)
    if trim_count:
        proposed.append({"id": "trim_spaces", "label": "Remove extra spaces", "description": f"Trim leading/trailing spaces in {trim_count} cell(s).", "change_count": trim_count, "safe": True})
    case_candidates = []
    for col in text_cols:
        if not re.search(r"city|district|state|area|place|ward|category|status|payment method|branch", str(col), re.I):
            continue
        vals = df[col].dropna().astype(str)
        groups: dict[str, set[str]] = {}
        for value in vals.unique():
            norm = re.sub(r"\s+", " ", value.strip()).casefold()
            groups.setdefault(norm, set()).add(value)
        for norm, variants in groups.items():
            if len(variants) > 1:
                canonical = max(variants, key=lambda v: (int((vals == v).sum()), len(v)))
                case_candidates.append({"field": str(col), "variants": sorted(variants), "suggested_value": canonical.strip().title() if re.search(r"city|district|state|area|place|ward", str(col), re.I) else canonical.strip()})
    if case_candidates:
        proposed.append({"id": "normalise_spelling", "label": "Match capital letters and spacing", "description": f"Found {len(case_candidates)} group(s) such as pune / Pune / PUNE. Review each suggested match before approval.", "change_count": len(case_candidates), "safe": False, "suggestions": case_candidates[:50]})
    date_cols = []
    for col in df.columns:
        if DATE_NAME_RE.search(str(col)):
            parsed, _ = infer_date_format(df[col])
            changed = int((parsed.notna() & (df[col].astype(str) != parsed.dt.strftime("%Y-%m-%d"))).sum())
            if changed:
                date_cols.append({"field": str(col), "change_count": changed})
    if date_cols:
        proposed.append({"id": "standardise_dates", "label": "Use one date format", "description": "Convert recognised dates to YYYY-MM-DD. Unreadable dates are left unchanged.", "change_count": sum(x["change_count"] for x in date_cols), "safe": True, "fields": date_cols})
    dup = int(df.duplicated().sum())
    if dup:
        proposed.append({"id": "remove_exact_duplicates", "label": "Remove exact repeat rows", "description": f"Remove {dup} row(s) that are identical across all fields. Review before approving.", "change_count": dup, "safe": False})
    # Show a sample after only the low-risk suggestions (trim spaces and parseable
    # dates). Duplicates and spelling merges are intentionally not auto-applied.
    safe_preview, _ = apply_cleaning(df, ["trim_spaces", "standardise_dates"], {})
    return {"changes": proposed, "before": masked_records(df.head(6)),
            "after_safe": masked_records(safe_preview.head(6)),
            "note": "Nothing has been changed. This is only a preview. Select the changes you approve; the original upload remains untouched."}


def apply_cleaning(df: pd.DataFrame, approved: list[str], fuzzy_mappings: dict[str, str]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    result = df.copy(deep=True)
    log = []
    if "trim_spaces" in approved:
        changed = 0
        for col in result.columns:
            if result[col].dtype == object or pd.api.types.is_string_dtype(result[col]):
                before = result[col].copy()
                result[col] = result[col].map(lambda x: re.sub(r"\s+", " ", x.strip()) if isinstance(x, str) else x)
                changed += int((before.fillna("<NA>") != result[col].fillna("<NA>")).sum())
        log.append({"change": "Remove extra spaces", "cells_changed": changed})
    if "normalise_spelling" in approved:
        changed = 0
        for key, canonical in fuzzy_mappings.items():
            if "::" not in key:
                continue
            col, variant = key.split("::", 1)
            if col in result.columns:
                mask = result[col].astype(str).str.strip().str.casefold() == variant.strip().casefold()
                changed += int(mask.sum())
                result.loc[mask, col] = canonical
        log.append({"change": "Match approved spelling variants", "cells_changed": changed, "mappings": fuzzy_mappings})
    if "standardise_dates" in approved:
        changed = 0
        for col in result.columns:
            if DATE_NAME_RE.search(str(col)):
                parsed, _ = infer_date_format(result[col])
                mask = parsed.notna()
                changed += int((mask & (result[col].astype(str) != parsed.dt.strftime("%Y-%m-%d"))).sum())
                result.loc[mask, col] = parsed.loc[mask].dt.strftime("%Y-%m-%d")
        log.append({"change": "Standardise recognised dates", "cells_changed": changed, "format": "YYYY-MM-DD"})
    if "remove_exact_duplicates" in approved:
        before = len(result)
        result = result.drop_duplicates(keep="first").reset_index(drop=True)
        log.append({"change": "Remove exact duplicate rows", "rows_removed": before - len(result)})
    return result, log


# ---------------------------------------------------------------------------
# Comparisons
# ---------------------------------------------------------------------------

def compare_frames(a: pd.DataFrame, b: pd.DataFrame, name_a: str, name_b: str) -> dict[str, Any]:
    common = [c for c in a.columns if c in b.columns]
    if not common:
        return {"headline": "These files do not share column names, so a reliable comparison is not available.", "differences": [], "caveat": "Rename matching fields in a copy and compare again."}
    # Align table shape and exclude total rows if grouped.
    shape_a, shape_b = detect_shape(a), detect_shape(b)
    wa, excluded_a = exclude_total_rows(a, shape_a)
    wb, excluded_b = exclude_total_rows(b, shape_b)
    common_num = []
    for c in common:
        va, vb = numeric_view(wa[c]), numeric_view(wb[c])
        if va.notna().mean() >= .6 and vb.notna().mean() >= .6 and va.notna().sum() >= 1 and vb.notna().sum() >= 1:
            common_num.append(c)
    if shape_a["shape"] == "grouped_summary" and shape_b["shape"] == "grouped_summary":
        measure = next((c for c in common_num if re.search(r"\(\s*sum\s*\)$", str(c), re.I)), None)
        if measure is None:
            measure = next((c for c in common_num if re.search(r"\(\s*count\s*\)$", str(c), re.I)), None)
    else:
        measure = next((c for pattern in (r"sales|revenue|collection|receipt", r"amount|expense|spend|payment|income", r"profit|cost", r"quantity|count|total|value")
                        for c in common_num if re.search(pattern, c, re.I) and not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
    group = next((c for pattern in (r"category|district|ward|area|branch|city|department|product|income range|taxpayer type")
                  for c in common if re.search(pattern, str(c), re.I) and c in wa.columns and c in wb.columns), None)
    if measure:
        total_a = float(numeric_view(wa[measure]).sum())
        total_b = float(numeric_view(wb[measure]).sum())
        delta = total_b - total_a
        pct = delta / abs(total_a) * 100 if total_a else None
        headline = f"{measure} {'increased' if delta > 0 else 'decreased' if delta < 0 else 'stayed about the same'} from {name_a} to {name_b} by {abs(pct):.1f}%" if pct is not None else f"The total {measure} changed from {total_a:,.2f} to {total_b:,.2f}."
        differences = [{"measure": measure, "file_a": total_a, "file_b": total_b, "change": delta, "change_percent": pct}]
        if group:
            ga = numeric_view(wa[measure]).groupby(wa[group].astype(str)).sum()
            gb = numeric_view(wb[measure]).groupby(wb[group].astype(str)).sum()
            rows = []
            for key in sorted(set(ga.index) | set(gb.index)):
                av = float(ga.get(key, 0)); bv = float(gb.get(key, 0)); d = bv - av
                rows.append({"group": key, "file_a": av, "file_b": bv, "change": d, "change_percent": d / abs(av) * 100 if av else None})
            rows.sort(key=lambda x: abs(x["change"]), reverse=True)
            differences.extend(rows[:10])
        return {"headline": headline + ".", "differences": differences, "measure": measure, "group": group,
                "caveat": "This compares the selected records in each file. Check that both files cover comparable periods, populations and definitions."}
    return {"headline": f"{name_a} contains {len(a):,} rows and {name_b} contains {len(b):,} rows.",
            "differences": [{"measure": "Number of rows", "file_a": len(a), "file_b": len(b), "change": len(b)-len(a)}],
            "caveat": "No clearly shared additive measure was found, so this is only a row-count comparison."}


# ---------------------------------------------------------------------------
# Exports: PDF, DOCX, Excel evidence, WhatsApp text
# ---------------------------------------------------------------------------

def make_share_text(item: dict[str, Any]) -> str:
    analysis = item["analysis"]
    lines = ["OmniLens – Data summary", "", analysis["headline"], "", "What to check next:"]
    for i, action in enumerate(analysis["actions"][:5], 1):
        lines.append(f"{i}. {action['title']} – {action['action']}")
    lines.extend(["", "What this file cannot tell us: " + analysis["caveat"], "", "Prepared from the uploaded file using OmniLens. Review the source before acting."])
    return "\n".join(lines)


def make_pdf(item: dict[str, Any]) -> bytes:
    if SimpleDocTemplate is None:
        raise HTTPException(status_code=503, detail="PDF export is not installed. Install reportlab and restart OmniLens.")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("OmniLens – Your data, understood", styles["Title"]), Spacer(1, 5*mm)]
    a = item["analysis"]
    story.append(Paragraph(a["headline"], styles["Heading2"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f"File: {html.escape(item['filename'])} | Rows: {len(item['df']):,} | Fields: {len(item['df'].columns)}", styles["Normal"]))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("What to do next", styles["Heading2"]))
    for i, action in enumerate(a["actions"][:5], 1):
        story.append(Paragraph(f"{i}. <b>{html.escape(action['title'])}</b><br/>{html.escape(action['action'])}", styles["BodyText"]))
        story.append(Spacer(1, 2*mm))
    story.append(Paragraph("What the charts show", styles["Heading2"]))
    for chart in a["charts"][:3]:
        story.append(Paragraph(f"<b>{html.escape(chart['title'])}</b><br/>{html.escape(chart['explanation'])}", styles["BodyText"]))
        if Drawing is not None and VerticalBarChart is not None and chart.get("values"):
            chart_width = max(300, min(480, float(doc.width)))
            drawing = Drawing(chart_width, 175)
            bars = VerticalBarChart()
            bars.x = 42; bars.y = 32; bars.width = chart_width - 58; bars.height = 125
            bars.data = [tuple(float(v) for v in chart["values"][:8])]
            bars.categoryAxis.categoryNames = [str(x)[:18] for x in chart["labels"][:8]]
            bars.categoryAxis.labels.fontSize = 7
            bars.categoryAxis.labels.angle = 25
            bars.categoryAxis.labels.dy = -7
            bars.valueAxis.labels.fontSize = 7
            bars.valueAxis.valueMin = min(0, min(float(v) for v in chart["values"][:8]))
            maximum = max(float(v) for v in chart["values"][:8])
            bars.valueAxis.valueMax = maximum * 1.15 if maximum > 0 else 1
            bars.valueAxis.valueStep = max((bars.valueAxis.valueMax - bars.valueAxis.valueMin) / 5, 1)
            bars.bars[0].fillColor = colors.HexColor("#315bd6")
            bars.strokeColor = colors.HexColor("#cbd5e1")
            drawing.add(bars)
            story.append(drawing)
        data = [["Group", "Value"]] + [[str(label)[:45], f"{float(value):,.2f} {chart.get('unit', '')}".strip()] for label, value in zip(chart["labels"], chart["values"])]
        table = Table(data, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e8eefc")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#172554")),
            ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#ccd5e2")),
            ("FONTSIZE", (0,0), (-1,-1), 8), ("PADDING", (0,0), (-1,-1), 5),
        ]))
        story.extend([Spacer(1, 2*mm), table, Spacer(1, 4*mm)])
    story.append(Paragraph("Key findings", styles["Heading2"]))
    for i, f in enumerate(a["findings"][:5], 1):
        story.append(Paragraph(f"<b>{i}. {html.escape(f['title'])}</b><br/>{html.escape(f['happened'])}<br/><b>Evidence:</b> {html.escape(f['evidence'])}<br/><b>Next:</b> {html.escape(f['next_step'])}", styles["BodyText"]))
        story.append(Spacer(1, 3*mm))
    story.append(Paragraph("What this file cannot tell us", styles["Heading2"]))
    story.append(Paragraph(html.escape(a["caveat"]), styles["BodyText"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Privacy note: the application does not write uploaded files to persistent storage. This report should still be handled according to your organisation's data-sharing rules.", styles["Italic"]))
    doc.build(story)
    return buffer.getvalue()


def make_docx(item: dict[str, Any]) -> bytes:
    if Document is None:
        raise HTTPException(status_code=503, detail="Word export is not installed. Install python-docx and restart OmniLens.")
    doc = Document()
    a = item["analysis"]
    doc.add_heading("OmniLens – Your data, understood", 0)
    doc.add_heading("What the file says", level=1)
    doc.add_paragraph(a["headline"])
    doc.add_paragraph(f"File: {item['filename']} | {len(item['df']):,} rows | {len(item['df'].columns)} fields")
    doc.add_heading("What to do next", level=1)
    for i, action in enumerate(a["actions"][:5], 1):
        doc.add_paragraph(f"{i}. {action['title']} – {action['action']}")
    doc.add_heading("Charts and comparisons", level=1)
    for chart in a["charts"][:3]:
        doc.add_heading(chart["title"], level=2)
        doc.add_paragraph(chart["explanation"])
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Group"
        table.rows[0].cells[1].text = "Value"
        for label, value in zip(chart["labels"], chart["values"]):
            cells = table.add_row().cells
            cells[0].text = str(label)
            cells[1].text = f"{float(value):,.2f}"
    doc.add_heading("Key findings", level=1)
    for i, finding in enumerate(a["findings"][:5], 1):
        doc.add_heading(f"{i}. {finding['title']}", level=2)
        doc.add_paragraph(finding["happened"])
        doc.add_paragraph("Evidence: " + finding["evidence"])
        doc.add_paragraph("Next step: " + finding["next_step"])
    doc.add_heading("What this file cannot tell us", level=1)
    doc.add_paragraph(a["caveat"])
    buffer = io.BytesIO(); doc.save(buffer); return buffer.getvalue()


def make_evidence_xlsx(df: pd.DataFrame, indices: list[int], filename: str) -> bytes:
    selected = df.loc[[i for i in indices if i in df.index]].copy()
    selected.insert(0, "Source row", selected.index + 1)
    pii_cols = detect_pii_columns(selected)
    for col in pii_cols:
        selected[col] = selected[col].map(lambda x: mask_value(x) if not is_blank(x) else x)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        selected.to_excel(writer, index=False, sheet_name="Evidence")
        ws = writer.sheets["Evidence"]
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = __import__("openpyxl").styles.Font(bold=True, color="FFFFFF")
            cell.fill = __import__("openpyxl").styles.PatternFill("solid", fgColor="263B66")
        for column_cells in ws.columns:
            letter = column_cells[0].column_letter
            width = min(40, max(12, max(len(str(c.value or "")) for c in column_cells[:50]) + 2))
            ws.column_dimensions[letter].width = width
    return buffer.getvalue()


def make_clean_xlsx(df: pd.DataFrame, log: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    export_df = df.copy()
    for col in detect_pii_columns(export_df):
        export_df[col] = export_df[col].map(lambda x: mask_value(x) if not is_blank(x) else x)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Cleaned data")
        pd.DataFrame([{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in log]).to_excel(writer, index=False, sheet_name="Change log")
        ws = writer.sheets["Cleaned data"]
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = __import__("openpyxl").styles.Font(bold=True, color="FFFFFF")
            cell.fill = __import__("openpyxl").styles.PatternFill("solid", fgColor="263B66")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Samples: sourced from the deterministic demo-data builder
# ---------------------------------------------------------------------------

SAMPLES = build_samples()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    static_index = Path(__file__).resolve().parent / "static" / "index.html"
    if static_index.exists():
        return HTMLResponse(static_index.read_text(encoding="utf-8"))
    return {"name": "OmniLens", "version": APP_VERSION, "message": "Upload a file, get the answer, know what to do next, and share it."}


@app.get("/health")
def health():
    return {"status": "healthy", "version": APP_VERSION, "session_storage": "memory_only", "session_ttl_seconds": SESSION_TTL_SECONDS}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), language: str = Query("en")):
    filename = clean_filename(file.filename or "uploaded_file")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    try:
        df, meta = parse_upload(filename, content)
        sid, analysis = put_session(df, filename, meta, language if language in {"en", "hi", "mr"} else "en")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta_out = dict(meta)
    meta_out["rows_read"] = len(df); meta_out["fields_read"] = len(df.columns)
    return {"session_id": sid, "filename": filename, "import_report": meta_out, "analysis": analysis,
            "privacy": "This app does not save uploaded files to persistent storage. The current result is held temporarily in server memory for this session and expires automatically. The browser sends the file to the OmniLens server you selected.",
            "suggested_questions": get_suggested_questions(df, analysis["shape"])}


def get_suggested_questions(df: pd.DataFrame, shape: dict[str, Any]) -> list[str]:
    if shape["shape"] == "grouped_summary":
        available = set(map(str, df.columns))
        questions = []
        if "District" in available and "Income (Sum)" in available:
            questions.append("Which district has the highest total income?")
        if "Income (Count)" in available and "Income (Sum)" in available:
            questions.append("What is the weighted average income?")
        if "Tax Paid (Sum)" in available:
            questions.append("How much tax was paid in total?")
        if len(questions) < 3 and "Which fields have blank entries?" not in questions:
            questions.append("Which fields have blank entries?")
        return questions[:3]

    dims = shape["dimension_columns"]
    group = next((c for pattern in (r"category", r"district|ward|area|zone|city", r"merchant|recipient", r"department|branch", r"product")
                  for c in dims if re.search(pattern, str(c), re.I)), None)
    status = next((c for c in df.columns if re.search(r"status", c, re.I)), None)
    date = shape["date_column"]
    amount = next((c for pattern in (r"sales|revenue|collection|receipt", r"amount|expense|spend|payment|income", r"profit|cost", r"quantity|count|total|value")
                   for c in shape["numeric_columns"] if re.search(pattern, c, re.I) and not RATE_RE.search(c) and not ID_NAME_RE.search(c)), None)
    questions = []

    if "direction" in {str(c).lower() for c in df.columns} and group:
        category = next((c for c in dims if re.search(r"category", c, re.I)), None)
        if category:
            questions.append("How much did I spend on Food?")
        if any(re.search(r"merchant|recipient", c, re.I) for c in dims):
            questions.append("Which merchant received the most money?")
        if amount and date:
            questions.append(f"Show {amount} by month")
    else:
        if group and amount:
            measure_label = "sales" if re.search(r"sales|revenue", amount, re.I) else amount
            questions.append(f"Which {group} has the highest {measure_label}?")
        if group:
            place = next((c for c in dims if re.search(r"area|district|ward|city", c, re.I)), None)
            if place:
                questions.append(f"Which {place} has the most records?")
            else:
                other_dim = next((c for c in dims if c != group), None)
                if other_dim:
                    questions.append(f"Which {other_dim} appears most often?")
        if amount and date and len(questions) < 3:
            questions.append(f"Show {amount} by month")
    if status and len(questions) < 3:
        questions.append(f"Which {status} appears most often?")
    if "Which fields have blank entries?" not in questions and len(questions) < 3:
        questions.append("Which fields have blank entries?")
    if len(questions) < 3:
        questions.append("Are there duplicate rows in this file?")
    return questions[:3]


class ConfirmShapeRequest(BaseModel):
    session_id: str
    row_meaning: str


@app.post("/api/confirm-rows")
def confirm_rows(request: ConfirmShapeRequest):
    item = get_session(request.session_id)
    mapping = {"person_or_transaction": "records", "group_or_summary": "grouped_summary",
               "measurements_over_time": "time_series", "list_of_names_or_contacts": "register",
               "written_comments": "text_heavy", "area_or_district_summary": "place_based",
               "not_sure": None}
    selected = mapping.get(request.row_meaning)
    if selected is None:
        return {"analysis": item["analysis"], "message": "The general overview is unchanged; no row type was assumed."}
    analysis = build_analysis(item["df"], item["filename"], item["meta"], item["language"], selected)
    item["analysis"] = analysis
    return {"analysis": analysis, "message": "The analysis has been updated using your answer."}


@app.post("/api/sample/{sample_id}")
def sample_analysis(sample_id: str, language: str = Query("en")):
    if sample_id not in SAMPLES:
        raise HTTPException(status_code=404, detail="That example is not available. Choose one of the examples on the home screen.")
    df = SAMPLES[sample_id].copy()
    sid, analysis = put_session(df, f"example_{sample_id}.csv", {"method": "Built-in synthetic example", "note": "All example data is synthetic."}, language)
    descriptions = {
        "shop": "A six-month shop ledger with product sales, costs, payment methods, areas, mixed dates and a few deliberate cleanup examples.",
        "expenses": "A six-month personal money ledger with money in/out, completed and unsuccessful attempts, categories, merchants and masked account/contact fields.",
        "tax": "A synthetic district-wise tax summary with income bands, taxpayer counts, totals, weighted averages and subtotal rows that must not be double-counted.",
        "crime": "A fictional district-level incident register with monthly reports, crime categories, severity, case status and investigation follow-up. It contains no personal names and is not official crime data.",
    }
    return {"session_id": sid, "filename": f"example_{sample_id}.csv", "import_report": {"method": "Built-in synthetic example", "rows_read": len(df), "fields_read": len(df.columns), "note": descriptions.get(sample_id, "Synthetic example data.") + " All values are fictional and created for demonstration."}, "analysis": analysis,
            "privacy": "This example is synthetic. Uploaded files are not saved to persistent storage.", "sample_description": descriptions.get(sample_id, "Synthetic example data."), "suggested_questions": get_suggested_questions(df, analysis["shape"])}


@app.get("/api/sample-file/{sample_name}")
def download_sample_file(sample_name: str):
    """Download a built-in synthetic CSV, including the ready-made compare pair."""
    shop = SAMPLES["shop"].copy()
    if sample_name in {"shop", "expenses", "tax", "crime"}:
        frame = SAMPLES[sample_name].copy()
        filename = {
            "shop": "shop_sales.csv", "expenses": "personal_expenses.csv",
            "tax": "tax_summary.csv", "crime": "crime_statistics.csv",
        }[sample_name]
    elif sample_name in {"shop_earlier", "shop_later"}:
        dates, _ = infer_date_format(shop["date"])
        month_mask = dates.dt.month.between(1, 3) if sample_name == "shop_earlier" else dates.dt.month.between(4, 6)
        frame = shop.loc[month_mask].copy()
        filename = "shop_sales_earlier_period.csv" if sample_name == "shop_earlier" else "shop_sales_later_period.csv"
    else:
        raise HTTPException(status_code=404, detail="That sample file is not available. Choose one of the listed synthetic examples.")
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    return Response(content=payload, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@app.post("/api/ask")
def ask(request: AskRequest):
    item = get_session(request.session_id)
    result = answer_question(item["df"], item["analysis"]["shape"], request.question)
    return result


@app.get("/api/evidence/{session_id}/{finding_id}")
def evidence(session_id: str, finding_id: str):
    item = get_session(session_id)
    finding = next((f for f in item["analysis"]["findings"] if f["id"] == finding_id), None)
    if finding is None:
        raise HTTPException(status_code=404, detail="These rows are no longer available. Analyse the file again.")
    rows = finding["rows"]
    df = item["df"]
    selected = df.loc[[i for i in rows if i in df.index]].copy()
    return {"title": finding["title"], "message": "These are the source rows used for this finding. Sensitive-looking fields are masked in this view.", "rows": masked_records(selected), "count": len(selected)}


@app.get("/api/evidence/{session_id}/{finding_id}/excel")
def evidence_excel(session_id: str, finding_id: str):
    item = get_session(session_id)
    finding = next((f for f in item["analysis"]["findings"] if f["id"] == finding_id), None)
    if finding is None:
        raise HTTPException(status_code=404, detail="The evidence session has expired. Analyse the file again.")
    data = make_evidence_xlsx(item["df"], finding["rows"], item["filename"])
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=OmniLens_evidence_{finding_id[:8]}.xlsx"})


@app.get("/api/share-text/{session_id}")
def share_text(session_id: str):
    item = get_session(session_id)
    return {"text": make_share_text(item)}


@app.get("/api/report/{session_id}")
def report(session_id: str, format: str = Query("pdf")):
    item = get_session(session_id)
    if format.lower() == "pdf":
        data = make_pdf(item); media = "application/pdf"; filename = "OmniLens_report.pdf"
    elif format.lower() in {"docx", "word"}:
        data = make_docx(item); media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"; filename = "OmniLens_report.docx"
    else:
        raise HTTPException(status_code=400, detail="Choose PDF or Word report format.")
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/clean/preview/{session_id}")
def clean_preview(session_id: str):
    item = get_session(session_id)
    return prepare_cleaning(item["df"])


@app.post("/api/clean/preview-approved")
def clean_preview_approved(request: CleanPreviewRequest):
    item = get_session(request.session_id)
    allowed = {"trim_spaces", "normalise_spelling", "standardise_dates", "remove_exact_duplicates"}
    approved = [x for x in request.approved if x in allowed]
    cleaned, log = apply_cleaning(item["df"], approved, request.fuzzy_mappings)
    return {
        "before": masked_records(item["df"].head(6)),
        "after": masked_records(cleaned.head(6)),
        "rows_before": int(len(item["df"])),
        "rows_after": int(len(cleaned)),
        "change_log": log,
        "note": "This is a preview only. The original uploaded file has not been changed.",
    }


@app.post("/api/clean/apply")
def clean_apply(request: CleanApproval):
    item = get_session(request.session_id)
    allowed = {"trim_spaces", "normalise_spelling", "standardise_dates", "remove_exact_duplicates"}
    approved = [x for x in request.approved if x in allowed]
    cleaned, log = apply_cleaning(item["df"], approved, request.fuzzy_mappings)
    if request.output_format.lower() == "csv":
        # Exports are masked by default just like previews and evidence files.
        export_df = cleaned.copy()
        for col in detect_pii_columns(export_df):
            export_df[col] = export_df[col].map(
                lambda value: mask_value(value) if not is_blank(value) else value
            )
        buffer = io.StringIO(); export_df.to_csv(buffer, index=False)
        return Response(buffer.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=OmniLens_cleaned_masked.csv"})
    data = make_clean_xlsx(cleaned, log)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=OmniLens_cleaned.xlsx"})


@app.post("/api/compare")
async def compare(file_a: UploadFile = File(...), file_b: UploadFile = File(...)):
    name_a, name_b = clean_filename(file_a.filename or "file_a"), clean_filename(file_b.filename or "file_b")
    content_a = await file_a.read(MAX_UPLOAD_BYTES + 1); content_b = await file_b.read(MAX_UPLOAD_BYTES + 1)
    await file_a.close(); await file_b.close()
    try:
        a, _ = parse_upload(name_a, content_a); b, _ = parse_upload(name_b, content_b)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return compare_frames(a, b, name_a, name_b)


@app.get("/api/technical/{session_id}")
def technical(session_id: str):
    item = get_session(session_id)
    df = item["df"]
    return {"shape": item["analysis"]["technical"], "column_types": {str(c): str(df[c].dtype) for c in df.columns},
            "blank_cells": int(df.isna().sum().sum()), "duplicate_rows": int(df.duplicated().sum()),
            "date_note": item["analysis"].get("date_notes")}


@app.get("/api/session/{session_id}")
def session_status(session_id: str):
    item = get_session(session_id)
    return {"active": True, "filename": item["filename"], "expires_in_seconds": max(0, SESSION_TTL_SECONDS - int(time.time()-item["created"]))}


@app.delete("/api/session/{session_id}")
@app.post("/api/session/{session_id}/purge")
def purge_session(session_id: str):
    item = SESSIONS.pop(session_id, None)
    if item:
        if "df" in item:
            del item["df"]
        item.clear()
        gc.collect()
        return {"status": "purged", "session_id": session_id, "message": "All session data erased from RAM."}
    return {"status": "not_found", "session_id": session_id, "message": "Session already expired or purged."}


@app.get("/api/privacy-audit")
def privacy_audit():
    return {
        "storage_mode": "in_memory_ram_only",
        "persistent_disk_writes": False,
        "database_connected": False,
        "third_party_telemetry": False,
        "session_ttl_seconds": SESSION_TTL_SECONDS,
        "active_ram_sessions": len(SESSIONS),
        "zero_retention_guarantee": "Data is held solely in bounded volatile RAM and vanishes upon purge, TTL timeout, or server restart."
    }


# Serve the built React app when the frontend build is copied into backend/static
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    @app.get("/", response_class=HTMLResponse)
    def spa_root():
        index = STATIC_DIR / "index.html"
        return HTMLResponse(index.read_text(encoding="utf-8")) if index.exists() else HTMLResponse("OmniLens frontend is not built.")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
