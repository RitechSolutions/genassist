/**
 * Single source of truth for template variable syntax {{variable_name}}.
 * Used by parsing, highlighting, caret, and selection logic.
 *
 * The body excludes braces and newlines so a half-typed "{{" cannot reach
 * forward and swallow the closing braces of the next variable in the field —
 * that produced a bogus range spanning the text between them, which then
 * highlighted as one variable and yanked the caret past it.
 */

export const TEMPLATE_VARIABLE_REGEX = /\{\{[^{}\n]+\}\}/g

// Same pattern without the global flag, which carries lastIndex between tests
const TEMPLATE_VARIABLE_TEST = new RegExp(TEMPLATE_VARIABLE_REGEX.source)

export function hasVariableSyntax(val: unknown): val is string {
  return typeof val === "string" && TEMPLATE_VARIABLE_TEST.test(val)
}
