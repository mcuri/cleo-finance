# Dashboard Charts Redesign — Design Spec

**Date:** 2026-04-25
**Status:** Approved

---

## Overview

Three visual improvements to the Dashboard, one backend data addition, and removal of the unused CSV import feature.

1. **Category chart** — replace vertical BarChart with horizontal bars showing `$amount · XX%` per category
2. **Monthly Savings chart** — replace the income/expense LineChart with a net-savings BarChart (green = saved, red = overspent), with savings rate % label on each bar
3. **Savings Rate card** — add a 4th summary card showing savings rate % and a mini progress bar
4. **`created_at` column** — record when each transaction was added (spreadsheet only, no UI)
5. **Remove CSV import** — delete `csv_import.py`, its routes, the `CsvImport` frontend component, and its nav link

---

## 1. Category Chart

**Replace** the Recharts `<BarChart>` in Dashboard with a plain HTML/CSS horizontal bar list. No Recharts component needed.

**Layout per row:**
```
[Category name — right-aligned, fixed width] [████░░░░░░░ bar] [$amount · XX%]
```

- Rows sorted by amount descending (already computed)
- Bar width = `(amount / totalExpenses * 100)%`
- Each row gets a color from a fixed 8-color palette cycling by index
- If no expenses in the period: show "No expenses this period" placeholder text
- Title stays "Spending by category"

**Color palette (index order):**
```
#6366f1, #34d399, #f59e0b, #f87171, #818cf8, #a3e635, #fb923c, #94a3b8
```

---

## 2. Monthly Savings Chart

**Replace** the Recharts `<LineChart>` trend chart with a `<BarChart>`.

**Data:** New utility function `buildMonthlySavingsData` (always monthly buckets, regardless of date range). It replaces `buildTrendData` in the Dashboard — `buildTrendData` stays in `dateFilter.ts` for now (used in tests).

```typescript
export interface MonthlySavingsPoint {
  label: string;   // "YYYY-MM"
  net: number;     // income - expenses (can be negative)
  rate: number;    // net / income * 100, or 0 if no income
  income: number;
  expenses: number;
}
```

**Bar rendering:**
- Fill: `#34d399` if `net >= 0`, `#f87171` if `net < 0`
- Custom label above bar: savings rate as `+XX%` / `-XX%`
- Tooltip shows: `Net: $X,XXX · Rate: XX% · Income: $X,XXX · Expenses: $X,XXX`
- Y-axis allows negative values (bar extends below the zero line)
- Zero line rendered as a reference line at `y=0`

**Title:** "Monthly Savings" (was "Trend")

**Short date ranges:** "This Month" = 1 bar, "This Week" = 1 partial-month bar. Both are valid — the user can switch to 3/6 months for trend context.

**Default filter:** Keep `this_month` as the default preset on load (no change from current behaviour).

---

## 3. Savings Rate Card

Add a 4th summary card after the existing Income / Expenses / Net cards.

```
┌─────────────────┐
│ SAVINGS RATE    │
│ 60%             │  ← color: #818cf8; "—" if no income
│ ████████░░░░    │  ← progress bar, capped at 100%
└─────────────────┘
```

- Savings rate = `net / totalIncome * 100`
- Show `—` (em dash, no progress bar) when `totalIncome === 0`
- Progress bar width capped at 100% (handles edge case where income is very small)
- Card gets a subtle `border: 1px solid #6366f1` accent to distinguish it

---

## 4. `created_at` Column

**Transaction model** — add one field, populated at creation time:

```python
from datetime import datetime as datetime_type

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

**`sheets.py` — `append_transaction`:** append `t.created_at` as column I; change range to `Transactions!A:I`.

**`sheets.py` — `get_all_transactions`:** read column I if present (index 8), default to `""` for old rows that don't have it. The `len(row) < 7` guard stays; `created_at` is read with `row[8] if len(row) > 8 else ""`.

**`sheets.py` — `update_transaction`:** update all range references from `A:H` / `A{n}:H{n}` to `A:I` / `A{n}:I{n}`. Do not add `created_at` to `field_map` — it is immutable once set.

**`init_sheets.py`:** extend Transactions header range to `A1:I1` and add `"created_at"` as the 9th header.

**Existing rows** without a `created_at` value load fine — the field defaults to `""`.

---

## 5. Remove CSV Import

**Backend — delete:**
- `finances/backend/csv_import.py`
- `finances/tests/test_csv_import.py`

**Backend — `main.py`:** remove `from backend.csv_import import router as csv_router` and `app.include_router(csv_router)`.

**Frontend — delete:**
- `finances/frontend/src/components/CsvImport.tsx`

**Frontend — `App.tsx`:** remove the `/import` route (`<Route path="/import" element={<CsvImport />} />`), remove the "Import CSV" `<NavLink>`, reorder nav to `✦ Chat · Dashboard · Transactions · Add · Config`, and rename the "Categories" nav label to "Config". The `/categories` route itself is unchanged.

---

## File Map

| File | Change |
|------|--------|
| `finances/backend/models.py` | Add `created_at: str` to `Transaction`, set in `from_create` |
| `finances/backend/sheets.py` | Add column I to `append_transaction`; read it in `get_all_transactions`; update range refs in `update_transaction` |
| `finances/backend/init_sheets.py` | Extend Transactions header to A1:I1 |
| `finances/backend/main.py` | Remove csv_router import and registration |
| `finances/backend/csv_import.py` | **Delete** |
| `finances/tests/test_csv_import.py` | **Delete** |
| `finances/frontend/src/utils/dateFilter.ts` | Add `MonthlySavingsPoint` type and `buildMonthlySavingsData` function |
| `finances/frontend/src/utils/dateFilter.test.ts` | Add tests for `buildMonthlySavingsData` |
| `finances/frontend/src/components/Dashboard.tsx` | Replace category chart, replace trend chart, add savings rate card |
| `finances/frontend/src/components/CsvImport.tsx` | **Delete** |
| `finances/frontend/src/App.tsx` | Remove `/import` route and NavLink |

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| No expenses in period | Category chart shows "No expenses this period" |
| No income in period | Savings Rate card shows "—" with no progress bar |
| All-negative net months | Monthly Savings chart renders bars below zero line |
| `created_at` missing on old rows | Defaults to `""`, no error |

---

## Out of Scope

- Showing `created_at` in the Transaction List UI
- Backfilling `created_at` for existing rows
- Paginating or virtualising the category chart
- Any changes to the `Payslips` sheet or payslip model
