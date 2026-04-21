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
