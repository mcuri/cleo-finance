from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import backend.transactions as _self

from backend.models import Transaction, TransactionCreate, TransactionUpdate
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


@router.put("/{transaction_id}", response_model=Transaction)
def update_transaction(
    transaction_id: str,
    data: TransactionUpdate,
    sheets: SheetsClient = Depends(_get_sheets_client),
):
    # Get current transaction
    transactions = sheets.get_all_transactions()
    current_transaction = None
    for t in transactions:
        if t.id == transaction_id:
            current_transaction = t
            break
    
    if not current_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Prepare updates
    updates = {}
    if data.date is not None:
        updates['date'] = data.date
    if data.amount is not None:
        updates['amount'] = data.amount
    if data.merchant is not None:
        updates['merchant'] = data.merchant
    if data.category is not None:
        updates['category'] = data.category
    if data.type is not None:
        updates['type'] = data.type
    if data.notes is not None:
        updates['notes'] = data.notes

    if not updates:
        return current_transaction  # No changes needed

    # Update in spreadsheet
    if not sheets.update_transaction(transaction_id, updates):
        raise HTTPException(status_code=500, detail="Failed to update transaction")

    # Return updated transaction
    return Transaction(
        id=current_transaction.id,
        date=updates.get('date', current_transaction.date),
        amount=updates.get('amount', current_transaction.amount),
        merchant=updates.get('merchant', current_transaction.merchant),
        category=updates.get('category', current_transaction.category),
        type=updates.get('type', current_transaction.type),
        source=current_transaction.source,
        notes=updates.get('notes', current_transaction.notes),
    )
