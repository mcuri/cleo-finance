import json
from datetime import date as date_type
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.credit_card_parser import (
    CreditCardTransaction,
    _clean_merchant_name,
    _extract_location,
    _infer_category_from_keywords,
    _parse_date,
    categorize_transactions,
    dedup_and_save_credit_card_transactions,
    infer_category,
)


class TestCreditCardTransaction:
    def test_creation(self):
        tx = CreditCardTransaction(
            tran_date=date_type(2025, 8, 6),
            post_date=date_type(2025, 8, 8),
            merchant="Safeway",
            amount=32.64,
            location="San Francisco, CA",
            category="Groceries",
        )
        assert tx.merchant == "Safeway"
        assert tx.amount == 32.64
        assert tx.category == "Groceries"


class TestMerchantCleaning:
    def test_clean_simple_merchant(self):
        # "SAFEWAY #2606 SAN FRANCISCO CA"
        cleaned = _clean_merchant_name("SAFEWAY #2606 SAN FRANCISCO CA")
        assert "Safeway" in cleaned
        assert "#2606" not in cleaned

    def test_clean_square_payment(self):
        # "SQ *MISSION BAY CAFE REVE San Francisco CA"
        cleaned = _clean_merchant_name("SQ *MISSION BAY CAFE REVE San Francisco CA")
        assert "Mission Bay Cafe Reve" in cleaned
        assert "SQ" not in cleaned

    def test_clean_merpago(self):
        # "MERPAGO*LOSTULIPANES CIUDAD DE MEX MX"
        cleaned = _clean_merchant_name("MERPAGO*LOSTULIPANES CIUDAD DE MEX MX")
        assert "Lostulipanes" in cleaned
        assert "MX" not in cleaned

    def test_clean_airline(self):
        # "UNITED 0162320966584 UNITED.COM TX"
        cleaned = _clean_merchant_name("UNITED 0162320966584 UNITED.COM TX")
        # Should at least contain United and remove the reference number and .COM
        assert "United" in cleaned
        assert "0162320966584" not in cleaned
        assert ".Com" not in cleaned

    def test_clean_eb_prefix(self):
        # "EB *THE DINAH 2025 FES 801-413-7200 CA"
        cleaned = _clean_merchant_name("EB *THE DINAH 2025 FES 801-413-7200 CA")
        assert "The Dinah" in cleaned
        assert "801" not in cleaned  # phone removed

    def test_clean_reference_number(self):
        # "ROSS STORES SAN FRANCISCO CA 24610436Y03R4APVW"
        cleaned = _clean_merchant_name("ROSS STORES SAN FRANCISCO CA 24610436Y03R4APVW")
        assert "Ross Stores" in cleaned
        assert "24610436Y03R4APVW" not in cleaned
        assert "Francisco" not in cleaned  # location should be removed


class TestLocationExtraction:
    def test_extract_city_state(self):
        loc = _extract_location("SAFEWAY #2606 SAN FRANCISCO CA")
        assert "SAN FRANCISCO" in loc or "San Francisco" in loc
        assert "CA" in loc

    def test_extract_city_country(self):
        loc = _extract_location("RESTAURANTS MEXICO CITY CIUDAD DE MEX MX")
        assert "MX" in loc

    def test_extract_no_location(self):
        loc = _extract_location("AMAZON.COM")
        assert loc == ""


class TestDateParsing:
    def test_parse_date(self):
        d = _parse_date("08/06", 2025)
        assert d == date_type(2025, 8, 6)

    def test_parse_date_different_year(self):
        d = _parse_date("12/31", 2024)
        assert d == date_type(2024, 12, 31)


class TestCategoryInference:
    def test_keyword_match_safeway_groceries(self):
        keywords = {
            "Groceries": ["SAFEWAY", "WHOLE FOODS"],
            "Restaurants": ["CAFE", "PIZZA"],
        }
        category = _infer_category_from_keywords("Safeway #2606 San Francisco, CA", keywords)
        assert category == "Groceries"

    def test_keyword_match_restaurant(self):
        keywords = {
            "Restaurants": ["CAFE", "PIZZA"],
        }
        category = _infer_category_from_keywords("Pizza Hut", keywords)
        assert category == "Restaurants"

    def test_keyword_no_match(self):
        keywords = {
            "Groceries": ["SAFEWAY"],
        }
        category = _infer_category_from_keywords("Random Merchant", keywords)
        assert category is None

    @pytest.mark.asyncio
    @patch("backend.credit_card_parser.anthropic.Anthropic")
    async def test_infer_category_with_claude_fallback(self, mock_anthropic):
        # Mock Claude response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Shopping")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        with patch(
            "backend.credit_card_parser._load_category_keywords", return_value={}
        ):
            category = await infer_category("Random Store San Francisco")
            assert category == "Shopping"
            # Verify Claude was called
            mock_client.messages.create.assert_called_once()


class TestDeduplication:
    def test_dedup_save_credit_card_transactions(self):
        # Mock SheetsClient
        mock_sheets = MagicMock()
        existing_tx = MagicMock()
        existing_tx.date = date_type(2025, 8, 17)  # Use post_date to match dedup key
        existing_tx.amount = 32.64
        existing_tx.merchant = "safeway"
        mock_sheets.get_all_transactions.return_value = [existing_tx]

        # Create transactions
        tx1 = CreditCardTransaction(
            tran_date=date_type(2025, 8, 15),
            post_date=date_type(2025, 8, 17),
            merchant="Safeway",
            amount=32.64,
            category="Groceries",
        )
        tx2 = CreditCardTransaction(
            tran_date=date_type(2025, 8, 20),
            post_date=date_type(2025, 8, 22),
            merchant="Amazon",
            amount=50.00,
            category="Shopping",
        )

        saved, skipped = dedup_and_save_credit_card_transactions(
            [tx1, tx2], mock_sheets
        )

        # tx1 should be skipped (duplicate), tx2 should be saved
        assert skipped == 1
        assert len(saved) == 1
        assert saved[0].merchant == "Amazon"


class TestCategoryMapping:
    def test_category_keywords_file_exists(self):
        keywords_path = Path(__file__).parent.parent / "backend" / "category_keywords.json"
        assert keywords_path.exists(), "category_keywords.json must exist"

        with open(keywords_path) as f:
            keywords = json.load(f)
        
        # Verify structure
        assert isinstance(keywords, dict)
        assert "Groceries" in keywords
        assert "Restaurants" in keywords
        assert all(isinstance(v, list) for v in keywords.values())
