# Dashboard Date Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add preset + custom date-range filtering to the Dashboard so all summary cards and charts reflect the selected period.

**Architecture:** Frontend-only change — no backend or API modifications. Pure date-math helpers are extracted to `src/utils/dateFilter.ts` and unit-tested with vitest. `Dashboard.tsx` imports these helpers, holds a `DateFilter` state, and filters the already-fetched transaction list in a `useMemo`.

**Tech Stack:** React 19, TypeScript 6, Vite 8, vitest 3 (added), recharts 3.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `finances/frontend/src/utils/dateFilter.ts` | Pure helpers: `presetToRange`, `buildTrendData`, shared types |
| Create | `finances/frontend/src/utils/dateFilter.test.ts` | vitest unit tests for the helpers |
| Modify | `finances/frontend/vite.config.ts` | Add vitest config |
| Modify | `finances/frontend/package.json` | Add vitest dev dependency + `test` script |
| Modify | `finances/frontend/src/components/Dashboard.tsx` | Filter state, filter bar UI, wire helpers |

---

### Task 1: Add vitest and date-filter utility

**Files:**
- Create: `finances/frontend/src/utils/dateFilter.ts`
- Create: `finances/frontend/src/utils/dateFilter.test.ts`
- Modify: `finances/frontend/vite.config.ts`
- Modify: `finances/frontend/package.json`

- [ ] **Step 1: Install vitest**

```bash
cd finances/frontend
npm install --save-dev vitest@^3.0.0
```

Expected: vitest appears in `node_modules`, `package-lock.json` updated.

- [ ] **Step 2: Add vitest config to `vite.config.ts`**

Replace the entire file:

```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
  },
})
```

- [ ] **Step 3: Add `test` script to `package.json`**

In the `"scripts"` block, add:

```json
"test": "vitest run"
```

Full scripts block becomes:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run"
}
```

- [ ] **Step 4: Create the failing tests in `src/utils/dateFilter.test.ts`**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { presetToRange, buildTrendData } from './dateFilter';

describe('presetToRange', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-25T12:00:00Z'));
  });
  afterEach(() => { vi.useRealTimers(); });

  it('this_month: first day of month → today', () => {
    const { from, to } = presetToRange('this_month');
    expect(from).toBe('2026-04-01');
    expect(to).toBe('2026-04-25');
  });

  it('this_week: Monday of current week → today', () => {
    // 2026-04-25 is Saturday; Monday = 2026-04-20
    const { from, to } = presetToRange('this_week');
    expect(from).toBe('2026-04-20');
    expect(to).toBe('2026-04-25');
  });

  it('last_month: full previous month', () => {
    const { from, to } = presetToRange('last_month');
    expect(from).toBe('2026-03-01');
    expect(to).toBe('2026-03-31');
  });

  it('3_months: first day 2 months ago → today', () => {
    const { from, to } = presetToRange('3_months');
    expect(from).toBe('2026-02-01');
    expect(to).toBe('2026-04-25');
  });

  it('6_months: first day 5 months ago → today', () => {
    const { from, to } = presetToRange('6_months');
    expect(from).toBe('2025-11-01');
    expect(to).toBe('2026-04-25');
  });
});

describe('buildTrendData', () => {
  const txs = [
    { date: '2026-04-20', amount: 10, type: 'expense' },
    { date: '2026-04-20', amount: 20, type: 'expense' },
    { date: '2026-04-21', amount: 5,  type: 'income'  },
    { date: '2026-03-15', amount: 100, type: 'expense' },
  ];

  it('daily buckets for range ≤ 31 days', () => {
    const result = buildTrendData(txs, '2026-04-20', '2026-04-21');
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ label: '2026-04-20', expenses: 30, income: 0 });
    expect(result[1]).toEqual({ label: '2026-04-21', expenses: 0,  income: 5 });
  });

  it('monthly buckets for range > 31 days', () => {
    const result = buildTrendData(txs, '2026-03-01', '2026-04-25');
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ label: '2026-03', expenses: 100, income: 0 });
    expect(result[1]).toEqual({ label: '2026-04', expenses: 30,  income: 5 });
  });
});
```

- [ ] **Step 5: Run tests — expect failures**

```bash
cd finances/frontend
npm test
```

Expected: `Cannot find module './dateFilter'` or similar.

- [ ] **Step 6: Create `src/utils/dateFilter.ts`**

