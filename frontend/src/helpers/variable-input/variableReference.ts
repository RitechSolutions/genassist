/**
 * Building and inserting "{{path}}" references, shared by the variable tree,
 * the typeahead and the Ace completer.
 */

/** Format a workflow variable path for insertion into scripts/templates. */
export function formatVariableReference(path: string): string {
  const trimmed = path.trim();
  if (trimmed.startsWith("{{") && trimmed.endsWith("}}")) {
    return trimmed;
  }
  return `{{${trimmed}}}`;
}

/** Build an indexed array item path such as ``source.prediction[0]``. */
export function buildArrayItemPath(arrayPath: string, index: number): string {
  return `${arrayPath}[${index}]`;
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    !(value instanceof Date)
  );
}

/** True when a separating space is wanted between `char` and a reference. */
function needsSpace(char: string | undefined): boolean {
  return char !== undefined && !/[\s,;:]/.test(char);
}

/**
 * Insert a `{{path}}` reference at `position`, padding with spaces so it does
 * not fuse with surrounding words. Returns the caret offset after the insert.
 */
export function insertReferenceAt(
  value: string,
  reference: string,
  position: number
): { value: string; cursor: number } {
  if (!value) return { value: reference, cursor: reference.length };

  const at = Math.max(0, Math.min(position, value.length));
  const before = value.slice(0, at);
  const after = value.slice(at);

  const leading = at > 0 && needsSpace(value[at - 1]) ? " " : "";
  const trailing = at < value.length && needsSpace(value[at]) ? " " : "";

  return {
    value: before + leading + reference + trailing + after,
    cursor: at + leading.length + reference.length,
  };
}
