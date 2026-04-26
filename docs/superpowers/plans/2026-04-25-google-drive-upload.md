# Google Drive PDF Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After saving a payslip or CC bill to Google Sheets, upload the original PDF to Google Drive under `cleo-finance/Payslips/YYYY-MM/` or `cleo-finance/Credit Card Bills/YYYY-MM/`.

**Architecture:** New `backend/drive.py` with a `DriveClient` class that resolves/creates the folder hierarchy lazily and uploads the PDF using the Drive v3 API. `chat.py` calls `DriveClient().upload_pdf()` in a best-effort `try/except` after each successful Sheets save — Drive failures never block or change the chat response. Uses the same service account credentials as `sheets.py` with the `drive.file` scope.

**Tech Stack:** Python 3.11, `google-api-python-client` (already installed), `google.oauth2.service_account.Credentials`, `googleapiclient.http.MediaIoBaseUpload`.

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/drive.py` | **New** — `build_drive_service`, `_get_or_create_folder`, `DriveClient.upload_pdf` |
| `finances/backend/chat.py` | Add `DriveClient` import + Drive upload calls in payslip and CC bill branches |
| `finances/tests/test_drive.py` | **New** — 2 tests: happy path upload, skip when root not found |
| `finances/tests/test_chat.py` | 2 new tests: Drive called on payslip upload, Drive failure doesn't block response |

---

## Task 1: Create `backend/drive.py`

**Files:**
- Create: `finances/backend/drive.py`
- Create: `finances/tests/test_drive.py`

- [ ] **Step 1: Write the failing tests**

Create `finances/tests/test_drive.py`:

```python
from unittest.mock import MagicMock, patch


def test_upload_pdf_uploads_to_correct_folder():
    from backend.drive import DriveClient

    mock_svc = MagicMock()
    # Three list() calls: root found, Payslips/ missing, 2026-04/ missing
    mock_svc.files.return_value.list.return_value.execute.side_effect = [
        {"files": [{"id": "root-id"}]},
        {"files": []},
        {"files": []},
    ]
    # Three create() calls: Payslips/ folder, 2026-04/ folder, file upload
    mock_svc.files.return_value.create.return_value.execute.side_effect = [
        {"id": "type-id"},
        {"id": "month-id"},
        {"id": "file-id"},
    ]

    with patch("backend.drive.build_drive_service", return_value=mock_svc):
        client = DriveClient()
        client.upload_pdf(b"pdf-data", "payslip.pdf", "Payslips", "2026-04")

    assert mock_svc.files.return_value.create.call_count == 3
    last_call = mock_svc.files.return_value.create.call_args_list[2]
    assert last_call.kwargs["body"]["name"] == "payslip.pdf"
    assert last_call.kwargs["body"]["parents"] == ["month-id"]


def test_upload_pdf_skips_when_root_not_found():
    from backend.drive import DriveClient

    mock_svc = MagicMock()
    mock_svc.files.return_value.list.return_value.execute.return_value = {"files": []}

    with patch("backend.drive.build_drive_service", return_value=mock_svc):
        client = DriveClient()
        client.upload_pdf(b"pdf-data", "payslip.pdf", "Payslips", "2026-04")

    mock_svc.files.return_value.create.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances && python3 -m pytest tests/test_drive.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'backend.drive'`.

- [ ] **Step 3: Create `finances/backend/drive.py`**

```python
import json
import logging
import os
from io import BytesIO

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service-account.json")
_ROOT_FOLDER_NAME = "cleo-finance"


