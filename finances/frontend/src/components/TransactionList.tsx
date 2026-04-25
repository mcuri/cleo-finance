import { useEffect, useState } from "react";
import { api } from "../api";
import type { Transaction } from "../types";

export default function TransactionList() {
  const [all, setAll] = useState<Transaction[]>([]);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [type, setType] = useState<"all" | "income" | "expense">("all");
  const [category, setCategory] = useState("all");

  useEffect(() => { api.getTransactions().then(setAll); }, []);

  const categories = Array.from(new Set(all.map(t => t.category))).sort();
  const filtered = all.filter(t =>
    t.date.startsWith(month) &&
    (type === "all" || t.type === type) &&
    (category === "all" || t.category === category)
  );

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this transaction?")) return;
    await api.deleteTransaction(id);
    setAll(prev => prev.filter(t => t.id !== id));
  };

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
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {filtered.length === 0
        ? <p>No transactions for this period.</p>
        : (
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Merchant</th><th>Category</th>
                  <th style={{ textAlign: "right" }}>Amount</th><th>Type</th><th>Source</th><th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => (
                  <tr key={t.id}>
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
                        onClick={() => handleDelete(t.id)}
                        style={{ background: "none", border: "none", color: "var(--expense)", padding: "0 0.25rem", fontSize: "1rem" }}
                      >×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  );
}
