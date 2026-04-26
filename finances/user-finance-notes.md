# User Finance Notes

Personal reference for understanding how Cleo tracks your money.

---

## backend/models.py

Defines the data shapes used throughout the app. A **Transaction** has: date, amount, merchant, category, type (income or expense), notes, source (where it came from — web form, Telegram, CSV, credit card, or payslip), and `created_at` (when it was recorded). A **ParsedPayslip** captures 12 fields from your pay stubs: gross pay, pre/post-tax deductions, employee taxes, net pay, 401k contributions (yours + employer match), and Life@ Choice. **ParsedExpense** is a lightweight shape used when Claude parses a receipt or text message before saving it as a full Transaction.

---

## backend/sheets.py

The layer that reads and writes your actual financial data to Google Sheets. Your transactions live in the **Transactions** tab (columns A–I: id, date, amount, merchant, category, type, source, notes, created_at). Payslips live in the **Payslips** tab (12 columns). It handles duplicate detection (same date + amount + merchant = skipped), and logs every Claude API call in a **Logs** tab for cost tracking.

---

## backend/init_sheets.py

One-time setup script that creates the Transactions, Categories, Logs, and Payslips tabs in your spreadsheet and writes the column headers. Run this once when setting up or adding new columns. Predefined categories include: Utilities, Groceries, Restaurants, Transport, Entertainment, Health, Shopping, Travel, Subscriptions, Income, Other.

---

## backend/main.py

The web server entry point. Registers all the API routes (auth, transactions, categories, chat, Telegram) and serves the React frontend. Writes logs to `logs/app.log` (rotated at 5 MB). The CSV import endpoints were removed — file-based imports now happen only via the chat interface (PDF statements, receipts).

---

## backend/payslip_parser.py

Sends your payslip PDFs to Claude Haiku and extracts the 12 financial fields into a structured format. Uses up to 8,192 output tokens to handle large PDFs. Returns a list of payslips (in case a PDF contains multiple pay periods).

---

## backend/drive.py

Uploads PDFs to Google Drive after saving to Sheets. Organizes files under `cleo-finance/Payslips/YYYY-MM/` or `cleo-finance/Credit Card Bills/YYYY-MM/`. Creates subfolders automatically. If the root `cleo-finance` folder isn't found, the upload is silently skipped — it never blocks saving your data.

---

## backend/chat.py

The main brain of the app. Handles your chat messages and file uploads. Routes PDFs to the right parser (payslip, credit card bill, or general statement), saves transactions to Sheets, uploads PDFs to Drive, and calls Claude to write a human-readable reply. Deduplicates transactions before saving so the same charge is never counted twice. Also fires a background extraction call after each reply to update your financial profile.

---

## backend/profile_extractor.py

Builds and maintains a behavioral financial profile from your chat conversations. After each chat response, it fires a lightweight Claude Haiku call that reads the exchange and decides whether to update your profile. The profile lives in the `## Current Profile` section of this file — a set of bullet points summarizing your observed financial patterns (e.g. "tends to track restaurant spending", "appears savings-conscious"). A dated `## Observations Log` below it records what triggered each update. The profile is automatically included in Cleo's system prompt so her responses get more personalized over time.

---

## frontend/src/components/Dashboard.tsx

The financial summary screen. Shows income, expenses, net, and savings rate for the selected time period. Breaks down spending by category as horizontal bars (with % of total). Shows a monthly savings chart (green = you saved, red = you overspent). Default view is the current month.

---

## frontend/src/utils/dateFilter.ts

Handles all the date math for the dashboard filters (This Week, This Month, Last Month, 3 Months, 6 Months, Custom). `buildMonthlySavingsData` computes net savings per month (income − expenses), savings rate (net ÷ income × 100), and groups everything into monthly buckets regardless of the selected range.

---
