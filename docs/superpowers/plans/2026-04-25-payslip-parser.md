# Payslip Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a payslip PDF is uploaded via chat, extract 12 summary fields with Claude, write a full row to a new Payslips Google Sheet tab, and save the net pay as an income transaction to Transactions.

**Architecture:** A new `payslip_parser.py` handles Claude-based extraction into a `ParsedPayslip` model. `chat.py` gains a `_is_payslip()` pdfplumber detector slotted between the existing CC bill and generic PDF branches. `sheets.py` gains `append_payslip()`. `init_sheets.py` sets up the Payslips tab headers.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Anthropic SDK (`claude-haiku-4-5-20251001`), pdfplumber, Google Sheets API.

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/models.py` | Add `ParsedPayslip`; add `"payslip"` to `TransactionSource` |
| `finances/backend/payslip_parser.py` | **New** — `parse_payslip()` + `_parse_response()` |
| `finances/backend/sheets.py` | Add `append_payslip()` method |
| `finances/backend/init_sheets.py` | Add Payslips tab + header init |
| `finances/backend/chat.py` | Add `_is_payslip()` + payslip routing branch |
| `finances/tests/test_models.py` | 1 new test for `ParsedPayslip` |
| `finances/tests/test_payslip_parser.py` | **New** — 2 tests (happy path + bad JSON) |
| `finances/tests/test_sheets.py` | 1 new test for `append_payslip` |
| `finances/tests/test_chat.py` | 1 new test for payslip routing |

---

## Task 1: Add ParsedPayslip model and update TransactionSource

**Files:**
- Modify: `finances/backend/models.py`
- Test: `finances/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to the bottom of `finances/tests/test_models.py`:

```python
def test_parsed_payslip_fields():
    from datetime import date
    from backend.models import ParsedPayslip
    p = ParsedPayslip(
        company="Meta Platforms, Inc.",
        pay_period_begin=date(2026, 4, 6),
        pay_period_end=date(2026, 4, 19),
        check_date=date(2026, 4, 24),
        gross_pay=8628.24,
        pre_tax_deductions=1067.69,
        employee_taxes=2758.68,
        post_tax_deductions=0.00,
        net_pay=4801.87,
        employee_401k=1035.39,
        employer_401k_match=1035.39,
        life_choice=1129.17,
    )
    assert p.net_pay == 4801.87
    assert p.employee_401k == 1035.39
    assert p.life_choice == 1129.17
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd finances && python -m pytest tests/test_models.py::test_parsed_payslip_fields -v
```

Expected: `FAILED` — `ImportError` or `ValidationError` because `ParsedPayslip` doesn't exist yet.

- [ ] **Step 3: Add ParsedPayslip and update TransactionSource**

In `finances/backend/models.py`, replace:

```python
TransactionSource = Literal["web", "csv", "telegram", "credit_card"]
```

With:

```python
TransactionSource = Literal["web", "csv", "telegram", "credit_card", "payslip"]
```

Then add `ParsedPayslip` after the existing `ParsedExpense` class:

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
    life_choice: float = 0.0
```

- [ ] **Step 4: Run all model tests**

```bash
cd finances && python -m pytest tests/test_models.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add finances/backend/models.py finances/tests/test_models.py
git commit -m "feat: add ParsedPayslip model and payslip TransactionSource"
```

---

## Task 2: Create payslip_parser.py

**Files:**
- Create: `finances/backend/payslip_parser.py`
- Create: `finances/tests/test_payslip_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `finances/tests/test_payslip_parser.py`:

