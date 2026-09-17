/**
 * Geometry for a Switch node whose outputs don't fit on the node's edge.
 *
 * Collapsed, every output handle sits on one point in the middle of the node's
 * right edge (edges leave the node as a bundle). Expanded, the handles fan out
 * around the node's right side. Handles are always spaced by a constant
 * vertical gap, so the label drawn beside each handle never overlaps the next
 * one, whatever the number of outputs.
 *
 * Two shapes:
 *   - "arc": a circle around the node's centre. Suits the square compact tile.
 *   - "bracket": a column just off the right edge that curves over the top and
 *     bottom corners. Suits the wide detailed card, where a circle clearing its
 *     corners would sit far away from the card.
 *
 * All coordinates are in px relative to the node's top-left corner.
 */

/** More outputs than this (Default included) switch the node to the fan-out. */
export const SWITCH_FAN_OUT_THRESHOLD = 6;

/** Vertical distance between two neighbouring handles. */
export const SWITCH_FAN_OUT_GAP = 32;

/** Clearance between the node and the handles. */
const CLEARANCE = 44;

/** Extra room the hover area keeps around the handles. */
const HIT_MARGIN = 28;

/** Where the fan curves around a corner, the outermost handles stay within this angle. */
const MAX_CURVE_ANGLE_RAD = (75 * Math.PI) / 180;

/** Smallest corner curve of the bracket shape. */
const MIN_CORNER_RADIUS = 72;

export type FanOutShape = "arc" | "bracket";

export interface FanOutPoint {
  x: number;
  y: number;
}

export interface FanOutLayout {
  /** Where every handle sits while collapsed. */
  anchor: FanOutPoint;
  /** One point per output, top to bottom, in output order. */
  points: FanOutPoint[];
  /** Area that keeps the node hovered while the fan is open. */
  hitArea: { left: number; top: number; width: number; height: number; borderRadius: string };
}

export interface FanOutSize {
  width: number;
  height: number;
}

export const needsSwitchFanOut = (outputCount: number): boolean =>
  outputCount > SWITCH_FAN_OUT_THRESHOLD;

const verticalOffsets = (count: number): number[] => {
  const span = Math.max(0, count - 1) * SWITCH_FAN_OUT_GAP;
  return Array.from({ length: count }, (_, i) => -span / 2 + i * SWITCH_FAN_OUT_GAP);
};

export function computeSwitchFanOut(
  outputCount: number,
  size: FanOutSize,
  shape: FanOutShape = "arc"
): FanOutLayout {
  const { width, height } = size;
  const count = Math.max(0, Math.floor(outputCount));
  const offsets = verticalOffsets(count);
  const halfSpan = offsets.length ? -offsets[0] : 0;
  const cy = height / 2;
  const anchor = { x: width, y: cy };

  if (shape === "bracket") {
    // Straight along the right edge for the card's own height, then a curve of
    // radius `corner` over each corner for the handles that don't fit beside it.
    const straightHalf = height / 2;
    const overflow = Math.max(0, halfSpan - straightHalf);
    const corner = Math.max(MIN_CORNER_RADIUS, overflow / Math.sin(MAX_CURVE_ANGLE_RAD));
    const columnX = width + CLEARANCE;
    const points = offsets.map((dy) => {
      const beyond = Math.abs(dy) - straightHalf;
      const x = beyond <= 0 ? columnX : columnX - (corner - Math.sqrt(corner * corner - beyond * beyond));
      return { x, y: cy + dy };
    });
    const top = Math.min(0, cy - halfSpan - HIT_MARGIN);
    const bottom = Math.max(height, cy + halfSpan + HIT_MARGIN);
    const left = Math.min(width / 2, ...points.map((p) => p.x - HIT_MARGIN));
    return {
      anchor,
      points,
      hitArea: {
        left,
        top,
        width: columnX + HIT_MARGIN - left,
        height: bottom - top,
        borderRadius: `${HIT_MARGIN}px`,
      },
    };
  }

  const cx = width / 2;
  const minRadius = Math.hypot(width / 2, height / 2) + CLEARANCE;
  const radius = Math.max(minRadius, halfSpan / Math.sin(MAX_CURVE_ANGLE_RAD));
  const points = offsets.map((dy) => ({ x: cx + Math.sqrt(radius * radius - dy * dy), y: cy + dy }));
  const hitRadius = radius + HIT_MARGIN;
  return {
    anchor,
    points,
    hitArea: {
      left: cx - hitRadius,
      top: cy - hitRadius,
      width: hitRadius * 2,
      height: hitRadius * 2,
      borderRadius: "50%",
    },
  };
}
