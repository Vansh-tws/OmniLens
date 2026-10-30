"""Deterministic, synthetic demo data for OmniLens.

The examples are deliberately designed to exercise the main user journey:
headline analysis, useful charts, row evidence, cleaning preview, Indian-format
checks, natural-language questions, masked exports, reports and file comparison.
They are not real customer, taxpayer or payment records.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd


SEED = 50301

SHOP_PRODUCTS = [
    ("Basmati rice 5 kg", "Groceries", 690, 555),
    ("Toor dal 1 kg", "Groceries", 168, 136),
    ("Sunflower oil 1 L", "Groceries", 154, 127),
    ("Assam tea 500 g", "Beverages", 285, 218),
    ("Instant coffee 100 g", "Beverages", 175, 132),
    ("Full cream milk 1 L", "Dairy", 72, 56),
    ("Paneer 200 g", "Dairy", 98, 75),
    ("Digestive biscuits", "Snacks", 45, 31),
    ("Potato chips family pack", "Snacks", 40, 27),
    ("Bath soap 125 g", "Personal Care", 62, 43),
    ("Laundry detergent 1 kg", "Household", 145, 109),
    ("Floor cleaner 1 L", "Household", 118, 84),
]


def _date_text(d: date, index: int) -> str:
    # A mix of recognised ISO and day-first dates makes date cleaning visible,
    # while dates with day > 12 keep the Indian interpretation unambiguous.
    if index % 5 == 0:
        return d.strftime("%Y-%m-%d")
    if index % 5 == 1:
        return d.strftime("%d/%m/%Y")
    if index % 5 == 2:
        return d.strftime("%d-%m-%Y")
    if index % 5 == 3:
        return d.strftime("%d.%m.%Y")
    return d.strftime("%Y-%m-%d")


def build_shop_sales() -> pd.DataFrame:
    rng = random.Random(SEED)
    rows = []
    month_factors = [0.92, 1.00, 1.13, 1.18, 1.08, 0.79]
    areas = ["Pune", "Nashik", "Nagpur", "Mumbai", "Thane"]
    payment_methods = ["UPI", "Cash", "Card", "Bank transfer"]
    channels = ["In store", "WhatsApp order", "Phone order"]
    customer_types = ["Regular", "New", "Wholesale"]
    gstins = ["27ABCDE1234F1Z5", "27PQRSX5678L1Z2", "27LMNOP4321Q1Z7"]
    phone_base = 9000001000

    for month in range(1, 7):
        # 48 records/month gives enough evidence for stable charts and findings.
        for j in range(48):
            index = (month - 1) * 48 + j
            day = 1 + ((j * 3 + month * 2) % 28)
            d = date(2025, month, day)
            product, category, unit_price, unit_cost = SHOP_PRODUCTS[(j * 5 + month * 3) % len(SHOP_PRODUCTS)]
            qty = 1 + ((j * 7 + month) % 5)
            if j == 17 and month == 3:
                # A legitimate but unusually large wholesale order.
                qty = 34
            seasonal = month_factors[month - 1]
            noise = rng.uniform(0.92, 1.09)
            unit_price_real = round(unit_price * noise, 2)
            sales = round(unit_price_real * qty * seasonal, 2)
            cost = round(unit_cost * qty, 2)
            area = areas[(j + month) % len(areas)]
            category_value = category
            if index % 37 == 0 and category == "Groceries":
                category_value = "groceries"
            elif index % 41 == 0 and category == "Personal Care":
                category_value = "Personal care "
            if index % 29 == 0 and area == "Pune":
                area = "pune "
            elif index % 31 == 0 and area == "Pune":
                area = "PUNE"

            row = {
                "transaction_id": f"TXN-{index + 1:05d}",
                "invoice_no": f"INV-25-{index + 1:05d}",
                "date": _date_text(d, index),
                "product": product,
                "category": category_value,
                "quantity": qty,
                "unit_price_inr": unit_price_real,
                "sales_amount_inr": sales,
                "cost_amount_inr": cost,
                "gross_profit_inr": round(sales - cost, 2),
                "payment_method": payment_methods[(j + month) % len(payment_methods)],
                "customer_type": customer_types[(j * 2 + month) % len(customer_types)],
                "area": area,
                "sales_channel": channels[(j + month * 2) % len(channels)],
                "customer_phone": str(phone_base + index),
                "customer_email": f"buyer{index + 1}@example.test",
                "supplier_gstin": gstins[(j + month) % len(gstins)],
                "order_status": "Returned" if index in {33, 147, 221} else "Completed",
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    # Deliberate, explainable data-quality issues for the Fix and See Rows flows.
    df.loc[12, "sales_amount_inr"] = None
    df.loc[87, "sales_amount_inr"] = None
    df.loc[156, "sales_amount_inr"] = None
    df.loc[21, "customer_phone"] = "12345"  # format-only warning, not a real phone
    df.loc[42, "customer_phone"] = None
    # Add two exact duplicate invoice rows so the duplicate preview can be shown.
    df = pd.concat([df, df.loc[[26, 173]]], ignore_index=True)
    return df


def build_personal_expenses() -> pd.DataFrame:
    rng = random.Random(SEED + 1)
    rows = []
    categories = ["Food", "Travel", "Housing", "Bills", "Health", "Education", "Shopping"]
    descriptions = {
        "Food": ["Groceries", "Vegetables", "Lunch", "Dinner", "Milk and bread", "Monthly ration"],
        "Travel": ["Bus pass", "Auto fare", "Petrol", "Metro card", "Train ticket"],
        "Housing": ["Monthly rent", "Society maintenance"],
        "Bills": ["Electricity bill", "Mobile recharge", "Internet bill", "Cooking gas"],
        "Health": ["Pharmacy", "Doctor consultation", "Medical tests"],
        "Education": ["Books", "Course fee", "Stationery"],
        "Shopping": ["Clothing", "Household item", "Footwear", "Online purchase"],
    }
    merchants = {
        "Food": ["Local grocery", "Fresh Basket", "Market Store", "Daily Needs"],
        "Travel": ["City Bus", "Metro Services", "Fuel Station", "Rail Ticketing"],
        "Housing": ["Landlord Transfer", "Society Office"],
        "Bills": ["Power Utility", "Mobile Network", "Internet Provider", "Gas Agency"],
        "Health": ["City Pharmacy", "Care Clinic", "Diagnostic Centre"],
        "Education": ["Book House", "Learning Centre", "Campus Store"],
        "Shopping": ["General Store", "Online Marketplace", "Clothing Shop"],
    }
    amount_ranges = {
        "Food": (90, 1600), "Travel": (35, 1100), "Housing": (12000, 16500),
        "Bills": (250, 3200), "Health": (180, 8500), "Education": (250, 6500),
        "Shopping": (250, 9500),
    }
    payment_methods = ["UPI", "Debit card", "Cash", "Net banking"]
    phone_base = 9100002000
    ifscs = ["HDFC0000123", "SBIN0000456", "ICIC0000789", "UTIB0000234"]
    pan_examples = ["ABCDE1234F", "PQRSX5678L", "LMNOP4321Q"]
    counter = 0

    for month in range(1, 7):
        # A steady set of monthly activity with a salary and recurring rent.
        month_records = []
        salary_date = date(2025, month, 1)
        month_records.append({
            "date": _date_text(salary_date, counter), "description": "Monthly salary credit",
            "category": "Income", "direction": "Money in", "amount_inr": 42000 + (month - 1) * 500,
            "status": "Completed", "merchant": "Employer Payroll", "payment_method": "Bank transfer",
        })
        counter += 1
        rent_date = date(2025, month, 5)
        month_records.append({
            "date": _date_text(rent_date, counter), "description": "Monthly rent payment",
            "category": "Housing", "direction": "Money out", "amount_inr": 14500 + (month % 2) * 500,
            "status": "Completed", "merchant": "Landlord Transfer", "payment_method": "UPI",
        })
        counter += 1

        for j in range(43):
            category = categories[(j * 3 + month * 2) % len(categories)]
            desc = rng.choice(descriptions[category])
            low, high = amount_ranges[category]
            amount = round(rng.uniform(low, high), 2)
            direction = "Money out"
            merchant = rng.choice(merchants[category])
            # Occasionally record a refund or transfer received.
            if j in {8, 25}:
                direction = "Money in"
                category = "Refund" if j == 8 else "Other income"
                desc = "Purchase refund" if j == 8 else "Family transfer received"
                merchant = "Marketplace Refund" if j == 8 else "Family Transfer"
                amount = round(rng.uniform(250, 2200), 2)
            status = "Completed"
            if j in {11, 36}:
                status = "Failed"
            elif j == 20:
                status = "Pending"
            elif (month + j) % 53 == 0:
                status = "Pending"
            d = date(2025, month, 1) + timedelta(days=(j * 2 + month) % 27)
            month_records.append({
                "date": _date_text(d, counter), "description": desc,
                "category": category, "direction": direction, "amount_inr": amount,
                "status": status, "merchant": merchant,
                "payment_method": payment_methods[(j + month) % len(payment_methods)],
            })
            counter += 1

        for record in month_records:
            record.update({
                "transaction_id": f"PAY-{counter:05d}",
                "account_type": "Savings account",
                "phone_number": str(phone_base + counter),
                "email": f"demo.user{counter}@example.test",
                "bank_ifsc": ifscs[(counter + month) % len(ifscs)],
                "pan": pan_examples[(counter + month) % len(pan_examples)],
                "reference_no": f"UPI25{counter:012d}",
            })
            rows.append(record)
            counter += 1

    df = pd.DataFrame(rows)
    # Category variants make spelling/spacing suggestions visible.
    food_indices = df.index[df["category"].eq("Food")].tolist()
    if len(food_indices) >= 5:
        df.loc[food_indices[1], "category"] = "food "
        df.loc[food_indices[3], "category"] = "FOOD"
    df.loc[17, "description"] = "  " + str(df.loc[17, "description"]) + "  "
    df.loc[58, "amount_inr"] = None
    df.loc[119, "phone_number"] = None
    df.loc[143, "bank_ifsc"] = "BADIFSC000"  # deliberately malformed synthetic test value
    # A repeated line tests exact duplicate detection. It remains clearly synthetic.
    df = pd.concat([df, df.loc[[76]]], ignore_index=True)
    return df


def _tax_metrics(count: int, band_index: int, district_factor: float, type_factor: float, year_factor: float) -> dict[str, float | int]:
    avg_income = [185000, 365000, 735000, 1620000][band_index] * year_factor
    income_count = max(1, int(count * year_factor))
    income_sum = round(income_count * avg_income, 2)
    taxable_ratio = [0.18, 0.72, 0.91, 0.96][band_index]
    taxable_count = int(income_count * taxable_ratio)
    taxable_income_sum = round(income_sum * taxable_ratio * 0.91, 2)
    tax_rate = [0.0, 0.035, 0.075, 0.135][band_index]
    tax_paid_count = int(taxable_count * [0.86, 0.90, 0.94, 0.97][band_index])
    tax_paid_sum = round(taxable_income_sum * tax_rate, 2)
    refund_count = int(income_count * [0.025, 0.045, 0.06, 0.08][band_index])
    refund_sum = round(refund_count * [1200, 3200, 7800, 18500][band_index] * district_factor, 2)
    return {
        "Income (Count)": income_count,
        "Income (Sum)": income_sum,
        "Income (Average)": round(income_sum / income_count, 2),
        "Tax Paid (Count)": tax_paid_count,
        "Tax Paid (Sum)": tax_paid_sum,
        "Tax Paid (Average)": round(tax_paid_sum / tax_paid_count, 2) if tax_paid_count else 0,
        "Refund (Count)": refund_count,
        "Refund (Sum)": refund_sum,
        "Refund (Average)": round(refund_sum / refund_count, 2) if refund_count else 0,
    }


def build_tax_summary() -> pd.DataFrame:
    districts = [
        ("Pune", 1.48), ("Mumbai Suburban", 1.72), ("Nagpur", 1.15),
        ("Nashik", 1.08), ("Thane", 1.32), ("Kolhapur", 0.82),
        ("Amravati", 0.71), ("Chhatrapati Sambhajinagar", 0.94),
    ]
    taxpayer_types = [("Individual", 1.0), ("HUF", 0.12), ("Company", 0.34)]
    bands = ["0-2.5 lakh", "2.5-5 lakh", "5-10 lakh", "Above 10 lakh"]
    band_base_counts = [760, 540, 365, 190]
    type_base_counts = {"Individual": 1.0, "HUF": 0.10, "Company": 0.25}
    years = [("2024-25", 1.0), ("2025-26", 1.075)]
    rows = []

    for district, district_factor in districts:
        for taxpayer_type, type_factor in taxpayer_types:
            for band_idx, band in enumerate(bands):
                for assessment_year, year_factor in years:
                    base = band_base_counts[band_idx] * type_base_counts[taxpayer_type] * district_factor
                    count = max(1, int(base * year_factor))
                    metrics = _tax_metrics(count, band_idx, district_factor, type_factor, year_factor)
                    rows.append({
                        "District": district,
                        "Taxpayer Type": taxpayer_type,
                        "Income Band": band,
                        "Assessment Year": assessment_year,
                        "Income Range Order": band_idx + 1,
                        **metrics,
                    })

    # District/year subtotals and one grand total are supplied by the report.
    # OmniLens must exclude these from rankings rather than adding them again.
    base_df = pd.DataFrame(rows)
    metric_cols = [c for c in base_df.columns if c.endswith("(Count)") or c.endswith("(Sum)")]
    for district, _factor in districts:
        for assessment_year, _year_factor in years:
            subset = base_df[(base_df["District"] == district) & (base_df["Assessment Year"] == assessment_year)]
            record = {"District": district, "Taxpayer Type": "All", "Income Band": "All",
                      "Assessment Year": assessment_year, "Income Range Order": 0}
            for col in metric_cols:
                record[col] = int(subset[col].sum()) if col.endswith("(Count)") else round(float(subset[col].sum()), 2)
            for avg_col in [c for c in base_df.columns if c.endswith("(Average)")]:
                base = avg_col.rsplit(" (", 1)[0]
                count_col, sum_col = f"{base} (Count)", f"{base} (Sum)"
                record[avg_col] = round(record[sum_col] / record[count_col], 2) if record[count_col] else 0
            rows.append(record)

    # Grand total across every district, entity type, income band and year.
    record = {"District": "All", "Taxpayer Type": "All", "Income Band": "All",
              "Assessment Year": "All", "Income Range Order": 0}
    all_detail = base_df
    for col in metric_cols:
        record[col] = int(all_detail[col].sum()) if col.endswith("(Count)") else round(float(all_detail[col].sum()), 2)
    for avg_col in [c for c in base_df.columns if c.endswith("(Average)")]:
        base = avg_col.rsplit(" (", 1)[0]
        count_col, sum_col = f"{base} (Count)", f"{base} (Sum)"
        record[avg_col] = round(record[sum_col] / record[count_col], 2) if record[count_col] else 0
    rows.append(record)

    return pd.DataFrame(rows)



def build_crime_statistics() -> pd.DataFrame:
    """Create synthetic district-level incident records for the Government demo.

    This is a fictional teaching dataset. It contains no victim, suspect, or
    officer names and must never be presented as official crime statistics.
    """
    rng = random.Random(SEED + 2)
    monthly_counts = [20, 21, 22, 23, 22, 24, 27, 28, 31, 30, 27, 25]
    districts = [
        "Pune City", "Mumbai Suburban", "Nagpur", "Nashik",
        "Thane", "Kolhapur", "Satara", "Ahmednagar",
    ]
    category_weights = {
        "Theft": [22, 22, 20, 19, 21, 18, 17, 16],
        "Cybercrime": [18, 22, 21, 20, 20, 14, 13, 15],
        "Vehicle Theft": [17, 18, 15, 14, 16, 13, 12, 11],
        "Fraud": [15, 17, 16, 15, 16, 13, 12, 13],
        "Assault": [12, 8, 12, 13, 10, 15, 16, 14],
        "Burglary": [9, 8, 9, 10, 9, 12, 13, 14],
        "Public Disturbance": [7, 5, 7, 9, 8, 15, 17, 17],
    }
    stations = {
        "Pune City": ["Shivajinagar", "Kothrud", "Hadapsar"],
        "Mumbai Suburban": ["Andheri", "Borivali", "Kurla"],
        "Nagpur": ["Sitabuldi", "Sadar", "Mankapur"],
        "Nashik": ["Panchavati", "Gangapur", "Ambad"],
        "Thane": ["Naupada", "Vartak Nagar", "Kopri"],
        "Kolhapur": ["Shahupuri", "Rajwada", "Rajarampuri"],
        "Satara": ["Satara City", "Karad", "Wai"],
        "Ahmednagar": ["Kotwali", "Toufkhana", "MIDC"],
    }
    categories = list(category_weights)
    weights_by_month_and_district = {}
    for month in range(1, 13):
        for district_index in range(len(districts)):
            weights_by_month_and_district[(month, district_index)] = [
                category_weights[category][district_index]
                + (4 if category == "Cybercrime" and month >= 8 else 0)
                + (3 if category == "Fraud" and month >= 9 else 0)
                for category in categories
            ]
    rows = []
    serial = 1
    channels = ["Police station", "Emergency call", "Citizen portal", "Helpline"]
    for month, count in enumerate(monthly_counts, start=1):
        for j in range(count):
            district_index = (j * 3 + month * 2 + rng.randrange(0, 3)) % len(districts)
            district = districts[district_index]
            category = rng.choices(categories, weights=weights_by_month_and_district[(month, district_index)], k=1)[0]
            incident_day = 1 + ((j * 5 + month * 3) % 28)
            incident_date = date(2025, month, incident_day)
            severity = rng.choices(["Low", "Medium", "High"], weights=[35, 48, 17], k=1)[0]
            case_status = rng.choices(
                ["Closed", "Under investigation", "Pending"],
                weights=[62, 27, 11], k=1,
            )[0]
            investigation_days = None if serial % 47 == 0 else int(rng.triangular(2, 75, 18))
            loss_ranges = {
                "Theft": (1000, 65000), "Cybercrime": (2500, 180000),
                "Vehicle Theft": (15000, 250000), "Fraud": (5000, 220000),
                "Assault": (0, 15000), "Burglary": (3000, 125000),
                "Public Disturbance": (0, 5000),
            }
            loss_low, loss_high = loss_ranges[category]
            estimated_loss = round(rng.uniform(loss_low, loss_high), 2)
            date_index = serial
            date_value = _date_text(incident_date, date_index)
            # A few case-category text variants demonstrate safe whitespace/case review.
            category_value = category
            if serial % 89 == 0:
                category_value = category.lower()
            elif serial % 97 == 0:
                category_value = f" {category} "
            rows.append({
                "Case ID": f"DEMO-CR-{serial:05d}",
                "Incident Date": date_value,
                "District": district,
                "Police Station": rng.choice(stations[district]),
                "Crime Category": category_value,
                "Severity": severity,
                "Case Status": case_status,
                "Reported Through": channels[(serial + month) % len(channels)],
                "Case Count": 1,
                "Investigation Days": investigation_days,
                "Estimated Property Loss (INR)": estimated_loss,
            })
            serial += 1

    frame = pd.DataFrame(rows)
    # These blank operational durations are deliberate, visible examples for
    # the review-and-clean workflow; they do not remove or alter incidents.
    frame.loc[14, "Investigation Days"] = None
    frame.loc[113, "Investigation Days"] = None
    return frame

def build_samples() -> dict[str, pd.DataFrame]:
    return {
        "shop": build_shop_sales(),
        "expenses": build_personal_expenses(),
        "tax": build_tax_summary(),
        "crime": build_crime_statistics(),
    }


def write_sample_files(output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    samples = build_samples()
    paths = {}
    names = {
        "shop": "shop_sales.csv", "expenses": "personal_expenses.csv",
        "tax": "tax_summary.csv", "crime": "crime_statistics.csv",
    }
    for key, frame in samples.items():
        path = output / names[key]
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[key] = path

    # Two matching sales-period files give the comparison screen a ready-made demo.
    shop = samples["shop"].copy()
    parsed = pd.to_datetime(shop["date"], dayfirst=True, errors="coerce", format="mixed")
    prev = shop.loc[parsed.dt.month.between(1, 3)].copy()
    curr = shop.loc[parsed.dt.month.between(4, 6)].copy()
    paths["shop_earlier"] = output / "shop_sales_earlier_period.csv"
    paths["shop_current"] = output / "shop_sales_later_period.csv"
    prev.to_csv(paths["shop_earlier"], index=False, encoding="utf-8-sig")
    curr.to_csv(paths["shop_current"], index=False, encoding="utf-8-sig")
    return paths
