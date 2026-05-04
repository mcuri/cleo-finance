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

Builds and maintains a behavioral financial profile from your chat conversations. After each chat response, it fires a lightweight Claude Haiku call that reads the exchange and decides whether to update your profile. The profile lives in the `## Current Profile
_Last updated: 2026-05-03_

• Employment: Meta Platforms, Inc., biweekly paycheck (~$5,000–$5,700 net per pay period); Gross annual run rate: ~$214k (based on $8,234.32 biweekly base); 2026 Q1 YTD gross $122,202.95 through 04/24/2026
• Location: San Francisco Bay Area, SOMA waterfront resident (180 Brannan St # 221, San Francisco, CA 94107); Bayside Village apartment complex; California state tax, OASDI, Medicare, VDI subject
• Housing: Bayside Village rent $3,460/month + ~$192 utilities (~$3,652 total monthly); housing-to-gross ratio ~6% (well below 30% threshold); locked into February 2026 lease cycle
• Compensation structure: Base salary + bonus/RSU vesting with documented major RSU vesting events occurring on predictable quarterly/semi-annual cadence; relocation package fully exhausted as of 11/17/2025 final gross-up ($5,170.98); RSU withholding management via 401k deferrals ($411.72–$4,117/pay, variable on RSU vest dates) demonstrates intentional tax-efficient windfall management
• Income history: 33 deposits tracked spanning June 2025 – April 2026; RSU vesting pattern shows repeating cycle with major vesting event 03/20/2026 ($45,337.00 gross, $26,667.20 net); OASDI wage base maxed 11/21/2025 and reset for 2026 tax year
• Tax rate: ~36% effective withholding on base pay; RSU vesting events subject to marginal rates (~37–40%); 2026 OASDI reset applied; no relocation benefit continuation
• PTO: Stabilized at 80 hours per pay period; Q1 2026 shows 720 hours YTD (consistent consumption pattern)
• Benefits: 401k contributions continue scaling with RSU events; Medical FSA active; pretax medical/dental/vision coverage; Life@Choice imputed GTL/LTD coverage; dividend equivalent payments detected
• Spending patterns (Q1 2026): Discretionary mix of restaurants ($127–$200/cycle), rideshare/transit ($45–$75/cycle), shopping/online retail ($300–$350/cycle), professional development ($605 Stanford continuing studies enrollment detected 03/05/2026); furniture/home goods purchases ramping (IKEA $268.35 across two transactions 03/09–03/10); fresh/specialty food retail (Cypress Flower Farm, Eatwell Botanics); specialty bakery/prepared foods emerging (Arsicault, True Laurel); established San Francisco Bay Area lifestyle with mid-range dining and local mobility habits; grocery staples (Trader Joe's) now tracked
• Post-relocation baseline (2026 onward): Income structure fully normalized to base + RSU + bonus rhythm; relocation benefit permanently exhausted; all tax credits derived from RSU withholding management (401k deferral scaling); lumpy income architecture persists driven by quarterly/semi-quarterly RSU cycles
• 2026 RSU vesting cadence: Major vesting event 03/20/2026 ($45,337.00) confirms continued quarterly RSU distribution pattern; net pay on non-RSU vesting pay periods averaging $5,015–$5,395; tax-efficient deferral strategy continues post-relocation
• Subscription services: Amazon Prime active ($16.32 recurring); suggests bundled shopping/logistics reliance
• Housing lease cycle: Billing/payment cycle locked to 02/01 of each month; apartment amenities suggest mid-to-premium Bay Area rental market positioning

---

## frontend/src/components/Dashboard.tsx

The financial summary screen. Shows income, expenses, net, and savings rate for the selected time period. Breaks down spending by category as horizontal bars (with % of total). Shows a monthly savings chart (green = you saved, red = you overspent). Default view is the current month.

---

## frontend/src/utils/dateFilter.ts

Handles all the date math for the dashboard filters (This Week, This Month, Last Month, 3 Months, 6 Months, Custom). `buildMonthlySavingsData` computes net savings per month (income − expenses), savings rate (net ÷ income × 100), and groups everything into monthly buckets regardless of the selected range.

---

---

## Observations Log

- **2026-04-25**: Established income profile: Meta employee in CA, ~$214k gross annual salary + variable bonus/RSU, net ~$130k/year; 6-month income history loaded.
- **2026-04-25**: Confirmed large bonus/RSU payout pattern: $26.7k net received 03/20/2026, validating forward-looking income expectations for Q1 2026; PTO accumulation rate and full benefits breakdown documented.
- **2026-04-25**: Relocation package received 08/01/2025: $6,353.04 gross relocation benefit + $5,600 employer tax gross-up; net paycheck $4,656.26 (reduced by tax burden despite higher gross). Suggests potential geographic move or role transfer with employer-subsidized relocation support.
- **2026-04-25**: Major RSU vesting event 08/29/2025: $42,235.02 gross RSU income with $17,350.11 employer tax offset from relocation package; net $6,348.07 despite 54.9k gross pay; demonstrates Meta compensation heavily weighted to equity with concentrated vesting cycles and tax-efficient planning.
- **2026-04-25**: Second RSU vesting detected within 11 days (08/18 and 08/29/2025); relocation tax offset fully consumed on 08/18 event (net $0), leaving 08/29 event at higher marginal tax rate; 401k deferrals surge during RSU vests ($1,235.16 vs baseline $411.72), indicating intentional tax deferral strategy; PTO hours declined between payslips—monitor for burnout or usage pattern.
- **2026-04-25**: September 2025 RSU vesting ($42,235.02) with $24,722.72 relocation gross-up and $21,792 tax benefit; confirms relocation package is multi-installment recurring benefit (3+ offset events Aug–Sep), not one-time; sustained tax credit strategy absorbing 20.8% of YTD gross income; RSU vesting cycle appears quarterly/semi-quarterly with $42k+ events; relocation tax shield duration and magnitude tracking beyond original August 2025 package scope.
- **2026-04-25**: 09/26/2025 relocation offset reveals four-event tax shield pattern with $17,291.94 gross-up and 88% tax credit absorption (highest ratio observed); relocation package now confirmed as minimum 4-installment distributed benefit spanning Aug–Sep with coordinated withholding synchronization and increasing per-event magnitude.
- **2026-04-25**: Relocation tax benefit structure extended into October 2025 with largest single gross-up ($24,722.72) and highest tax offset absorption (88.2%); RSU vesting cycle confirmed predictable; relocation benefit now spanning minimum 3-month window (Aug–Oct) across 5+ separate paycheck events rather than original Aug–Sep window; October paycheck confirms relocation benefit multi-installment structure concluding or entering final phase.
- **2026-04-25**: Relocation benefit package confirmed fully distributed and exhausted as of 10/24/2025 (5 paycheck events, Aug–Oct span); 11/07 paycheck shows return to normal compensation pattern with bonus component; YTD gross now $116,041.95 reflecting completion of major tax offset cycle; no new financial obligations or behavioral signals detected.
- **2026-04-25**: Relocation tax benefit package fully exhausted as of 10/24/2025; 11/07 paycheck confirms clean post-relocation normalization with bonus component replacing gross-ups; YTD tax credits fully absorbed ($18,771.12); income structure returning to predictable RSU + base + bonus rhythm; no further relocation-related tax benefits expected.
- **2026-04-25**: 11/21/2025 paycheck captures Q4 RSU vesting concentration ($73,926.94 gross accumulation), confirms OASDI wage base maxed ($176,100), documents dividend equivalent payments ($32.26), validates sustained post-relocation income normalization with zero tax credits and YTD cumulative post-tax benefit of $29,925.65 (24.1% absorption rate across relocation + RSU offset strategy).
- **2026-04-25**: 11/18/2025 RSU vesting ($31,691.92 gross) fully offset by final relocation tax credit ($11,154.53), producing zero-net paycheck; relocation benefit period extended through November (6 paycheck events total), one event beyond previously documented October conclusion; tax credit absorption strategy optimized to final quarterly RSU vesting cycle.
- **2026-04-25**: Post-relocation paycheck 12/05/2025 confirms baseline normalization: $73.9k Q4 RSU accumulation vested (largest single RSU event detected), relocation benefit fully exhausted, net pay $6,615.42 (within expected $5k–$5.7k baseline range post-tax credits), RSU withholding management via continued 401k deferrals and excess refunds ($1,034.67) confirms intentional tax optimization pattern persists post-relocation; Q4 equity cycle accumulation warrants monitoring for year-end income concentration.
- **2026-04-25**: Relocation benefit package conclusively exhausted 11/17/2025 with final gross-up $5,170.98 and relocation tax benefit $21,792.29; 401k deferral escalated to $4,117 on RSU vesting event confirming tax-mitigation scaling behavior; post-relocation baseline now permanently established with zero-relocation-continuation assumption
- **2026-04-25**: Q1 2026 payroll loaded: 9 paychecks Jan–Apr 2026 with major RSU vesting event 03/20/2026 ($45,337 gross/$26,667 net); YTD gross $122,202.95; OASDI wage base reset for 2026 tax year; biweekly base stable $8,234–$9,589; quarterly RSU vesting pattern persists into new tax year.
- **2026-05-01**: Credit card statement parsed (52 transactions, 03/03–03/10/2026, ~$1,471 total); discretionary spending pattern established: restaurants, rideshare, Amazon retail, professional development (Stanford $605), home goods (IKEA furniture $268.35) consistent with Bay Area resident; no high-risk or anomalous spending detected; recurring cycle behavior captured for budgeting baseline.
- **2026-05-01**: 54 Q1 2026 transactions ingested (03/03–03/10); grocery/staple shopping (Trader Joe's) and subscription services (Amazon Prime) newly tracked; home furnishing purchases confirm residential establishment post-relocation; professional development spend ($605 Stanford) reaffirms upskilling commitment.
- **2026-05-03**: Housing anchor confirmed: $3,652/month (rent + utilities) at Bayside Village SOMA waterfront location; 6% housing cost ratio indicates financial capacity for discretionary spending and investment; lease cycle documentation establishes fixed monthly obligation baseline for cash flow modeling.
