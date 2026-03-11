import React, { useCallback, useRef, useEffect, useState } from "react";
import { Bold, Italic, Type, Link2, Undo2, Redo2 } from "lucide-react";
import { Toggle } from "@/components/toggle";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { Separator } from "@/components/separator";
import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";

/** Which toolbar features to show. All default to false. */
export interface RichTextEditorToolbar {
  bold?: boolean;
  italic?: boolean;
  fontSize?: boolean;
  link?: boolean;
  undoRedo?: boolean;
}

export interface RichTextEditorProps {
  /** Current HTML string value */
  value: string;
  /** Called with the updated HTML whenever the content changes */
  onChange: (html: string) => void;
  /** Toolbar feature toggles */
  toolbar?: RichTextEditorToolbar;
  /** Placeholder text shown when the editor is empty */
  placeholder?: string;
  /** Extra class names for the outer container */
  className?: string;
  /** Minimum height of the editable area (CSS value) */
  minHeight?: string;
  /** Maximum height of the editable area (CSS value) */
  maxHeight?: string;
  /** Available font sizes for the font-size picker */
  fontSizes?: string[];
  /** When true the editor is read-only */
  disabled?: boolean;
}

const DEFAULT_FONT_SIZES = ["12px", "14px", "16px", "18px", "20px"];

/**
 * A lightweight rich-text editor built on contentEditable.
 *
 * Supports bold, italic, font-size, and links.  The toolbar is fully
 * configurable via the `toolbar` prop so the same component can be
 * reused across different contexts with different feature sets.
 */