```python
import json
from unittest.mock import MagicMock, patch
from datetime import date


def test_parse_payslip_returns_list_of_payslips():
    from backend.payslip_parser import parse_payslip

    payload = [{
        "company": "Meta Platforms, Inc.",
        "pay_period_begin": "2026-04-06",
        "pay_period_end": "2026-04-19",
        "check_date": "2026-04-24",
        "gross_pay": 8628.24,
        "pre_tax_deductions": 1067.69,
        "employee_taxes": 2758.68,
        "post_tax_deductions": 0.00,
        "net_pay": 4801.87,
        "employee_401k": 1035.39,
        "employer_401k_match": 1035.39,
        "life_choice": 1129.17,
    }]
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(payload))]

    with patch("backend.payslip_parser.anthropic.Anthropic") as mock_cls, \
         patch("backend.payslip_parser.log_usage"):
        mock_cls.return_value.messages.create.return_value = mock_response
        result = parse_payslip(b"fake pdf bytes")

    assert len(result) == 1
    assert result[0].company == "Meta Platforms, Inc."
    assert result[0].net_pay == 4801.87
    assert result[0].employee_401k == 1035.39
    assert result[0].life_choice == 1129.17


def test_parse_payslip_returns_empty_list_on_bad_json():
    from backend.payslip_parser import parse_payslip

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json")]

    with patch("backend.payslip_parser.anthropic.Anthropic") as mock_cls, \
         patch("backend.payslip_parser.log_usage"):
        mock_cls.return_value.messages.create.return_value = mock_response
        result = parse_payslip(b"fake pdf bytes")

    assert result == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances && python -m pytest tests/test_payslip_parser.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'backend.payslip_parser'`.

- [ ] **Step 3: Create payslip_parser.py**

Create `finances/backend/payslip_parser.py`:

```python
import base64
import json
from typing import List

import anthropic

from backend.anthropic_logger import log_usage
from backend.config import get_settings
from backend.models import ParsedPayslip

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You extract payslip summary data from PDF documents. "
    "Respond ONLY with a valid JSON array — no explanation, no markdown. "
    "Return an array even if the PDF contains only one payslip."
)

_SCHEMA = (
    '[{"company": "...", "pay_period_begin": "YYYY-MM-DD", "pay_period_end": "YYYY-MM-DD", '
    '"check_date": "YYYY-MM-DD", "gross_pay": 0.00, "pre_tax_deductions": 0.00, '
    '"employee_taxes": 0.00, "post_tax_deductions": 0.00, "net_pay": 0.00, '
    '"employee_401k": 0.00, "employer_401k_match": 0.00, "life_choice": 0.00}, ...]'
)


def parse_payslip(pdf_bytes: bytes) -> List[ParsedPayslip]:
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        f"Extract all current-period payslip summaries and return a JSON array matching: {_SCHEMA}\n\n"
                        "Use 0.0 for any field not present. "
                        "All dates must be YYYY-MM-DD. All amounts are numbers, not strings."
                    ),
                },
            ],
        }],
    )
    log_usage(response, "parse_payslip")
    return _parse_response(response.content[0].text)


def _parse_response(text: str) -> List[ParsedPayslip]:
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data = [data]
        return [ParsedPayslip(**item) for item in data]
    except Exception:
        return []
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd finances && python -m pytest tests/test_payslip_parser.py -v
```

Expected: Both tests pass.

- [ ] **Step 5: Commit**

```bash
git add finances/backend/payslip_parser.py finances/tests/test_payslip_parser.py
git commit -m "feat: add payslip_parser with Claude-based extraction"
```

---

## Task 3: Add append_payslip to SheetsClient and init Payslips tab

**Files:**
- Modify: `finances/backend/sheets.py`
- Modify: `finances/backend/init_sheets.py`
- Test: `finances/tests/test_sheets.py`

- [ ] **Step 1: Write the failing test**

Add to the bottom of `finances/tests/test_sheets.py`:

```python
def test_append_payslip(sheets_client, mock_service):
    from datetime import date
    from backend.models import ParsedPayslip
    p = ParsedPayslip(
        company="Meta Platforms, Inc.",
        pay_period_begin=date(2026, 4, 6),
        pay_period_end=date(2026, 4, 19),
        check_date=date(2026, 4, 24),
        gross_pay=8628.24,
        pre_tax_deductions=1067.69,
        employee_taxes=2758.68,
        post_tax_deductions=0.00,
        net_pay=4801.87,
        employee_401k=1035.39,
        employer_401k_match=1035.39,
        life_choice=1129.17,
    )
    sheets_client.append_payslip(p)
    mock_service.spreadsheets().values().append.assert_called_once()
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    assert kwargs["range"] == "Payslips!A:L"
    row = kwargs["body"]["values"][0]
    assert row[0] == "Meta Platforms, Inc."
    assert row[8] == 4801.87   # net_pay
    assert row[9] == 1035.39   # employee_401k
    assert row[10] == 1035.39  # employer_401k_match
    assert row[11] == 1129.17  # life_choice
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd finances && python -m pytest tests/test_sheets.py::test_append_payslip -v
```

