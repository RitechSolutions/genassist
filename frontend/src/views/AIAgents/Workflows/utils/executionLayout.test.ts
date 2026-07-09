import { describe, it, expect } from 'vitest';
import { computeLayeredLayout } from './executionLayout';

describe('computeLayeredLayout', () => {
  it('lays a linear chain out left-to-right by layer', () => {
    const pos = computeLayeredLayout(
      ['a', 'b', 'c'],
      [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' },
      ]
    );
    expect(pos.a.x).toBeLessThan(pos.b.x);
    expect(pos.b.x).toBeLessThan(pos.c.x);
  });

  it('places branch targets in the same later column, stacked vertically', () => {
    const pos = computeLayeredLayout(
      ['root', 'b1', 'b2'],
      [
        { source: 'root', target: 'b1' },
        { source: 'root', target: 'b2' },
      ]
    );
    expect(pos.root.x).toBeLessThan(pos.b1.x);
    expect(pos.b1.x).toBe(pos.b2.x); // same layer
    expect(pos.b1.y).not.toBe(pos.b2.y); // stacked
  });

  it('uses longest-path layering when a node is reachable by paths of different length', () => {
    // a->b->c and a->c : c must sit past b, not next to it.
    const pos = computeLayeredLayout(
      ['a', 'b', 'c'],
      [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' },
        { source: 'a', target: 'c' },
      ]
    );
    expect(pos.c.x).toBeGreaterThan(pos.b.x);
  });

  it('ignores edges referencing unknown nodes and self-loops', () => {
    const pos = computeLayeredLayout(
      ['a', 'b'],
      [
        { source: 'a', target: 'ghost' },
        { source: 'a', target: 'a' },
        { source: 'a', target: 'b' },
      ]
    );
    expect(Object.keys(pos).sort()).toEqual(['a', 'b']);
    expect(pos.a.x).toBeLessThan(pos.b.x);
  });

  it('does not throw on cycles and still positions every node', () => {
    const pos = computeLayeredLayout(
      ['a', 'b', 'c'],
      [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' },
        { source: 'c', target: 'a' },
      ]
    );
    expect(Object.keys(pos).sort()).toEqual(['a', 'b', 'c']);
  });

  it('positions isolated nodes (no edges) without error', () => {
    const pos = computeLayeredLayout(['a', 'b', 'c'], []);
    expect(Object.keys(pos)).toHaveLength(3);
    // all in the first column
    expect(pos.a.x).toBe(pos.b.x);
    expect(pos.b.x).toBe(pos.c.x);
  });
});
