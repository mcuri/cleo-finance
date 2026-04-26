from unittest.mock import MagicMock, patch
from datetime import date
import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def mock_sheets():
    return MagicMock()

@pytest.fixture
def client(mock_sheets):
    with patch("backend.transactions.get_sheets_client", return_value=mock_sheets), \
         patch("backend.categories.get_sheets_client", return_value=mock_sheets), \
         patch("backend.auth.require_auth", return_value={"email": "test@test.com"}):
        yield TestClient(app)

def test_list_transactions_empty(client, mock_sheets):
    mock_sheets.get_all_transactions.return_value = []
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    assert resp.json() == []

def test_create_transaction(client, mock_sheets):
    mock_sheets.find_duplicate.return_value = False
    mock_sheets.append_transaction.return_value = None
    resp = client.post("/api/transactions", json={
        "date": "2026-04-20",
        "amount": 47.50,
        "merchant": "Trader Joe's",
        "category": "Groceries",
        "type": "expense",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["merchant"] == "Trader Joe's"
    assert data["source"] == "web"
    assert "id" in data

def test_create_transaction_duplicate_warns(client, mock_sheets):
    mock_sheets.find_duplicate.return_value = True
    resp = client.post("/api/transactions", json={
        "date": "2026-04-20",
        "amount": 47.50,
        "merchant": "Trader Joe's",
        "category": "Groceries",
        "type": "expense",
    })
    assert resp.status_code == 409

def test_delete_transaction(client, mock_sheets):
    mock_sheets.delete_transaction.return_value = True
    resp = client.delete("/api/transactions/abc123")
    assert resp.status_code == 204

def test_delete_transaction_not_found(client, mock_sheets):
    mock_sheets.delete_transaction.return_value = False
    resp = client.delete("/api/transactions/notexist")
    assert resp.status_code == 404

def test_update_transaction_applies_amount_and_merchant(client, mock_sheets):
    from backend.models import Transaction
    existing = Transaction(
        id="abc123",
        date=date(2026, 4, 20),
        amount=10.0,
        merchant="Old Name",
        category="Groceries",
        type="expense",
        source="web",
    )
    mock_sheets.get_all_transactions.return_value = [existing]
    mock_sheets.update_transaction.return_value = True
    resp = client.put("/api/transactions/abc123", json={
        "merchant": "New Name",
        "amount": 25.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant"] == "New Name"
    assert data["amount"] == 25.0
    assert data["category"] == "Groceries"  # unchanged

def test_update_transaction_not_found(client, mock_sheets):
    mock_sheets.get_all_transactions.return_value = []
    resp = client.put("/api/transactions/notexist", json={"merchant": "X"})
    assert resp.status_code == 404
