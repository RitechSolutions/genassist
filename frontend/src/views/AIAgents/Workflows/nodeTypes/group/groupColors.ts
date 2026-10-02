/**
 * Colour palette for visual node groups. A group stores only the palette key (`data.color`), so
 * the actual shades can change without touching saved workflows; an unknown or missing key falls
 * back to the neutral "default" look.
 *
 * Shades are Tailwind's 500 level as RGB triplets, applied at low alpha for the fill and higher
 * alpha for the border — translucent, so the same values read well on the light and dark canvas.
 */
export interface GroupColor {
  key: string;
  label: string;
  /** "r g b" (space-separated) for use in rgb(... / alpha). Null = neutral theme colours. */
  rgb: string | null;
}

export const DEFAULT_GROUP_COLOR = "default";

export const GROUP_COLORS: GroupColor[] = [
  { key: DEFAULT_GROUP_COLOR, label: "Default", rgb: null },
  { key: "blue", label: "Blue", rgb: "59 130 246" },
  { key: "teal", label: "Teal", rgb: "20 184 166" },
  { key: "green", label: "Green", rgb: "34 197 94" },
  { key: "amber", label: "Amber", rgb: "245 158 11" },
  { key: "orange", label: "Orange", rgb: "249 115 22" },
  { key: "red", label: "Red", rgb: "239 68 68" },
  { key: "pink", label: "Pink", rgb: "236 72 153" },
  { key: "purple", label: "Purple", rgb: "168 85 247" },
];

export const getGroupColor = (key?: string | null): GroupColor =>
  GROUP_COLORS.find((c) => c.key === key) ?? GROUP_COLORS[0];

/** Minimap fill for a group (the SVG fill attribute can't resolve CSS variables). */
export const getGroupMiniMapColor = (key?: string | null): string => {
  const { rgb } = getGroupColor(key);
  return rgb ? `rgb(${rgb} / 0.25)` : "rgb(148 163 184 / 0.2)";
};
