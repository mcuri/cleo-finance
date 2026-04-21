from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import backend.transactions as _self

from backend.models import Transaction, TransactionCreate
from backend.sheets import SheetsClient
from backend.config import get_settings

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


@router.get("", response_model=List[Transaction])
def list_transactions(sheets: SheetsClient = Depends(_get_sheets_client)):
    return sheets.get_all_transactions()


@router.post("", response_model=Transaction, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    sheets: SheetsClient = Depends(_get_sheets_client),
):
    if sheets.find_duplicate(data.date, data.amount, data.merchant):
        raise HTTPException(
            status_code=409,
            detail="A transaction with the same date, amount, and merchant already exists.",
        )
    transaction = Transaction.from_create(data, source="web")
    sheets.append_transaction(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    sheets: SheetsClient = Depends(_get_sheets_client),
):
    if not sheets.delete_transaction(transaction_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
