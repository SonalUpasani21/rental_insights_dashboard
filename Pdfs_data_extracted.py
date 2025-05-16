import gspread
import json
from google.oauth2 import service_account
import pandas as pd
import time
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part
from data_cleaner import clean_data  # Import the cleaning function

# === USER INPUTS === #
project_id = input("Enter your Google Cloud project ID: ").strip()
bucket_name = input("Enter your Google Cloud bucket name: ").strip()
sheet_name = input("Enter your Google Sheet name: ").strip()
service_account_file = input("Enter the path to your service account file (e.g., sa.json): ").strip()
pdf_folder = input("Enter the folder path inside the bucket (e.g., batch1_MM/): ").strip()

# === CREDENTIALS === #
gcp_credentials = service_account.Credentials.from_service_account_file(service_account_file)
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
gsheets_creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scope)

# === INIT SERVICES === #
vertexai.init(project=project_id, location="us-central1", credentials=gcp_credentials)
storage_client = storage.Client(credentials=gcp_credentials)
gsheets_client = gspread.authorize(gsheets_creds)
sheet = gsheets_client.open(sheet_name).sheet1

# === GET or CREATE EXPENSES LONG SHEET === #
def get_or_create_expense_long_sheet(sheet_name, client):
    try:
        return client.open(sheet_name).worksheet("Expenses Long")
    except gspread.exceptions.WorksheetNotFound:
        print("📄 'Expenses Long' tab not found. Creating new tab...")
        sheet = client.open(sheet_name)
        new_sheet = sheet.add_worksheet(title="Expenses Long", rows="1000", cols="10")
        headers = ["Owner", "Property Address", "Statement Period", "Expense Category", "Amount", "Period Month", "Period Year"]
        new_sheet.append_row(headers)
        return new_sheet

expenses_long_sheet = get_or_create_expense_long_sheet(sheet_name, gsheets_client)

# === FORCE HEADERS ON MAIN SHEET === #
def force_set_headers(sheet):
    headers = [
        "Owner", "Postal Code", "Statement Period", "Property Address", "Rent", "NSF Income", "Maintenance",
        "Income Total", "General Repairs", "Appliance Repair", "Advertising", "Lease Up (Billable)", "Plumbing",
        "Condo Fees", "Mgmt Fee", "Garbage Removal", "Hydro", "Other Billable", "Electrical",
        "Credit Check (NB)", "Lease Up (NB)", "Unit Cleaning", "NSF Expense", "Expenses", "Net",
        "Period Month", "Period Year"
    ]
    try:
        sheet.delete_rows(1)
    except:
        pass
    sheet.insert_row(headers, index=1)
    print("Headers added.")

force_set_headers(sheet)

# === PROMPT === #
prompt = """
You are a highly skilled document data extraction specialist. Your task is to extract structured financial data from rental owner statements in PDF format. Each statement may contain information for one or multiple properties, presented in a multi-column layout where each column represents a single property.

For each property identified in the document, extract the following information. If a piece of information is not present for a specific property, return an empty string for that field.

Output the extracted information as a JSON array of objects. Each object in the array should represent a single property and contain the following keys:

[
  {
    "Owner Name": "...",
    "Left Corner Address and Postal Code": "...",
    "Statement Period": "...",
    "Statement Date": "...",
    "Address": "...",
    "Rent Income": "...",
    "NSF Fee Income": "...",
    "Maintenance Income": "...",
    "Total Income": "...",
    "6800 - Common Area Repairs - 6865 - General Repairs/Maintenance": "...",
    "6910 - Unit Repairs and Maintenance - Appliance Repair - 6915": "...",
    "6700 - Billable Operating Expenses - 6710 - Advertising": "...",
    "6700 - Billable Operating Expenses - 6728 - Lease Up Expense": "...",
    "6800 - Common Area Repairs - 6890 - Plumbing Repairs": "...",
    "Condo Fees": "...",
    "General Office Expenses - 6500 - 6585 - Management Fee Expense": "...",
    "6800 - Common Area Repairs - 6860 Garbage/Large Item Removal": "...",
    "6740 - Occupancy Costs - 6760 – Hydro": "...",
    "6700 - Billable Operating Expenses – 6727": "...",
    "6800 - Common Area Repairs - 6835 Electrical Repair": "...",
    "6700 - Non Billable Operating Expenses 6727 - Credit Check": "...",
    "6700 - Non Billable Operating Expenses 6728 - Lease Up Expense": "...",
    "6910 - Unit Repairs and Maintenance - Unit Cleaning - 6950": "...",
    "NSF Fee (Expense)": "...",
    "Total Expenses": "...",
    "Net Income": "..."
  },
  {
    "...": "..."
  },
  ...
]

Follow these guidelines for extraction:

1.  *Owner Name:* Locate the line containing "Owner: [Name]" at the bottom-left or bottom-right of the last page and extract the name following "Owner:".

2.  *Left Corner Address and Postal Code:* Find the address block near the bottom of the page, often under "Prepared by" or as a footer. It's usually two lines. Extract this entire block as a single string.

3.  *Statement Period:* Look for the label "Statement period" or "Statement Period" near the bottom of the page and extract the date range that follows.

4.  *Statement Date:* Find the label "Statement date" near the bottom of the page and extract the date that follows.

5.  *Property Address:* For each vertical column representing a property, the address will be at the very top, often in bold. Extract this as the "Address" for that property.

6.  *Income Fields (Per Property Column):* Within the income section (usually at the top of each column), extract the values associated with the following labels:
    * "Rent", "Gross Rent", or "Rent Income" as "Rent Income".
    * "NSF Fee Income" or "NSF Fee" as "NSF Fee Income" (if present). If not present, return "".
    * "Maintenance Income" (if present) as "Maintenance Income". If not present, return "".
    * The value labeled "Total Income" at the bottom of the income block.

7.  *Expense Categories (Per Property Column):* In the middle section of each property column (under "Expenses", "Operating Expenses", "Recoverable", or "Non-Billable"), find and extract the amounts for each line item that matches the following full labels (including the codes):
    * "6800 - Common Area Repairs - 6865 - General Repairs/Maintenance"
    * "6910 - Unit Repairs and Maintenance - Appliance Repair - 6915"
    * "6700 - Billable Operating Expenses - 6710 - Advertising"
    * "6700 - Billable Operating Expenses - 6728 - Lease Up Expense"
    * "6800 - Common Area Repairs - 6890 - Plumbing Repairs"
    * "Condo Fees" or similar (e.g., "Strata Fees")
    * "General Office Expenses - 6500 - 6585 - Management Fee Expense"
    * "6800 - Common Area Repairs - 6860 Garbage/Large Item Removal"
    * "6740 - Occupancy Costs - 6760 - Hydro"
    * "6700 - Billable Operating Expenses - 6727"
    * "6800 - Common Area Repairs - 6835 Electrical Repair"
    * "6700 - Non Billable Operating Expenses 6727 - Credit Check"
    * "6700 - Non Billable Operating Expenses 6728 - Lease Up Expense"
    * "6910 - Unit Repairs and Maintenance - Unit Cleaning - 6950"
    * Look for "NSF Fee" at the bottom of the expense block and extract it as "NSF Fee (Expense)".

8.  *Totals (Per Property Column):* At the bottom of each property column, extract the value labeled "Total Expenses" and the value labeled "Net Income" (usually directly below or beside "Total Expenses").

Ensure that the JSON output is a list of dictionaries, where each dictionary corresponds to one property's extracted financial data. If a statement contains multiple property columns, you should have multiple objects in the JSON array.
"""

