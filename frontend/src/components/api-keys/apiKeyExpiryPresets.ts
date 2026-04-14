/** Value sent to API: omit property when "never". */
export const API_KEY_EXPIRY_PRESET_VALUES = [
  { value: "never", label: "Never" },
  { value: "30", label: "30d" },
  { value: "90", label: "90d" },
  { value: "180", label: "180d" },
  { value: "365", label: "1y" },
] as const;

export function presetToExpiresInDays(
  preset: string
): number | undefined {
  if (preset === "never" || !preset) return undefined;
  const n = Number.parseInt(preset, 10);
  return Number.isFinite(n) ? n : undefined;
}
