/**
 * Variable range detection and range merging for template variable syntax.
 */

import { TEMPLATE_VARIABLE_REGEX } from "./templateVariableConstants"

export interface VariableRange {
  start: number
  end: number
}

export function getVariableRanges(value: string): VariableRange[] {
  const ranges: VariableRange[] = []
  let match: RegExpExecArray | null
  const re = new RegExp(TEMPLATE_VARIABLE_REGEX.source, "g")
  while ((match = re.exec(value)) !== null) {
    ranges.push({ start: match.index, end: match.index + match[0].length })
  }
  return ranges
}

export function mergeRanges(ranges: VariableRange[]): VariableRange[] {
  if (ranges.length === 0) return []
  const sorted = [...ranges].sort((a, b) => a.start - b.start)
  const merged: VariableRange[] = [{ ...sorted[0] }]
  for (let i = 1; i < sorted.length; i++) {
    const last = merged[merged.length - 1]
    if (sorted[i].start <= last.end) {
      last.end = Math.max(last.end, sorted[i].end)
    } else {
      merged.push({ ...sorted[i] })
    }
  }
  return merged
}
