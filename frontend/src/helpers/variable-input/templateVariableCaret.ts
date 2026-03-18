/**
 * Caret and selection behavior for template variables:
 * snapping outside variables, removing whole variables on backspace/delete,
 * and adjusting selection boundaries.
 */

import { getVariableRanges, mergeRanges, type VariableRange } from "./templateVariableRanges"

export function snapCaretOutOfVariable(value: string, pos: number): number {
  const ranges = getVariableRanges(value)
  const r = ranges.find((r) => pos > r.start && pos < r.end)
  return r ? r.end : pos
}

export function snapToVariableBoundary(value: string, pos: number, toEnd: boolean): number {
  const ranges = getVariableRanges(value)
  const r = ranges.find((r) => pos > r.start && pos < r.end)
  if (!r) return pos
  return toEnd ? r.end : r.start
}

export function removeVariableAtCursor(
  value: string,
  cursor: number,
  isBackspace: boolean
): { newValue: string; newCursor: number } | null {
  const ranges = getVariableRanges(value)
  if (isBackspace) {
    if (cursor <= 0) return null
    const prev = cursor - 1
    const r = ranges.find((r) => prev >= r.start && prev < r.end)
    if (!r) return null
    return {
      newValue: value.slice(0, r.start) + value.slice(r.end),
      newCursor: r.start,
    }
  } else {
    if (cursor >= value.length) return null
    const r = ranges.find((r) => cursor >= r.start && cursor < r.end)
    if (!r) return null
    return {
      newValue: value.slice(0, r.start) + value.slice(r.end),
      newCursor: r.start,
    }
  }
}

export function deleteSelectionWithVariables(
  value: string,
  selStart: number,
  selEnd: number
): { newValue: string; newCursor: number } {
  const ranges = getVariableRanges(value)
  const overlapping = ranges.filter((r) => r.start < selEnd && r.end > selStart)
  const toRemove = mergeRanges([{ start: selStart, end: selEnd }, ...overlapping])
  let newValue = ""
  let lastEnd = 0
  for (const r of toRemove) {
    newValue += value.slice(lastEnd, r.start)
    lastEnd = r.end
  }
  newValue += value.slice(lastEnd)
  const newCursor = toRemove[0]?.start ?? selStart
  return { newValue, newCursor }
}

export function findVariableAtPosition(
  value: string,
  pos: number
): VariableRange | undefined {
  return getVariableRanges(value).find((r) => pos > r.start && pos < r.end)
}
