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
    m.find_duplicate_payslip.return_value = False
    return m


@pytest.fixture
def client(mock_sheets):
    with patch("backend.chat.get_sheets_client", return_value=mock_sheets), \
         patch("backend.auth.require_auth", return_value={"email": "test@test.com"}):
        yield TestClient(app)


def _mock_claude(mock_cls, text="OK"):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
    mock_response.model = "claude-haiku-4-5-20251001"
    mock_cls.return_value.messages.create.return_value = mock_response


def test_chat_returns_reply(client):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "You have no transactions yet.")
        resp = client.post("/api/chat", data={"message": "hello", "history": "[]"})

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
        _mock_claude(mock_cls, "Saved 1 expense.")
        resp = client.post("/api/chat", data={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": "[]",
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_called_once()


def test_chat_skips_duplicate(client, mock_sheets):
    from backend.models import ParsedExpense, Transaction, TransactionCreate
    existing = Transaction.from_create(
        TransactionCreate(
            date=date(2026, 4, 18), amount=15.66, merchant="The Brazilian Spot",
            category="Restaurants", type="expense",
        ),
        source="web",
    )
    mock_sheets.get_all_transactions.return_value = [existing]
    parsed = ParsedExpense(
        amount=15.66, merchant="The Brazilian Spot",
        category="Restaurants", date=date(2026, 4, 18), confidence=0.9,
    )
    with patch("backend.chat.parse_expense_text", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Skipped duplicate.")
        resp = client.post("/api/chat", data={
            "message": "Stanford FCU charge $15.66 at The Brazilian Spot",
            "history": "[]",
        })

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_not_called()


def test_chat_skips_within_batch_duplicate(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(
        amount=15.66, merchant="The Brazilian Spot",
        category="Restaurants", date=date(2026, 4, 18), confidence=0.9,
    )
    with patch("backend.chat.parse_expense_text", return_value=[parsed, parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Saved 1.")
        resp = client.post("/api/chat", data={"message": "...", "history": "[]"})

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_called_once()


def test_chat_with_image_file(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = ParsedExpense(amount=25.0, merchant="Whole Foods", category="Groceries", confidence=0.9)
    with patch("backend.chat.parse_receipt_image", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Saved receipt.")
        resp = client.post("/api/chat",
            data={"message": "what's on this receipt?", "history": "[]"},
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert resp.status_code == 200
    mock_sheets.append_transaction.assert_called_once()


def test_chat_with_pdf_file(client, mock_sheets):
    from backend.models import ParsedExpense
    parsed = [
        ParsedExpense(amount=50.0, merchant="Amazon", category="Shopping", confidence=0.9),
        ParsedExpense(amount=12.0, merchant="Netflix", category="Subscriptions", confidence=0.9),
    ]
    with patch("backend.chat.parse_pdf_statement", return_value=parsed), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Saved 2 transactions from statement.")
        resp = client.post("/api/chat",
            data={"message": "import this statement", "history": "[]"},
            files={"file": ("statement.pdf", b"fake-pdf-bytes", "application/pdf")},
        )

    assert resp.status_code == 200
    assert mock_sheets.append_transaction.call_count == 2


def test_chat_payslip_pdf_saves_payslip_and_transaction(client, mock_sheets):
    from backend.models import ParsedPayslip
    parsed = ParsedPayslip(
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

    with patch("backend.chat._is_credit_card_bill", return_value=False), \
         patch("backend.chat._is_payslip", return_value=True), \
         patch("backend.chat.parse_payslip", return_value=[parsed]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Payslip saved!")
        resp = client.post(
            "/api/chat",
            data={"message": "here is my payslip", "history": "[]"},
            files={"file": ("payslip.pdf", b"%PDF-1.4 payslip content", "application/pdf")},
        )

    assert resp.status_code == 200
    mock_sheets.append_payslip.assert_called_once_with(parsed)
    mock_sheets.append_transaction.assert_called_once()
    saved_tx = mock_sheets.append_transaction.call_args[0][0]
    assert saved_tx.amount == 4801.87
    assert saved_tx.type == "income"
    assert saved_tx.source == "payslip"


def test_chat_cc_bill_pdf_uploads_to_drive(client, mock_sheets):
    with patch("backend.chat._is_credit_card_bill", return_value=True), \
         patch("backend.chat.parse_credit_card_bill_pdf", return_value=[]), \
         patch("backend.chat.categorize_transactions"), \
         patch("backend.chat.dedup_and_save_credit_card_transactions", return_value=([], 0)), \
         patch("backend.chat.DriveClient") as mock_drive_cls, \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "CC bill processed!")
        resp = client.post(
            "/api/chat",
            data={"message": "here is my cc bill", "history": "[]"},
            files={"file": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert resp.status_code == 200
    mock_drive_cls.return_value.upload_pdf.assert_called_once()
    call_args = mock_drive_cls.return_value.upload_pdf.call_args
    assert call_args[0][2] == "Credit Card Bills"


def test_chat_payslip_pdf_uploads_to_drive(client, mock_sheets):
    from backend.models import ParsedPayslip
    parsed = ParsedPayslip(
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
    with patch("backend.chat._is_credit_card_bill", return_value=False), \
         patch("backend.chat._is_payslip", return_value=True), \
         patch("backend.chat.parse_payslip", return_value=[parsed]), \
         patch("backend.chat.DriveClient") as mock_drive_cls, \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        _mock_claude(mock_cls, "Payslip saved!")
        resp = client.post(
            "/api/chat",
            data={"message": "here is my payslip", "history": "[]"},
            files={"file": ("Meta_payslip.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert resp.status_code == 200
    mock_drive_cls.return_value.upload_pdf.assert_called_once_with(
        b"%PDF-1.4", "Meta_payslip.pdf", "Payslips", "2026-04"
    )


def test_chat_drive_failure_does_not_affect_response(client, mock_sheets):
    from backend.models import ParsedPayslip
    parsed = ParsedPayslip(
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
    with patch("backend.chat._is_credit_card_bill", return_value=False), \
         patch("backend.chat._is_payslip", return_value=True), \
         patch("backend.chat.parse_payslip", return_value=[parsed]), \
         patch("backend.chat.DriveClient") as mock_drive_cls, \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"):
        mock_drive_cls.return_value.upload_pdf.side_effect = Exception("Drive unavailable")
        _mock_claude(mock_cls, "Payslip saved!")
        resp = client.post(
            "/api/chat",
            data={"message": "here is my payslip", "history": "[]"},
            files={"file": ("payslip.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert resp.status_code == 200


def test_chat_includes_profile_in_system_prompt(client):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"), \
         patch("backend.chat.load_user_profile", return_value="- Saves regularly"), \
         patch("backend.chat.asyncio.create_task", side_effect=lambda coro: coro.close()):
        _mock_claude(mock_cls, "OK")
        resp = client.post("/api/chat", data={"message": "hello", "history": "[]"})
    assert resp.status_code == 200
    call_kwargs = mock_cls.return_value.messages.create.call_args
    assert "Saves regularly" in call_kwargs.kwargs["system"]


def test_chat_fires_extraction_task(client):
    import inspect
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"), \
         patch("backend.chat.load_user_profile", return_value=""), \
         patch("backend.chat.asyncio.create_task", side_effect=lambda coro: coro.close()) as mock_task:
        _mock_claude(mock_cls, "OK")
        client.post("/api/chat", data={"message": "hello", "history": "[]"})
    assert mock_task.called
    assert inspect.iscoroutine(mock_task.call_args[0][0])


def test_chat_does_not_inject_empty_profile(client):
    with patch("backend.chat.parse_expense_text", return_value=[]), \
         patch("backend.chat.anthropic.Anthropic") as mock_cls, \
         patch("backend.chat.log_usage"), \
         patch("backend.chat.load_user_profile", return_value=""), \
         patch("backend.chat.asyncio.create_task", side_effect=lambda coro: coro.close()):
        _mock_claude(mock_cls, "OK")
        client.post("/api/chat", data={"message": "hello", "history": "[]"})
    call_kwargs = mock_cls.return_value.messages.create.call_args
    assert "User financial profile" not in call_kwargs.kwargs["system"]
