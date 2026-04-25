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
