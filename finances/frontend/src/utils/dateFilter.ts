export type Preset = 'this_week' | 'this_month' | 'last_month' | '3_months' | '6_months' | 'custom';

export interface DateFilter {
  preset: Preset;
  from: string;
  to: string;
}

export interface TrendPoint {
  label: string;
  expenses: number;
  income: number;
}

function toYMD(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function presetToRange(preset: Exclude<Preset, 'custom'>): { from: string; to: string } {
  const today = new Date();
  const todayStr = toYMD(today);

  if (preset === 'this_week') {
    const d = new Date(today);
    const day = d.getDay();
    d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
    return { from: toYMD(d), to: todayStr };
  }
  if (preset === 'this_month') {
    const from = new Date(today.getFullYear(), today.getMonth(), 1);
    return { from: toYMD(from), to: todayStr };
  }
  if (preset === 'last_month') {
    const first = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const last  = new Date(today.getFullYear(), today.getMonth(), 0);
    return { from: toYMD(first), to: toYMD(last) };
  }
  if (preset === '3_months') {
    const from = new Date(today.getFullYear(), today.getMonth() - 2, 1);
    return { from: toYMD(from), to: todayStr };
  }
  // 6_months
  const from = new Date(today.getFullYear(), today.getMonth() - 5, 1);
  return { from: toYMD(from), to: todayStr };
}

export function buildTrendData(
  transactions: Array<{ date: string; amount: number; type: string }>,
  from: string,
  to: string,
): TrendPoint[] {
  const fromDate = new Date(from + 'T00:00:00');
  const toDate   = new Date(to   + 'T00:00:00');
  const diffDays = (toDate.getTime() - fromDate.getTime()) / 86_400_000;

  if (diffDays <= 31) {
    const points: TrendPoint[] = [];
    const d = new Date(fromDate);
    while (toYMD(d) <= to) {
      const label = toYMD(d);
      const day = transactions.filter(t => t.date === label);
      points.push({
        label,
        expenses: +day.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0).toFixed(2),
        income:   +day.filter(t => t.type === 'income' ).reduce((s, t) => s + t.amount, 0).toFixed(2),
      });
      d.setDate(d.getDate() + 1);
    }
    return points;
  }

  // Monthly buckets
  const points: TrendPoint[] = [];
  const d = new Date(fromDate.getFullYear(), fromDate.getMonth(), 1);
  const toMonth = to.slice(0, 7);
  while (toYMD(d).slice(0, 7) <= toMonth) {
    const label = toYMD(d).slice(0, 7);
    const month = transactions.filter(t => t.date.startsWith(label));
    points.push({
      label,
      expenses: +month.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0).toFixed(2),
      income:   +month.filter(t => t.type === 'income' ).reduce((s, t) => s + t.amount, 0).toFixed(2),
    });
    d.setMonth(d.getMonth() + 1);
  }
  return points;
}
