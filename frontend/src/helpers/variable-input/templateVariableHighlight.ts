/**
 * Parses a string value into plain and variable segments for highlighting.
 * No HTML or escaping — output is used to render React elements.
 */

import { TEMPLATE_VARIABLE_REGEX } from "./templateVariableConstants"

export type HighlightSegment =
  | { type: "text"; content: string }
  | { type: "variable"; content: string }

const VARIABLE_PATTERN = new RegExp(TEMPLATE_VARIABLE_REGEX.source)

export function parseValueToSegments(value: string): HighlightSegment[] {
  if (!value) return []
  const parts = value.split(new RegExp(`(${TEMPLATE_VARIABLE_REGEX.source})`, "g"))
  const segments: HighlightSegment[] = []
  for (const part of parts) {
    if (!part) continue
    segments.push({
      type: VARIABLE_PATTERN.test(part) ? "variable" : "text",
      content: part,
    })
  }
  return segments
}
