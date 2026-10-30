"""Generate fifteen small synthetic files to regression-test OmniLens ingestion.
Run: python tests/generate_torture_set.py [output_dir]
All records are synthetic and contain no real personal data.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "torture_files"
ROOT.mkdir(parents=True, exist_ok=True)

pd.DataFrame({"invoice_no":[f"I{i:03d}" for i in range(30)], "date":pd.date_range("2025-01-01",periods=30).astype(str), "product_category":["Food","Home","Health"]*10, "sales_amount":[100+i*5 for i in range(30)], "quantity":[1+i%4 for i in range(30)]}).to_csv(ROOT/"01_records_sales.csv",index=False)

groups=[]
for tax, mult in [("Individual",1), ("HUF",.2), ("Company",.5), ("All",1.7)]:
 for band, count, avg in [("0-2.5 lakh",100,80000),("2.5-5 lakh",70,350000),("5-10 lakh",40,700000)]:
  groups.append({"Taxpayer Type":tax,"Income Range":band,"Income (Count)":int(count*mult),"Income (Sum)":count*mult*avg,"Income (Average)":avg})
pd.DataFrame(groups).to_csv(ROOT/"02_grouped_tax.csv",index=False)

pd.DataFrame({"month":pd.date_range("2024-01-01",periods=24,freq="MS").astype(str),"rainfall_mm":[4,8,13,20,65,180,240,160,90,35,12,5]*2}).to_csv(ROOT/"03_time_series.csv",index=False)
pd.DataFrame({"District":["A","B","C"],"Jan":[10,20,30],"Feb":[12,22,31],"Mar":[13,19,35],"Apr":[15,23,36],"May":[17,24,40]}).to_csv(ROOT/"04_wide_table.csv",index=False)
pd.DataFrame({"respondent_id":range(1,31),"satisfaction_rating":[1,2,3,4,5]*6,"service_quality":["Good","Average","Poor"]*10,"would_recommend":["Yes","No"]*15,"feedback_text":["Service was quick and helpful"]*30}).to_csv(ROOT/"05_survey.csv",index=False)
pd.DataFrame({"Full Name":[f"Person {i}" for i in range(1,20)],"Phone Number":[f"98765432{i:02d}" for i in range(1,20)],"Email Address":[f"person{i}@example.test" for i in range(1,20)],"District":["Pune","pune ","PUNE"]*6+[
"Nashik"]}).to_csv(ROOT/"06_register.csv",index=False)
(ROOT/"07_complaint_text.txt").write_text("\n".join(["Water supply has stopped in our street for three days.","Road repair is needed near the school.","Water pressure is low in the morning."]*8),encoding="utf-8")
pd.DataFrame({"district":["Pune","Nashik","Nagpur","Pune"],"pending_cases":[15,10,22,8],"resolved_cases":[100,90,120,80]}).to_csv(ROOT/"08_place_based.csv",index=False)
pd.DataFrame({"Name":["A","B"],"Amount":["1,50,000","₹2,00,000"]}).to_csv(ROOT/"09_indian_numbers.csv",sep=";",index=False)
(ROOT/"10_title_rows.csv").write_text("Monthly Office Report\nPrepared for review\nName,Amount\nA,10\nB,20\nC,30\n",encoding="utf-8")
pd.DataFrame({"transaction_date":["31/01/2025","02/02/2025","2025-03-03","04-03-2025"],"merchant":["A","B","C","D"],"amount":[10,20,30,40],"direction":["Money out"]*4}).to_csv(ROOT/"11_mixed_dates.csv",index=False)
with pd.ExcelWriter(ROOT/"12_excel_multi_sheet.xlsx",engine="openpyxl") as writer:
 pd.DataFrame({"Cover":["Annual Report"]}).to_excel(writer,sheet_name="Cover",index=False)
 pd.DataFrame({"Sales report title":["FY 2025"]}).to_excel(writer,sheet_name="Sales",index=False,header=False)
 pd.DataFrame({"District":["Pune","Nashik"],"Sales Amount":[100,80],"Orders":[10,8]}).to_excel(writer,sheet_name="Sales",startrow=2,index=False)
(ROOT/"13_nested.json").write_text(json.dumps({"meta":{"created":"2025-01-01"},"data":{"records":[{"district":"Pune","cases":4},{"district":"Nashik","cases":7}]}}),encoding="utf-8")
(ROOT/"14_html_table.html").write_text("<html><body><h1>Ward report</h1><table><tr><th>Ward</th><th>Complaints</th></tr><tr><td>1</td><td>12</td></tr><tr><td>2</td><td>18</td></tr></table></body></html>",encoding="utf-8")
pdf=ROOT/"15_pdf_table.pdf"
doc=SimpleDocTemplate(str(pdf),pagesize=A4)
t=Table([["Ward","Complaints"],["1","12"],["2","18"],["3","9"]])
t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.5,colors.black), ("BACKGROUND",(0,0),(-1,0),colors.lightgrey)]))
doc.build([t])
print(f"Generated 15 synthetic torture files in {ROOT}")
