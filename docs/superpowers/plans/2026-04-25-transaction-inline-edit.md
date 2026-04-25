# Transaction Inline Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to click any transaction row in the list to edit all its fields inline, with a notes sub-row and save/cancel controls.

**Architecture:** Extend the existing `TransactionUpdate` model and `PUT /api/transactions/{id}` endpoint to accept all mutable fields (date, amount, merchant, category, type, notes). On the frontend, track which row is in edit mode via `editingId` state and render inputs in-place when active. No new files, no new routes.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, React 18 + TypeScript, existing `api.ts` fetch wrapper.

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/models.py` | Add `date`, `amount`, `type` to `TransactionUpdate` |
| `finances/backend/transactions.py` | Apply new fields in PUT handler |
| `finances/frontend/src/api.ts` | Add `updateTransaction` method |
| `finances/frontend/src/components/TransactionList.tsx` | Full inline edit UI |
| `finances/tests/test_models.py` | 2 new tests for `TransactionUpdate` |
| `finances/tests/test_transactions.py` | 2 new tests for PUT endpoint |

---

## Task 1: Extend TransactionUpdate model

**Files:**
- Modify: `finances/backend/models.py`
- Test: `finances/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `finances/tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances && python -m pytest tests/test_models.py::test_transaction_update_accepts_all_fields tests/test_models.py::test_transaction_update_all_fields_optional -v
```

Expected: `FAILED` — `ValidationError` or `AttributeError` because `date`, `amount`, `type` don't exist on the model yet.

- [ ] **Step 3: Extend the model**

In `finances/backend/models.py`, replace:

```python
class TransactionUpdate(BaseModel):
    merchant: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
```

With:

```python
class TransactionUpdate(BaseModel):
    date: Optional[date_type] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    type: Optional[TransactionType] = None
    notes: Optional[str] = None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd finances && python -m pytest tests/test_models.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add finances/backend/models.py finances/tests/test_models.py
git commit -m "feat: extend TransactionUpdate to include date, amount, type"
```

---

## Task 2: Update PUT endpoint to apply all fields

**Files:**
- Modify: `finances/backend/transactions.py`
- Test: `finances/tests/test_transactions.py`

- [ ] **Step 1: Write the failing tests**

Add to `finances/tests/test_transactions.py`:

```python
def test_update_transaction_applies_amount_and_merchant(client, mock_sheets):
    from backend.models import Transaction
    existing = Transaction(
        id="abc123",
        date=date(2026, 4, 20),
        amount=10.0,
        merchant="Old Name",
        category="Groceries",
        type="expense",
        source="web",
    )
    mock_sheets.get_all_transactions.return_value = [existing]
    mock_sheets.update_transaction.return_value = True
    resp = client.put("/api/transactions/abc123", json={
        "merchant": "New Name",
        "amount": 25.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["merchant"] == "New Name"
    assert data["amount"] == 25.0
    assert data["category"] == "Groceries"  # unchanged

def test_update_transaction_not_found(client, mock_sheets):
    mock_sheets.get_all_transactions.return_value = []
    resp = client.put("/api/transactions/notexist", json={"merchant": "X"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances && python -m pytest tests/test_transactions.py::test_update_transaction_applies_amount_and_merchant tests/test_transactions.py::test_update_transaction_not_found -v
```

Expected: `test_update_transaction_applies_amount_and_merchant` FAILS (`assert data["amount"] == 25.0` — amount doesn't get updated yet). `test_update_transaction_not_found` may already pass.

- [ ] **Step 3: Update the PUT handler**

In `finances/backend/transactions.py`, replace the `updates = {}` block inside `update_transaction`:

```python
    updates = {}
    if data.merchant is not None:
        updates['merchant'] = data.merchant
    if data.category is not None:
        updates['category'] = data.category
    if data.notes is not None:
        updates['notes'] = data.notes
```

With:

```python
    updates = {}
    if data.date is not None:
        updates['date'] = data.date
    if data.amount is not None:
        updates['amount'] = data.amount
    if data.merchant is not None:
        updates['merchant'] = data.merchant
    if data.category is not None:
        updates['category'] = data.category
    if data.type is not None:
        updates['type'] = data.type
    if data.notes is not None:
        updates['notes'] = data.notes
```

Also update the `return Transaction(...)` at the end of the handler to include `date` and `type` fallbacks:

```python
    return Transaction(
        id=current_transaction.id,
        date=updates.get('date', current_transaction.date),
        amount=updates.get('amount', current_transaction.amount),
        merchant=updates.get('merchant', current_transaction.merchant),
        category=updates.get('category', current_transaction.category),
        type=updates.get('type', current_transaction.type),
        source=current_transaction.source,
        notes=updates.get('notes', current_transaction.notes),
    )
```

- [ ] **Step 4: Run all transaction tests**

```bash
cd finances && python -m pytest tests/test_transactions.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add finances/backend/transactions.py finances/tests/test_transactions.py
git commit -m "feat: PUT /api/transactions/:id applies date, amount, type fields"
```

---

## Task 3: Add updateTransaction to api.ts

**Files:**
- Modify: `finances/frontend/src/api.ts`

- [ ] **Step 1: Add the method**

In `finances/frontend/src/api.ts`, add after `deleteTransaction`:

```typescript
  updateTransaction: (id: string, data: Partial<TransactionCreate>) =>
    req<Transaction>(`/api/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) }),