```ts
export type Preset = 'this_week' | 'this_month' | 'last_month' | '3_months' | '6_months' | 'custom';

export interface DateFilter {
  preset: Preset;
  from: string;
  to: string;
}

export interface TrendPoint {
  label: string;
  expenses: number;
  income: number;
}

function toYMD(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function presetToRange(preset: Exclude<Preset, 'custom'>): { from: string; to: string } {
  const today = new Date();
  const todayStr = toYMD(today);

  if (preset === 'this_week') {
    const d = new Date(today);
    const day = d.getDay();
    d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
    return { from: toYMD(d), to: todayStr };
  }
  if (preset === 'this_month') {
    const from = new Date(today.getFullYear(), today.getMonth(), 1);
    return { from: toYMD(from), to: todayStr };
  }
  if (preset === 'last_month') {
    const first = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const last  = new Date(today.getFullYear(), today.getMonth(), 0);
    return { from: toYMD(first), to: toYMD(last) };
  }
  if (preset === '3_months') {
    const from = new Date(today.getFullYear(), today.getMonth() - 2, 1);
    return { from: toYMD(from), to: todayStr };
  }
  // 6_months
  const from = new Date(today.getFullYear(), today.getMonth() - 5, 1);
  return { from: toYMD(from), to: todayStr };
}

export function buildTrendData(
  transactions: Array<{ date: string; amount: number; type: string }>,
  from: string,
  to: string,
): TrendPoint[] {
  const fromDate = new Date(from + 'T00:00:00');
  const toDate   = new Date(to   + 'T00:00:00');
  const diffDays = (toDate.getTime() - fromDate.getTime()) / 86_400_000;

  if (diffDays <= 31) {
    const points: TrendPoint[] = [];
    const d = new Date(fromDate);
    while (toYMD(d) <= to) {
      const label = toYMD(d);
      const day = transactions.filter(t => t.date === label);
      points.push({
        label,
        expenses: +day.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0).toFixed(2),
        income:   +day.filter(t => t.type === 'income' ).reduce((s, t) => s + t.amount, 0).toFixed(2),
      });
      d.setDate(d.getDate() + 1);
    }
    return points;
  }

  // Monthly buckets
  const points: TrendPoint[] = [];
  const d = new Date(fromDate.getFullYear(), fromDate.getMonth(), 1);
  const toMonth = to.slice(0, 7);
  while (d.toISOString().slice(0, 7) <= toMonth) {
    const label = d.toISOString().slice(0, 7);
    const month = transactions.filter(t => t.date.startsWith(label));
    points.push({
      label,
      expenses: +month.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0).toFixed(2),
      income:   +month.filter(t => t.type === 'income' ).reduce((s, t) => s + t.amount, 0).toFixed(2),
    });
    d.setMonth(d.getMonth() + 1);
  }
  return points;
}
```

- [ ] **Step 7: Run tests — expect all passing**

```bash
cd finances/frontend
npm test
```

Expected: `7 passed`.

- [ ] **Step 8: Commit**

```bash
cd finances/frontend && npm run build
cd ../..
git add finances/frontend/src/utils/dateFilter.ts \
        finances/frontend/src/utils/dateFilter.test.ts \
        finances/frontend/vite.config.ts \
        finances/frontend/package.json \
        finances/frontend/package-lock.json
git commit -m "feat: add dateFilter utility with vitest tests"
```

---

### Task 2: Update Dashboard.tsx

**Files:**
- Modify: `finances/frontend/src/components/Dashboard.tsx`

- [ ] **Step 1: Replace `Dashboard.tsx` with the new implementation**

Replace the entire file content:

```tsx
import { useEffect, useState, useMemo } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api";
import type { Transaction } from "../types";
import { presetToRange, buildTrendData } from "../utils/dateFilter";
import type { DateFilter, Preset } from "../utils/dateFilter";

const PRESETS: { key: Exclude<Preset, 'custom'>; label: string }[] = [
  { key: 'this_week',  label: 'This Week'  },
  { key: 'this_month', label: 'This Month' },
  { key: 'last_month', label: 'Last Month' },
  { key: '3_months',   label: '3 Months'   },
  { key: '6_months',   label: '6 Months'   },
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

  const byCategory: Record<string, number> = {};
  filteredTransactions.filter(t => t.type === "expense").forEach(t => {
    byCategory[t.category] = (byCategory[t.category] ?? 0) + t.amount;
  });
  const categoryData = Object.entries(byCategory)
    .map(([category, amount]) => ({ category, amount: +amount.toFixed(2) }))
    .sort((a, b) => b.amount - a.amount);

  const trendData = useMemo(
    () => buildTrendData(filteredTransactions, dateFilter.from, dateFilter.to),
    [filteredTransactions, dateFilter],
  );

  const selectPreset = (key: Exclude<Preset, 'custom'>) => {
    setDateFilter({ preset: key, ...presetToRange(key) });
    setShowCustom(false);
  };

  const today = new Date().toISOString().slice(0, 10);
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
          <input type="date" value={customTo}   onChange={e => setCustomTo(e.target.value)}   style={{ width: 'auto', marginTop: 0 }} />
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
      </div>

      <h2>Spending by category</h2>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={categoryData} margin={{ left: 10 }}>
            <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <Tooltip formatter={(v) => `$${Number(v).toFixed(2)}`}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
            <Bar dataKey="amount" fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h2>Trend</h2>
      <div className="card">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={trendData} margin={{ left: 10 }}>
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <Tooltip formatter={(v) => `$${Number(v).toFixed(2)}`}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
            <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
            <Line type="monotone" dataKey="expenses" stroke="#f87171" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="income"   stroke="#34d399" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript build passes**

```bash
cd finances/frontend
npm run build
```

Expected: `✓ built in ~600ms`, zero TypeScript errors.

- [ ] **Step 3: Run vitest to confirm utility tests still pass**

```bash
npm test
```

Expected: `7 passed`.

- [ ] **Step 4: Smoke test in browser**

```bash
npm run dev
```

Open http://localhost:5173 and verify:
- Dashboard loads with "This Month" pill highlighted
- Summary cards and category chart show current-month data
- Click "This Week" — cards and charts update, title changes to "This Week"
- Click "6 Months" — title changes to "Last 6 Months", trend shows 6 monthly bars
- Click "Custom…" — date inputs appear; set a valid range and click Apply — filter applies, inputs hide, "Custom…" pill highlighted
- Set From > To — Apply button is disabled

- [ ] **Step 5: Commit**

```bash
cd ../..
git add finances/frontend/src/components/Dashboard.tsx
git commit -m "feat: dashboard date-range filter with preset pills and custom range"
```
