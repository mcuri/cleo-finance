import { useEffect, useState, useMemo, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine, LabelList,
} from "recharts";
import { api } from "../api";
import type { Transaction } from "../types";
import { monthToRange, buildMonthlySavingsData, toYMD } from "../utils/dateFilter";
import type { MonthlySavingsPoint } from "../utils/dateFilter";

const _NOW = new Date();

const CATEGORY_COLORS = [
  '#6366f1', '#34d399', '#f59e0b', '#f87171',
  '#818cf8', '#a3e635', '#fb923c', '#94a3b8',
];


function ExpensesTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: MonthlySavingsPoint }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "#e2e8f0" }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{d.label}</div>
      <div>Expenses: <span style={{ color: "#f87171" }}>${d.expenses.toFixed(2)}</span></div>
      {d.income > 0 && (
        <div style={{ color: "#64748b", marginTop: 4 }}>
          {Math.round(d.expenses / d.income * 100)}% of income
        </div>
      )}
    </div>
  );
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
  const [viewYear,  setViewYear]  = useState(_NOW.getFullYear());
  const [viewMonth, setViewMonth] = useState(_NOW.getMonth());

  useEffect(() => { api.getTransactions().then(setTransactions); }, []);

  const { from, to } = useMemo(() => monthToRange(viewYear, viewMonth), [viewYear, viewMonth]);

  const isCurrentMonth = viewYear === _NOW.getFullYear() && viewMonth === _NOW.getMonth();

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (isCurrentMonth) return;
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  };
  const goToToday = () => { setViewYear(_NOW.getFullYear()); setViewMonth(_NOW.getMonth()); };

  const monthLabel = new Date(viewYear, viewMonth).toLocaleString('default', { month: 'long', year: 'numeric' });

  const filteredTransactions = useMemo(
    () => transactions.filter(t => t.date >= from && t.date <= to),
    [transactions, from, to],
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

  const monthlySavingsData = useMemo(() => {
    if (!transactions.length) return [];
    const earliest = [...transactions].map(t => t.date).sort()[0];
    return buildMonthlySavingsData(transactions, earliest, toYMD(_NOW));
  }, [transactions]);

  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);
  const [popoverRelTop, setPopoverRelTop] = useState(0);
  const categoryCardRef = useRef<HTMLDivElement>(null);

  const hoveredTransactions = useMemo(() => {
    if (!hoveredCategory) return [];
    return filteredTransactions
      .filter(t => t.type === "expense" && t.category === hoveredCategory)
      .sort((a, b) => b.date.localeCompare(a.date));
  }, [hoveredCategory, filteredTransactions]);

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <h1>Dashboard</h1>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <button onClick={prevMonth} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '0.25rem 0.6rem', cursor: 'pointer', fontSize: '1rem', color: 'var(--text-secondary)' }}>‹</button>
        <span style={{ minWidth: 140, textAlign: 'center', fontWeight: 600, fontSize: '0.95rem' }}>{monthLabel}</span>
        <button onClick={nextMonth} disabled={isCurrentMonth} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '0.25rem 0.6rem', cursor: isCurrentMonth ? 'default' : 'pointer', fontSize: '1rem', color: isCurrentMonth ? 'var(--text-muted)' : 'var(--text-secondary)', opacity: isCurrentMonth ? 0.4 : 1 }}>›</button>
        {!isCurrentMonth && (
          <button onClick={goToToday} style={{ padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.8rem', cursor: 'pointer', border: 'none', background: 'var(--accent)', color: '#fff', fontWeight: 600 }}>This Month</button>
        )}
      </div>

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
      <div ref={categoryCardRef} className="card" style={{ marginBottom: "1.5rem", position: "relative" }}>
        {categoryData.length === 0 ? (
          <p style={{ color: "var(--text-muted)", margin: 0 }}>No expenses this period.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {categoryData.map(({ category, amount }, i) => {
              const pct = Math.round(amount / totalExpenses * 100);
              return (
                <div
                  key={category}
                  style={{ display: "flex", alignItems: "center", gap: "0.75rem", cursor: "default" }}
                  onMouseEnter={e => {
                    setHoveredCategory(category);
                    const rowRect = e.currentTarget.getBoundingClientRect();
                    const cardRect = categoryCardRef.current?.getBoundingClientRect();
                    setPopoverRelTop(cardRect ? rowRect.top - cardRect.top - 8 : 0);
                  }}
                  onMouseLeave={() => setHoveredCategory(null)}
                >
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

        {hoveredCategory && hoveredTransactions.length > 0 && (
          <div style={{
            position: "absolute",
            top: Math.max(0, popoverRelTop),
            right: 0,
            zIndex: 10,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "0.75rem",
            minWidth: 230,
            maxHeight: 260,
            overflowY: "auto",
            boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
            pointerEvents: "none",
          }}>
            <div style={{ fontWeight: 600, fontSize: "0.8rem", marginBottom: "0.5rem", color: "var(--text)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              {hoveredCategory}
            </div>
            {hoveredTransactions.map(t => (
              <div key={t.id} style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem", padding: "0.25rem 0", borderBottom: "1px solid var(--bg)" }}>
                <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>{t.date.slice(5)}</span>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text-secondary)" }}>{t.merchant}</span>
                <span style={{ color: "#f87171", fontWeight: 500, flexShrink: 0 }}>${t.amount.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <h2>Monthly Expenses</h2>
      <div className="card">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={monthlySavingsData} margin={{ left: 10, top: 20 }}>
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
            <Tooltip content={<ExpensesTooltip />} />
            <Bar dataKey="expenses" fill="#f87171" radius={[4, 4, 0, 0]}>
              <LabelList
                dataKey="expenses"
                position="top"
                formatter={(v: number) => v === 0 ? '' : `$${v.toFixed(0)}`}
                style={{ fontSize: 10, fill: "#94a3b8" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
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
