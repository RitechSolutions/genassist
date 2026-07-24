/**
 * Format a USD amount as "$1.2345". Null/undefined/non-finite values render as "$0.0000".
 */
export function formatUsd(value: number | null | undefined, fractionDigits = 4): string {
  const n = typeof value === "number" && Number.isFinite(value) ? value : 0;
  return `$${n.toFixed(fractionDigits)}`;
}
