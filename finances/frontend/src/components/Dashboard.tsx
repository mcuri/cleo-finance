import { useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api";
import type { Transaction } from "../types";

function currentMonth() { return new Date().toISOString().slice(0, 7); }
function lastNMonths(n: number): string[] {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - (n - 1 - i));
    return d.toISOString().slice(0, 7);
  });
}

export default function Dashboard() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  useEffect(() => { api.getTransactions().then(setTransactions); }, []);

  const month = currentMonth();
  const thisMonth = transactions.filter(t => t.date.startsWith(month));

  const totalIncome = thisMonth.filter(t => t.type === "income").reduce((s, t) => s + t.amount, 0);
  const totalExpenses = thisMonth.filter(t => t.type === "expense").reduce((s, t) => s + t.amount, 0);
  const net = totalIncome - totalExpenses;

  const byCategory: Record<string, number> = {};
  thisMonth.filter(t => t.type === "expense").forEach(t => {
    byCategory[t.category] = (byCategory[t.category] ?? 0) + t.amount;
  });
  const categoryData = Object.entries(byCategory)
    .map(([category, amount]) => ({ category, amount: +amount.toFixed(2) }))
    .sort((a, b) => b.amount - a.amount);

  const trendData = lastNMonths(6).map(m => ({
    month: m,
    expenses: +transactions.filter(t => t.date.startsWith(m) && t.type === "expense")
      .reduce((s, t) => s + t.amount, 0).toFixed(2),
    income: +transactions.filter(t => t.date.startsWith(m) && t.type === "income")
      .reduce((s, t) => s + t.amount, 0).toFixed(2),
  }));

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <h1>Dashboard — {month}</h1>

      <div className="summary-cards">
        <div className="card">
          <div style={{ color: "#555", fontSize: "0.85rem" }}>Income</div>
          <div className="amount-income" style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            ${totalIncome.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div style={{ color: "#555", fontSize: "0.85rem" }}>Expenses</div>
          <div className="amount-expense" style={{ fontSize: "1.75rem", fontWeight: 700 }}>
            ${totalExpenses.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div style={{ color: "#555", fontSize: "0.85rem" }}>Net</div>
          <div
            className={net >= 0 ? "amount-income" : "amount-expense"}
            style={{ fontSize: "1.75rem", fontWeight: 700 }}
          >
            {net >= 0 ? "+" : ""}${net.toFixed(2)}
          </div>
        </div>
      </div>

      <h2>Spending by category (this month)</h2>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={categoryData} margin={{ left: 10 }}>
          <XAxis dataKey="category" tick={{ fontSize: 12 }} />
          <YAxis />
          <Tooltip formatter={(v) => `$${Number(v).toFixed(2)}`} />
          <Bar dataKey="amount" fill="#6c47ff" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      <h2>6-month trend</h2>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={trendData} margin={{ left: 10 }}>
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis />
          <Tooltip formatter={(v) => `$${Number(v).toFixed(2)}`} />
          <Legend />
          <Line type="monotone" dataKey="expenses" stroke="#dc2626" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="income" stroke="#16a34a" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
