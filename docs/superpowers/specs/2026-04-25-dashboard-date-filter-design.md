# Dashboard Date Filter — Design Spec

> **For agentic workers:** Use superpowers:writing-plans to implement this spec.

**Goal:** Add a date-range filter to the Dashboard so all summary cards and charts reflect the selected period instead of always showing the current month.

**Scope:** Frontend only — `finances/frontend/src/components/Dashboard.tsx`. No backend changes, no new files.

---

## Filter UI

A row of pill buttons sits at the top of the dashboard, above the summary cards:

```
This Week  |  This Month  |  Last Month  |  3 Months  |  6 Months  |  Custom…
```

- The active preset is highlighted (indigo background, white text); inactive pills have a dark surface background with a border.
- Clicking **Custom…** reveals two `<input type="date">` fields (From / To) and an **Apply** button inline below the pills. Clicking Apply updates the active range and hides the inputs. Clicking any preset dismisses the custom inputs.
- Default on load: **This Month** (first day of current month → today).

## State

```ts
type Preset = 'this_week' | 'this_month' | 'last_month' | '3_months' | '6_months' | 'custom';

interface DateFilter {
  preset: Preset;
  from: string;  // YYYY-MM-DD
  to: string;    // YYYY-MM-DD
}
```

`dateFilter` is `useState<DateFilter>` initialised to `this_month`.

Helper `presetToRange(preset: Preset): { from: string; to: string }` computes boundaries:
- `this_week` — Monday of current week → today
- `this_month` — first day of current month → today
- `last_month` — first→last day of previous month
- `3_months` — 3 months ago (first of that month) → today
- `6_months` — 6 months ago (first of that month) → today
- `custom` — boundaries set by the user via date inputs

## Filtered Data

```ts
const filteredTransactions = useMemo(
  () => transactions.filter(t => t.date >= dateFilter.from && t.date <= dateFilter.to),
  [transactions, dateFilter]
);
```

All derived values (income, expenses, net, `byCategory`, `trendData`) use `filteredTransactions` instead of the hard-coded `thisMonth` slice.

## Trend Chart

The trend chart adapts its bucket granularity based on the active range:

- Range ≤ 31 days → **daily** buckets (one entry per day in the range)
- Range > 31 days → **monthly** buckets (one entry per calendar month in the range)

A helper `buildTrendData(transactions, from, to): TrendPoint[]` encapsulates this logic. `TrendPoint` is `{ label: string; expenses: number; income: number }`.

## Dashboard Title

The `<h1>` updates to reflect the active period:
- Preset: `Dashboard — May 2026` (month name) or `Dashboard — This Week`
- Custom: `Dashboard — May 1 – May 15`

## Error Handling

- If `from > to` in custom mode, the Apply button is disabled.
- If `to` is beyond today, cap it to today's date silently.

## Testing

No new backend tests. Frontend-only logic is validated by:
1. `presetToRange` unit tests covering all 5 presets and boundary conditions (end-of-month, year rollover)
2. Manual smoke: switch between all presets, verify cards and charts update; set custom range, verify Apply works and pill shows as active; set `from > to`, verify Apply is disabled
