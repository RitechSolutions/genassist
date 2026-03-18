/**
 * Renders parsed template variable segments as React elements.
 * Used by Input/Textarea overlay — no HTML string injection.
 */

import type { HighlightSegment } from "./templateVariableHighlight"

const VARIABLE_TAG_CLASS =
  "variable-tag inline text-blue-700 bg-blue-100 dark:bg-blue-950/60 dark:text-blue-300 rounded text-inherit"
const TEXT_CLASS = "text-foreground"

function SegmentSpan({ segment }: { segment: HighlightSegment }) {
  if (segment.type === "variable") {
    return <span className={VARIABLE_TAG_CLASS}>{segment.content}</span>
  }
  return <span className={TEXT_CLASS}>{segment.content}</span>
}

export interface VariableOverlayContentProps {
  segments: HighlightSegment[]
  className?: string
}

export function VariableOverlayContent({ segments, className }: VariableOverlayContentProps) {
  return (
    <span className={className}>
      {segments.map((seg, i) => (
        <SegmentSpan key={i} segment={seg} />
      ))}
    </span>
  )
}
