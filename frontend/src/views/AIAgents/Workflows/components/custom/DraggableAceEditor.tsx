import React, { useState, useRef, useCallback } from "react";
import AceEditor from "react-ace";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";

interface DraggableAceEditorProps {
  id?: string;
  label?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  mode?: string;
  theme?: string;
  height?: string;
  width?: string;
  setOptions?: Record<string, unknown>;
  onVariableDrop?: (path: string, value: unknown) => void;
  name?: string; // Add name prop for compatibility
}

/**
 * AceEditor component that can receive dropped values from the JSON viewer
 * Supports both manual input and drag-and-drop from available variables
 * Variables can be dropped at cursor position or replace selected text
 * Shows real-time drag cursor for precise positioning
 *
 * Styling:
 * - Inherits all AceEditor component styles
 * - Supports custom className for additional styling
 * - Full width by default (w-full)
 * - Proper drag and drop visual feedback
 * - Syntax highlighting for variables in the preview section
 */
export const DraggableAceEditor: React.FC<DraggableAceEditorProps> = ({
  id,
  label,
  value,
  onChange,
  placeholder,
  className,
  mode = "text",
  theme = "twilight",
  height = "100%",
  width = "100%",
  setOptions = {},
  onVariableDrop,
  name,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const editorRef = useRef<any>(null);

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

    if (!editorRef.current) {
      return;
    }

    try {
      // Try to get JSON data first
      const jsonData = e.dataTransfer.getData("application/json");

      if (jsonData) {
        const { path, value: droppedValue } = JSON.parse(jsonData);
        // Insert the variable reference at the cursor position
        // const variableReference = `{{${path}}}`;
        //insertAtCursor(path);

        // Call the callback if provided
        if (onVariableDrop) {
          onVariableDrop(path, droppedValue);
        }
        return;
      }

      // Fallback to plain text
      const textData = e.dataTransfer.getData("text/plain");

      if (textData) {
        const variableReference = `{{${textData}}}`;
        insertAtCursor(variableReference);
      }
    } catch (error) {
      // ignore
    }
  };

  // Helper function to insert value at cursor position in AceEditor
  const insertAtCursor = useCallback(
    (textToInsert: string) => {
      if (!editorRef.current) return;

      const session = editorRef.current.getSession();
      const cursor = editorRef.current.getCursorPosition();

      // Insert the text at cursor position
      session.insert(cursor, textToInsert);

      // Update the value in the parent component
      const newValue = session.getValue();
      onChange(newValue);
    },
    [onChange]
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleEditorLoad = (editor: any) => {
    editorRef.current = editor;
  };

  const defaultSetOptions = {
    showLineNumbers: true,
    tabSize: 2,
    useWorker: false,
    enableBasicAutocompletion: true,
    enableLiveAutocompletion: true,
    enableSnippets: true,
    showPrintMargin: false,
    fontSize: 14,
    wrap: true,
    ...setOptions,
  };

  return (
    <div className="space-y-2 w-full">
      {label && <Label htmlFor={id}>{label}</Label>}
      <div
        className={cn(
          "relative w-full",
          isDragOver && "ring-2 ring-blue-500 ring-opacity-50"
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="editor-card relative flex flex-col p-6 gap-2.5 h-[500px] bg-[#1C1C1C] backdrop-blur-[20px] rounded-[16px] w-full">
          <AceEditor
            mode={mode}
            theme={theme}
            name={name || id || "draggable-editor"}
            value={value}
            onChange={onChange}
            width={width}
            height={height}
            setOptions={defaultSetOptions}
            onLoad={handleEditorLoad}
            className={cn(
              "transition-colors",
              isDragOver && "border-blue-500",
              className
            )}
          />
        </div>
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
