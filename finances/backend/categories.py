from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel
import backend.categories as _self

from backend.models import Category
from backend.sheets import SheetsClient
from backend.config import get_settings

router = APIRouter(prefix="/api/categories", tags=["categories"])


def get_sheets_client() -> SheetsClient:
    return SheetsClient(spreadsheet_id=get_settings().google_sheets_id)


def _get_sheets_client():
    return _self.get_sheets_client()


class CategoryCreate(BaseModel):
    name: str


@router.get("", response_model=List[Category])
def list_categories(sheets: SheetsClient = Depends(_get_sheets_client)):
    return sheets.get_categories()


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, sheets: SheetsClient = Depends(_get_sheets_client)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name required")
    sheets.append_category(name)
    return Category(name=name, predefined=False)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(name: str, sheets: SheetsClient = Depends(_get_sheets_client)):
    if not sheets.delete_category(name):
        raise HTTPException(status_code=404, detail="Category not found")
