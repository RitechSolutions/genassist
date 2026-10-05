/** Value order for an ordinal mapping: { Low: 0, Medium: 1, High: 2 } -> ["Low", "Medium", "High"]. */
export const orderFromMapping = (mapping?: Record<string, number>): string[] =>
  Object.entries(mapping || {})
    .sort(([, a], [, b]) => a - b)
    .map(([value]) => value);

/** Ordinal mapping for a value order: each value's position is its code. */
export const mappingFromOrder = (order: string[]): Record<string, number> =>
  Object.fromEntries(order.map((value, index) => [value, index]));
