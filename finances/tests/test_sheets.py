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
    assert len(row) == 5
    assert "T" in row[0]  # ISO-8601 timestamp sanity check
    assert row[1] == "chat"
    assert row[2] == "claude-haiku-4-5-20251001"
    assert row[3] == 100
    assert row[4] == 50

def test_append_payslip(sheets_client, mock_service):
    from backend.models import ParsedPayslip
    p = ParsedPayslip(
        company="Meta Platforms, Inc.",
        pay_period_begin=date(2026, 4, 6),
        pay_period_end=date(2026, 4, 19),
        check_date=date(2026, 4, 24),
        gross_pay=8628.24,
        pre_tax_deductions=1067.69,
        employee_taxes=2758.68,
        post_tax_deductions=0.00,
        net_pay=4801.87,
        employee_401k=1035.39,
        employer_401k_match=1035.39,
        life_choice=1129.17,
    )
    sheets_client.append_payslip(p)
    mock_service.spreadsheets().values().append.assert_called_once()
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    assert kwargs["range"] == "Payslips!A:L"
    row = kwargs["body"]["values"][0]
    assert row[0] == "Meta Platforms, Inc."
    assert row[8] == 4801.87   # net_pay
    assert row[9] == 1035.39   # employee_401k
    assert row[10] == 1035.39  # employer_401k_match
    assert row[11] == 1129.17  # life_choice

def test_append_transaction_includes_created_at(sheets_client, mock_service):
    t = Transaction(
        id="abc123",
        date=date(2026, 4, 20),
        amount=47.50,
        merchant="Trader Joe's",
        category="Groceries",
        type="expense",
        source="web",
        created_at="2026-04-20T10:00:00",
    )
    sheets_client.append_transaction(t)
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    assert kwargs["range"] == "Transactions!A:I"
    row = kwargs["body"]["values"][0]
    assert len(row) == 9
    assert row[8] == "2026-04-20T10:00:00"


def test_get_all_transactions_reads_created_at(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [[
            "id1", "2026-04-20", "47.50", "Trader Joe's",
            "Groceries", "expense", "web", "", "2026-04-20T10:00:00",
        ]]
    }
    result = sheets_client.get_all_transactions()
    assert result[0].created_at == "2026-04-20T10:00:00"


def test_get_all_transactions_missing_created_at_defaults_empty(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [[
            "id1", "2026-04-20", "47.50", "Trader Joe's",
            "Groceries", "expense", "web",
        ]]
    }
    result = sheets_client.get_all_transactions()
    assert result[0].created_at == ""
