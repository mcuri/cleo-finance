from datetime import date
import pytest
from backend.models import Transaction, TransactionCreate, Category, ParsedExpense

def test_transaction_create_valid():
    t = TransactionCreate(
        date=date(2026, 4, 20),
        amount=47.50,
        merchant="Trader Joe's",
        category="Groceries",
        type="expense",
    )
    assert t.amount == 47.50

def test_transaction_create_negative_amount_raises():
    with pytest.raises(ValueError):
        TransactionCreate(
            date=date(2026, 4, 20),
            amount=-10.0,
            merchant="Test",
            category="Other",
            type="expense",
        )

def test_category_name_stripped():
    c = Category(name="  Groceries  ", predefined=False)
    assert c.name == "Groceries"

def test_parsed_expense_optional_fields():
    p = ParsedExpense(amount=100.0, merchant="Starbucks", category="Restaurants")
    assert p.date is None
    assert p.notes is None

def test_transaction_from_create_sets_id_and_source():
    create = TransactionCreate(
        date=date(2026, 4, 20),
        amount=50.0,
        merchant="Target",
        category="Shopping",
        type="expense",
    )
    t = Transaction.from_create(create, source="web")
    assert t.source == "web"
    assert len(t.id) > 0

def test_transaction_update_accepts_all_fields():
    from backend.models import TransactionUpdate
    u = TransactionUpdate(
        date=date(2026, 4, 25),
        amount=50.0,
        merchant="Whole Foods",
        category="Groceries",
        type="expense",
        notes="weekly shop",
    )
    assert u.date == date(2026, 4, 25)
    assert u.amount == 50.0
    assert u.type == "expense"

def test_transaction_update_all_fields_optional():
    from backend.models import TransactionUpdate
    u = TransactionUpdate()
    assert u.date is None
    assert u.amount is None
    assert u.type is None

def test_parsed_payslip_fields():
    from datetime import date
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
    assert p.net_pay == 4801.87
    assert p.employee_401k == 1035.39
    assert p.life_choice == 1129.17
