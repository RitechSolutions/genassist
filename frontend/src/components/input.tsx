import * as React from "react"

import { cn } from "@/helpers/utils"

const highlightPattern = (text: string) => {
  if (!text) return text;
  const parts = text.split(/(\{\{[^}]+\}\})/g);
  return parts.map(part => {
    if (part.match(/\{\{[^}]+\}\}/)) {
      return `<span class="text-blue-500 bg-background ">${part}</span>`;
    }
    return `<span class="text-transparent">${part}</span>`;
  }).join('');
}

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, value, ...props }, ref) => {
    const [displayValue, setDisplayValue] = React.useState(value);

    React.useEffect(() => {
      if (typeof value === 'string') {
        setDisplayValue(highlightPattern(value));
      }
    }, [value]);

    return (
      <div className="relative w-full">
        <input
          type={type}
          className={cn(
            "flex h-10 w-full rounded-full border border-input bg-transparent px-3 py-2 text-base ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm pointer-events-auto relative z-10",
            className
          )}
          ref={ref}
          value={value}
          {...props}
        />
        {typeof value === 'string' && (
          <div 
            className={cn("flex items-center absolute inset-0 pointer-events-none px-3 py-2 text-base md:text-sm select-none whitespace-pre z-0", className)}
            dangerouslySetInnerHTML={{ __html: displayValue }}
          />
        )}
      </div>
    )
  }
)
Input.displayName = "Input"

export { Input }
