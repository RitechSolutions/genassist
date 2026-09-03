import * as React from "react"

import { cn } from "@/helpers/utils"
import {
  resolveTextareaSizing,
  type TextareaSizingProps,
} from "@/components/ui/textarea-sizing"
import {
  hasVariableSyntax,
  parseValueToSegments,
  VariableOverlayContent,
  createVariableFocusHandler,
  createVariableKeyDownHandler,
  createVariableKeyUpHandler,
  createVariableMouseUpHandler,
} from "../helpers/variable-input"

export type TextareaProps = Omit<
  React.TextareaHTMLAttributes<HTMLTextAreaElement>,
  "size"
> &
  TextareaSizingProps

// Layered over the shared chrome so the highlight overlay sits behind the caret.
const TEXTAREA_STACK_CLASS = "pointer-events-auto relative z-10"

// No leading-* here: tailwind-merge drops a leading utility when a font-size
// class follows it, and the overlay resolves its size after this string. Both
// elements must land on the same line-height or the caret drifts from the text.
const TEXTAREA_TYPO_CLASS = "text-sm whitespace-pre-wrap break-words"
const OVERLAY_BASE_CLASS =
  "block absolute inset-0 pointer-events-none px-3 py-2 select-none z-0 overflow-hidden text-foreground"

const RichTextarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className,
      size,
      rows,
      value,
      onFocus,
      onChange,
      onMouseUp,
      onKeyDown,
      ...props
    },
    ref
  ) => {
    const sizing = resolveTextareaSizing({ size, rows, className })
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

    // The caller's handler runs first; the variable-aware one still runs unless
    // the caller handled the key itself (e.g. Enter-to-send).
    const handleKeyDown = React.useMemo(() => {
      const handleVariableKeyDown =
        createVariableKeyDownHandler<HTMLTextAreaElement>({
          useOverlay,
          value,
          onChange,
          pendingCursorRef,
        })

      return (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
        onKeyDown?.(event)
        if (event.defaultPrevented) return
        handleVariableKeyDown(event)
      }
    }, [useOverlay, value, onChange, onKeyDown])

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
          rows={sizing.rows}
          spellCheck={sizing.spellCheck}
          className={cn(
            TEXTAREA_STACK_CLASS,
            sizing.className,
            useOverlay && "text-transparent caret-foreground"
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
            className={cn(
              OVERLAY_BASE_CLASS,
              TEXTAREA_TYPO_CLASS,
              sizing.contentClassName
            )}
            aria-hidden
          >
            <VariableOverlayContent segments={segments} />
          </div>
        )}
      </div>
    )
  }
)
RichTextarea.displayName = "RichTextarea"

export { RichTextarea }
