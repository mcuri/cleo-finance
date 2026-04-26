from pydantic import BaseModel, field_validator
from datetime import date as date_type, datetime as datetime_type
from typing import Literal, Optional
import uuid

TransactionType = Literal["income", "expense"]
TransactionSource = Literal["web", "csv", "telegram", "credit_card", "payslip"]


class TransactionCreate(BaseModel):
    date: date_type
    amount: float
    merchant: str
    category: str
    type: TransactionType
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("amount must be non-negative")
        return v


class TransactionUpdate(BaseModel):
    date: Optional[date_type] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    type: Optional[TransactionType] = None
    notes: Optional[str] = None


class Transaction(TransactionCreate):
    id: str
    source: TransactionSource
    created_at: str = ""

    @classmethod
    def from_create(cls, data: TransactionCreate, source: TransactionSource) -> "Transaction":
        return cls(
            **data.model_dump(),
            id=str(uuid.uuid4()),
            source=source,
            created_at=datetime_type.utcnow().isoformat(),
        )


class Category(BaseModel):
    name: str
    predefined: bool

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class ParsedExpense(BaseModel):
    amount: float
    merchant: str
    category: str
    date: Optional[date_type] = None
    notes: Optional[str] = None
    confidence: float = 1.0


class ParsedPayslip(BaseModel):
    company: str
    pay_period_begin: date_type
    pay_period_end: date_type
    check_date: date_type
    gross_pay: float
    pre_tax_deductions: float
    employee_taxes: float
    post_tax_deductions: float
    net_pay: float
    employee_401k: float
    employer_401k_match: float
    life_choice: float = 0.0
