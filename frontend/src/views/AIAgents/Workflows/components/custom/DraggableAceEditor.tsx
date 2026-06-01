import React, { useState, useRef, useCallback, useEffect } from "react";
import AceEditor from "react-ace";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";
import { parseDroppedVariable } from "@/helpers/variable-input/droppedVariable";

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
  name?: string;
}

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
  const cleanupDropListenersRef = useRef<(() => void) | null>(null);
  const dropHandledRef = useRef(false);

  useEffect(() => {
    return () => {
      cleanupDropListenersRef.current?.();
    };
  }, []);

  const processDrop = useCallback(
    (dataTransfer: DataTransfer, clientX?: number, clientY?: number) => {
      if (dropHandledRef.current) {
        return;
      }

      const dropped = parseDroppedVariable(dataTransfer);
      if (!dropped || !editorRef.current) {
        return;
      }

      dropHandledRef.current = true;
      requestAnimationFrame(() => {
        dropHandledRef.current = false;
      });

      const editor = editorRef.current;

      if (clientX != null && clientY != null) {
        const position = editor.renderer.screenToTextCoordinates(
          clientX,
          clientY
        );
        editor.moveCursorToPosition(position);
      }

      editor.focus();

      if (onVariableDrop) {
        onVariableDrop(dropped.path, dropped.value);
        return;
      }

      editor.insert(dropped.reference);
      onChange(editor.getValue());
    },
    [onChange, onVariableDrop]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleEditorLoad = useCallback(
    (editor: any) => {
      cleanupDropListenersRef.current?.();
      editorRef.current = editor;

      const container = editor.container as HTMLElement;
      const capture = true;

      const onDragOver = (event: DragEvent) => {
        event.preventDefault();
        event.stopPropagation();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "copy";
        }
        setIsDragOver(true);
      };

      const onDragLeave = (event: DragEvent) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragOver(false);
      };

      const onDrop = (event: DragEvent) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        setIsDragOver(false);
        if (event.dataTransfer) {
          processDrop(event.dataTransfer, event.clientX, event.clientY);
        }
      };

      container.addEventListener("dragover", onDragOver, capture);
      container.addEventListener("dragleave", onDragLeave, capture);
      container.addEventListener("drop", onDrop, capture);

      cleanupDropListenersRef.current = () => {
        container.removeEventListener("dragover", onDragOver, capture);
        container.removeEventListener("dragleave", onDragLeave, capture);
        container.removeEventListener("drop", onDrop, capture);
      };
    },
    [processDrop]
  );

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
