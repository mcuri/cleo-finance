from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def mock_sheets():
    m = MagicMock()
    m.get_all_transactions.return_value = []
    m.find_duplicate.return_value = False
    m.find_duplicate_payslip.return_value = False
    return m


@pytest.fixture
def client():
    with patch("backend.auth.require_auth", return_value={"email": "test@test.com"}):
        yield TestClient(app)


def _webhook_payload(text: str) -> dict:
    return {
        "message": {
            "chat": {"id": 12345},
            "text": text,
        }
    }


def _mock_claude(mock_cls, text="OK"):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
    mock_response.model = "claude-haiku-4-5-20251001"
    mock_cls.return_value.messages.create.return_value = mock_response


def _mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


def test_webhook_rejects_invalid_secret(client):
    resp = client.post(
        "/webhook",
        json=_webhook_payload("hello"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 403


def test_webhook_text_saves_expense_and_replies(mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(amount=12.0, merchant="Cafe", category="Food", confidence=0.9)

    with patch("backend.telegram_bot.SheetsClient", return_value=mock_sheets), \
         patch("backend.telegram_bot.parse_expense_text", return_value=[parsed]), \
         patch("backend.telegram_bot.anthropic.Anthropic") as mock_cls, \
         patch("backend.telegram_bot.log_usage"), \
         patch("backend.telegram_bot.load_user_profile", return_value=""), \
         patch("backend.telegram_bot.extract_and_update_profile", new_callable=AsyncMock), \
         patch("backend.telegram_bot._get_bot", return_value=_mock_bot()), \
         patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value.telegram_webhook_secret = "secret"
        mock_settings.return_value.anthropic_api_key = "key"
        mock_settings.return_value.google_sheets_id = "id"
        _mock_claude(mock_cls, "Saved your lunch!")
        import asyncio
        asyncio.run(
            __import__("backend.telegram_bot", fromlist=["_handle_text"])
            ._handle_text(12345, "lunch at Cafe $12")
        )

    mock_sheets.append_transaction.assert_called_once()


def test_webhook_text_injects_profile(mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(amount=5.0, merchant="Coffee", category="Food", confidence=0.9)

    captured_system = {}

    def fake_create(**kwargs):
        captured_system["system"] = kwargs.get("system", "")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Got it")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_response.model = "claude-haiku-4-5-20251001"
        return mock_response

    with patch("backend.telegram_bot.SheetsClient", return_value=mock_sheets), \
         patch("backend.telegram_bot.parse_expense_text", return_value=[parsed]), \
         patch("backend.telegram_bot.anthropic.Anthropic") as mock_cls, \
         patch("backend.telegram_bot.log_usage"), \
         patch("backend.telegram_bot.load_user_profile", return_value="- Spends on coffee daily"), \
         patch("backend.telegram_bot.extract_and_update_profile", new_callable=AsyncMock), \
         patch("backend.telegram_bot._get_bot", return_value=_mock_bot()), \
         patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value.telegram_webhook_secret = "secret"
        mock_settings.return_value.anthropic_api_key = "key"
        mock_settings.return_value.google_sheets_id = "id"
        mock_cls.return_value.messages.create.side_effect = fake_create
        import asyncio
        asyncio.run(
            __import__("backend.telegram_bot", fromlist=["_handle_text"])
            ._handle_text(12345, "coffee $5")
        )

    assert "Spends on coffee daily" in captured_system.get("system", "")


def test_webhook_text_fires_extraction(mock_sheets):
    from backend.models import ParsedExpense

    with patch("backend.telegram_bot.SheetsClient", return_value=mock_sheets), \
         patch("backend.telegram_bot.parse_expense_text", return_value=[]), \
         patch("backend.telegram_bot.anthropic.Anthropic") as mock_cls, \
         patch("backend.telegram_bot.log_usage"), \
         patch("backend.telegram_bot.load_user_profile", return_value=""), \
         patch("backend.telegram_bot.extract_and_update_profile", new_callable=AsyncMock) as mock_extract, \
         patch("backend.telegram_bot._get_bot", return_value=_mock_bot()), \
         patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value.telegram_webhook_secret = "secret"
        mock_settings.return_value.anthropic_api_key = "key"
        mock_settings.return_value.google_sheets_id = "id"
        _mock_claude(mock_cls, "No expenses found.")
        import asyncio
        asyncio.run(
            __import__("backend.telegram_bot", fromlist=["_handle_text"])
            ._handle_text(12345, "hello")
        )

    mock_extract.assert_awaited_once()


def test_webhook_photo_saves_expense_and_replies(mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(amount=30.0, merchant="Grocery", category="Food", confidence=0.9)
    mock_tg_file = AsyncMock()
    mock_tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"img"))
    mock_bot = _mock_bot()
    mock_bot.get_file = AsyncMock(return_value=mock_tg_file)

    with patch("backend.telegram_bot.SheetsClient", return_value=mock_sheets), \
         patch("backend.telegram_bot.parse_receipt_image", return_value=[parsed]), \
         patch("backend.telegram_bot.anthropic.Anthropic") as mock_cls, \
         patch("backend.telegram_bot.log_usage"), \
         patch("backend.telegram_bot.load_user_profile", return_value=""), \
         patch("backend.telegram_bot.extract_and_update_profile", new_callable=AsyncMock), \
         patch("backend.telegram_bot._get_bot", return_value=mock_bot), \
         patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value.telegram_webhook_secret = "secret"
        mock_settings.return_value.anthropic_api_key = "key"
        mock_settings.return_value.google_sheets_id = "id"
        _mock_claude(mock_cls, "Receipt saved!")
        import asyncio
        asyncio.run(
            __import__("backend.telegram_bot", fromlist=["_handle_photo"])
            ._handle_photo(12345, "file_id_abc")
        )

    mock_sheets.append_transaction.assert_called_once()
    mock_bot.send_message.assert_awaited_once()
