/**
 * Single source of truth for template variable syntax {{variable_name}}.
 * Used by parsing, highlighting, caret, and selection logic.
 */

export const TEMPLATE_VARIABLE_REGEX = /\{\{[^}]+\}\}/g

export function hasVariableSyntax(val: unknown): val is string {
  return typeof val === "string" && /\{\{[^}]+\}\}/.test(val)
}