Expected: `FAILED` — `AttributeError: 'SheetsClient' object has no attribute 'append_payslip'`.

- [ ] **Step 3: Add append_payslip to sheets.py**

At the top of `finances/backend/sheets.py`, update the import from models:

```python
from backend.models import Transaction, Category, TransactionSource, ParsedPayslip
```

Then add `append_payslip` after `append_transaction` in the `SheetsClient` class:

```python
def append_payslip(self, p: ParsedPayslip) -> None:
    row = [
        p.company,
        p.pay_period_begin.isoformat(),
        p.pay_period_end.isoformat(),
        p.check_date.isoformat(),
        p.gross_pay,
        p.pre_tax_deductions,
        p.employee_taxes,
        p.post_tax_deductions,
        p.net_pay,
        p.employee_401k,
        p.employer_401k_match,
        p.life_choice,
    ]
    self._values().append(
        spreadsheetId=self.spreadsheet_id,
        range="Payslips!A:L",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()
```

- [ ] **Step 4: Run all sheet tests**

```bash
cd finances && python -m pytest tests/test_sheets.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Update init_sheets.py**

In `finances/backend/init_sheets.py`, replace:

```python
    for title in ("Transactions", "Categories", "Logs"):
        _ensure_sheet(svc, settings.google_sheets_id, title)
```

With:

```python
    for title in ("Transactions", "Categories", "Logs", "Payslips"):
        _ensure_sheet(svc, settings.google_sheets_id, title)
```

Then add the Payslips header write after the Logs header write (before the final print):

```python
    vals.update(
        spreadsheetId=settings.google_sheets_id,
        range="Payslips!A1:L1",
        valueInputOption="RAW",
        body={"values": [[
            "Company", "Pay Period Begin", "Pay Period End", "Check Date",
            "Gross Pay", "Pre Tax Deductions", "Employee Taxes", "Post Tax Deductions",
            "Net Pay", "401k Salary", "401k Employer Match", "Life@ Choice",
        ]]},
    ).execute()
    print("Sheets initialised (Transactions, Categories, Logs, Payslips).")
```

Also replace the existing final print:

```python
    print("Sheets initialised (Transactions, Categories, Logs).")
