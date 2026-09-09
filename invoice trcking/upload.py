import pandas as pd
from supabase import create_client
import numpy as np

# ── Config ────────────────────────────────────────────────
SUPABASE_URL = 'https://rcfivcosgxtghhcedqhv.supabase.co';  
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJjZml2Y29zZ3h0Z2hoY2VkcWh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcyNTg1MTcsImV4cCI6MjA5MjgzNDUxN30.T7cwDxpm9c3u07demXvwatzxWEiYWzldRhPqaW2G26s';
EXCEL_FILE = r"C:\Users\bedoor.alsulami\OneDrive - Algihaz\Documents\invoice-app-try\Projects list.xlsx"
TABLE_NAME   = "project_tracker"


# ── Column mapping: Excel header → SQL column name ────────
COLUMN_MAP = {
    "Project name":                                 "project_name",
    "Contract No.":                                 "contract_no",
    "Cost center ":                                 "cost_center",
    "Business unit":                                "business_unit",
    "Client":                                       "client",
    "LC actual":                                    "lc_actual",
    "LC %":                                         "lc_pct",
    "Goods & Services Plan":                        "goods_services_plan",
    "Goods & Services Actual":                      "goods_services_actual",
    "Plan Of Headcount Skilled/Semi ":              "hc_skilled_semi_plan",
    "Plan Of Headcount Management ":                "hc_management_plan",
    "Plan Of Headcount Total":                      "hc_total_plan",
    "Actual":                                       "hc_actual",
    "Plan Of Compensation Skilled/Semi ":           "comp_skilled_semi_plan",
    "Plan Of Compensation Management ":             "comp_management_plan",
    "Plan Of Compensation Total":                   "comp_total_plan",
    "Actual Jan 2026":                              "comp_actual_jan2026",
    "Plan Of Headcount Skilled/Semi _1":            "hc_skilled_semi_plan_2",
    "Plan Of Headcount Management _2":              "hc_management_plan_2",
    "Plan Of Headcount Total_3":                    "hc_total_plan_2",
    "Actual_4":                                     "hc_actual_2",
    "Plan Of Compensation Skilled/Semi _5":         "comp_skilled_semi_plan_2",
    "Plan Of Compensation Management _6":           "comp_management_plan_2",
    "Plan Of Compensation Total_7":                 "comp_total_plan_2",
    "Actual_8":                                     "comp_actual_2",
    "Project manager":                              "project_manager",
    "Project head manager":                         "project_head_manager",
    "Duration (include extention separately if any)": "duration_notes",
    "Date Notice of Award":                         "date_notice_of_award",
    "Start date":                                   "start_date",
    "End date":                                     "end_date",
    "Project value":                                "project_value",
    "LC auditor (if any)":                          "lc_auditor",
    "How many reports submitted to client ":        "reports_submitted_to_client",
    "Attach the contract":                          "contract_attachment",
    "Dates are confirmed? (Yes/ No), in case of extention, mention the date explicitly": "dates_confirmed",
    "Updated TCC due date":                         "updated_tcc_due_date",
    "Updated PAC due date":                         "updated_pac_due_date",
    "Updated FAC due date":                         "updated_fac_due_date",
    "Which last Certifiacte is issued? from AM to AO": "last_certificate_issued",
    "in case project is completed, did we get the bond? (Yes/ No/ Not applicable)": "bond_received",
}

# ── Load Excel ─────────────────────────────────────────────
df = pd.read_excel(EXCEL_FILE, dtype=str)   # dtype=str keeps everything as text
df = pd.read_excel(EXCEL_FILE, dtype=str)

# ADD THESE 3 LINES to see what's happening
print("Rows found:", len(df))
print("Columns in your Excel:")
for col in df.columns:
    print(f"  '{col}'")

df = df.rename(columns=COLUMN_MAP)
df = df[[col for col in COLUMN_MAP.values() if col in df.columns]]

# ── Clean up: replace NaN/blanks with None (NULL in Supabase) ──
df = df.replace({np.nan: None, "nan": None, "NaT": None, "": None})

# ── Upload in batches ──────────────────────────────────────
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
records  = df.to_dict(orient="records")
BATCH    = 50

for i in range(0, len(records), BATCH):
    batch = records[i : i + BATCH]
    res   = supabase.table(TABLE_NAME).insert(batch).execute()
    print(f"Inserted rows {i+1}–{min(i+BATCH, len(records))}")

print("✅ Done!") 