def build_drive_service():
    if os.path.exists(_SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_service_account_file(_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    else:
        from backend.config import get_settings
        info = json.loads(get_settings().google_service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    query = (
        f"name = '{name}' and '{parent_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()
    return folder["id"]


class DriveClient:
    def __init__(self):
        self._service = build_drive_service()

    def upload_pdf(self, file_bytes: bytes, filename: str, doc_type: str, month: str) -> None:
        query = (
            f"name = '{_ROOT_FOLDER_NAME}' "
            f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        results = self._service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])
        if not files:
            logger.warning(f"'{_ROOT_FOLDER_NAME}' folder not found in Drive; skipping upload")
            return
        root_id = files[0]["id"]
        type_id = _get_or_create_folder(self._service, doc_type, root_id)
        month_id = _get_or_create_folder(self._service, month, type_id)
        media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype="application/pdf")
        self._service.files().create(
            body={"name": filename, "parents": [month_id]},
            media_body=media,
            fields="id",
        ).execute()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd finances && python3 -m pytest tests/test_drive.py -v
```

Expected: Both tests pass.

- [ ] **Step 5: Commit**

```bash
git add finances/backend/drive.py finances/tests/test_drive.py
git commit -m "feat: add DriveClient for PDF upload to Google Drive"
```

---

## Task 2: Wire DriveClient into chat.py

**Files:**
- Modify: `finances/backend/chat.py`
- Test: `finances/tests/test_chat.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `finances/tests/test_chat.py`:

```python
def test_chat_payslip_pdf_uploads_to_drive(client, mock_sheets):
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
    with patch("backend.chat._is_credit_card_bill", return_value=False), \
         patch("backend.chat._is_payslip", return_value=True), \
         patch("backend.chat.parse_payslip", return_value=[parsed]), \
         patch("backend.chat.DriveClient") as mock_drive_cls, \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Payslip saved!")
        resp = client.post(
            "/api/chat",
            data={"message": "here is my payslip", "history": "[]"},
            files={"file": ("Meta_payslip.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert resp.status_code == 200
    mock_drive_cls.return_value.upload_pdf.assert_called_once_with(
        b"%PDF-1.4", "Meta_payslip.pdf", "Payslips", "2026-04"
    )


def test_chat_drive_failure_does_not_affect_response(client, mock_sheets):
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
    with patch("backend.chat._is_credit_card_bill", return_value=False), \
         patch("backend.chat._is_payslip", return_value=True), \
         patch("backend.chat.parse_payslip", return_value=[parsed]), \
         patch("backend.chat.DriveClient") as mock_drive_cls, \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_drive_cls.return_value.upload_pdf.side_effect = Exception("Drive unavailable")
        _mock_claude(mock_cls, "Payslip saved!")
        resp = client.post(
            "/api/chat",
            data={"message": "here is my payslip", "history": "[]"},
            files={"file": ("payslip.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances && python3 -m pytest tests/test_chat.py::test_chat_payslip_pdf_uploads_to_drive tests/test_chat.py::test_chat_drive_failure_does_not_affect_response -v
```

Expected: `FAILED` — `cannot import name 'DriveClient' from 'backend.chat'`.

- [ ] **Step 3: Update `chat.py`**

**a. Add import** — after `from backend.sheets import SheetsClient` (line 23), add:

```python
from backend.drive import DriveClient
```

**b. Add Drive upload to payslip branch** — replace the `result = (...)` block at the end of the `elif _is_payslip` branch (currently lines 218–223) with:

```python
                result = (
                    f"[BACKEND RESULT] Saved {len(parsed_payslips)} payslip(s) to Payslips sheet "
                    f"and {len(saved)} income transaction(s): "
                    + "; ".join(payslip_summaries)
                    + "."
                )
                try:
                    DriveClient().upload_pdf(
                        file_bytes,
                        file.filename or "payslip.pdf",
                        "Payslips",
                        parsed_payslips[0].check_date.strftime("%Y-%m"),
                    )
                except Exception as e:
                    logger.warning(f"Drive upload failed for payslip: {e}")
```

**c. Add Drive upload to CC bill branch** — after the existing `except Exception as e: raise HTTPException(...)` block in the `if _is_credit_card_bill` branch (currently ending around line 191), add a new `try/except` block at the same indentation level as the existing `try`:

```python
                try:
                    DriveClient().upload_pdf(
                        file_bytes,
                        file.filename or "cc_bill.pdf",
                        "Credit Card Bills",
                        date_type.today().strftime("%Y-%m"),
                    )
                except Exception as e:
                    logger.warning(f"Drive upload failed for CC bill: {e}")
```

The full `if _is_credit_card_bill` block after the change:

```python
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
                try:
                    DriveClient().upload_pdf(
                        file_bytes,
                        file.filename or "cc_bill.pdf",
                        "Credit Card Bills",
                        date_type.today().strftime("%Y-%m"),
                    )
                except Exception as e:
                    logger.warning(f"Drive upload failed for CC bill: {e}")
```

- [ ] **Step 4: Run the two new tests**

```bash
cd finances && python3 -m pytest tests/test_chat.py::test_chat_payslip_pdf_uploads_to_drive tests/test_chat.py::test_chat_drive_failure_does_not_affect_response -v
```

Expected: Both pass.

- [ ] **Step 5: Run full test suite**

```bash
cd finances && python3 -m pytest -v
```

Expected: All tests pass. Count should be previous total + 4 new tests (2 drive + 2 chat).

- [ ] **Step 6: Commit**

```bash
git add finances/backend/chat.py finances/tests/test_chat.py
git commit -m "feat: upload payslip and CC bill PDFs to Google Drive after save"
```
