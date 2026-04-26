import json
import os
from typing import List
from datetime import date as date_type, datetime

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from backend.models import Transaction, Category, TransactionSource, ParsedPayslip

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service-account.json")


def build_service():
    if os.path.exists(_SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_service_account_file(_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    else:
        from backend.config import get_settings
        info = json.loads(get_settings().google_service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


class SheetsClient:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self._service = build_service()

    def _values(self):
        return self._service.spreadsheets().values()

    def _get_sheet_id(self, sheet_name: str) -> int:
        meta = self._service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id
        ).execute()
        for sheet in meta["sheets"]:
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        raise ValueError(f"Sheet '{sheet_name}' not found")

    def append_transaction(self, t: Transaction) -> None:
        row = [
            t.id,
            t.date.isoformat(),
            t.amount,
            t.merchant,
            t.category,
            t.type,
            t.source,
            t.notes or "",
            t.created_at,
        ]
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A:I",
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

    def find_duplicate_payslip(self, company: str, check_date: date_type) -> bool:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Payslips!A:D",
        ).execute()
        rows = result.get("values", [])[1:]  # skip header
        return any(len(r) >= 4 and r[0] == company and r[3] == check_date.isoformat() for r in rows)

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

    def get_all_transactions(self) -> List[Transaction]:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A2:I",
        ).execute()
        rows = result.get("values", [])
        transactions = []
        for row in rows:
            if len(row) < 7:
                continue
            transactions.append(Transaction(
                id=row[0],
                date=date_type.fromisoformat(row[1]),
                amount=float(row[2]),
                merchant=row[3],
                category=row[4],
                type=row[5],
                source=row[6],
                notes=row[7] if len(row) > 7 and row[7] else None,
                created_at=row[8] if len(row) > 8 else "",
            ))
        return transactions

    def delete_transaction(self, transaction_id: str) -> bool:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A:A",
        ).execute()
        rows = result.get("values", [])
        for idx, row in enumerate(rows):
            if row and row[0] == transaction_id:
                sheet_id = self._get_sheet_id("Transactions")
                self._service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": [{"deleteDimension": {"range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    }}}]},
                ).execute()
                return True
        return False

    def update_transaction(self, transaction_id: str, updates: dict) -> bool:
        """Update a transaction with the given field updates."""
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Transactions!A:A",
        ).execute()
        rows = result.get("values", [])
        for idx, row in enumerate(rows):
            if row and row[0] == transaction_id:
                # Get the current transaction data
                current_result = self._values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"Transactions!A{idx+1}:I{idx+1}",
                ).execute()
                current_row = current_result.get("values", [[]])[0]

                # Update the fields
                updated_row = current_row.copy()
                field_map = {
                    'date': 1,
                    'amount': 2,
                    'merchant': 3,
                    'category': 4,
                    'type': 5,
                    'notes': 7
                }

                for field, value in updates.items():
                    if field in field_map:
                        if field == 'date' and hasattr(value, 'isoformat'):
                            updated_row[field_map[field]] = value.isoformat()
                        else:
                            updated_row[field_map[field]] = str(value)

                # Update the row
                self._values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"Transactions!A{idx+1}:I{idx+1}",
                    valueInputOption="RAW",
                    body={"values": [updated_row]},
                ).execute()
                return True
        return False

    def find_duplicate(self, date: date_type, amount: float, merchant: str) -> bool:
        transactions = self.get_all_transactions()
        for t in transactions:
            if t.date == date and t.amount == amount and t.merchant.lower() == merchant.lower():
                return True
        return False

    def get_categories(self) -> List[Category]:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Categories!A2:B",
        ).execute()
        rows = result.get("values", [])
        return [
            Category(name=row[0], predefined=(row[1].upper() == "TRUE"))
            for row in rows
            if len(row) >= 2
        ]

    def append_category(self, name: str) -> None:
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Categories!A:B",
            valueInputOption="RAW",
            body={"values": [[name, "FALSE"]]},
        ).execute()

    def delete_category(self, name: str) -> bool:
        result = self._values().get(
            spreadsheetId=self.spreadsheet_id,
            range="Categories!A:A",
        ).execute()
        rows = result.get("values", [])
        for idx, row in enumerate(rows):
            if row and row[0] == name:
                sheet_id = self._get_sheet_id("Categories")
                self._service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": [{"deleteDimension": {"range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    }}}]},
                ).execute()
                return True
        return False

    def append_log(self, endpoint: str, model: str, input_tokens: int, output_tokens: int) -> None:
        row = [datetime.utcnow().isoformat(), endpoint, model, input_tokens, output_tokens]
        self._values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Logs!A:E",
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()
