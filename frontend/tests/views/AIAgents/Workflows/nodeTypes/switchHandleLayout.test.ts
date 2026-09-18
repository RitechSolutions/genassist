import { describe, it, expect } from "vitest";
import {
  computeSwitchFanOut,
  needsSwitchFanOut,
  SWITCH_FAN_OUT_GAP,
  SWITCH_FAN_OUT_THRESHOLD,
} from "@/views/AIAgents/Workflows/nodeTypes/router/switchHandleLayout";

const TILE = { width: 144, height: 144 };
const CARD = { width: 400, height: 420 };

const expectConstantGap = (points: { y: number }[], centerY: number) => {
  for (let i = 1; i < points.length; i++) {
    expect(points[i].y - points[i - 1].y).toBeCloseTo(SWITCH_FAN_OUT_GAP);
  }
  expect(points[0].y + points[points.length - 1].y).toBeCloseTo(2 * centerY);
};

describe("needsSwitchFanOut", () => {
  it("keeps the regular edge layout up to 6 outputs and fans out beyond", () => {
    expect(SWITCH_FAN_OUT_THRESHOLD).toBe(6);
    expect(needsSwitchFanOut(2)).toBe(false);
    expect(needsSwitchFanOut(6)).toBe(false);
    expect(needsSwitchFanOut(7)).toBe(true);
    expect(needsSwitchFanOut(40)).toBe(true);
  });
});

describe("computeSwitchFanOut — arc (compact tile)", () => {
  it("collapses onto the middle of the tile's right edge", () => {
    expect(computeSwitchFanOut(8, TILE, "arc").anchor).toEqual({ x: 144, y: 72 });
  });

  it.each([7, 12, 25, 60])("places %i outputs top to bottom with a constant gap", (count) => {
    const { points } = computeSwitchFanOut(count, TILE, "arc");
    expect(points).toHaveLength(count);
    expectConstantGap(points, 72);
  });

  it.each([7, 12, 25, 60])("keeps all %i outputs on one circle, right of centre and clear of the corners", (count) => {
    const { points } = computeSwitchFanOut(count, TILE, "arc");
    const radii = points.map((p) => Math.hypot(p.x - 72, p.y - 72));
    for (const r of radii) {
      expect(r).toBeCloseTo(radii[0]);
      expect(r).toBeGreaterThan(Math.hypot(72, 72));
    }
    for (const p of points) expect(p.x).toBeGreaterThan(72);
  });

  it("grows only when the outputs no longer fit the smallest circle", () => {
    const radius = (count: number) => {
      const p = computeSwitchFanOut(count, TILE, "arc").points[0];
      return Math.hypot(p.x - 72, p.y - 72);
    };
    expect(radius(8)).toBeCloseTo(radius(7));
    expect(radius(30)).toBeGreaterThan(radius(7));
  });

  it("uses a round hover area around the tile", () => {
    const { hitArea } = computeSwitchFanOut(10, TILE, "arc");
    expect(hitArea.borderRadius).toBe("50%");
    expect(hitArea.left + hitArea.width / 2).toBeCloseTo(72);
    expect(hitArea.top + hitArea.height / 2).toBeCloseTo(72);
  });
});

describe("computeSwitchFanOut — bracket (detailed card)", () => {
  it("collapses onto the middle of the card's right edge", () => {
    expect(computeSwitchFanOut(8, CARD, "bracket").anchor).toEqual({ x: 400, y: 210 });
  });

  it.each([7, 13, 24, 60])("places %i outputs top to bottom with a constant gap", (count) => {
    const { points } = computeSwitchFanOut(count, CARD, "bracket");
    expect(points).toHaveLength(count);
    expectConstantGap(points, 210);
  });

  it("lines up the outputs beside the card in one column when they fit its height", () => {
    const { points } = computeSwitchFanOut(13, CARD, "bracket");
    const xs = new Set(points.map((p) => p.x));
    expect(xs.size).toBe(1);
    expect(points[0].x).toBeGreaterThan(CARD.width);
  });

  it("curves the outputs that don't fit over the top and bottom corners, clear of them", () => {
    const { points } = computeSwitchFanOut(40, CARD, "bracket");
    const beside = points.filter((p) => p.y >= 0 && p.y <= CARD.height);
    const above = points.filter((p) => p.y < 0);
    const below = points.filter((p) => p.y > CARD.height);
    expect(above.length).toBeGreaterThan(0);
    expect(below.length).toBe(above.length);
    for (const p of beside) expect(p.x).toBeGreaterThan(CARD.width);
    // Moving away from the card, the curve bends back toward it.
    for (let i = 1; i < above.length; i++) expect(above[i - 1].x).toBeLessThanOrEqual(above[i].x);
    for (const p of [...above, ...below]) {
      const corner = { x: CARD.width, y: p.y < 0 ? 0 : CARD.height };
      expect(Math.hypot(p.x - corner.x, p.y - corner.y)).toBeGreaterThan(24);
    }
  });

  it("covers the card and every output with the hover area", () => {
    const { points, hitArea } = computeSwitchFanOut(40, CARD, "bracket");
    for (const p of points) {
      expect(p.x).toBeGreaterThanOrEqual(hitArea.left);
      expect(p.x).toBeLessThanOrEqual(hitArea.left + hitArea.width);
      expect(p.y).toBeGreaterThanOrEqual(hitArea.top);
      expect(p.y).toBeLessThanOrEqual(hitArea.top + hitArea.height);
    }
    expect(hitArea.top).toBeLessThanOrEqual(0);
    expect(hitArea.top + hitArea.height).toBeGreaterThanOrEqual(CARD.height);
  });
});

it("handles no outputs", () => {
  expect(computeSwitchFanOut(0, TILE, "arc").points).toEqual([]);
  expect(computeSwitchFanOut(0, CARD, "bracket").points).toEqual([]);
});
