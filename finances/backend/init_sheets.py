from backend.sheets import build_service
from backend.config import get_settings

PREDEFINED = [
    "Utilities", "Groceries", "Restaurants", "Transport",
    "Entertainment", "Health", "Shopping", "Travel", "Subscriptions", "Income", "Other",
]

def _ensure_sheet(svc, spreadsheet_id: str, title: str) -> None:
    meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta["sheets"]}
    if title not in existing:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()
        print(f"  Created sheet: {title}")


def init():
    settings = get_settings()
    svc = build_service()
    vals = svc.spreadsheets().values()

    for title in ("Transactions", "Categories", "Logs"):
        _ensure_sheet(svc, settings.google_sheets_id, title)

    vals.update(
        spreadsheetId=settings.google_sheets_id,
        range="Transactions!A1:H1",
        valueInputOption="RAW",
        body={"values": [["id", "date", "amount", "merchant", "category", "type", "source", "notes"]]},
    ).execute()

    rows = [["name", "predefined"]] + [[c, "TRUE"] for c in PREDEFINED]
    vals.update(
        spreadsheetId=settings.google_sheets_id,
        range=f"Categories!A1:B{len(rows)}",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    vals.update(
        spreadsheetId=settings.google_sheets_id,
        range="Logs!A1:E1",
        valueInputOption="RAW",
        body={"values": [["timestamp", "endpoint", "model", "input_tokens", "output_tokens"]]},
    ).execute()
    print("Sheets initialised (Transactions, Categories, Logs).")

if __name__ == "__main__":
    init()
