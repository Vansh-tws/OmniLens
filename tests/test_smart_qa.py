from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import main

client = TestClient(main.app)

def test_smart_measure_matching_profit_vs_sales_vs_quantity():
    df = main.SAMPLES["shop"]
    shape = main.detect_shape(df)
    
    # 1. Gross profit vs Sales amount
    sales_res = main.answer_question(df, shape, "What is the total sales amount?")
    profit_res = main.answer_question(df, shape, "What is the total gross profit?")
    qty_res = main.answer_question(df, shape, "Total quantity sold")
    avg_price_res = main.answer_question(df, shape, "What is the average unit price?")
    
    expected_sales = df["sales_amount_inr"].sum()
    expected_profit = df["gross_profit_inr"].sum()
    expected_qty = df["quantity"].sum()
    expected_avg_price = df["unit_price_inr"].mean()
    
    assert f"{expected_sales:,.2f}" in sales_res["answer"]
    assert f"{expected_profit:,.2f}" in profit_res["answer"]
    assert "gross_profit_inr" in profit_res["answer"]
    assert f"{expected_qty:,.2f}" in qty_res["answer"]
    assert "quantity" in qty_res["answer"]
    assert f"{expected_avg_price:,.2f}" in avg_price_res["answer"]
    assert "unit_price_inr" in avg_price_res["answer"]

def test_smart_extreme_value_lookups():
    shop_df = main.SAMPLES["shop"]
    shop_shape = main.detect_shape(shop_df)
    
    # Highest sale record
    highest_sale = main.answer_question(shop_df, shop_shape, "What was the highest sale?")
    max_sale_val = shop_df["sales_amount_inr"].max()
    assert f"{max_sale_val:,.2f}" in highest_sale["answer"]
    assert highest_sale["evidence_indices"]
    
    # Cheapest product (Potato chips family pack ~40 INR)
    cheapest = main.answer_question(shop_df, shop_shape, "What was the cheapest product?")
    assert "Potato chips" in cheapest["answer"]
    
    # Biggest expense in personal expenses
    exp_df = main.SAMPLES["expenses"]
    exp_shape = main.detect_shape(exp_df)
    biggest_exp = main.answer_question(exp_df, exp_shape, "What was my biggest expense?")
    max_expense_val = exp_df[exp_df["direction"] == "Money out"]["amount_inr"].max()
    assert f"{max_expense_val:,.2f}" in biggest_exp["answer"]
    
    # Crime days to resolution
    crime_df = main.SAMPLES["crime"]
    crime_shape = main.detect_shape(crime_df)
    max_days = main.answer_question(crime_df, crime_shape, "Highest days to resolution")
    assert f"{crime_df['Investigation Days'].max():,.2f}" in max_days["answer"]

def test_smart_dynamic_filtering_by_cell_value():
    df = main.SAMPLES["shop"]
    shape = main.detect_shape(df)
    
    # Filter by Area "Pune"
    pune_res = main.answer_question(df, shape, "Total sales in Pune")
    pune_expected = df[df["area"].astype(str).str.strip().str.lower() == "pune"]["sales_amount_inr"].sum()
    assert f"{pune_expected:,.2f}" in pune_res["answer"]
    assert "area='Pune'" in pune_res["answer"]
    
    # Filter by Payment method "UPI" row count
    upi_res = main.answer_question(df, shape, "How many transactions were paid using UPI?")
    upi_count = len(df[df["payment_method"].str.lower() == "upi"])
    assert f"{upi_count:,}" in upi_res["answer"]
    assert "payment_method='UPI'" in upi_res["answer"]
    
    # Filter by Status "Failed"
    exp_df = main.SAMPLES["expenses"]
    exp_shape = main.detect_shape(exp_df)
    failed_res = main.answer_question(exp_df, exp_shape, "How many transactions failed?")
    failed_count = len(exp_df[exp_df["status"].str.lower() == "failed"])
    assert f"{failed_count}" in failed_res["answer"]
    assert "failed" in failed_res["answer"]

def test_smart_unique_count_and_date_range_and_duplicates():
    shop_df = main.SAMPLES["shop"]
    shop_shape = main.detect_shape(shop_df)
    
    # Unique products
    uniq_prod = main.answer_question(shop_df, shop_shape, "How many unique products are there?")
    assert "12" in uniq_prod["answer"]
    assert "product" in uniq_prod["answer"]
    
    # Date range
    date_rng = main.answer_question(shop_df, shop_shape, "What is the date range of these records?")
    assert "2025-01-01" in date_rng["answer"]
    assert "2025-06-28" in date_rng["answer"]
    
    # Duplicates
    dup_res = main.answer_question(shop_df, shop_shape, "Are there duplicate records in this file?")
    assert "duplicate" in dup_res["answer"]
    assert dup_res["evidence_indices"]

def test_smart_breakdown_by_payment_method_and_incident_type():
    shop_df = main.SAMPLES["shop"]
    shop_shape = main.detect_shape(shop_df)
    
    pay_res = main.answer_question(shop_df, shop_shape, "Show sales by payment method")
    assert "UPI" in pay_res["answer"]
    assert pay_res["chart"] is not None
    assert len(pay_res["chart"]["labels"]) > 0
    
    crime_df = main.SAMPLES["crime"]
    crime_shape = main.detect_shape(crime_df)
    inc_res = main.answer_question(crime_df, crime_shape, "Which incident type occurs most often?")
    assert "Theft" in inc_res["answer"]
    assert inc_res["chart"] is not None

def test_multilingual_hindi_and_marathi_questions():
    shop_df = main.SAMPLES["shop"]
    shop_shape = main.detect_shape(shop_df)
    
    # Hindi total sales: कुल बिक्री कितनी है?
    hindi_sales = main.answer_question(shop_df, shop_shape, "कुल बिक्री कितनी है?")
    expected_sales = shop_df["sales_amount_inr"].sum()
    assert f"{expected_sales:,.2f}" in hindi_sales["answer"]
    
    # Hindi food expense: भोजन पर कितना खर्च हुआ?
    exp_df = main.SAMPLES["expenses"]
    exp_shape = main.detect_shape(exp_df)
    hindi_food = main.answer_question(exp_df, exp_shape, "भोजन पर कितना खर्च हुआ?")
    expected_food = exp_df[
        exp_df["category"].astype(str).str.strip().str.casefold().eq("food")
        & exp_df["direction"].eq("Money out")
        & exp_df["status"].eq("Completed")
    ]["amount_inr"].sum()
    assert f"{expected_food:,.2f}" in hindi_food["answer"]
    assert "Outgoing transactions only" in hindi_food["answer"]
    
    # Hindi pending cases: पेंडिंग केस कितने हैं?
    crime_df = main.SAMPLES["crime"]
    crime_shape = main.detect_shape(crime_df)
    hindi_pending = main.answer_question(crime_df, crime_shape, "पेंडिंग केस कितने हैं?")
    pending_count = len(crime_df[crime_df["Case Status"].str.lower().str.contains("pending")])
    assert f"{pending_count}" in hindi_pending["answer"]
