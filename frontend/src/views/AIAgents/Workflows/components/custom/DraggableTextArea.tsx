import React, { useState, useRef } from "react";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";
import { RichTextarea } from "@/components/richTextarea";

interface DraggableTextAreaProps {
  id?: string;
  label?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  className?: string;
  rows?: number;
  onVariableDrop?: (path: string, value: unknown) => void;
}

/**
 * Textarea component that can receive dropped values from the JSON viewer
 * Supports both manual input and drag-and-drop from available variables
 * Variables can be dropped at cursor position or replace selected text
 * Shows real-time drag cursor for precise positioning
 *
 * Styling:
 * - Inherits all Textarea component styles
 * - Supports custom className for additional styling
 * - Full width by default (w-full)
 * - Proper drag and drop visual feedback
 * - Syntax highlighting for variables in the preview section
 */
export const DraggableTextArea: React.FC<DraggableTextAreaProps> = ({
  id,
  label,
  value,
  onChange,
  placeholder,
  className,
  rows = 4,
  onVariableDrop,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

    const el = textareaRef.current;
    const insertPos =
      el && document.activeElement === el
        ? el.selectionStart ?? value.length
        : value.length;

    try {
      const jsonData = e.dataTransfer.getData("application/json");

      if (jsonData) {
        const { path, value: droppedValue } = JSON.parse(jsonData);
        const variableReference = path;
        const newValue = insertAtPosition(value, variableReference, insertPos);
        const cursorAfter = insertPos + variableReference.length;

        const syntheticEvent = {
          target: { value: newValue }
        } as React.ChangeEvent<HTMLTextAreaElement>;
        onChange(syntheticEvent);

        setTimeout(() => {
          if (textareaRef.current && document.activeElement === textareaRef.current) {
            textareaRef.current.setSelectionRange(cursorAfter, cursorAfter);
          }
        }, 0);

        if (onVariableDrop) {
          onVariableDrop(path, droppedValue);
        }
        return;
      }

      const textData = e.dataTransfer.getData("text/plain");

      if (textData) {
        const variableReference = textData;
        const newValue = insertAtPosition(value, variableReference, insertPos);
        const cursorAfter = insertPos + variableReference.length;

        const syntheticEvent = {
          target: { value: newValue }
        } as React.ChangeEvent<HTMLTextAreaElement>;
        onChange(syntheticEvent);

        setTimeout(() => {
          if (textareaRef.current && document.activeElement === textareaRef.current) {
            textareaRef.current.setSelectionRange(cursorAfter, cursorAfter);
          }
        }, 0);
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

    // Add space separator if needed (let natural text wrapping handle line breaks)
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

  return (
    <div className="space-y-2 w-full">
      {label && <Label htmlFor={id}>{label}</Label>}
      <div
        className={cn(
          "relative w-full",
          isDragOver && "ring-2 ring-blue-500 ring-opacity-50"
        )}
      >
        <RichTextarea
          ref={textareaRef}
          id={id}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          rows={rows}
          className={cn(
            "w-full transition-colors",
            isDragOver && "border-blue-500 bg-blue-50",
            className
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        />
        {isDragOver && (
          <div className="absolute inset-0 flex items-center justify-center bg-blue-100 bg-opacity-50 rounded-md pointer-events-none z-10">
            <span className="text-blue-600 font-medium text-sm bg-white px-3 py-1 rounded-full shadow-sm">
              Drop variable here
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
