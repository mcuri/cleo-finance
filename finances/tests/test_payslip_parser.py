import json
from unittest.mock import MagicMock, patch
from datetime import date


def test_parse_payslip_returns_list_of_payslips():
    from backend.payslip_parser import parse_payslip

    payload = [{
        "company": "Meta Platforms, Inc.",
        "pay_period_begin": "2026-04-06",
        "pay_period_end": "2026-04-19",
        "check_date": "2026-04-24",
        "gross_pay": 8628.24,
        "pre_tax_deductions": 1067.69,
        "employee_taxes": 2758.68,
        "post_tax_deductions": 0.00,
        "net_pay": 4801.87,
        "employee_401k": 1035.39,
        "employer_401k_match": 1035.39,
        "life_choice": 1129.17,
    }]
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(payload))]

    with patch("backend.payslip_parser.anthropic.Anthropic") as mock_cls, \
         patch("backend.payslip_parser.log_usage"):
        mock_cls.return_value.messages.create.return_value = mock_response
        result = parse_payslip(b"fake pdf bytes")

    assert len(result) == 1
    assert result[0].company == "Meta Platforms, Inc."
    assert result[0].net_pay == 4801.87
    assert result[0].employee_401k == 1035.39
    assert result[0].life_choice == 1129.17


def test_parse_payslip_returns_empty_list_on_bad_json():
    from backend.payslip_parser import parse_payslip

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json")]

    with patch("backend.payslip_parser.anthropic.Anthropic") as mock_cls, \
         patch("backend.payslip_parser.log_usage"):
        mock_cls.return_value.messages.create.return_value = mock_response
        result = parse_payslip(b"fake pdf bytes")

    assert result == []
