export type TransactionType = "income" | "expense";
export type TransactionSource = "web" | "csv" | "telegram";

export interface Transaction {
  id: string;
  date: string;
  amount: number;
  merchant: string;
  category: string;
  type: TransactionType;
  source: TransactionSource;
  notes?: string;
}

export interface TransactionCreate {
  date: string;
  amount: number;
  merchant: string;
  category: string;
  type: TransactionType;
  notes?: string;
}

export interface Category {
  name: string;
  predefined: boolean;
}

export interface ImportPreviewRow {
  date: string;
  amount: number;
  merchant: string;
  category: string;
  type: string;
}

export interface ImportPreviewError {
  row: number;
  reason: string;
}
