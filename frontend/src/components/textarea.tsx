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

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const TEXTAREA_BASE_CLASS =
  "flex min-h-[80px] w-full rounded-3xl border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 pointer-events-auto relative z-10"

const TEXTAREA_TYPO_CLASS = "text-sm leading-normal whitespace-pre-wrap break-words"
const OVERLAY_BASE_CLASS =
  "block absolute inset-0 pointer-events-none px-3 py-2 select-none z-0 overflow-hidden text-foreground"

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, value, onFocus, onChange, onMouseUp, ...props }, ref) => {
    const textareaRef = React.useRef<HTMLTextAreaElement | null>(null)
    const overlayRef = React.useRef<HTMLDivElement | null>(null)
    const pendingCursorRef = React.useRef<number | null>(null)
    const useOverlay = hasVariableSyntax(value)

    const segments = React.useMemo(
      () => (typeof value === "string" ? parseValueToSegments(value) : []),
      [value]
    )

    React.useEffect(() => {
      if (!ref) return
      if (typeof ref === "function") {
        ref(textareaRef.current)
      } else {
        ;(ref as React.MutableRefObject<HTMLTextAreaElement | null>).current =
          textareaRef.current
      }
    }, [ref])

    React.useEffect(() => {
      const el = textareaRef.current
      if (!el || document.activeElement !== el) return
      if (pendingCursorRef.current !== null) {
        const pos = Math.min(pendingCursorRef.current, (value as string)?.length ?? 0)
        el.setSelectionRange(pos, pos)
        pendingCursorRef.current = null
      }
    }, [value])

    const handleFocus = React.useMemo(
      () =>
        createVariableFocusHandler<HTMLTextAreaElement>({
          useOverlay,
          value,
          onFocus,
        }),
      [useOverlay, value, onFocus]
    )

    const syncScroll = () => {
      if (!textareaRef.current || !overlayRef.current) return
      overlayRef.current.scrollTop = textareaRef.current.scrollTop
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft
    }

    const handleScroll: React.UIEventHandler<HTMLTextAreaElement> = () => {
      syncScroll()
    }

    const handleKeyDown = React.useMemo(
      () =>
        createVariableKeyDownHandler<HTMLTextAreaElement>({
          useOverlay,
          value,
          onChange,
          pendingCursorRef,
        }),
      [useOverlay, value, onChange]
    )

    const handleKeyUp = React.useMemo(
      () =>
        createVariableKeyUpHandler<HTMLTextAreaElement>({
          useOverlay,
          value,
        }),
      [useOverlay, value]
    )

    const handleMouseUp = React.useMemo(
      () =>
        createVariableMouseUpHandler<HTMLTextAreaElement>({
          useOverlay,
          value,
          onMouseUp,
        }),
      [useOverlay, value, onMouseUp]
    )

    React.useLayoutEffect(() => {
      syncScroll()
    })

    return (
      <div className="relative w-full">
        <textarea
          className={cn(
            TEXTAREA_BASE_CLASS,
            useOverlay && "text-transparent caret-foreground leading-normal",
            className
          )}
          ref={textareaRef}
          value={value}
          onFocus={handleFocus}
          onScroll={handleScroll}
          onKeyDown={handleKeyDown}
          onKeyUp={handleKeyUp}
          onMouseUp={handleMouseUp}
          onChange={onChange}
          {...props}
        />
        {useOverlay && segments.length > 0 && (
          <div
            ref={overlayRef}
            className={cn(OVERLAY_BASE_CLASS, TEXTAREA_TYPO_CLASS, className)}
            aria-hidden
          >
            <VariableOverlayContent segments={segments} />
          </div>
        )}
      </div>
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
