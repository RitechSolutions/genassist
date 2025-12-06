import * as React from "react"
import { Input } from "@/components/input"
import { cn } from "@/helpers/utils"
import { NodeSchema } from "../../types/schemas"

interface DynamicInputProps extends React.ComponentProps<typeof Input> {
  availableParams?: string[]
  inputSchema?: NodeSchema
}

const DynamicInput = React.forwardRef<HTMLInputElement, DynamicInputProps>(
  ({ className, value, availableParams = [], inputSchema, onChange, ...props }, ref) => {
    const [showSuggestions, setShowSuggestions] = React.useState(false)
    const [suggestions, setSuggestions] = React.useState<string[]>([])
    const [cursorPosition, setCursorPosition] = React.useState(0)

    // Get available parameters from inputSchema
    const getAvailableParams = React.useCallback(() => {
      if (inputSchema) {
        return Object.keys(inputSchema)
      }
      return availableParams
    }, [inputSchema, availableParams])

    // Handle input changes and suggestion logic
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value
      setCursorPosition(e.target.selectionStart || 0)

      // Check if we should show suggestions
      const textBeforeCursor = newValue.slice(0, e.target.selectionStart || 0)
      const match = textBeforeCursor.match(/@(\w*)$/)
      
      if (match) {
        const searchTerm = match[1].toLowerCase()
        const filtered = getAvailableParams().filter(param => 
          param.toLowerCase().includes(searchTerm)
        )
        setSuggestions(filtered)
        setShowSuggestions(true)
      } else {
        setShowSuggestions(false)
      }

      // Call the original onChange if provided
      onChange?.(e)
    }

    // Handle suggestion selection
    const handleSuggestionClick = (param: string) => {
      const currentValue = value as string || ""
      const textBeforeCursor = currentValue.slice(0, cursorPosition)
      const textAfterCursor = currentValue.slice(cursorPosition)
      const lastAtIndex = textBeforeCursor.lastIndexOf('@')
      
      const newValue = 
        textBeforeCursor.slice(0, lastAtIndex) + 
        `{{${param}}}` + 
        textAfterCursor

      // Create a synthetic event to trigger onChange
      const syntheticEvent = {
        target: { value: newValue },
      } as React.ChangeEvent<HTMLInputElement>

      onChange?.(syntheticEvent)
      setShowSuggestions(false)
    }

    return (
      <div className="relative w-full min-w-0">
        <Input
          ref={ref}
          className={cn("w-full", className)}
          value={value}
          onChange={handleInputChange}
          {...props}
        />
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg">
            {suggestions.map((param, index) => (
              <div
                key={index}
                className="px-3 py-2 hover:bg-gray-100 cursor-pointer break-words"
                onClick={() => handleSuggestionClick(param)}
              >
                {param}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)

DynamicInput.displayName = "DynamicInput"

export { DynamicInput }