export const RichTextEditor: React.FC<RichTextEditorProps> = ({
  value,
  onChange,
  toolbar = {},
  placeholder = "",
  className,
  minHeight = "60px",
  maxHeight = "200px",
  fontSizes = DEFAULT_FONT_SIZES,
  disabled = false,
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const lastEmittedRef = useRef(value);
  const [, forceUpdate] = useState(0);

  // Sync external value changes into the editor
  useEffect(() => {
    if (editorRef.current && value !== lastEmittedRef.current) {
      editorRef.current.innerHTML = value;
      lastEmittedRef.current = value;
    }
  }, [value]);

  // Set initial content on mount
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = value;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── helpers ────────────────────────────────────────────────────────

  const emitChange = useCallback(() => {
    if (!editorRef.current) return;
    const html = editorRef.current.innerHTML;
    const cleaned =
      html === "<br>" || html.replace(/<[^>]*>/g, "").trim() === ""
        ? ""
        : html;
    lastEmittedRef.current = cleaned;
    onChange(cleaned);
  }, [onChange]);

  const exec = useCallback(
    (command: string, val?: string) => {
      editorRef.current?.focus();
      document.execCommand(command, false, val);
      emitChange();
      forceUpdate((n) => n + 1);
    },
    [emitChange],
  );

  // ── toolbar handlers ───────────────────────────────────────────────

  const handleBold = useCallback(() => exec("bold"), [exec]);
  const handleItalic = useCallback(() => exec("italic"), [exec]);
  const handleUndo = useCallback(() => exec("undo"), [exec]);
  const handleRedo = useCallback(() => exec("redo"), [exec]);

  const handleFontSize = useCallback(
    (size: string) => {
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0 || sel.getRangeAt(0).collapsed) return;
      const span = document.createElement("span");
      span.style.fontSize = size;
      sel.getRangeAt(0).surroundContents(span);
      sel.removeAllRanges();
      emitChange();
    },
    [emitChange],
  );

  const isInsideLink = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return false;
    return !!sel.getRangeAt(0).startContainer.parentElement?.closest("a");
  }, []);

  const handleLink = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;

    if (isInsideLink()) {
      exec("unlink");
      return;
    }

    const url = prompt("Enter URL:");
    if (!url) return;
    exec("createLink", url);

    // Ensure all new links open in a new tab
    editorRef.current
      ?.querySelectorAll('a:not([target="_blank"])')
      .forEach((link) => {
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
      });
    emitChange();
  }, [exec, emitChange, isInsideLink]);

  // Detect active formatting state for toggle pressed styling
  const isBold = document.queryCommandState?.("bold") ?? false;
  const isItalic = document.queryCommandState?.("italic") ?? false;

  const hasToolbar = Object.values(toolbar).some(Boolean);

  // ── render ─────────────────────────────────────────────────────────

  return (
    <div
      className={cn(
        "border rounded-lg overflow-hidden bg-background",
        disabled && "opacity-60 pointer-events-none",
        className,
      )}
    >
      {hasToolbar && (
        <div className="flex items-center gap-0.5 px-1.5 py-1 border-b bg-muted/30 flex-wrap">
          {toolbar.bold && (
            <Toggle
              size="sm"
              pressed={isBold}
              className="h-7 w-7 p-0 rounded-md"
              aria-label="Bold"
              onPressedChange={handleBold}
            >
              <Bold className="h-3.5 w-3.5" />
            </Toggle>
          )}

          {toolbar.italic && (
            <Toggle
              size="sm"
              pressed={isItalic}
              className="h-7 w-7 p-0 rounded-md"
              aria-label="Italic"
              onPressedChange={handleItalic}
            >
              <Italic className="h-3.5 w-3.5" />
            </Toggle>
          )}

          {toolbar.fontSize && (
            <Popover>
              <PopoverTrigger asChild>
                <Toggle
                  size="sm"
                  className="h-7 w-7 p-0 rounded-md"
                  aria-label="Font size"
                  pressed={false}
                >
                  <Type className="h-3.5 w-3.5" />
                </Toggle>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-auto p-1">
                {fontSizes.map((size) => (
                  <Button
                    key={size}
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start text-sm h-7 px-2"
                    onClick={() => handleFontSize(size)}
                  >
                    {size}
                  </Button>
                ))}
              </PopoverContent>
            </Popover>
          )}

          {toolbar.link && (toolbar.bold || toolbar.italic || toolbar.fontSize) && (
            <Separator orientation="vertical" className="mx-0.5 h-4" />
          )}

          {toolbar.link && (
            <Toggle
              size="sm"
              pressed={isInsideLink()}
              className="h-7 w-7 p-0 rounded-md"
              aria-label="Insert or remove link"
              onPressedChange={handleLink}
            >
              <Link2 className="h-3.5 w-3.5" />
            </Toggle>
          )}

          {toolbar.undoRedo && (
            <>
              <Separator orientation="vertical" className="mx-0.5 h-4" />
              <Toggle
                size="sm"
                className="h-7 w-7 p-0 rounded-md"
                aria-label="Undo"
                pressed={false}
                onPressedChange={handleUndo}
              >
                <Undo2 className="h-3.5 w-3.5" />
              </Toggle>
              <Toggle
                size="sm"
                className="h-7 w-7 p-0 rounded-md"
                aria-label="Redo"
                pressed={false}
                onPressedChange={handleRedo}
              >
                <Redo2 className="h-3.5 w-3.5" />
              </Toggle>
            </>
          )}
        </div>
      )}

      {/* Editable area */}
      <div
        ref={editorRef}
        contentEditable={!disabled}
        className="overflow-y-auto px-3 py-2 text-sm outline-none focus:ring-0 [&_a]:text-primary [&_a]:underline"
        style={{ minHeight, maxHeight }}
        onInput={emitChange}
        onBlur={emitChange}
        onKeyUp={() => forceUpdate((n) => n + 1)}
        onMouseUp={() => forceUpdate((n) => n + 1)}
        data-placeholder={placeholder}
      />

      {placeholder && (
        <style>{`
          [data-placeholder]:empty::before {
            content: attr(data-placeholder);
            color: hsl(var(--muted-foreground));
            pointer-events: none;
          }
        `}</style>
      )}
    </div>
  );
};
