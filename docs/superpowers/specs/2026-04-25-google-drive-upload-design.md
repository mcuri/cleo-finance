# Google Drive PDF Upload — Design Spec

**Date:** 2026-04-25  
**Status:** Approved

---

## Overview

When a payslip PDF or credit card bill PDF is uploaded via chat, save a copy to Google Drive after the existing Sheets save. Files are organized into type and month subfolders under a root `cleo-finance/` folder. Drive upload is best-effort and never blocks or fails the chat response.

---

## Folder Structure

```
cleo-finance/                   ← must exist and be shared with the service account (manual setup)
  Payslips/                     ← created automatically
    2026-04/                    ← created automatically, one per calendar month
      original_filename.pdf
  Credit Card Bills/            ← created automatically
    2026-04/
      original_filename.pdf
```

- Month is derived from `p.check_date` (YYYY-MM) for payslips and from today's date for CC bills.
- Original filename is taken from `file.filename` (the name the user uploaded).
- Subfolders are created automatically on first upload. The root `cleo-finance/` folder must be pre-created and shared with the service account email (same setup as the Google Spreadsheet).

---

## New File: `backend/drive.py`

Single public method:

```python
def upload_pdf(self, file_bytes: bytes, filename: str, doc_type: str, month: str) -> None
```

- `doc_type`: `"Payslips"` or `"Credit Card Bills"`
- `month`: `"YYYY-MM"` string

**`build_drive_service()`** — loads the same service account credentials as `sheets.py` but with the `drive.file` scope:

```python
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
```

**`_get_or_create_folder(service, name, parent_id) -> str`** — searches for a folder with the given name under `parent_id`; creates it if not found. Returns the folder ID.

**`DriveClient.upload_pdf` logic:**
1. Find the root `cleo-finance/` folder by name (no parent constraint). If not found, log a warning and return.
2. `_get_or_create_folder` for the `doc_type` subfolder under root.
3. `_get_or_create_folder` for the `month` subfolder under the type folder.
4. Upload `file_bytes` as `application/pdf` into the month folder with the given filename.

---

## Updated: `backend/sheets.py`

No changes to `sheets.py`. The Drive service account uses a separate `build_drive_service()` in `drive.py` with its own scope list.

---

## Updated: `backend/chat.py`

Add import:

```python
from backend.drive import DriveClient
```

Instantiate once per request (same pattern as `SheetsClient` — lightweight):

```python
drive = DriveClient()
```

**Payslip branch** — after `sheets.append_transaction(income_tx)` in the loop, add:

```python
try:
    drive.upload_pdf(
        file_bytes,
        file.filename or "payslip.pdf",
        "Payslips",
        p.check_date.strftime("%Y-%m"),
    )
except Exception as e:
    logger.warning(f"Drive upload failed for payslip: {e}")
```

**CC bill branch** — after the `dedup_and_save_credit_card_transactions` call succeeds, add:

```python
from datetime import date
try:
    drive.upload_pdf(
        file_bytes,
        file.filename or "cc_bill.pdf",
        "Credit Card Bills",
        date.today().strftime("%Y-%m"),
    )
except Exception as e:
    logger.warning(f"Drive upload failed for CC bill: {e}")
```

The `try/except` wraps each upload so Drive failures never propagate to the user.

---

## Prerequisites (manual)

1. Create a folder named exactly `cleo-finance` in Google Drive.
2. Share it with the service account email (Editor access) — same as the spreadsheet.
3. No config changes needed; the root folder is found by name at runtime.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `cleo-finance/` folder not found | Log warning, skip upload silently |
| Drive API error (quota, network) | Log warning, skip upload silently |
| Subfolder creation fails | Exception propagates to outer `try/except`, logged as warning |
| Both Sheets save and Drive upload fail | Sheets failure raises HTTP error as normal; Drive failure is silent |

---

## Out of Scope

- Duplicate file detection (uploading the same PDF twice creates two Drive files)
- Surfacing the Drive file URL in the chat response
- Deleting Drive files when transactions are deleted
- Generic PDF uploads (only payslips and CC bills)
