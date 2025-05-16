# Rental Property Data Analysis 📊

This project automates the extraction and analysis of rental income and expense data from property management PDF statements. The extracted data is cleaned, transformed, and visualized in Power BI to provide actionable insights into property performance.

## 🧾 Project Highlights
- Extracted structured financial data from 80+ income statement PDFs using Google Vertex AI
- Built a scalable pipeline that pushes cleaned data into Google Sheets
- Connected Power BI to Google Sheets for automated dashboard updates

## 📊 Dashboard Features
- Property-wise income and expense breakdown
- Net income trends over time
- Comparative performance across landlords and properties
- Filters by month, landlord, and location

## 🛠️ Tools & Technologies
- Power BI (Dashboards & DAX)
- Python (PDF data processing)
- Google Vertex AI (Document parsing)
- Google Sheets (as data layer)

## 💡 Insights Delivered
- Identified properties with consistently low net income
- Flagged anomalies in monthly expenses (e.g., sudden tax hikes)
- Enabled property managers to track landlord-specific performance

## 📂 Files
- `rental-dashboard.pbix` – Power BI dashboard
- `data-sample.csv` – Cleaned data sample
- `pipeline-script.py` – PDF extraction script
- `images/` – Dashboard screenshots

## 📸 Screenshots
![Dashboard Preview](images/rental-dashboard.png)
