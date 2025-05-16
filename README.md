# Rental Property Data Analysis
This project automates the extraction and analysis of rental income and expense data from property management PDF statements. The extracted data is cleaned, transformed, and visualized in Power BI to provide actionable insights into property performance.

## Project Workflow

Below are the steps followed to complete this rental property data analysis project:

### 1. Project Planning
- Identified the need to automate analysis of monthly rental income and expense statements.
- Defined goals: extract structured data from PDFs, clean it, and visualize insights via dashboards.

### 2. PDF Data Extraction
- Collected 80+ rental income statement PDFs from a property management company.
- Uploaded PDFs to Google Cloud Storage for centralized access.
- Used Google Vertex AI (Document AI) to extract metadata and financial tables from each PDF.
- Parsed owner name, statement period, income, and expense data into structured format.

### 3. Data Cleaning & Transformation
- Built a Python script to:
  - Send PDFs to Vertex AI and parse response
  - Clean currency fields and convert to float
  - Merge similar expense categories across documents
  - Extract month/year from statement period
  - Handle missing values and normalize the schema

### 4. Data Storage
- Used the `gspread` package to push cleaned data into Google Sheets.
- Created two tabs:
  - `pdf_extracted`: Main cleaned dataset
  - `Expense long`: Normalized long-format expense table

### 5. Dashboard Development (Power BI)
- Connected Power BI directly to Google Sheets for live data updates.
- Created an interactive dashboard including:
  - Property-wise income and expense summaries
  - Net income trends over time
  - Landlord-level comparison
  - Filters for statement period, property, and expense category

### 6. Automation & Scalability
- Designed a modular pipeline to support monthly updates.
- Enabled users to upload new PDFs and refresh dashboards without technical steps.
- Ensured data flows automatically from PDFs → Vertex AI → Google Sheets → Power BI.