# === GET PDF FILES FROM GCS === #
def get_pdf_files(bucket_name, folder_path):
    try:
        blobs = storage_client.list_blobs(bucket_name, prefix=folder_path)
        pdf_files = [f"gs://{bucket_name}/{blob.name}" for blob in blobs if blob.name.endswith(".pdf")]
        print(f"Found {len(pdf_files)} PDF(s):")
        for pdf in pdf_files:
            print("•", pdf)
        return pdf_files
    except GoogleAPIError as e:
        print("GCS Error:", e)
        return []

# === LOAD EXISTING KEYS === #
def load_existing_keys(sheet):
    existing_rows = sheet.get_all_values()[1:]
    return {(row[0].strip(), row[2].strip(), row[3].strip()) for row in existing_rows if len(row) >= 4}

# === INIT GEMINI MODEL === #
model = GenerativeModel(model_name="gemini-2.0-flash-001", generation_config={"response_mime_type": "application/json"})

# === PROCESS EACH PDF === #
def process_pdf(pdf_uri, sheet, existing_keys):
    print(f"\nProcessing: {pdf_uri}")
    try:
        pdf_part = Part.from_uri(pdf_uri, mime_type="application/pdf")
        response = model.generate_content([pdf_part, prompt])
        raw_text = response.text.strip()
        json_response = json.loads(raw_text)

        if not isinstance(json_response, list):
            json_response = [json_response]

        new_rows = []
        headers = sheet.row_values(1)

        for item in json_response:
            df = pd.DataFrame([item])
            df = clean_data(df)

            if df.empty:
                print("Skipping — cleaned DataFrame is empty.")
                continue

            dedup_key = (
                df["Owner"].iloc[0].strip(),
                df["Statement Period"].iloc[0].strip(),
                df["Property Address"].iloc[0].strip()
            )

            if dedup_key not in existing_keys:
                row_data = [df[col].iloc[0] if col in df.columns else "0" for col in headers]
                new_rows.append(row_data)
                existing_keys.add(dedup_key)

                # Append to Expenses Long sheet
                expense_columns = [
                    "Advertising", "Hydro", "Plumbing", "General Repairs", "Appliance Repair",
                    "Lease Up (Billable)", "Condo Fees", "Mgmt Fee", "Garbage Removal", "Other Billable",
                    "Electrical", "Credit Check (NB)", "Lease Up (NB)", "Unit Cleaning", "NSF Expense"
                ]

                for col in expense_columns:
                    if col in df.columns:
                        value = df[col].iloc[0]
                        try:
                            value_float = float(value)
                            if value_float != 0:
                                expenses_long_sheet.append_row([
                                    df["Owner"].iloc[0],
                                    df["Property Address"].iloc[0],
                                    df["Statement Period"].iloc[0],
                                    col,
                                    value_float
                                ])
                        except ValueError:
                            print(f"Skipping invalid float in {col} for {df['Property Address'].iloc[0]}")

        if new_rows:
            sheet.append_rows(new_rows, value_input_option='RAW')
            print(f"Appended {len(new_rows)} new row(s).")
        else:
            print("No new data. Already processed.")

    except Exception as e:
        print(f"Error processing {pdf_uri}:\n{e}")

    time.sleep(15)

# === MAIN DRIVER === #
pdf_files = get_pdf_files(bucket_name, pdf_folder)
existing_keys = load_existing_keys(sheet)

if pdf_files:
    for pdf_uri in pdf_files:
        process_pdf(pdf_uri, sheet, existing_keys)

print("\nAll PDFs processed successfully!")