```

With the new print line shown above.

- [ ] **Step 6: Commit**

```bash
git add finances/backend/sheets.py finances/backend/init_sheets.py finances/tests/test_sheets.py
git commit -m "feat: add append_payslip to SheetsClient and init Payslips tab"
```

---

## Task 4: Add payslip detection and routing to chat.py

**Files:**
- Modify: `finances/backend/chat.py`
- Test: `finances/tests/test_chat.py`

- [ ] **Step 1: Write the failing test**

Read `finances/tests/test_chat.py` first to understand the existing test structure, then add:

```python
def test_chat_payslip_pdf_saves_payslip_and_transaction(client):
    from unittest.mock import MagicMock, patch
    from datetime import date
    from backend.models import ParsedPayslip

    parsed = ParsedPayslip(
        company="Meta Platforms, Inc.",
        pay_period_begin=date(2026, 4, 6),
        pay_period_end=date(2026, 4, 19),
        check_date=date(2026, 4, 24),
        gross_pay=8628.24,
        pre_tax_deductions=1067.69,
        employee_taxes=2758.68,
        post_tax_deductions=0.00,
        net_pay=4801.87,
        employee_401k=1035.39,
        employer_401k_match=1035.39,
        life_choice=1129.17,
    )
    mock_sheets = MagicMock()
    mock_sheets.get_all_transactions.return_value = []

    mock_reply = MagicMock()
    mock_reply.content = [MagicMock(text="Payslip saved!")]
    mock_reply.usage = MagicMock(input_tokens=10, output_tokens=5)

    fake_pdf = b"%PDF-1.4 payslip content"

    with patch("backend.chat._get_sheets_client", return_value=mock_sheets), \
         patch("backend.chat.require_auth", return_value={"email": "test@test.com"}), \
         patch("backend.chat._is_credit_card_bill", return_value=False), \
         patch("backend.chat._is_payslip", return_value=True), \
         patch("backend.chat.parse_payslip", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_reply
        resp = client.post(
            "/api/chat",
            data={"message": "here is my payslip", "history": "[]"},
            files={"file": ("payslip.pdf", fake_pdf, "application/pdf")},
        )

    assert resp.status_code == 200
    mock_sheets.append_payslip.assert_called_once_with(parsed)
    mock_sheets.append_transaction.assert_called_once()
    saved_tx = mock_sheets.append_transaction.call_args[0][0]
    assert saved_tx.amount == 4801.87
    assert saved_tx.type == "income"
    assert saved_tx.source == "payslip"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd finances && python -m pytest tests/test_chat.py::test_chat_payslip_pdf_saves_payslip_and_transaction -v
```

Expected: `FAILED` — attribute or import error since `_is_payslip` and `parse_payslip` don't exist in `chat.py` yet.

- [ ] **Step 3: Update chat.py**

At the top of `finances/backend/chat.py`, add the import for `parse_payslip` alongside the existing parser imports:

```python
from backend.payslip_parser import parse_payslip
```

After the existing `_is_credit_card_bill` function, add:

```python
def _is_payslip(file_bytes: bytes) -> bool:
    """Detect if PDF is a payslip by checking for known markers."""
    try:
        import pdfplumber
        import io
    except ImportError:
        return False

    markers = ["net pay", "gross pay", "pay period", "pre tax deductions", "check date"]
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if pdf.pages:
                text = (pdf.pages[0].extract_text() or "").lower()
                found = sum(1 for m in markers if m in text)
                return found >= 3
    except Exception as e:
        logger.warning(f"Error detecting payslip: {e}")
    return False
```

Inside the `chat()` endpoint, find the PDF routing block:

```python
        elif ct == "application/pdf":
            # Check if this is a credit card statement
            if _is_credit_card_bill(file_bytes):
                ...
            else:
                # Generic PDF statement parser
                saved, skipped_count = _save_expenses(
                    parse_pdf_statement(file_bytes), sheets
                )
```

Replace the `else` branch with:

```python
            elif _is_payslip(file_bytes):
                parsed_payslips = parse_payslip(file_bytes)
                if not parsed_payslips:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract payslip data from this PDF.",
                    )
                saved = []
                payslip_summaries = []
                for p in parsed_payslips:
                    sheets.append_payslip(p)
                    income_tx = Transaction.from_create(
                        TransactionCreate(
                            date=p.check_date,
                            amount=p.net_pay,
                            merchant=p.company,
                            category="Income",
                            type="income",
                            notes=f"Pay period: {p.pay_period_begin} - {p.pay_period_end}",
                        ),
                        source="payslip",
                    )
                    sheets.append_transaction(income_tx)
                    saved.append(income_tx)
                    payslip_summaries.append(
                        f"{p.company} (Gross: ${p.gross_pay:,.2f}, Net: ${p.net_pay:,.2f}, Date: {p.check_date})"
                    )
                result = (
                    f"[BACKEND RESULT] Saved {len(parsed_payslips)} payslip(s) to Payslips sheet "
                    f"and {len(saved)} income transaction(s): "
                    + "; ".join(payslip_summaries)
                    + "."
                )
            else:
                # Generic PDF statement parser
                saved, skipped_count = _save_expenses(
                    parse_pdf_statement(file_bytes), sheets
                )