```

The full `api` object should now read:

```typescript
export const api = {
  getMe: () => req<{ email: string }>("/auth/me"),

  getTransactions: () => req<Transaction[]>("/api/transactions"),
  createTransaction: (data: TransactionCreate) =>
    req<Transaction>("/api/transactions", { method: "POST", body: JSON.stringify(data) }),
  deleteTransaction: (id: string) =>
    req<void>(`/api/transactions/${id}`, { method: "DELETE" }),
  updateTransaction: (id: string, data: Partial<TransactionCreate>) =>
    req<Transaction>(`/api/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  getCategories: () => req<Category[]>("/api/categories"),
  createCategory: (name: string) =>
    req<Category>("/api/categories", { method: "POST", body: JSON.stringify({ name }) }),
  deleteCategory: (name: string) =>
    req<void>(`/api/categories/${encodeURIComponent(name)}`, { method: "DELETE" }),

  importPreview: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ valid_rows: ImportPreviewRow[]; errors: ImportPreviewError[] }>(
      "/api/import/preview", { method: "POST", body: form }
    );
  },
  importConfirm: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ imported: number }>("/api/import/confirm", { method: "POST", body: form });
  },
  chatForm: (form: FormData) =>
    req<{ reply: string }>("/api/chat", { method: "POST", body: form }),
};
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd finances/frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add finances/frontend/src/api.ts
git commit -m "feat: add updateTransaction to api client"
```

---

## Task 4: Inline edit UI in TransactionList

**Files:**
- Modify: `finances/frontend/src/components/TransactionList.tsx`

**Note:** The existing table has a column mismatch — the 3rd sortable header says "Amount" but column 3 data shows `category`, and the 4th header says "Category" but column 4 data shows `amount`. This is a pre-existing bug. The edit inputs below match the **data** column order to stay visually aligned, not the headers.

- [ ] **Step 1: Replace TransactionList.tsx with the full updated version**

```tsx
import { Fragment, useEffect, useState } from "react";
import { api } from "../api";
import type { Category, Transaction } from "../types";

type SortKey = "date" | "merchant" | "amount";
type SortDir = "asc" | "desc";

type EditForm = {
  date: string;
  amount: string;
  merchant: string;
  category: string;
  type: "income" | "expense";
  notes: string;
};

export default function TransactionList() {
  const [all, setAll] = useState<Transaction[]>([]);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [type, setType] = useState<"all" | "income" | "expense">("all");
  const [category, setCategory] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [categories, setCategories] = useState<Category[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({
    date: "", amount: "", merchant: "", category: "", type: "expense", notes: "",
  });
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.getTransactions().then(setAll); }, []);
  useEffect(() => { api.getCategories().then(setCategories); }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setEditingId(null); setEditError(""); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "amount" ? "desc" : "asc");
    }
  };

  const handleEdit = (t: Transaction) => {
    setEditingId(t.id);
    setEditForm({
      date: t.date,
      amount: String(t.amount),
      merchant: t.merchant,
      category: t.category,
      type: t.type,
      notes: t.notes ?? "",
    });
    setEditError("");
  };

  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const updated = await api.updateTransaction(editingId, {
        date: editForm.date,
        amount: parseFloat(editForm.amount),
        merchant: editForm.merchant,
        category: editForm.category,
        type: editForm.type,
        notes: editForm.notes || undefined,
      });
      setAll(prev => prev.map(t => t.id === editingId ? updated : t));
      setEditingId(null);
      setEditError("");
    } catch {
      setEditError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => { setEditingId(null); setEditError(""); };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this transaction?")) return;
    await api.deleteTransaction(id);
    setAll(prev => prev.filter(t => t.id !== id));
  };

  const set = (key: keyof EditForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setEditForm(f => ({ ...f, [key]: e.target.value }));

  const categories_all = Array.from(new Set(all.map(t => t.category))).sort();
  const filtered = all
    .filter(t =>
      t.date.startsWith(month) &&
      (type === "all" || t.type === type) &&
      (category === "all" || t.category === category)
    )
    .sort((a, b) => {
      let cmp = 0;
      if (sortKey === "date") cmp = a.date.localeCompare(b.date);
      else if (sortKey === "merchant") cmp = a.merchant.localeCompare(b.merchant);
      else if (sortKey === "amount") cmp = a.amount - b.amount;
      return sortDir === "asc" ? cmp : -cmp;
    });

  const inputStyle = { width: "100%", padding: "0.15rem 0.25rem", fontSize: "0.875rem" };

  return (
    <div style={{ maxWidth: 920, margin: "0 auto" }}>
      <h1>Transactions</h1>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <input type="month" value={month} onChange={e => setMonth(e.target.value)} style={{ width: "auto" }} />
        <select value={type} onChange={e => setType(e.target.value as typeof type)} style={{ width: "auto" }}>
          <option value="all">All types</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ width: "auto" }}>
          <option value="all">All categories</option>
          {categories_all.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {filtered.length === 0
        ? <p>No transactions for this period.</p>
        : (
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table>
              <thead>
                <tr>
                  {(["date", "merchant", "amount"] as SortKey[]).map(key => (
                    <th
                      key={key}
                      onClick={() => handleSort(key)}
                      style={{ cursor: "pointer", userSelect: "none", textAlign: key === "amount" ? "right" : "left" }}
                    >
                      {key.charAt(0).toUpperCase() + key.slice(1)}
                      {sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : " ↕"}
                    </th>
                  ))}
                  <th>Category</th>
                  <th>Type</th><th>Source</th><th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => {
                  if (editingId === t.id) {
                    return (
                      <Fragment key={t.id}>
                        <tr style={{ background: "var(--surface, #f9f9f9)" }}>
                          <td><input type="date" value={editForm.date} onChange={set("date")} style={inputStyle} /></td>
                          <td><input type="text" value={editForm.merchant} onChange={set("merchant")} style={inputStyle} /></td>
                          <td style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                            <select value={editForm.category} onChange={set("category")} style={inputStyle}>
                              {categories.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                            </select>
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <input
                              type="number" step="0.01" min="0.01"
                              value={editForm.amount} onChange={set("amount")}
                              style={{ ...inputStyle, textAlign: "right", width: "6rem" }}
                            />
                          </td>
                          <td>
                            <select value={editForm.type} onChange={set("type")} style={inputStyle}>
                              <option value="expense">expense</option>
                              <option value="income">income</option>
                            </select>
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.source}</td>
                          <td style={{ whiteSpace: "nowrap" }}>
                            <button
                              onClick={handleSave} disabled={saving} title="Save"
                              style={{ background: "none", border: "none", color: "var(--income, green)", padding: "0 0.25rem", fontSize: "1rem" }}
                            >✓</button>
                            <button
                              onClick={handleCancel} title="Cancel"
                              style={{ background: "none", border: "none", color: "var(--expense)", padding: "0 0.25rem", fontSize: "1rem" }}
                            >✗</button>
                          </td>
                        </tr>
                        <tr>
                          <td colSpan={7} style={{ padding: "0.25rem 0.75rem 0.5rem", background: "var(--surface, #f9f9f9)" }}>
                            <input
                              type="text" placeholder="Notes (optional)"
                              value={editForm.notes} onChange={set("notes")}
                              style={{ width: "100%", fontSize: "0.875rem" }}
                            />
                            {editError && <p style={{ color: "var(--expense)", margin: "0.25rem 0 0", fontSize: "0.8rem" }}>{editError}</p>}
                          </td>
                        </tr>
                      </Fragment>
                    );
                  }
                  return (
                    <tr key={t.id} onClick={() => handleEdit(t)} style={{ cursor: "pointer" }}>
                      <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.date}</td>
                      <td>{t.merchant}</td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>{t.category}</td>
                      <td style={{ textAlign: "right" }} className={t.type === "income" ? "amount-income" : "amount-expense"}>
                        {t.type === "income" ? "+" : "-"}${t.amount.toFixed(2)}
                      </td>
                      <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.type}</td>
                      <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{t.source}</td>
                      <td>
                        <button
                          onClick={e => { e.stopPropagation(); handleDelete(t.id); }}
                          style={{ background: "none", border: "none", color: "var(--expense)", padding: "0 0.25rem", fontSize: "1rem" }}
                        >×</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  );
}
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd finances/frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Start dev server and verify visually**

```bash
# Terminal 1 — backend
cd finances && uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd finances/frontend && npm run dev
```

Open http://localhost:5173/transactions. Verify:
1. Clicking a row replaces it with input fields (date, merchant, category select, amount, type select)
2. Notes sub-row appears below
3. ✓ saves changes and row returns to read-only with updated values
4. ✗ cancels with no change
5. Escape key cancels
6. Delete button (×) still works and does NOT trigger edit mode
7. Only one row editable at a time — clicking a second row while one is open closes the first

- [ ] **Step 4: Commit**

```bash
git add finances/frontend/src/components/TransactionList.tsx
git commit -m "feat: inline row editing for transactions"
```
