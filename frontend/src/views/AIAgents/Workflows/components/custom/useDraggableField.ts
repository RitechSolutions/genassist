import { useState, useRef } from "react";

function insertAtPosition(currentValue: string, newValue: string, position: number): string {
  if (!currentValue) return newValue;
  const safePosition = Math.max(0, Math.min(position, currentValue.length));
  const before = currentValue.slice(0, safePosition);
  const after = currentValue.slice(safePosition);
  const needsLeadingSpace =
    safePosition > 0 &&
    !currentValue[safePosition - 1].match(/\s/) &&
    !currentValue[safePosition - 1].match(/[,;:]/);
  const needsTrailingSpace =
    safePosition < currentValue.length &&
    !currentValue[safePosition].match(/\s/) &&
    !currentValue[safePosition].match(/[,;:]/);
  return before + (needsLeadingSpace ? " " : "") + newValue + (needsTrailingSpace ? " " : "") + after;
}

export function useDraggableField<T extends HTMLInputElement | HTMLTextAreaElement>(
  value: string,
  onChange: (e: React.ChangeEvent<T>) => void,
  onVariableDrop?: (path: string, value: unknown) => void,
) {
  const [isDragOver, setIsDragOver] = useState(false);
  const ref = useRef<T>(null);

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

    const el = ref.current;
    const insertPos =
      el && document.activeElement === el
        ? el.selectionStart ?? value.length
        : value.length;

    const applyInsert = (text: string, droppedValue?: unknown, path?: string) => {
      const newValue = insertAtPosition(value, text, insertPos);
      const cursorAfter = insertPos + text.length;
      onChange({ target: { value: newValue } } as React.ChangeEvent<T>);
      setTimeout(() => {
        if (ref.current && document.activeElement === ref.current) {
          ref.current.setSelectionRange(cursorAfter, cursorAfter);
        }
      }, 0);
      if (path !== undefined && onVariableDrop) {
        onVariableDrop(path, droppedValue);
      }
    };

    try {
      const jsonData = e.dataTransfer.getData("application/json");
      if (jsonData) {
        const { path, value: droppedValue } = JSON.parse(jsonData);
        applyInsert(path, droppedValue, path);
        return;
      }
      const textData = e.dataTransfer.getData("text/plain");
      if (textData) {
        applyInsert(textData);
      }
    } catch {
      // ignore malformed drag data
    }
  };

  return { isDragOver, ref, handleDragOver, handleDragLeave, handleDrop };
}
