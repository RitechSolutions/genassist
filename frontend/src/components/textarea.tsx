import * as React from "react"

import { cn } from "@/helpers/utils"

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const highlightPattern = (text: string) => {
  if (!text) return text
  const parts = text.split(/(\{\{[^}]+\}\})/g)
  return parts
    .map((part) => {
      if (part.match(/\{\{[^}]+\}\}/)) {
        return `<span class="text-blue-500 bg-background ">${part}</span>`
      }
      return `<span class="text-transparent">${part}</span>`
    })
    .join("")
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, value, ...props }, ref) => {
    const [displayValue, setDisplayValue] = React.useState(value)
    const textareaRef = React.useRef<HTMLTextAreaElement | null>(null)
    const overlayRef = React.useRef<HTMLDivElement | null>(null)

    // Expose internal ref to parent ref
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
      if (typeof value === "string") {
        setDisplayValue(highlightPattern(value))
      }
    }, [value])

    const syncScroll = () => {
      if (!textareaRef.current || !overlayRef.current) return
      overlayRef.current.scrollTop = textareaRef.current.scrollTop
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft
    }

    const handleScroll: React.UIEventHandler<HTMLTextAreaElement> = () => {
      syncScroll()
    }

    // Keep overlay scroll in sync after mount and when value changes
    React.useLayoutEffect(() => {
      syncScroll()
    })

    return (
      <div className="relative w-full">
        <textarea
          className={cn(
            "flex min-h-[80px] w-full rounded-3xl border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 pointer-events-auto relative z-10",
            className
          )}
          ref={textareaRef}
          value={value}
          onScroll={handleScroll}
          {...props}
        />
        {typeof value === "string" && (
          <div
            ref={overlayRef}
            className={cn(
              "absolute inset-0 pointer-events-none px-3 py-2 text-sm select-none whitespace-pre-wrap break-words z-0 overflow-hidden",
              className
            )}
            dangerouslySetInnerHTML={{ __html: displayValue as string }}
          />
        )}
      </div>
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
