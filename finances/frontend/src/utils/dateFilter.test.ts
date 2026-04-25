import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { presetToRange, buildTrendData } from './dateFilter';

describe('presetToRange', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-25T12:00:00Z'));
  });
  afterEach(() => { vi.useRealTimers(); });

  it('this_month: first day of month → today', () => {
    const { from, to } = presetToRange('this_month');
    expect(from).toBe('2026-04-01');
    expect(to).toBe('2026-04-25');
  });

  it('this_week: Monday of current week → today', () => {
    // 2026-04-25 is Saturday; Monday = 2026-04-20
    const { from, to } = presetToRange('this_week');
    expect(from).toBe('2026-04-20');
    expect(to).toBe('2026-04-25');
  });

  it('last_month: full previous month', () => {
    const { from, to } = presetToRange('last_month');
    expect(from).toBe('2026-03-01');
    expect(to).toBe('2026-03-31');
  });

  it('3_months: first day 2 months ago → today', () => {
    const { from, to } = presetToRange('3_months');
    expect(from).toBe('2026-02-01');
    expect(to).toBe('2026-04-25');
  });

  it('6_months: first day 5 months ago → today', () => {
    const { from, to } = presetToRange('6_months');
    expect(from).toBe('2025-11-01');
    expect(to).toBe('2026-04-25');
  });
});

describe('buildTrendData', () => {
  const txs = [
    { date: '2026-04-20', amount: 10, type: 'expense' },
    { date: '2026-04-20', amount: 20, type: 'expense' },
    { date: '2026-04-21', amount: 5,  type: 'income'  },
    { date: '2026-03-15', amount: 100, type: 'expense' },
  ];

  it('daily buckets for range ≤ 31 days', () => {
    const result = buildTrendData(txs, '2026-04-20', '2026-04-21');
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ label: '2026-04-20', expenses: 30, income: 0 });
    expect(result[1]).toEqual({ label: '2026-04-21', expenses: 0,  income: 5 });
  });

  it('monthly buckets for range > 31 days', () => {
    const result = buildTrendData(txs, '2026-03-01', '2026-04-25');
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ label: '2026-03', expenses: 100, income: 0 });
    expect(result[1]).toEqual({ label: '2026-04', expenses: 30,  income: 5 });
  });
});
