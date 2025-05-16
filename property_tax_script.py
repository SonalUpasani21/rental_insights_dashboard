import os
import time
import json
import vertexai
import pandas as pd
import gspread
from google.cloud import storage
from vertexai.preview.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
from gspread.exceptions import WorksheetNotFound

# === USER INPUT === #
project_id = input("Enter your Google Cloud project ID: ").strip()
bucket_name = input("Enter your Cloud Storage bucket name: ").strip()
folder_path = input("Enter the folder path inside the bucket (e.g., tax/): ").strip()
sheet_name = input("Enter the name of your Google Sheet (created manually): ").strip()
service_account_file = input("Enter path to your service account JSON (e.g., sa.json): ").strip()

# === CREDENTIALS === #
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
gcp_creds = service_account.Credentials.from_service_account_file(service_account_file)
gsheets_creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)

vertexai.init(project=project_id, location="us-central1", credentials=gcp_creds)
gsheets_client = gspread.authorize(gsheets_creds)
storage_client = storage.Client(credentials=gcp_creds)

# === GET EXISTING SHEET + CREATE TAB IF NEEDED === #
def get_or_create_summary_sheet(sheet_name, tab_name, headers):
    spreadsheet = gsheets_client.open(sheet_name)

    try:
        worksheet = spreadsheet.worksheet(tab_name)
        print(f"📄 Found existing tab: {tab_name}")
    except WorksheetNotFound:
        print(f"Tab '{tab_name}' not found. Creating it in your Google Sheet...")
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="20")
        worksheet.insert_row(headers, index=1)

    return worksheet

summary_headers = [
    "Property Address", "Roll Number", "Assessment Value", "Year", "Tax Rate Used",
    "Property Tax", "First Half Payment", "Second Half Payment", "Monthly Payment"
]

summary_sheet = get_or_create_summary_sheet(sheet_name, "Property Tax Summary", summary_headers)

# === GEMINI PROMPT === #
prompt = """

Extract structured property tax data from each uploaded property assessment and tax levy PDF. Each PDF contains data for a single property.

Return a flat structured table (CSV or list of JSON objects). Each row must include the following columns:

- Property Address
- Roll Number
- Assessment Value
- Year (2021 to 2025)
- Tax Rate Used
- Property Tax
- First Half Payment (50% of the previous year's Property Tax)
- Second Half Payment (Property Tax - First Half), except for 2025
- Monthly Payment (Property Tax ÷ 12)

Year-by-Year Calculation Rules:

1. **Tax Rate Used**:
   - Extract from PDF if shown.
   - If missing, use these City of Kingston residential tax rates:
     - 2020: 1.309528%
     - 2021: 1.365454%
     - 2022: 1.399366%
     - 2023: 1.444608%
     - 2024: 1.478321%
     - 2025: 1.556000% (only if confirmed)

2. **Property Tax**:
   - Extract from PDF if available.
   - If missing, calculate as:
     `Property Tax = Assessment Value × Tax Rate Used`

3. **First Half Payment**:
   - For 2021:
     - Use the 2020 tax calculated as:
       `Assessment Value × 1.309528%`
     - First Half = 50% of that amount
   - For 2022 to 2025:
     - First Half = 50% of the **previous year’s** Property Tax
       (use either extracted or calculated value)

4. **Second Half Payment**:
   - For 2021 to 2024:  
     `Second Half = Property Tax - First Half`
   - For 2025:  
     `Second Half = 0.0` (2025 final bill not yet available)

5. **Monthly Payment**:
   - `Monthly = Property Tax ÷ 12`

Output Format & Requirements:

- Always extract Property Address and Roll Number exactly as shown in the PDF.
- Use year-specific Assessment Values if available; otherwise reuse the only one listed.
- Round all numeric values (taxes, rates, payments) to 2 decimal places.
- Output must be clean, machine-readable (CSV or JSON).
- Do not leave any fields blank or null unless data is entirely unavailable and cannot be inferred.

Goal:

To automate the accurate and complete extraction of property tax records across 2021 to 2025, reflecting the City of Kingston's billing model — including interim/final split logic, default rate handling, and safeguards for missing future data like 2025’s final tax.

"""

# === INITIALIZE GEMINI === #
model = GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"}
)

# === GET PDF FILES FROM GCS === #
def get_pdf_uris(bucket_name, folder_path):
    blobs = storage_client.list_blobs(bucket_name, prefix=folder_path)
    return [f"gs://{bucket_name}/{blob.name}" for blob in blobs if blob.name.endswith(".pdf")]

# === LOAD EXISTING RECORD KEYS === #
def load_existing_keys(sheet):
    rows = sheet.get_all_values()[1:]  # Skip header
    return {(row[0].strip(), row[3].strip()) for row in rows if len(row) >= 4}  # (Property Address, Year)

# === PROCESS INDIVIDUAL PDF === #
def process_pdf(pdf_uri, summary_sheet, existing_keys):
    print(f"\nProcessing: {pdf_uri}")
    try:
        part = Part.from_uri(pdf_uri, mime_type="application/pdf")
        response = model.generate_content([part, prompt])
        records = json.loads(response.text)

        if not isinstance(records, list):
            records = [records]

        new_rows = []
        for rec in records:
            key = (rec["Property Address"].strip(), str(rec["Year"]).strip())
            if key in existing_keys:
                continue

            row = [rec.get(col, "") for col in summary_headers]
            new_rows.append(row)
            existing_keys.add(key)

        if new_rows:
            summary_sheet.append_rows(new_rows, value_input_option='RAW')
            print(f"Appended {len(new_rows)} new rows.")
        else:
            print("No new rows to add (already processed).")

    except Exception as e:
        print(f"Error processing {pdf_uri}: {e}")

    time.sleep(10)

# === MAIN DRIVER === #
pdf_uris = get_pdf_uris(bucket_name, folder_path)
existing_keys = load_existing_keys(summary_sheet)

for uri in pdf_uris:
    process_pdf(uri, summary_sheet, existing_keys)

print("\nAll PDFs processed and your Google Sheet has been updated!")
