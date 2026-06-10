import * as React from "react"

import { cn } from "@/helpers/utils"
import {
  hasVariableSyntax,
  parseValueToSegments,
  VariableOverlayContent,
  createVariableFocusHandler,
  createVariableKeyDownHandler,
  createVariableKeyUpHandler,
  createVariableMouseUpHandler,
} from "../helpers/variable-input"

const INPUT_BASE_CLASS =
  "flex h-10 w-full rounded-full border border-input bg-transparent px-3 py-2 text-base ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm pointer-events-auto relative z-10"

const INPUT_TYPO_CLASS = "text-base md:text-sm leading-normal whitespace-pre"
const OVERLAY_BASE_CLASS =
  "block absolute inset-0 pointer-events-none px-3 py-2 select-none z-0 text-foreground"

const RichInput = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, value, onFocus, onChange, onMouseUp, ...props }, ref) => {
    const inputRef = React.useRef<HTMLInputElement | null>(null)
    const pendingCursorRef = React.useRef<number | null>(null)
    const useOverlay = hasVariableSyntax(value)

    const segments = React.useMemo(
      () => (typeof value === "string" ? parseValueToSegments(value) : []),
      [value]
    )

    const setRef = React.useCallback(
      (el: HTMLInputElement | null) => {
        inputRef.current = el
        if (typeof ref === "function") {
          ref(el)
        } else if (ref) {
          ;(ref as React.MutableRefObject<HTMLInputElement | null>).current = el
        }
      },
      [ref]
    )

    React.useEffect(() => {
      const el = inputRef.current
      if (!el || document.activeElement !== el) return
      if (pendingCursorRef.current !== null) {
        const pos = Math.min(pendingCursorRef.current, (value as string)?.length ?? 0)
        el.setSelectionRange(pos, pos)
        pendingCursorRef.current = null
      }
    }, [value])

    const handleFocus = React.useMemo(
      () =>
        createVariableFocusHandler<HTMLInputElement>({
          useOverlay,
          value,
          onFocus,
        }),
      [useOverlay, value, onFocus]
    )

    const handleKeyDown = React.useMemo(
      () =>
        createVariableKeyDownHandler<HTMLInputElement>({
          useOverlay,
          value,
          onChange,
          pendingCursorRef,
        }),
      [useOverlay, value, onChange]
    )

    const handleKeyUp = React.useMemo(
      () =>
        createVariableKeyUpHandler<HTMLInputElement>({
          useOverlay,
          value,
        }),
      [useOverlay, value]
    )

    const handleMouseUp = React.useMemo(
      () =>
        createVariableMouseUpHandler<HTMLInputElement>({
          useOverlay,
          value,
          onMouseUp,
        }),
      [useOverlay, value, onMouseUp]
    )

    return (
      <div className="relative w-full">
        <input
          type={type}
          className={cn(
            INPUT_BASE_CLASS,
            useOverlay && "text-transparent caret-foreground leading-normal",
            className
          )}
          ref={setRef}
          value={value ?? ""}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          onKeyUp={handleKeyUp}
          onMouseUp={handleMouseUp}
          onChange={onChange}
          {...props}
        />
        {useOverlay && segments.length > 0 && (
          <div
            className={cn(OVERLAY_BASE_CLASS, INPUT_TYPO_CLASS)}
            aria-hidden
          >
            <VariableOverlayContent segments={segments} />
          </div>
        )}
      </div>
    )
  }
)
RichInput.displayName = "RichInput"

export { RichInput }
