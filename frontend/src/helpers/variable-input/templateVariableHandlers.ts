import * as React from "react"

import {
  deleteSelectionWithVariables,
  findVariableAtPosition,
  removeVariableAtCursor,
  snapCaretOutOfVariable,
  snapToVariableBoundary,
} from "./templateVariableCaret"

export interface VariableHandlersOptions<TEl extends HTMLInputElement | HTMLTextAreaElement> {
  /** Whether variable overlay/logic is active for this value */
  useOverlay: boolean
  /** Current value of the field */
  value: unknown
  /** Called when the value should be updated */
  onChange?: (e: React.ChangeEvent<TEl>) => void
  /** Forwarded user handler */
  onFocus?: React.FocusEventHandler<TEl>
  /** Forwarded user handler */
  onMouseUp?: React.MouseEventHandler<TEl>
  /** Cursor restore after programmatic deletion */
  pendingCursorRef: React.MutableRefObject<number | null>
}

export function createVariableFocusHandler<TEl extends HTMLInputElement | HTMLTextAreaElement>(
  opts: Pick<VariableHandlersOptions<TEl>, "useOverlay" | "value" | "onFocus">
): React.FocusEventHandler<TEl> {
  return (e) => {
    if (opts.useOverlay && typeof opts.value === "string" && opts.value.length > 0) {
      e.target.setSelectionRange(opts.value.length, opts.value.length)
    }
    opts.onFocus?.(e)
  }
}

export function createVariableKeyDownHandler<TEl extends HTMLInputElement | HTMLTextAreaElement>(
  opts: Pick<VariableHandlersOptions<TEl>, "useOverlay" | "value" | "onChange" | "pendingCursorRef">
): React.KeyboardEventHandler<TEl> {
  return (e) => {
    if (!opts.useOverlay || typeof opts.value !== "string") return
    const el = e.currentTarget
    const start = el.selectionStart ?? 0
    const end = el.selectionEnd ?? 0

    if (e.key === "Backspace" || e.key === "Delete") {
      if (start !== end) {
        const { newValue, newCursor } = deleteSelectionWithVariables(opts.value, start, end)
        e.preventDefault()
        opts.pendingCursorRef.current = newCursor
        opts.onChange?.({ target: { value: newValue } } as React.ChangeEvent<TEl>)
        return
      }
      const result =
        e.key === "Backspace"
          ? removeVariableAtCursor(opts.value, start, true)
          : removeVariableAtCursor(opts.value, start, false)
      if (result) {
        e.preventDefault()
        opts.pendingCursorRef.current = result.newCursor
        opts.onChange?.({ target: { value: result.newValue } } as React.ChangeEvent<TEl>)
        return
      }
    }

    if (start === end) {
      const insideVariable = findVariableAtPosition(opts.value, start)
      if (
        insideVariable &&
        e.key.length === 1 &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey
      ) {
        // Allow manual creation of {{...}} by typing braces
        if (e.key === "{" || e.key === "}") return
        e.preventDefault()
        opts.pendingCursorRef.current = insideVariable.end
        el.setSelectionRange(insideVariable.end, insideVariable.end)
      }
    }
  }
}

export function createVariableKeyUpHandler<TEl extends HTMLInputElement | HTMLTextAreaElement>(
  opts: Pick<VariableHandlersOptions<TEl>, "useOverlay" | "value">
): React.KeyboardEventHandler<TEl> {
  return (e) => {
    if (!opts.useOverlay || typeof opts.value !== "string") return
    const el = e.currentTarget
    if (el.selectionStart !== el.selectionEnd) return
    const pos = el.selectionStart ?? 0
    const snapped = snapCaretOutOfVariable(opts.value, pos)
    if (snapped !== pos) {
      el.setSelectionRange(snapped, snapped)
    }
  }
}

export function createVariableMouseUpHandler<TEl extends HTMLInputElement | HTMLTextAreaElement>(
  opts: Pick<VariableHandlersOptions<TEl>, "useOverlay" | "value" | "onMouseUp">
): React.MouseEventHandler<TEl> {
  return (e) => {
    const el = e.currentTarget
    if (!opts.useOverlay || typeof opts.value !== "string") return
    const start = el.selectionStart ?? 0
    const end = el.selectionEnd ?? 0
    if (start === end) {
      const inside = findVariableAtPosition(opts.value, start)
      if (inside) {
        el.setSelectionRange(inside.start, inside.end)
      } else {
        const snapped = snapCaretOutOfVariable(opts.value, start)
        if (snapped !== start) el.setSelectionRange(snapped, snapped)
      }
    } else {
      const snappedStart = snapToVariableBoundary(opts.value, start, false)
      const snappedEnd = snapToVariableBoundary(opts.value, end, true)
      if (snappedStart !== start || snappedEnd !== end) {
        el.setSelectionRange(snappedStart, snappedEnd)
      }
    }
    opts.onMouseUp?.(e)
  }
}

