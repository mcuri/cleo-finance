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
