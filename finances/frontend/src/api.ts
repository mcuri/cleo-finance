import type { Transaction, TransactionCreate, Category } from "./types";

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
  updateTransaction: (id: string, data: Partial<TransactionCreate>) =>
    req<Transaction>(`/api/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  getCategories: () => req<Category[]>("/api/categories"),
  createCategory: (name: string) =>
    req<Category>("/api/categories", { method: "POST", body: JSON.stringify({ name }) }),
  deleteCategory: (name: string) =>
    req<void>(`/api/categories/${encodeURIComponent(name)}`, { method: "DELETE" }),

  chatForm: (form: FormData) =>
    req<{ reply: string }>("/api/chat", { method: "POST", body: form }),
};
