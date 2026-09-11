/**
 * Detects the "{{" typeahead trigger that opens the variable picker, and
 * replaces it once a variable is chosen. Shared by inputs, textareas and Ace.
 */

export interface VariableTrigger {
  /** Index of the opening "{{" */
  start: number
  /** Text typed between "{{" and the caret */
  query: string
}

/** Find an unclosed "{{" preceding the caret, or null when there is none. */
export function detectVariableTrigger(
  value: string,
  caret: number
): VariableTrigger | null {
  if (typeof value !== "string") return null

  const pos = Math.max(0, Math.min(caret, value.length))
  const start = value.lastIndexOf("{{", pos - 1)
  if (start === -1 || start + 2 > pos) return null

  const query = value.slice(start + 2, pos)
  // Any further brace or a line break means the trigger is no longer open
  if (/[{}\n]/.test(query)) return null

  return { start, query }
}

/** Swap the "{{query" span at the caret for a complete "{{path}}" reference. */
export function replaceTriggerWithReference(
  value: string,
  trigger: VariableTrigger,
  reference: string,
  caret: number
): { value: string; cursor: number } {
  const pos = Math.max(0, Math.min(caret, value.length))
  // Absorb a "}}" the user already typed ahead of the caret
  const trailing = value.slice(pos).startsWith("}}") ? 2 : 0

  return {
    value: value.slice(0, trigger.start) + reference + value.slice(pos + trailing),
    cursor: trigger.start + reference.length,
  }
}
