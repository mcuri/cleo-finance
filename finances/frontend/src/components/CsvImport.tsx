import { useState } from "react";
import { api } from "../api";
import type { ImportPreviewRow, ImportPreviewError } from "../types";

export default function CsvImport() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{
    valid_rows: ImportPreviewRow[];
    errors: ImportPreviewError[];
  } | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    if (!file) return;
    setError(null);
    setResult(null);
    try {
      setPreview(await api.importPreview(file));
    } catch {
      setError("Failed to parse CSV. Check that all required columns are present.");
    }
  };

  const handleConfirm = async () => {
    if (!file || !preview) return;
    setImporting(true);
    try {
      const data = await api.importConfirm(file);
      setResult(`Imported ${data.imported} transactions successfully.`);
      setPreview(null);
      setFile(null);
    } catch {
      setError("Import failed. Please try again.");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <h1>Import CSV</h1>
      <p>Required columns: <code>date</code>, <code>amount</code>, <code>merchant</code>, <code>category</code>, <code>type</code></p>
      <p style={{ fontSize: "0.875rem" }}>Date format: YYYY-MM-DD. Type: <code>income</code> or <code>expense</code>.</p>

      {error && <p className="amount-expense">{error}</p>}
      {result && <p className="amount-income">{result}</p>}

      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
        <input type="file" accept=".csv" style={{ width: "auto", marginTop: 0 }}
          onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); setResult(null); }} />
        <button onClick={handlePreview} disabled={!file} style={{ width: "auto" }}>Preview</button>
      </div>

      {preview && (
        <>
          {preview.errors.length > 0 && (
            <div style={{
              background: "var(--surface)",
              border: "1px solid var(--expense)",
              borderRadius: 6,
              padding: "0.75rem",
              marginBottom: "1rem",
            }}>
              <strong style={{ color: "var(--expense)" }}>Rows with errors (skipped):</strong>
              {preview.errors.map(e => (
                <div key={e.row} style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                  Row {e.row}: {e.reason}
                </div>
              ))}
            </div>
          )}

          <h3>{preview.valid_rows.length} valid rows</h3>
          <div className="card" style={{ padding: 0, overflow: "hidden", marginBottom: "1rem" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Merchant</th><th>Category</th>
                  <th style={{ textAlign: "right" }}>Amount</th><th>Type</th>
                </tr>
              </thead>
              <tbody>
                {preview.valid_rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.date}</td>
                    <td>{r.merchant}</td>
                    <td>{r.category}</td>
                    <td style={{ textAlign: "right" }} className="amount-expense">${r.amount.toFixed(2)}</td>
                    <td>{r.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            className="primary"
            onClick={handleConfirm}
            disabled={importing || preview.valid_rows.length === 0}
          >
            {importing ? "Importing…" : `Import ${preview.valid_rows.length} transactions`}
          </button>
        </>
      )}
    </div>
  );
}
