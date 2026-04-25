# Transaction Inline Edit — Design Spec

**Date:** 2026-04-25  
**Status:** Approved

---

## Overview

Add inline row editing to the Transactions list. Clicking a row turns its cells into inputs in-place. A notes sub-row appears below. Save/Cancel replace the delete button. All fields are editable except source.

---

## Backend

### `TransactionUpdate` model (`backend/models.py`)

Extend to include all mutable fields (all optional):

```python
class TransactionUpdate(BaseModel):
    date: Optional[date_type] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    type: Optional[TransactionType] = None
    notes: Optional[str] = None
```

### `PUT /api/transactions/{id}` (`backend/transactions.py`)

Update the handler to pass all six fields (date, amount, merchant, category, type, notes) through to `sheets.update_transaction()`. The sheets layer already supports all of them via `field_map`.

### `sheets.update_transaction()` (`backend/sheets.py`)

No changes needed — already handles date, amount, merchant, category, type, and notes.

---

## Frontend

### `api.ts`

Add:

```ts
updateTransaction: (id: string, data: Partial<TransactionCreate>) =>
  req<Transaction>(`/api/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) }),
```

### `TransactionList.tsx`

**New state:**
- `editingId: string | null` — id of the row currently in edit mode
- `editForm: { date, amount, merchant, category, type, notes }` — working copy of the row being edited
- `categories: Category[]` — fetched once on mount via `api.getCategories()`
- `editError: string` — inline error message while saving

**Interactions:**
- Click a normal row → set `editingId` to its id, copy its fields into `editForm`. If another row is already editing, cancel it first (no save).
- Escape key → cancel current edit (clear `editingId`, no API call).
- Click ✗ Cancel → same as Escape.
- Click ✓ Save → call `api.updateTransaction(editingId, editForm)`. On success, update that row in the `all` array in-place and clear `editingId`. On error, show `editError` in the notes sub-row.

**Row rendering (edit mode):**

| Column | Normal row | Edit row |
|--------|-----------|----------|
| Date | text | `<input type="date">` |
| Merchant | text | `<input type="text">` |
| Category | text | `<select>` from categories |
| Amount | formatted | `<input type="number" step="0.01" min="0.01">` |
| Type | text | `<select>` income/expense |
| Source | text | text (read-only) |
| Action | × delete | ✓ save + ✗ cancel |

A second `<tr>` is inserted directly below the editing row with `<td colspan={7}>` containing:
- A text input for Notes
- An error message if save failed

**No new files, no new routes, no new components.**

---

## Out of scope

- Bulk editing
- Undo after save
- Keyboard navigation between edit rows
