from unittest.mock import MagicMock, patch
from datetime import date
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def mock_sheets():
    m = MagicMock()
    m.get_all_transactions.return_value = []
    m.find_duplicate.return_value = False
    return m


@pytest.fixture
def client(mock_sheets):
    with patch("backend.chat.get_sheets_client", return_value=mock_sheets), \
         patch("backend.auth.require_auth", return_value={"email": "test@test.com"}):
        yield TestClient(app)


def test_chat_returns_reply(client, mock_sheets):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="You have no transactions yet.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_cls.return_value.messages.create.return_value = mock_response

        resp = client.post("/api/chat", json={"message": "hello", "history": []})

    assert resp.status_code == 200
    assert resp.json()["reply"] == "You have no transactions yet."


def test_chat_saves_parsed_expense(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(
        amount=15.66, merchant="The Brazilian Spot",
        category="Restaurants", date=date(2026, 4, 18), confidence=0.9,
    )
    with patch("backend.chat.parse_expense_text", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Saved 1 expense.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_cls.return_value.messages.create.return_value = mock_response

        resp = client.post("/api/chat", json={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": [],
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_called_once()


def test_chat_skips_duplicate(client, mock_sheets):
    from backend.models import ParsedExpense
    mock_sheets.find_duplicate.return_value = True
    parsed = ParsedExpense(
        amount=15.66, merchant="The Brazilian Spot",
        category="Restaurants", date=date(2026, 4, 18), confidence=0.9,
    )
    with patch("backend.chat.parse_expense_text", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Skipped duplicate.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
        mock_response.model = "claude-haiku-4-5-20251001"
        mock_cls.return_value.messages.create.return_value = mock_response

        resp = client.post("/api/chat", json={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": [],
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_not_called()
