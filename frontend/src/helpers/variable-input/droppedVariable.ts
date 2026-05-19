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

export function isPrimitiveJsonValue(value: unknown): boolean {
  return (
    value === null ||
    typeof value !== "object" ||
    value instanceof Date
  );
}

export interface DroppedVariable {
  /** Raw path without template braces, e.g. ``source.prediction[0].result`` */
  path: string;
  /** Path wrapped for template insertion, e.g. ``{{source.prediction[0].result}}`` */
  reference: string;
  value: unknown;
}

export function parseDroppedVariable(
  dataTransfer: DataTransfer
): DroppedVariable | null {
  const jsonData = dataTransfer.getData("application/json");
  if (jsonData) {
    const { path, value } = JSON.parse(jsonData) as {
      path: string;
      value: unknown;
    };
    return {
      path,
      reference: formatVariableReference(path),
      value,
    };
  }

  const textData = dataTransfer.getData("text/plain");
  if (textData) {
    const reference = formatVariableReference(textData);
    const path = reference.slice(2, -2);
    return { path, reference, value: undefined };
  }

  return null;
}
