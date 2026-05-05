/**
 * Tests for shopping list state management logic from app.js.
 *
 * The functions below mirror the logic in app.js. If you change app.js,
 * update these mirrors and expectations too.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// ── Mirrors of app.js shopping logic ────────────────────────────────

function toggleItemLogic(checked, index) {
  return { ...checked, [index]: !checked[index] };
}

function computeProgress(items, checked) {
  const done = items.filter((_, i) => checked[i]).length;
  const total = items.length;
  return total ? (done / total) * 100 : 0;
}

function getStoreKey(bundleId, week) {
  return `checked_${bundleId || week}`;
}

// ── toggleItem logic ─────────────────────────────────────────────────
describe('toggleItemLogic', () => {
  it('checks an unchecked item', () => {
    const result = toggleItemLogic({}, 0);
    expect(result[0]).toBe(true);
  });

  it('unchecks a checked item', () => {
    const result = toggleItemLogic({ 0: true }, 0);
    expect(result[0]).toBe(false);
  });

  it('does not mutate the original checked state', () => {
    const original = { 0: true };
    toggleItemLogic(original, 0);
    expect(original[0]).toBe(true);
  });

  it('only toggles the target index', () => {
    const result = toggleItemLogic({ 0: true, 1: false }, 1);
    expect(result[0]).toBe(true);
    expect(result[1]).toBe(true);
  });
});

// ── progress calculation ──────────────────────────────────────────────
describe('computeProgress', () => {
  const items = [{}, {}, {}, {}]; // 4 items

  it('returns 0 when nothing is checked', () => {
    expect(computeProgress(items, {})).toBe(0);
  });

  it('returns 100 when everything is checked', () => {
    const checked = { 0: true, 1: true, 2: true, 3: true };
    expect(computeProgress(items, checked)).toBe(100);
  });

  it('returns 50 when half are checked', () => {
    const checked = { 0: true, 1: true };
    expect(computeProgress(items, checked)).toBe(50);
  });

  it('returns 0 for empty list', () => {
    expect(computeProgress([], {})).toBe(0);
  });

  it('ignores false values in checked', () => {
    const checked = { 0: true, 1: false };
    expect(computeProgress(items, checked)).toBe(25);
  });
});

// ── store key scoping ─────────────────────────────────────────────────
describe('getStoreKey', () => {
  it('uses bundleId when present', () => {
    expect(getStoreKey('bundle-abc123', '2026-05-05')).toBe('checked_bundle-abc123');
  });

  it('falls back to week when bundleId is falsy', () => {
    expect(getStoreKey(null, '2026-05-05')).toBe('checked_2026-05-05');
    expect(getStoreKey(undefined, '2026-05-05')).toBe('checked_2026-05-05');
  });

  it('different bundles get different keys', () => {
    const k1 = getStoreKey('bundle-aaa', '2026-05-05');
    const k2 = getStoreKey('bundle-bbb', '2026-05-05');
    expect(k1).not.toBe(k2);
  });
});

// ── localStorage integration ─────────────────────────────────────────
describe('shopping checked state via localStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('persists checked state', () => {
    const key = 'checked_bundle-abc123';
    const state = { 0: true, 2: true };
    localStorage.setItem(key, JSON.stringify(state));

    const loaded = JSON.parse(localStorage.getItem(key) || '{}');
    expect(loaded[0]).toBe(true);
    expect(loaded[2]).toBe(true);
    expect(loaded[1]).toBeUndefined();
  });

  it('returns empty object for unknown key', () => {
    const loaded = JSON.parse(localStorage.getItem('checked_unknown') || '{}');
    expect(loaded).toEqual({});
  });

  it('clearing state resets to empty', () => {
    const key = 'checked_bundle-abc123';
    localStorage.setItem(key, JSON.stringify({ 0: true }));
    localStorage.setItem(key, JSON.stringify({}));
    const loaded = JSON.parse(localStorage.getItem(key) || '{}');
    expect(loaded).toEqual({});
  });
});
