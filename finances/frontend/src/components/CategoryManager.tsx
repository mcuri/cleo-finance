import { useEffect, useState } from "react";
import { api } from "../api";
import type { Category } from "../types";

export default function CategoryManager() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { api.getCategories().then(setCategories); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setError("");
    try {
      const cat = await api.createCategory(newName.trim());
      setCategories(prev => [...prev, cat]);
      setNewName("");
    } catch {
      setError("Failed to add category.");
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete "${name}"?`)) return;
    await api.deleteCategory(name);
    setCategories(prev => prev.filter(c => c.name !== name));
  };

  const predefined = categories.filter(c => c.predefined);
  const custom = categories.filter(c => !c.predefined);

  return (
    <div style={{ maxWidth: 480, margin: "0 auto" }}>
      <h1>Categories</h1>
      {error && <p className="amount-expense">{error}</p>}

      <h2>Predefined</h2>
      <ul style={{ paddingLeft: "1.25rem", color: "var(--text-secondary)" }}>
        {predefined.map(c => <li key={c.name} style={{ marginBottom: "0.25rem" }}>{c.name}</li>)}
      </ul>

      <h2>Custom</h2>
      {custom.length === 0 && <p style={{ color: "var(--text-muted)" }}>No custom categories yet.</p>}
      <ul style={{ paddingLeft: "1.25rem" }}>
        {custom.map(c => (
          <li key={c.name} style={{
            display: "flex",
            gap: "0.5rem",
            alignItems: "center",
            marginBottom: "0.25rem",
            color: "var(--text-primary)",
          }}>
            {c.name}
            <button onClick={() => handleDelete(c.name)}
              style={{ color: "var(--expense)", border: "none", background: "none", padding: "0 0.25rem", fontSize: "1.1rem", cursor: "pointer" }}>
              ×
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={handleAdd} style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <input
          type="text"
          placeholder="New category name"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          style={{ flex: 1, marginTop: 0 }}
        />
        <button type="submit" className="primary" style={{ width: "auto" }}>Add</button>
      </form>
    </div>
  );
}
