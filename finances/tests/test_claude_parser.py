from unittest.mock import MagicMock, patch
import pytest
from backend.claude_parser import parse_expense_text, parse_receipt_image

def _mock_response(text: str):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock

VALID_JSON = '{"amount": 100.0, "merchant": "Trader Joe\'s", "category": "Groceries", "date": "2026-04-20", "confidence": 0.95}'

def test_parse_expense_text_returns_parsed_expense():
    with patch("backend.claude_parser._client") as mock_client:
        mock_client.messages.create.return_value = _mock_response(f"[{VALID_JSON}]")
        result = parse_expense_text("I spent $100 at Trader Joe's on groceries")
    assert len(result) == 1
    assert result[0].amount == 100.0
    assert result[0].merchant == "Trader Joe's"
    assert result[0].confidence == 0.95

def test_parse_expense_text_malformed_json_returns_empty_list():
    with patch("backend.claude_parser._client") as mock_client:
        mock_client.messages.create.return_value = _mock_response("not valid json at all")
        result = parse_expense_text("gibberish")
    assert result == []

def test_parse_receipt_image_returns_parsed_expense():
    with patch("backend.claude_parser._client") as mock_client:
        mock_client.messages.create.return_value = _mock_response(f"[{VALID_JSON}]")
        result = parse_receipt_image(b"fake-image-bytes", "image/jpeg")
    assert len(result) == 1
    assert result[0].amount == 100.0
