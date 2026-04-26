"""
Remove duplicate transactions from the Transactions sheet.

Duplicates are defined as rows with the same (date, amount, merchant — case-insensitive).
The FIRST occurrence is kept; subsequent duplicates are deleted.

Usage:
    python3 -m dedup_transactions          # dry run — shows what would be deleted
    python3 -m dedup_transactions --execute  # actually deletes
"""
import sys
from backend.config import get_settings
from backend.sheets import SheetsClient, build_service

DRY_RUN = "--execute" not in sys.argv


def main():
    settings = get_settings()
    client = SheetsClient(spreadsheet_id=settings.google_sheets_id)

    transactions = client.get_all_transactions()
    print(f"Total rows: {len(transactions)}")

    # Identify duplicates — keep first, mark rest for deletion
    seen: dict = {}   # key → first transaction id
    duplicate_ids: list = []
    for t in transactions:
        key = (t.date, t.amount, t.merchant.lower())
        if key in seen:
            duplicate_ids.append(t.id)
        else:
            seen[key] = t.id

    if not duplicate_ids:
        print("No duplicates found.")
        return

    print(f"\nDuplicates found: {len(duplicate_ids)}")
    for tid in duplicate_ids:
        t = next(x for x in transactions if x.id == tid)
        print(f"  {t.date}  ${t.amount:.2f}  {t.merchant}  [{t.category}]  id={t.id}")

    if DRY_RUN:
        print(f"\nDry run — {len(duplicate_ids)} row(s) would be deleted.")
        print("Run with --execute to delete them.")
        return

    # Delete — use batchUpdate with multiple deleteDimension requests.
    # Must resolve row indices BEFORE any deletions (indices shift after each delete),
    # then delete from highest index to lowest.
    svc = build_service()
    sheet_id = client._get_sheet_id("Transactions")

    # Get current row order from the sheet (column A, includes header at index 0)
    result = svc.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_id,
        range="Transactions!A:A",
    ).execute()
    id_column = [row[0] if row else "" for row in result.get("values", [])]

    # Collect indices (0-based) to delete, highest first
    indices_to_delete = []
    for tid in duplicate_ids:
        try:
            idx = id_column.index(tid)
            indices_to_delete.append(idx)
        except ValueError:
            print(f"  WARNING: id {tid} not found in sheet, skipping")

    indices_to_delete.sort(reverse=True)

    # Build one batchUpdate request per row (already highest-to-lowest, so indices stay valid)
    requests = [
        {"deleteDimension": {"range": {
            "sheetId": sheet_id,
            "dimension": "ROWS",
            "startIndex": idx,
            "endIndex": idx + 1,
        }}}
        for idx in indices_to_delete
    ]

    svc.spreadsheets().batchUpdate(
        spreadsheetId=settings.google_sheets_id,
        body={"requests": requests},
    ).execute()

    print(f"\nDeleted {len(indices_to_delete)} duplicate row(s).")


if __name__ == "__main__":
    main()
