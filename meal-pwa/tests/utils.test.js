/**
 * Tests for the pure utility functions defined in app.js.
 *
 * Because app.js is a non-module browser script, the functions below are
 * mirrored here to keep tests self-contained. If you change the logic in
 * app.js, update these mirrors and expectations too.
 */

import { describe, it, expect } from 'vitest';

// ── Mirrors of app.js utility functions ─────────────────────────────
const fmt$ = n => `$${Number(n).toFixed(2)}`;

function fmtWeek(str) {
  if (!str) return '';
  return new Date(str).toLocaleDateString('en-NZ', {
    day: 'numeric', month: 'long', year: 'numeric',
  });
}

function fmtTime(str) {
  if (!str) return '';
  return new Date(str).toLocaleTimeString('en-NZ', {
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

// ── fmt$ ─────────────────────────────────────────────────────────────
describe('fmt$', () => {
  it('formats integer as dollar amount', () => {
    expect(fmt$(5)).toBe('$5.00');
  });

  it('formats decimal with two places', () => {
    expect(fmt$(45.5)).toBe('$45.50');
  });

  it('formats zero', () => {
    expect(fmt$(0)).toBe('$0.00');
  });

  it('formats string number', () => {
    expect(fmt$('12.3')).toBe('$12.30');
  });

  it('rounds to two decimal places', () => {
    expect(fmt$(1.999)).toBe('$2.00');
  });
});

// ── fmtWeek ───────────────────────────────────────────────────────────
describe('fmtWeek', () => {
  it('returns empty string for falsy input', () => {
    expect(fmtWeek('')).toBe('');
    expect(fmtWeek(null)).toBe('');
    expect(fmtWeek(undefined)).toBe('');
  });

  it('returns a non-empty string for a valid date', () => {
    const result = fmtWeek('2026-05-05');
    expect(result).toBeTruthy();
    expect(typeof result).toBe('string');
  });

  it('includes the year', () => {
    const result = fmtWeek('2026-05-05');
    expect(result).toContain('2026');
  });
});

// ── fmtTime ───────────────────────────────────────────────────────────
describe('fmtTime', () => {
  it('returns empty string for falsy input', () => {
    expect(fmtTime('')).toBe('');
    expect(fmtTime(null)).toBe('');
    expect(fmtTime(undefined)).toBe('');
  });

  it('returns a non-empty string for a valid datetime', () => {
    const result = fmtTime('2026-05-05T10:30:00');
    expect(result).toBeTruthy();
    expect(typeof result).toBe('string');
  });
});
