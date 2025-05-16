import pandas as pd
import re

def clean_data(df):
    # === 1. Fill NaNs with 0 === #
    df.fillna(0, inplace=True)

    # === 2. Convert currency columns to float (remove $ and commas) === #
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace("$", "", regex=False).str.replace(",", "")

    # === 3. Shorten column names === #
    rename_map = {
        "Owner Name": "Owner",
        "Left Corner Address and Postal Code": "Postal Code",
        "Statement Date": None,
        "Address": "Property Address",
        "Rent Income": "Rent",
        "NSF Fee Income": "NSF Income",
        "Maintenance Income": "Maintenance",
        "Total Income": "Income Total",
        "6800 - Common Area Repairs - 6865 - General Repairs/Maintenance": "General Repairs",
        "6910 - Unit Repairs and Maintenance - Appliance Repair - 6915": "Appliance Repair",
        "6700 - Billable Operating Expenses - 6710 - Advertising": "Advertising",
        "6700 - Billable Operating Expenses - 6728 - Lease Up Expense": "Lease Up (Billable)",
        "6800 - Common Area Repairs - 6890 - Plumbing Repairs": "Plumbing",
        "Condo Fees": "Condo Fees",
        "General Office Expenses - 6500 - 6585 - Management Fee Expense": "Mgmt Fee",
        "6800 - Common Area Repairs - 6860 Garbage/Large Item Removal": "Garbage Removal",
        "6740 - Occupancy Costs - 6760 – Hydro": "Hydro",
        "6700 - Billable Operating Expenses – 6727": "Other Billable",
        "6800 - Common Area Repairs - 6835 Electrical Repair": "Electrical",
        "6700 - Non Billable Operating Expenses 6727 - Credit Check": "Credit Check (NB)",
        "6700 - Non Billable Operating Expenses 6728 - Lease Up Expense": "Lease Up (NB)",
        "6910 - Unit Repairs and Maintenance - Unit Cleaning - 6950": "Unit Cleaning",
        "NSF Fee (Expense)": "NSF Expense",
        "Total Expenses": "Expenses",
        "Net Income": "Net"
    }

    df.rename(columns={k: v for k, v in rename_map.items() if v is not None}, inplace=True)
    df.drop(columns=[k for k, v in rename_map.items() if v is None], inplace=True, errors='ignore')

    # === 4. Extract Postal Code from address string === #
    if "Postal Code" in df.columns:
        df["Postal Code"] = df["Postal Code"].astype(str).str.extract(
            r'(\b[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d\b)', expand=False
        ).fillna("")

    # === 5. Extract Month and Year from Statement Period === #
    if "Statement Period" in df.columns:
        df["Statement Period"] = df["Statement Period"].astype(str)
        df["Period Month"] = df["Statement Period"].str.extract(r'(\d{4})-(\d{2})-\d{2}', expand=True)[1]
        df["Period Year"] = df["Statement Period"].str.extract(r'(\d{4})', expand=False)

        df["Period Month"] = df["Period Month"].map({
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December"
        })

    # === 6. Standardize Property Address === #
    if "Property Address" in df.columns:
        df["Property Address"] = (
            df["Property Address"]
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)
            .str.replace(r"[.,]", "", regex=True)
            .str.title()
        )

    # === 7. Ensure all numeric columns are valid float (0 if blank or invalid) === #
    for col in df.columns:
        if col not in ["Owner", "Property Address", "Postal Code", "Statement Period", "Period Month", "Period Year"]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

    # === 8. Drop summary rows like "All Properties" === #
    if "Property Address" in df.columns:
        df = df[df["Property Address"].str.lower() != "all properties"]

    return df
