# Payslip Parser — Design Spec

**Date:** 2026-04-25  
**Status:** Approved

---

## Overview

When the user uploads a payslip PDF through the chat, the system:
1. Detects it as a payslip (not a credit card bill or generic PDF)
2. Extracts 11 summary fields using Claude
3. Writes a detailed row to a new **Payslips** Google Sheet tab
4. Writes the net pay as an income transaction to the **Transactions** tab
5. Cleo confirms both saves in the chat response

Payslips are always PDFs. Image payslips are out of scope.

---

## Data Model

### `ParsedPayslip` (new, `backend/models.py`)

```python
class ParsedPayslip(BaseModel):
    company: str
    pay_period_begin: date_type
    pay_period_end: date_type
    check_date: date_type
    gross_pay: float
    pre_tax_deductions: float
    employee_taxes: float
    post_tax_deductions: float
    net_pay: float
    employee_401k: float
    employer_401k_match: float
```

### `TransactionSource` (updated, `backend/models.py`)

```python
TransactionSource = Literal["web", "csv", "telegram", "credit_card", "payslip"]
```

---

## Spreadsheet

### Payslips tab

**Prerequisite (manual):** Add a tab named exactly `Payslips` to the Google Sheet and share it with the service account (same setup as `Transactions` and `Categories`).

New sheet tab named `Payslips`, initialized by `init_sheets.py`. Column headers (row 1):

| A | B | C | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|
| Company | Pay Period Begin | Pay Period End | Check Date | Gross Pay | Pre Tax Deductions | Employee Taxes | Post Tax Deductions | Net Pay | 401k Salary | 401k Employer Match |

Data rows start at row 2. One row per uploaded payslip.

### Transactions tab

Unchanged. The net pay is appended as a standard income row:
- `date` = `check_date`
- `amount` = `net_pay`
- `merchant` = `company`
- `category` = `"Income"`
- `type` = `"income"`
- `source` = `"payslip"`
- `notes` = `"Pay period: {pay_period_begin} - {pay_period_end}"`

---

## New File: `backend/payslip_parser.py`

Single public function:

```python
def parse_payslip(pdf_bytes: bytes) -> Optional[ParsedPayslip]
```

**Implementation:**
- Encodes PDF as base64
- Sends to `claude-haiku-4-5-20251001` as a `document` content block (same pattern as `parse_pdf_statement` in `claude_parser.py`)
- Prompt asks for exactly 11 fields as a JSON object matching the `ParsedPayslip` schema
- Returns `None` on malformed or missing JSON
- Calls `log_usage(response, "parse_payslip")`

**Prompt schema hint:**
```
{"company": "...", "pay_period_begin": "YYYY-MM-DD", "pay_period_end": "YYYY-MM-DD",
 "check_date": "YYYY-MM-DD", "gross_pay": 0.00, "pre_tax_deductions": 0.00,
 "employee_taxes": 0.00, "post_tax_deductions": 0.00, "net_pay": 0.00,
 "employee_401k": 0.00, "employer_401k_match": 0.00}
```

---

## Updated: `backend/sheets.py`

New method on `SheetsClient`:

```python
def append_payslip(self, p: ParsedPayslip) -> None
```

Appends a row to `Payslips!A:K` with the 11 fields in column order. Dates serialized as `YYYY-MM-DD` strings.

---

## Updated: `backend/init_sheets.py`

Add Payslips tab initialization: write the 11 column headers to `Payslips!A1:K1` if the sheet exists, or log a warning if not. Pattern matches existing Transactions/Categories tab setup.

---

## Updated: `backend/chat.py`

### Detection function

```python
def _is_payslip(file_bytes: bytes) -> bool
```

Scans the first page with pdfplumber for any of:
`"net pay"`, `"gross pay"`, `"pay period"`, `"pre tax deductions"`, `"check date"`

Returns `True` if 3 or more markers are found (threshold avoids false positives from documents that happen to mention one or two terms).

### Routing (inside `chat()`, PDF branch)

```python
if _is_credit_card_bill(file_bytes):
    # existing CC bill path
elif _is_payslip(file_bytes):
    parsed_payslip = parse_payslip(file_bytes)
    if parsed_payslip is None:
        raise HTTPException(400, "Could not extract payslip data from this PDF.")
    sheets.append_payslip(parsed_payslip)
    income_tx = Transaction.from_create(
        TransactionCreate(
            date=parsed_payslip.check_date,
            amount=parsed_payslip.net_pay,
            merchant=parsed_payslip.company,
            category="Income",
            type="income",
            notes=f"Pay period: {parsed_payslip.pay_period_begin} - {parsed_payslip.pay_period_end}",
        ),
        source="payslip",
    )
    sheets.append_transaction(income_tx)
    saved = [income_tx]
    result = (
        f"[BACKEND RESULT] Payslip saved to Payslips sheet "
        f"(Gross: ${parsed_payslip.gross_pay:,.2f}, Net: ${parsed_payslip.net_pay:,.2f}). "
        f"Income transaction saved: ${parsed_payslip.net_pay:,.2f} from {parsed_payslip.company} on {parsed_payslip.check_date}."
    )
else:
    # existing generic PDF path
```

The `result` string is injected into the system prompt so Cleo can confirm both saves accurately.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Claude returns malformed JSON | `parse_payslip` returns `None` → 400 HTTP error in chat |
| PDF has payslip markers but missing fields | Claude returns partial JSON → `ParsedPayslip` validation fails → `None` → 400 error |
| `append_payslip` fails | Exception propagates → 500 error, transaction not saved |
| `append_transaction` fails after payslip saved | Payslip row is in sheet but transaction is missing — acceptable for v1, no rollback |

---

## Out of Scope

- Image payslips
- YTD fields
- Individual tax/deduction line items
- Payslips API endpoint (view/delete payslip rows)
- Duplicate payslip detection
