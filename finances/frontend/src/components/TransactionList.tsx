import { Fragment, useEffect, useState, useMemo } from "react";
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
  const _now = new Date();
  const _currentMonth = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}`;

  const [all, setAll] = useState<Transaction[]>([]);
  const [month, setMonth] = useState(_currentMonth);
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

  const isCurrentMonth = month === _currentMonth;

  const shiftMonth = (delta: number) => {
    const [y, m] = month.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  };

  const monthLabel = useMemo(() => {
    const [y, m] = month.split('-').map(Number);
    return new Date(y, m - 1).toLocaleString('default', { month: 'long', year: 'numeric' });
  }, [month]);

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
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem", alignItems: "center" }}>
        <button onClick={() => shiftMonth(-1)} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '0.25rem 0.6rem', cursor: 'pointer', fontSize: '1rem', color: 'var(--text-secondary)' }}>‹</button>
        <span style={{ minWidth: 140, textAlign: 'center', fontWeight: 600, fontSize: '0.95rem' }}>{monthLabel}</span>
        <button onClick={() => shiftMonth(1)} disabled={isCurrentMonth} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: '0.25rem 0.6rem', cursor: isCurrentMonth ? 'default' : 'pointer', fontSize: '1rem', color: isCurrentMonth ? 'var(--text-muted)' : 'var(--text-secondary)', opacity: isCurrentMonth ? 0.4 : 1 }}>›</button>
        {!isCurrentMonth && (
          <button onClick={() => setMonth(_currentMonth)} style={{ padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.8rem', cursor: 'pointer', border: 'none', background: 'var(--accent)', color: '#fff', fontWeight: 600 }}>This Month</button>
        )}
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
                          <td style={{ textAlign: "right" }}>
                            <input
                              type="number" step="0.01" min="0.01"
                              value={editForm.amount} onChange={set("amount")}
                              style={{ ...inputStyle, textAlign: "right", width: "6rem" }}
                            />
                          </td>
                          <td style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                            <select value={editForm.category} onChange={set("category")} style={inputStyle}>
                              {categories.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                            </select>
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
                      <td style={{ textAlign: "right" }} className={t.type === "income" ? "amount-income" : "amount-expense"}>
                        {t.type === "income" ? "+" : "-"}${t.amount.toFixed(2)}
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>{t.category}</td>
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
