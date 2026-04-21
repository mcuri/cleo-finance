import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import IO, List, Tuple

from backend.models import TransactionCreate

REQUIRED_COLUMNS = {"date", "amount", "merchant", "category", "type"}


class CsvParseError(Exception):
    pass


@dataclass
class CsvRowError:
    row_number: int
    reason: str


@dataclass
class CsvRow:
    date: date
    amount: float
    merchant: str
    category: str
    type: str


def parse_csv(file: IO[str]) -> Tuple[List[CsvRow], List[CsvRowError]]:
    reader = csv.DictReader(file)
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CsvParseError(f"Missing required columns: {missing}")

    rows: List[CsvRow] = []
    errors: List[CsvRowError] = []

    for i, raw in enumerate(reader, start=2):
        try:
            rows.append(CsvRow(
                date=date.fromisoformat(raw["date"].strip()),
                amount=float(raw["amount"].strip()),
                merchant=raw["merchant"].strip(),
                category=raw["category"].strip(),
                type=raw["type"].strip().lower(),
            ))
        except (ValueError, KeyError) as exc:
            errors.append(CsvRowError(row_number=i, reason=str(exc)))

    return rows, errors


def csv_rows_to_creates(rows: List[CsvRow]) -> List[TransactionCreate]:
    return [
        TransactionCreate(
            date=row.date,
            amount=row.amount,
            merchant=row.merchant,
            category=row.category,
            type=row.type,
        )
        for row in rows
    ]
