from backend.sheets import build_service
from backend.config import get_settings

PREDEFINED = [
    "Utilities", "Groceries", "Restaurants", "Transport",
    "Entertainment", "Health", "Shopping", "Travel", "Income", "Other",
]

def init():
    settings = get_settings()
    svc = build_service()
    vals = svc.spreadsheets().values()

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
    print("Sheets initialised.")

if __name__ == "__main__":
    init()
