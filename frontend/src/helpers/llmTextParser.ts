/** Safely attempt to parse a JSON string, returning null on failure. */
export const tryParseJson = (text: string): unknown | null => {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

/** Extract the content of all ```json ... ``` (or bare ```) code-fence blocks. */
export const findCodeFenceBlocks = (text: string): string[] => {
  const blocks: string[] = [];
  const re = /```(?:json)?\s*([\s\S]*?)\s*```/gi;
  let match: RegExpExecArray | null = null;
  while ((match = re.exec(text))) {
    if (match[1]) blocks.push(match[1].trim());
  }
  return blocks;
};

/**
 * Starting at `startIndex` (which must be `{` or `[`), walk the string
 * respecting nesting and JSON string escaping, and return the balanced
 * substring — or `null` if the braces/brackets never balance.
 */
export const findBalancedJsonCandidate = (text: string, startIndex: number): string | null => {
  let braceDepth = 0;
  let bracketDepth = 0;
  let inString = false;
  let isEscaping = false;

  for (let i = startIndex; i < text.length; i += 1) {
    const ch = text[i];

    if (inString) {
      if (isEscaping) {
        isEscaping = false;
        continue;
      }
      if (ch === "\\") {
        isEscaping = true;
        continue;
      }
      if (ch === "\"") {
        inString = false;
      }
      continue;
    }

    if (ch === "\"") {
      inString = true;
      continue;
    }

    if (ch === "{") {
      braceDepth += 1;
      continue;
    }

    if (ch === "}") {
      braceDepth -= 1;
      if (braceDepth < 0) return null;
      if (braceDepth === 0 && bracketDepth === 0) {
        return text.slice(startIndex, i + 1);
      }
      continue;
    }

    if (ch === "[") {
      bracketDepth += 1;
      continue;
    }

    if (ch === "]") {
      bracketDepth -= 1;
      if (bracketDepth < 0) return null;
      if (braceDepth === 0 && bracketDepth === 0) {
        return text.slice(startIndex, i + 1);
      }
    }
  }

  return null;
};

/** Check whether a value is a non-null, non-array plain object. */
export const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);
