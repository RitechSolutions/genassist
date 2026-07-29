const EM_DASH = "—";

/**
 * Format a USD amount as "$1.2345". Missing or non-finite values render as an em dash
 * so "no data" never reads as a real $0.0000.
 */
export function formatUsd(value: number | null | undefined, fractionDigits = 4): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return EM_DASH;
  return `$${value.toFixed(fractionDigits)}`;
}
