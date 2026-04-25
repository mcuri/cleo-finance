from unittest.mock import MagicMock, patch
from datetime import date
import pytest
from backend.models import Transaction, Category

FAKE_ID = "fake-spreadsheet-id"

@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.spreadsheets().get().execute.return_value = {
        "sheets": [
            {"properties": {"title": "Transactions", "sheetId": 0}},
            {"properties": {"title": "Categories", "sheetId": 1}},
        ]
    }
    return svc

@pytest.fixture
def sheets_client(mock_service):
    from backend.sheets import SheetsClient
    client = SheetsClient.__new__(SheetsClient)
    client.spreadsheet_id = FAKE_ID
    client._service = mock_service
    return client

def test_append_transaction(sheets_client, mock_service):
    t = Transaction(
        id="abc123",
        date=date(2026, 4, 20),
        amount=47.50,
        merchant="Trader Joe's",
        category="Groceries",
        type="expense",
        source="web",
    )
    sheets_client.append_transaction(t)
    mock_service.spreadsheets().values().append.assert_called_once()
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    row = kwargs["body"]["values"][0]
    assert row[0] == "abc123"
    assert row[2] == 47.50

def test_get_all_transactions_empty(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {"values": []}
    result = sheets_client.get_all_transactions()
    assert result == []

def test_get_categories(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [
            ["Groceries", "TRUE"],
            ["My Custom", "FALSE"],
        ]
    }
    cats = sheets_client.get_categories()
    assert len(cats) == 2
    assert cats[0].name == "Groceries"
    assert cats[0].predefined is True
    assert cats[1].predefined is False

def test_append_log(sheets_client, mock_service):
    sheets_client.append_log("chat", "claude-haiku-4-5-20251001", 100, 50)
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    assert kwargs["range"] == "Logs!A:E"
    row = kwargs["body"]["values"][0]
    assert row[1] == "chat"
    assert row[2] == "claude-haiku-4-5-20251001"
    assert row[3] == 100
    assert row[4] == 50
