import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Category } from "../types";

export default function AddTransaction() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    amount: "",
    merchant: "",
    category: "",
    type: "expense" as "income" | "expense",
    notes: "",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.getCategories().then(setCategories); }, []);

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.amount || !form.merchant || !form.category) {
      setError("Amount, merchant, and category are required.");
      return;
    }
    setSaving(true);
    try {
      await api.createTransaction({
        date: form.date,
        amount: parseFloat(form.amount),
        merchant: form.merchant,
        category: form.category,
        type: form.type,
        notes: form.notes || undefined,
      });
      navigate("/transactions");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg.includes("409") ? "Duplicate transaction detected." : "Failed to save.");
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: "0 auto" }}>
      <h1>Add Transaction</h1>
      {error && <p style={{ color: "#dc2626" }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <label>Date <input type="date" value={form.date} onChange={set("date")} /></label>
        <label>Amount ($) <input type="number" step="0.01" min="0.01" value={form.amount} onChange={set("amount")} placeholder="0.00" /></label>
        <label>Merchant <input type="text" value={form.merchant} onChange={set("merchant")} placeholder="e.g. Trader Joe's" /></label>
        <label>
          Category
          <select value={form.category} onChange={set("category")}>
            <option value="">Select category</option>
            {categories.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label>
          Type
          <select value={form.type} onChange={set("type")}>
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </label>
        <label>Notes (optional) <input type="text" value={form.notes} onChange={set("notes")} /></label>
        <button type="submit" className="primary" disabled={saving} style={{ marginTop: "0.5rem", width: "100%" }}>
          {saving ? "Saving…" : "Save Transaction"}
        </button>
      </form>
    </div>
  );
}