```

Note: for the payslip branch, `skipped_count` is not used, and `result` is set directly rather than going through the generic result-building logic below. Make sure the payslip branch sets `result` before the generic result block runs. The cleanest approach: wrap the generic result-building block (the `if saved: ... elif skipped_count: ... else:` block) in an `if result is None:` guard, and initialise `result = None` before the file-type detection.

Full updated structure for the result section of `chat()`:

```python
    result = None  # will be set by whichever branch runs

    if file:
        file_bytes = await file.read()
        b64 = base64.standard_b64encode(file_bytes).decode()
        ct = file.content_type or ""
        if ct.startswith("image/"):
            saved, skipped_count = _save_expenses(parse_receipt_image(file_bytes, ct), sheets)
            file_block = {"type": "image", "source": {"type": "base64", "media_type": ct, "data": b64}}
        elif ct == "application/pdf":
            if _is_credit_card_bill(file_bytes):
                logger.info("Detected credit card statement, using specialized parser")
                try:
                    cc_transactions = parse_credit_card_bill_pdf(file_bytes)
                    logger.info(f"Parsed {len(cc_transactions)} transactions from credit card bill")
                    await categorize_transactions(cc_transactions)
                    logger.info("Categorized transactions")
                    saved, skipped_count = dedup_and_save_credit_card_transactions(
                        cc_transactions, sheets
                    )
                    logger.info(f"Saved {len(saved)} credit card transactions, skipped {skipped_count}")
                except Exception as e:
                    logger.error(f"Error parsing credit card bill: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to parse credit card statement: {str(e)}",
                    )
            elif _is_payslip(file_bytes):
                parsed_payslips = parse_payslip(file_bytes)
                if not parsed_payslips:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract payslip data from this PDF.",
                    )
                saved = []
                payslip_summaries = []
                for p in parsed_payslips:
                    sheets.append_payslip(p)
                    income_tx = Transaction.from_create(
                        TransactionCreate(
                            date=p.check_date,
                            amount=p.net_pay,
                            merchant=p.company,
                            category="Income",
                            type="income",
                            notes=f"Pay period: {p.pay_period_begin} - {p.pay_period_end}",
                        ),
                        source="payslip",
                    )
                    sheets.append_transaction(income_tx)
                    saved.append(income_tx)
                    payslip_summaries.append(
                        f"{p.company} (Gross: ${p.gross_pay:,.2f}, Net: ${p.net_pay:,.2f}, Date: {p.check_date})"
                    )
                result = (
                    f"[BACKEND RESULT] Saved {len(parsed_payslips)} payslip(s) to Payslips sheet "
                    f"and {len(saved)} income transaction(s): "
                    + "; ".join(payslip_summaries)
                    + "."
                )
            else:
                saved, skipped_count = _save_expenses(
                    parse_pdf_statement(file_bytes), sheets
                )
            file_block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Send an image or PDF.")
        user_content = [file_block, {"type": "text", "text": message}]
    else:
        saved, skipped_count = _save_expenses(parse_expense_text(message), sheets)

    # 2. Fetch all transactions (after saving)
    transactions = sheets.get_all_transactions()
    tx_json = json.dumps([
        {"date": str(t.date), "amount": t.amount, "merchant": t.merchant,
         "category": t.category, "type": t.type}
        for t in transactions
    ])

    # 3. Build system prompt
    system = _SYSTEM + f"\n\nTransaction data: {tx_json}"
    if result is None:
        if saved:
            summary = ", ".join(
                f"${t.amount:.2f} at {t.merchant} [{t.category}] on {t.date}" for t in saved
            )
            result = f"[BACKEND RESULT] Saved {len(saved)} expense(s): {summary}."
            if skipped_count:
                result += f" Skipped {skipped_count} duplicate(s)."
        elif skipped_count:
            result = f"[BACKEND RESULT] All {skipped_count} expense(s) were duplicates — already in your history."
        else:
            result = "[BACKEND RESULT] 0 expenses saved — message format not recognized by the expense parser."
    system += f"\n\n{result}"
```

- [ ] **Step 4: Run the new test**

```bash
cd finances && python -m pytest tests/test_chat.py::test_chat_payslip_pdf_saves_payslip_and_transaction -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

```bash
cd finances && python -m pytest -v
```

Expected: All tests pass. Count should be previous total + 4 new tests.

- [ ] **Step 6: Commit**

```bash
git add finances/backend/chat.py finances/tests/test_chat.py
git commit -m "feat: payslip PDF detection and routing in chat endpoint"
```
