import type { Transaction, TransactionCreate, Category, ImportPreviewRow, ImportPreviewError, ChatMessage } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: options?.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : undefined,
    ...options,
  });
  if (res.status === 401) {
    window.location.href = `${BASE}/auth/login`;
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  getMe: () => req<{ email: string }>("/auth/me"),

  getTransactions: () => req<Transaction[]>("/api/transactions"),
  createTransaction: (data: TransactionCreate) =>
    req<Transaction>("/api/transactions", { method: "POST", body: JSON.stringify(data) }),
  deleteTransaction: (id: string) =>
    req<void>(`/api/transactions/${id}`, { method: "DELETE" }),

  getCategories: () => req<Category[]>("/api/categories"),
  createCategory: (name: string) =>
    req<Category>("/api/categories", { method: "POST", body: JSON.stringify({ name }) }),
  deleteCategory: (name: string) =>
    req<void>(`/api/categories/${encodeURIComponent(name)}`, { method: "DELETE" }),

  importPreview: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ valid_rows: ImportPreviewRow[]; errors: ImportPreviewError[] }>(
      "/api/import/preview", { method: "POST", body: form }
    );
  },
  importConfirm: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ imported: number }>("/api/import/confirm", { method: "POST", body: form });
  },
  chat: (message: string, history: ChatMessage[]) =>
    req<{ reply: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),
};
