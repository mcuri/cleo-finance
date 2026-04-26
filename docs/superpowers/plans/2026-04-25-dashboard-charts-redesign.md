# Dashboard Charts Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dashboard charts with a horizontal category breakdown (% of spend), a monthly net-savings bar chart, a 4th savings-rate summary card, a `created_at` column on the Transactions sheet, and remove the unused CSV import feature.

**Architecture:** Four independent tasks: (1) backend-only `created_at` field, (2) backend+frontend CSV removal, (3) frontend utility function `buildMonthlySavingsData`, (4) Dashboard.tsx rewrite. Tasks 1–2 touch no frontend charts; Tasks 3–4 touch no backend. Complete in order.

**Tech Stack:** Python 3.9, FastAPI, Pydantic v2, Google Sheets API v4, React 18 + TypeScript, Recharts, Vitest.

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/models.py` | Add `created_at: str` field + `datetime_type` import |
| `finances/backend/sheets.py` | Append column I in `append_transaction`; read it in `get_all_transactions`; widen ranges in `update_transaction` |
| `finances/backend/init_sheets.py` | Extend Transactions header to A1:I1 |
| `finances/backend/main.py` | Remove `io` import, `csv_import` import, and both CSV endpoints |
| `finances/backend/csv_import.py` | **Delete** |
| `finances/tests/test_csv_import.py` | **Delete** |
| `finances/frontend/src/components/CsvImport.tsx` | **Delete** |
| `finances/frontend/src/App.tsx` | Already updated (nav reordered, CSV route removed) — no further changes |
| `finances/frontend/src/utils/dateFilter.ts` | Add `MonthlySavingsPoint` type + `buildMonthlySavingsData` function |
| `finances/frontend/src/utils/dateFilter.test.ts` | Add 5 tests for `buildMonthlySavingsData` |
| `finances/frontend/src/components/Dashboard.tsx` | Replace category chart, trend chart, add savings rate card |

---

## Task 1: Add `created_at` column

**Files:**
- Modify: `finances/backend/models.py`
- Modify: `finances/backend/sheets.py`
- Modify: `finances/backend/init_sheets.py`
- Test: `finances/tests/test_models.py`
- Test: `finances/tests/test_sheets.py`

- [ ] **Step 1: Write failing tests**

Add to `finances/tests/test_models.py`:

```python
def test_transaction_from_create_sets_created_at():
    from backend.models import TransactionCreate, Transaction
    create = TransactionCreate(
        date=date(2026, 4, 25), amount=10.0, merchant="Test",
        category="Other", type="expense",
    )
    t = Transaction.from_create(create, source="web")
    assert t.created_at != ""
    assert "T" in t.created_at  # ISO-8601 datetime has a T separator
```

Add to `finances/tests/test_sheets.py`:

```python
def test_append_transaction_includes_created_at(sheets_client, mock_service):
    t = Transaction(
        id="abc123",
        date=date(2026, 4, 20),
        amount=47.50,
        merchant="Trader Joe's",
        category="Groceries",
        type="expense",
        source="web",
        created_at="2026-04-20T10:00:00",
    )
    sheets_client.append_transaction(t)
    kwargs = mock_service.spreadsheets().values().append.call_args[1]
    assert kwargs["range"] == "Transactions!A:I"
    row = kwargs["body"]["values"][0]
    assert len(row) == 9
    assert row[8] == "2026-04-20T10:00:00"


def test_get_all_transactions_reads_created_at(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [[
            "id1", "2026-04-20", "47.50", "Trader Joe's",
            "Groceries", "expense", "web", "", "2026-04-20T10:00:00",
        ]]
    }
    result = sheets_client.get_all_transactions()
    assert result[0].created_at == "2026-04-20T10:00:00"


