import React, { useState, useRef } from "react";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";

interface DraggableInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  id?: string;
  label?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  className?: string;
  onVariableDrop?: (path: string, value: unknown) => void;
}

/**
 * Input component that can receive dropped values from the JSON viewer
 * Supports both manual input and drag-and-drop from available variables
 *
 * Styling:
 * - Inherits all Input component styles
 * - Supports custom className for additional styling
 * - Full width by default (w-full)
 * - Proper drag and drop visual feedback
 * - Syntax highlighting for variables in the preview section
 * - Supports dropping variables at cursor position
 */
export const DraggableInput: React.FC<DraggableInputProps> = ({
  id,
  label,
  value,
  onChange,
  placeholder,
  className,
  onVariableDrop,
  ...props
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursorPosition, setCursorPosition] = useState(0);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    try {
      // Try to get JSON data first
      const jsonData = e.dataTransfer.getData("application/json");

      if (jsonData) {
        const { path, value: droppedValue } = JSON.parse(jsonData);

        // Format the raw path as {{path}} for workflow variables
        const variableReference = path;
        const newValue = insertAtPosition(
          value,
          variableReference,
          cursorPosition
        );
        
        // Create a synthetic event for the onChange callback
        const syntheticEvent = {
          target: { value: newValue }
        } as React.ChangeEvent<HTMLInputElement>;
        onChange(syntheticEvent);

        // Call the callback if provided
        if (onVariableDrop) {
          onVariableDrop(path, droppedValue);
        }
        return;
      }

      // Fallback to plain text
      const textData = e.dataTransfer.getData("text/plain");

      if (textData) {
        // Format the raw path as {{path}} for workflow variables
        const variableReference = textData;
        const newValue = insertAtPosition(
          value,
          variableReference,
          cursorPosition
        );
        
        // Create a synthetic event for the onChange callback
        const syntheticEvent = {
          target: { value: newValue }
        } as React.ChangeEvent<HTMLInputElement>;
        onChange(syntheticEvent);
      }
    } catch (error) {
      // ignore
    }
  };

  // Helper function to insert value at specific position
  const insertAtPosition = (
    currentValue: string,
    newValue: string,
    position: number
  ): string => {
    if (!currentValue) return newValue;

    // Ensure position is within bounds
    const safePosition = Math.max(0, Math.min(position, currentValue.length));

    // Insert at the specified position
    const before = currentValue.slice(0, safePosition);
    const after = currentValue.slice(safePosition);

    // Add appropriate spacing if needed
    const needsLeadingSpace =
      safePosition > 0 &&
      !currentValue[safePosition - 1].match(/\s/) &&
      !currentValue[safePosition - 1].match(/[,;:]/);

    const needsTrailingSpace =
      safePosition < currentValue.length &&
      !currentValue[safePosition].match(/\s/) &&
      !currentValue[safePosition].match(/[,;:]/);

    const leadingSpace = needsLeadingSpace ? " " : "";
    const trailingSpace = needsTrailingSpace ? " " : "";

    return before + leadingSpace + newValue + trailingSpace + after;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e);
  };

  // Track cursor position on input events
  const handleInputSelect = () => {
    if (inputRef.current) {
      setCursorPosition(inputRef.current.selectionStart || 0);
    }
  };

  const handleInputClick = () => {
    if (inputRef.current) {
      setCursorPosition(inputRef.current.selectionStart || 0);
    }
  };

  const handleInputKeyUp = () => {
    if (inputRef.current) {
      setCursorPosition(inputRef.current.selectionStart || 0);
    }
  };

  return (
    <div className="space-y-2 w-full">
      {label && <Label htmlFor={id}>{label}</Label>}
      <div
        className={cn(
          "relative w-full",
          isDragOver && "ring-2 ring-blue-500 ring-opacity-50"
        )}
      >
        <Input
          ref={inputRef}
          id={id}
          value={value}
          onChange={handleInputChange}
          onSelect={handleInputSelect}
          onClick={handleInputClick}
          onKeyUp={handleInputKeyUp}
          placeholder={placeholder}
          className={cn(
            "w-full transition-colors",
            isDragOver && "border-blue-500 bg-blue-50",
            className
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          {...props}
        />
        {isDragOver && (
          <div className="absolute inset-0 flex items-center justify-center bg-blue-100 bg-opacity-50 rounded-md pointer-events-none z-10">
            <span className="text-blue-600 font-medium text-sm bg-white px-3 py-1 rounded-full shadow-sm">
              Drop variable at cursor position
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
