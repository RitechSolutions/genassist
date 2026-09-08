import React, { useRef, useState } from "react";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";
import {
  isVariableDrag,
  readVariableReference,
} from "@/helpers/variable-input/variableDragDrop";
import { insertReferenceAt } from "@/helpers/variable-input/variableReference";
import { RichTextarea } from "@/components/richTextarea";
import { useVariableAutocomplete } from "../../hooks/useVariableAutocomplete";
import { VariablePickerButton } from "./VariablePickerButton";

interface DraggableTextAreaProps {
  id?: string;
  label?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  className?: string;
  rows?: number;
}

/**
 * Textarea for workflow config fields. Variables go in either by typing "{{"
 * for the tree typeahead or through the picker button, and the underlying
 * RichTextarea highlights them once inserted.
 */
export const DraggableTextArea: React.FC<DraggableTextAreaProps> = ({
  id,
  label,
  value,
  onChange,
  placeholder,
  className,
  rows = 4,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { fieldProps, suggestions, insertVariable } =
    useVariableAutocomplete<HTMLTextAreaElement>({
      elementRef: textareaRef,
      value,
      onChange,
    });


  const [isDragOver, setIsDragOver] = useState(false);

  // Only our own drags are intercepted; anything else keeps native behaviour
  const handleDragOver = (e: React.DragEvent) => {
    if (!isVariableDrag(e.dataTransfer)) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    if (!isVariableDrag(e.dataTransfer)) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const reference = readVariableReference(e.dataTransfer);
    if (!reference) return;

    const el = textareaRef.current;
    const at =
      el && document.activeElement === el
        ? el.selectionStart ?? value.length
        : value.length;

    const next = insertReferenceAt(value, reference, at);
    onChange({
      target: { value: next.value },
    } as React.ChangeEvent<HTMLTextAreaElement>);

    setTimeout(() => {
      const node = textareaRef.current;
      if (node && document.activeElement === node) {
        node.setSelectionRange(next.cursor, next.cursor);
      }
    }, 0);
  };

  return (
    <div className="space-y-2 w-full">
      {label && <Label htmlFor={id}>{label}</Label>}
      <div
        className={cn(
          "group relative w-full",
          isDragOver && "ring-2 ring-blue-500 ring-opacity-50 rounded-3xl"
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <RichTextarea
          ref={textareaRef}
          id={id}
          value={value}
          placeholder={placeholder}
          rows={rows}
          className={cn("w-full pr-10", className)}
          {...fieldProps}
        />
        {isDragOver && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-md bg-blue-100/50 dark:bg-blue-500/20">
            <span className="rounded-full bg-card px-3 py-1 text-sm font-medium text-blue-600 shadow-sm dark:text-blue-400">
              Drop variable here
            </span>
          </div>
        )}
        <VariablePickerButton
          onSelect={insertVariable}
          className="absolute right-2 top-2 z-20"
        />
      </div>
      {suggestions}
    </div>
  );
};