def test_get_all_transactions_missing_created_at_defaults_empty(sheets_client, mock_service):
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [[
            "id1", "2026-04-20", "47.50", "Trader Joe's",
            "Groceries", "expense", "web",
        ]]
    }
    result = sheets_client.get_all_transactions()
    assert result[0].created_at == ""
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances && python3 -m pytest tests/test_models.py::test_transaction_from_create_sets_created_at tests/test_sheets.py::test_append_transaction_includes_created_at tests/test_sheets.py::test_get_all_transactions_reads_created_at tests/test_sheets.py::test_get_all_transactions_missing_created_at_defaults_empty -v
```

Expected: all 4 `FAILED`.

- [ ] **Step 3: Update `finances/backend/models.py`**

Change the import line and the `Transaction` class:

```python
from datetime import date as date_type, datetime as datetime_type
```

Replace the `Transaction` class:

```python
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
```

- [ ] **Step 4: Update `finances/backend/sheets.py`**

Replace `append_transaction`:

```python
def append_transaction(self, t: Transaction) -> None:
    row = [
        t.id,
        t.date.isoformat(),
        t.amount,
        t.merchant,
        t.category,
        t.type,
        t.source,
        t.notes or "",
        t.created_at,
    ]
    self._values().append(
        spreadsheetId=self.spreadsheet_id,
        range="Transactions!A:I",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()
```

Replace `get_all_transactions`:

```python
def get_all_transactions(self) -> List[Transaction]:
    result = self._values().get(
        spreadsheetId=self.spreadsheet_id,
        range="Transactions!A2:I",
    ).execute()
    rows = result.get("values", [])
    transactions = []
    for row in rows:
        if len(row) < 7:
            continue
        transactions.append(Transaction(
            id=row[0],
            date=date_type.fromisoformat(row[1]),
            amount=float(row[2]),
            merchant=row[3],
            category=row[4],
            type=row[5],
            source=row[6],
            notes=row[7] if len(row) > 7 and row[7] else None,
            created_at=row[8] if len(row) > 8 else "",
        ))
    return transactions
```

In `update_transaction`, replace the two occurrences of `H{idx+1}` with `I{idx+1}`:

```python
# Line reading current data — change:
range=f"Transactions!A{idx+1}:H{idx+1}",
# to:
range=f"Transactions!A{idx+1}:I{idx+1}",

# Line writing updated data — change:
range=f"Transactions!A{idx+1}:H{idx+1}",
# to:
range=f"Transactions!A{idx+1}:I{idx+1}",
```

- [ ] **Step 5: Update `finances/backend/init_sheets.py`**

Replace the Transactions header update block:

```python
vals.update(
    spreadsheetId=settings.google_sheets_id,
    range="Transactions!A1:I1",
    valueInputOption="RAW",
    body={"values": [["id", "date", "amount", "merchant", "category", "type", "source", "notes", "created_at"]]},
).execute()
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd finances && python3 -m pytest tests/test_models.py::test_transaction_from_create_sets_created_at tests/test_sheets.py::test_append_transaction_includes_created_at tests/test_sheets.py::test_get_all_transactions_reads_created_at tests/test_sheets.py::test_get_all_transactions_missing_created_at_defaults_empty -v
```

Expected: all 4 `PASSED`.

- [ ] **Step 7: Run full test suite**

```bash
cd finances && python3 -m pytest -v
```

Expected: all 60 existing tests + 4 new = 64 passing.

- [ ] **Step 8: Commit**

```bash
git add finances/backend/models.py finances/backend/sheets.py finances/backend/init_sheets.py finances/tests/test_models.py finances/tests/test_sheets.py
git commit -m "feat: add created_at column to Transactions sheet"
```

---

## Task 2: Remove CSV Import

**Files:**
- Delete: `finances/backend/csv_import.py`
- Delete: `finances/tests/test_csv_import.py`
- Delete: `finances/frontend/src/components/CsvImport.tsx`
- Modify: `finances/backend/main.py`

- [ ] **Step 1: Delete the three files**

```bash
rm finances/backend/csv_import.py
rm finances/tests/test_csv_import.py
rm finances/frontend/src/components/CsvImport.tsx
```

- [ ] **Step 2: Update `finances/backend/main.py`**

Remove the `import io` line at the top (it is only used by the CSV endpoints).

Remove the CSV import line:

```python
from backend.csv_import import parse_csv, csv_rows_to_creates, CsvParseError
```

Remove these two endpoint functions in their entirety (lines 61–91 in the original file):

```python
@app.post("/api/import/preview", dependencies=[Depends(_require_auth)])
async def import_preview(file: UploadFile = File(...)):
    ...

@app.post("/api/import/confirm", dependencies=[Depends(_require_auth)])
async def import_confirm(file: UploadFile = File(...)):
    ...
```

After the removals `main.py` should no longer import `io`, `parse_csv`, `csv_rows_to_creates`, or `CsvParseError`, and should contain no `/api/import/` routes.

- [ ] **Step 3: Verify the app still starts**

```bash
cd finances && python3 -c "from backend.main import app; print('OK')"
```

Expected: `OK` with no import errors.

- [ ] **Step 4: Run full test suite**

```bash
cd finances && python3 -m pytest -v
```

Expected: 61 passing (64 minus the 3 `test_csv_import` tests that were deleted).

- [ ] **Step 5: Verify frontend TypeScript still compiles**

```bash
cd finances/frontend && npx tsc --noEmit
```

Expected: no errors (CsvImport.tsx is gone and App.tsx was already updated to not import it).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: remove CSV import feature"
```

---

## Task 3: `buildMonthlySavingsData` utility

**Files:**
- Modify: `finances/frontend/src/utils/dateFilter.ts`
- Modify: `finances/frontend/src/utils/dateFilter.test.ts`

- [ ] **Step 1: Write failing tests**

Add to `finances/frontend/src/utils/dateFilter.test.ts` (after the existing `buildTrendData` describe block):

```typescript
import { presetToRange, buildTrendData, buildMonthlySavingsData } from './dateFilter';
```

Update the import line at the top of the file (add `buildMonthlySavingsData`), then append:

```typescript
describe('buildMonthlySavingsData', () => {
  const txs = [
    { date: '2026-03-15', amount: 5000, type: 'income'  },
    { date: '2026-03-20', amount: 2000, type: 'expense' },
    { date: '2026-04-01', amount: 8628, type: 'income'  },
    { date: '2026-04-10', amount: 3000, type: 'expense' },
    { date: '2026-04-20', amount: 500,  type: 'expense' },
  ];

  it('always returns monthly buckets regardless of range length', () => {
    const result = buildMonthlySavingsData(txs, '2026-03-01', '2026-04-25');
    expect(result).toHaveLength(2);
    expect(result[0].label).toBe('2026-03');
    expect(result[1].label).toBe('2026-04');
  });

  it('computes net as income minus expenses', () => {
    const result = buildMonthlySavingsData(txs, '2026-03-01', '2026-04-25');
    expect(result[0]).toMatchObject({ label: '2026-03', income: 5000, expenses: 2000, net: 3000 });
    expect(result[1]).toMatchObject({ label: '2026-04', income: 8628, expenses: 3500, net: 5128 });
  });

  it('computes savings rate as net/income*100 rounded to 1 decimal', () => {
    const result = buildMonthlySavingsData(txs, '2026-03-01', '2026-03-31');
    expect(result[0].rate).toBe(60);  // 3000/5000*100
  });

  it('rate is 0 when no income', () => {
    const noIncome = [{ date: '2026-03-15', amount: 500, type: 'expense' }];
    const result = buildMonthlySavingsData(noIncome, '2026-03-01', '2026-03-31');
    expect(result[0].rate).toBe(0);
    expect(result[0].net).toBe(-500);
  });

  it('returns a single bucket for a short (within-month) range', () => {
    const result = buildMonthlySavingsData(txs, '2026-04-01', '2026-04-25');
    expect(result).toHaveLength(1);
    expect(result[0].label).toBe('2026-04');
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd finances/frontend && npx vitest run src/utils/dateFilter.test.ts 2>&1 | tail -10
```

Expected: 5 new tests `FAILED` — `buildMonthlySavingsData is not a function`.

- [ ] **Step 3: Add `MonthlySavingsPoint` and `buildMonthlySavingsData` to `dateFilter.ts`**

Append to `finances/frontend/src/utils/dateFilter.ts` (after the last line of `buildTrendData`):

```typescript
export interface MonthlySavingsPoint {
  label: string;
  net: number;
  rate: number;
  income: number;
  expenses: number;
}

export function buildMonthlySavingsData(
  transactions: Array<{ date: string; amount: number; type: string }>,
  from: string,
  to: string,
): MonthlySavingsPoint[] {
  const fromDate = new Date(from + 'T00:00:00');
  const toMonth = to.slice(0, 7);
  const points: MonthlySavingsPoint[] = [];
  const d = new Date(fromDate.getFullYear(), fromDate.getMonth(), 1);
  while (toYMD(d).slice(0, 7) <= toMonth) {
    const label = toYMD(d).slice(0, 7);
    const month = transactions.filter(t => t.date.startsWith(label));
    const income   = +month.filter(t => t.type === 'income' ).reduce((s, t) => s + t.amount, 0).toFixed(2);
    const expenses = +month.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0).toFixed(2);
    const net  = +(income - expenses).toFixed(2);
    const rate = income > 0 ? +(net / income * 100).toFixed(1) : 0;
    points.push({ label, net, rate, income, expenses });
    d.setMonth(d.getMonth() + 1);
  }
  return points;
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd finances/frontend && npx vitest run src/utils/dateFilter.test.ts 2>&1 | tail -10
```

Expected: all tests `PASSED` (existing 7 + new 5 = 12 total).

- [ ] **Step 5: Commit**

```bash
git add finances/frontend/src/utils/dateFilter.ts finances/frontend/src/utils/dateFilter.test.ts
git commit -m "feat: add buildMonthlySavingsData utility"
```

---

## Task 4: Dashboard charts

**Files:**
- Modify: `finances/frontend/src/components/Dashboard.tsx`

This task has no automated tests (it's a pure UI change). Verify visually by running the dev server.

- [ ] **Step 1: Replace `Dashboard.tsx`**

Replace the entire contents of `finances/frontend/src/components/Dashboard.tsx` with:

```tsx
import { useEffect, useState, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine, LabelList,
} from "recharts";
import { api } from "../api";
import type { Transaction } from "../types";
import { presetToRange, buildMonthlySavingsData } from "../utils/dateFilter";
import type { DateFilter, Preset, MonthlySavingsPoint } from "../utils/dateFilter";

const PRESETS: { key: Exclude<Preset, 'custom'>; label: string }[] = [
  { key: 'this_week',  label: 'This Week'  },
  { key: 'this_month', label: 'This Month' },
  { key: 'last_month', label: 'Last Month' },
  { key: '3_months',   label: '3 Months'   },
  { key: '6_months',   label: '6 Months'   },
];

const CATEGORY_COLORS = [
  '#6366f1', '#34d399', '#f59e0b', '#f87171',
  '#818cf8', '#a3e635', '#fb923c', '#94a3b8',
];

function filterTitle(filter: DateFilter): string {
  if (filter.preset === 'this_week') return 'This Week';
  if (filter.preset === 'this_month' || filter.preset === 'last_month') {
    const d = new Date(filter.from + 'T00:00:00');
    return d.toLocaleString('default', { month: 'long', year: 'numeric' });
  }
  if (filter.preset === '3_months') return 'Last 3 Months';
  if (filter.preset === '6_months') return 'Last 6 Months';
  return `${filter.from} – ${filter.to}`;
}

function SavingsTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: MonthlySavingsPoint }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "#e2e8f0" }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{d.label}</div>
      <div>Net: <span style={{ color: d.net >= 0 ? "#34d399" : "#f87171" }}>${d.net.toFixed(2)}</span></div>
      <div>Savings rate: <span style={{ color: "#818cf8" }}>{d.rate}%</span></div>
      <div style={{ color: "#64748b", marginTop: 4 }}>
        Income: ${d.income.toFixed(2)} · Expenses: ${d.expenses.toFixed(2)}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [dateFilter, setDateFilter] = useState<DateFilter>(() => {
    const range = presetToRange('this_month');
    return { preset: 'this_month', ...range };
  });
  const [customFrom, setCustomFrom] = useState('');
  const [customTo,   setCustomTo]   = useState('');
  const [showCustom, setShowCustom] = useState(false);

  useEffect(() => { api.getTransactions().then(setTransactions); }, []);

  const filteredTransactions = useMemo(
    () => transactions.filter(t => t.date >= dateFilter.from && t.date <= dateFilter.to),
    [transactions, dateFilter],
  );

  const totalIncome   = filteredTransactions.filter(t => t.type === "income" ).reduce((s, t) => s + t.amount, 0);
  const totalExpenses = filteredTransactions.filter(t => t.type === "expense").reduce((s, t) => s + t.amount, 0);
  const net = totalIncome - totalExpenses;
  const savingsRate = totalIncome > 0 ? Math.round(net / totalIncome * 100) : null;

  const categoryData = useMemo(() => {
    const byCategory: Record<string, number> = {};
    filteredTransactions.filter(t => t.type === "expense").forEach(t => {
      byCategory[t.category] = (byCategory[t.category] ?? 0) + t.amount;
    });
    return Object.entries(byCategory)
      .map(([category, amount]) => ({ category, amount: +amount.toFixed(2) }))
      .sort((a, b) => b.amount - a.amount);
  }, [filteredTransactions]);

  const monthlySavingsData = useMemo(
    () => buildMonthlySavingsData(transactions, dateFilter.from, dateFilter.to),
    [transactions, dateFilter],
  );

  const selectPreset = (key: Exclude<Preset, 'custom'>) => {
    setDateFilter({ preset: key, ...presetToRange(key) });
    setShowCustom(false);
  };

  const _now = new Date();
  const today = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`;
  const applyCustom = () => {
    if (!customFrom || !customTo || customFrom > customTo) return;
    setDateFilter({ preset: 'custom', from: customFrom, to: customTo > today ? today : customTo });
    setShowCustom(false);
  };

  const pill = (active: boolean): React.CSSProperties => ({
    padding: '0.25rem 0.75rem',
    borderRadius: '999px',
    fontSize: '0.8rem',
    cursor: 'pointer',
    border: active ? 'none' : '1px solid var(--border)',
    background: active ? 'var(--accent)' : 'var(--surface)',
    color: active ? '#fff' : 'var(--text-secondary)',
    fontWeight: active ? 600 : 400,
  });

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <h1>Dashboard — {filterTitle(dateFilter)}</h1>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem', alignItems: 'center' }}>
        {PRESETS.map(p => (
          <button key={p.key} style={pill(dateFilter.preset === p.key)} onClick={() => selectPreset(p.key)}>
            {p.label}
          </button>
        ))}
        <button style={pill(dateFilter.preset === 'custom')} onClick={() => setShowCustom(v => !v)}>
          Custom…
        </button>
      </div>

      {showCustom && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>From</span>
          <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)} style={{ width: 'auto', marginTop: 0 }} />
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>To</span>
          <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)} style={{ width: 'auto', marginTop: 0 }} />
          <button className="primary" onClick={applyCustom}
            disabled={!customFrom || !customTo || customFrom > customTo}
            style={{ width: 'auto' }}>
            Apply
          </button>
        </div>
      )}

      <div className="summary-cards">
        <div className="card">
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Income</div>
          <div className="amount-income" style={{ fontSize: "1.75rem", fontWeight: 700 }}>${totalIncome.toFixed(2)}</div>
        </div>
        <div className="card">
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Expenses</div>
          <div className="amount-expense" style={{ fontSize: "1.75rem", fontWeight: 700 }}>${totalExpenses.toFixed(2)}</div>
        </div>
        <div className="card">
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Net</div>
          <div className={net >= 0 ? "amount-income" : "amount-expense"} style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            {net >= 0 ? "+" : ""}${net.toFixed(2)}
          </div>
        </div>
        <div className="card" style={{ border: "1px solid var(--accent)" }}>
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>Savings Rate</div>
          {savingsRate === null ? (
            <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text-muted)" }}>—</div>
          ) : (
            <>
              <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#818cf8" }}>{savingsRate}%</div>
              <div style={{ background: "var(--bg)", borderRadius: "999px", height: "4px", marginTop: "0.5rem", overflow: "hidden" }}>
                <div style={{ background: "var(--accent)", width: `${Math.min(savingsRate, 100)}%`, height: "100%", borderRadius: "999px" }} />
              </div>
            </>
          )}
        </div>
      </div>

      <h2>Spending by category</h2>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        {categoryData.length === 0 ? (
          <p style={{ color: "var(--text-muted)", margin: 0 }}>No expenses this period.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {categoryData.map(({ category, amount }, i) => {
              const pct = Math.round(amount / totalExpenses * 100);
              return (
                <div key={category} style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <div style={{ width: 110, textAlign: "right", fontSize: "0.8rem", color: "var(--text-secondary)", flexShrink: 0 }}>
                    {category}
                  </div>
                  <div style={{ flex: 1, background: "var(--bg)", borderRadius: 4, height: 10, overflow: "hidden" }}>
                    <div style={{ width: `${pct}%`, height: "100%", background: CATEGORY_COLORS[i % CATEGORY_COLORS.length], borderRadius: 4 }} />
                  </div>
                  <div style={{ width: 100, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    ${amount.toFixed(2)} · {pct}%
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <h2>Monthly Savings</h2>
      <div className="card">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={monthlySavingsData} margin={{ left: 10, top: 20 }}>
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
            <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
            <Tooltip content={<SavingsTooltip />} />
            <Bar dataKey="net" radius={[4, 4, 0, 0]}>
              {monthlySavingsData.map((entry, index) => (
                <Cell key={index} fill={entry.net >= 0 ? "#34d399" : "#f87171"} />
              ))}
              <LabelList
                dataKey="rate"
                position="top"
                formatter={(v: number) => v === 0 ? '' : `${v > 0 ? '+' : ''}${v}%`}
                style={{ fontSize: 10, fill: "#94a3b8" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd finances/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run frontend tests**

```bash
cd finances/frontend && npx vitest run
```

Expected: all tests pass (the dateFilter tests; Dashboard has no unit tests).

- [ ] **Step 4: Start dev server and verify visually**

```bash
# Terminal 1 — backend
cd finances && uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd finances/frontend && npm run dev
```

Open http://localhost:5173. Check:
- Dashboard loads on "This Month" by default
- 4 summary cards visible: Income, Expenses, Net, Savings Rate (with % and progress bar; shows "—" if no income)
- Category section shows horizontal bars with `$amount · XX%` labels
- Monthly Savings section shows green/red bars; positive bars have `+XX%` label above
- Switching to "3 Months" or "6 Months" shows multiple bars in the savings chart
- No "Import CSV" link in nav; nav reads: `✦ Chat · Dashboard · Transactions · Add · Config`

- [ ] **Step 5: Commit**

```bash
git add finances/frontend/src/components/Dashboard.tsx
git commit -m "feat: redesign dashboard charts — horizontal category bars, monthly savings chart, savings rate card"
```
