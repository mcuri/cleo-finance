import io
import pytest
from backend.csv_import import parse_csv, CsvParseError, CsvRowError

VALID_CSV = """date,amount,merchant,category,type
2026-04-01,47.50,Trader Joe's,Groceries,expense
2026-04-02,3000.00,Employer,Income,income
"""

BAD_AMOUNT_CSV = """date,amount,merchant,category,type
2026-04-01,not-a-number,Trader Joe's,Groceries,expense
2026-04-02,3000.00,Employer,Income,income
"""

MISSING_COLUMNS_CSV = """date,amount,merchant
2026-04-01,47.50,Trader Joe's
"""

def test_parse_valid_csv():
    rows, errors = parse_csv(io.StringIO(VALID_CSV))
    assert len(rows) == 2
    assert rows[0].merchant == "Trader Joe's"
    assert rows[0].amount == 47.50
    assert len(errors) == 0

def test_parse_bad_amount_row_becomes_error():
    rows, errors = parse_csv(io.StringIO(BAD_AMOUNT_CSV))
    assert len(rows) == 1
    assert len(errors) == 1
    assert errors[0].row_number == 2

def test_parse_missing_required_column_raises():
    with pytest.raises(CsvParseError):
        parse_csv(io.StringIO(MISSING_COLUMNS_CSV))
