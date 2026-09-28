import React, { useRef, useState, useCallback, useEffect } from "react";
import AceEditor from "react-ace";
// Required for enableBasicAutocompletion/enableLiveAutocompletion to do anything
import "ace-builds/src-noconflict/ext-language_tools";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";
import { detectVariableTrigger } from "@/helpers/variable-input/variableTrigger";
import {
  isVariableDrag,
  readVariableReference,
} from "@/helpers/variable-input/variableDragDrop";
import { useAceVariableAutocomplete } from "../../hooks/useAceVariableAutocomplete";
import { VariablePickerButton } from "./VariablePickerButton";

/* eslint-disable @typescript-eslint/no-explicit-any */

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
  name?: string;
}

/**
 * Wraps one of Ace's built-in completers so it stays quiet while a "{{" is
 * being typed. They are useful for the surrounding code, but inside a variable
 * reference their keywords and scraped words compete with the variable tree.
 */
function silenceDuringVariable(completer: any) {
  // Delegates through the prototype so anything else the completer carries
  // (insertMatch, getDocTooltip, identifierRegexps) still reaches Ace
  const wrapped = Object.create(completer);

  wrapped.getCompletions = (
    editor: any,
    session: any,
    pos: { row: number; column: number },
    prefix: string,
    callback: (error: unknown, results: unknown[]) => void
  ) => {
    const line = session.getLine(pos.row) as string;
    if (detectVariableTrigger(line, pos.column)) {
      callback(null, []);
      return;
    }
    completer.getCompletions(editor, session, pos, prefix, callback);
  };

  return wrapped;
}

/**
 * Code editor for workflow config fields. Typing "{{" opens the same variable
 * tree the other fields use; Ace's own completion still handles the code.
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
  name,
}) => {
  const cleanupRef = useRef<(() => void) | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const { attach, suggestions, insertVariable } = useAceVariableAutocomplete();

  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  const handleEditorLoad = useCallback(
    (editor: any) => {
      cleanupRef.current?.();

      // react-ace has already applied setOptions, so the language-tools
      // defaults are in place and can be muted inside a variable reference.
      editor.completers = (editor.completers || []).map(silenceDuringVariable);

      // Ace swallows React's synthetic drag events, so the panel's drops are
      // taken on the container itself, in the capture phase.
      const container = editor.container as HTMLElement;
      const capture = true;

      const onDragOver = (event: DragEvent) => {
        if (!isVariableDrag(event.dataTransfer)) return;
        event.preventDefault();
        event.stopPropagation();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
        setIsDragOver(true);
      };

      const onDragLeave = () => setIsDragOver(false);

      const onDrop = (event: DragEvent) => {
        if (!event.dataTransfer || !isVariableDrag(event.dataTransfer)) return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        setIsDragOver(false);

        const reference = readVariableReference(event.dataTransfer);
        if (!reference) return;

        // Drop lands where the cursor is, not where the caret happened to be
        const position = editor.renderer.screenToTextCoordinates(
          event.clientX,
          event.clientY
        );
        editor.moveCursorToPosition(position);
        editor.focus();
        editor.insert(reference);
      };

      container.addEventListener("dragover", onDragOver, capture);
      container.addEventListener("dragleave", onDragLeave, capture);
      container.addEventListener("drop", onDrop, capture);

      const detachAutocomplete = attach(editor);
      cleanupRef.current = () => {
        container.removeEventListener("dragover", onDragOver, capture);
        container.removeEventListener("dragleave", onDragLeave, capture);
        container.removeEventListener("drop", onDrop, capture);
        detachAutocomplete();
      };
    },
    [attach]
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
          "group relative w-full",
          isDragOver && "ring-2 ring-blue-500 ring-opacity-50 rounded-[16px]"
        )}
      >
        <div className="editor-card relative flex flex-col p-6 gap-2.5 h-[500px] bg-[#1C1C1C] backdrop-blur-[20px] rounded-[16px] w-full">
          <AceEditor
            mode={mode}
            theme={theme}
            name={name || id || "draggable-editor"}
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            width={width}
            height={height}
            setOptions={defaultSetOptions}
            onLoad={handleEditorLoad}
            className={cn("transition-colors", className)}
          />
        </div>
        {isDragOver && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-[16px] bg-blue-500/20">
            <span className="rounded-full bg-card px-3 py-1 text-sm font-medium text-blue-600 shadow-sm dark:text-blue-400">
              Drop variable at cursor position
            </span>
          </div>
        )}
        <VariablePickerButton
          onSelect={insertVariable}
          className="absolute right-3 top-3 z-20 bg-black/40 text-white/70 hover:bg-black/60 hover:text-white"
        />
      </div>
      {suggestions}
    </div>
  );
};
