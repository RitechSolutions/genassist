import React, { useCallback, useRef, useEffect, useState } from "react";
import { Bold, Italic, Type, Link2, ImagePlus, Undo2, Redo2 } from "lucide-react";
import toast from "react-hot-toast";
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
  image?: boolean;
  undoRedo?: boolean;
}

/** Max inline image size (base64-embedded). Larger files are rejected. */
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

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
  const fileInputRef = useRef<HTMLInputElement>(null);
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
    // Empty unless there is text or embedded media (e.g. an image-only field).
    const hasMedia = /<img\b/i.test(html);
    const cleaned =
      !hasMedia && (html === "<br>" || html.replace(/<[^>]*>/g, "").trim() === "")
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

  const insertImageFromFile = useCallback(
    (file: File) => {
      if (!file.type.startsWith("image/")) {
        toast.error("Please choose an image file");
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        toast.error("Image is too large (max 2 MB)");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        editorRef.current?.focus();
        document.execCommand("insertImage", false, dataUrl);
        // Constrain newly inserted images so they fit the editor/preview.
        editorRef.current?.querySelectorAll<HTMLImageElement>("img:not([data-rte])").forEach((img) => {
          img.setAttribute("data-rte", "1");
          img.style.maxWidth = "100%";
          img.style.height = "auto";
        });
        emitChange();
        forceUpdate((n) => n + 1);
      };
      reader.readAsDataURL(file);
    },
    [emitChange],
  );

  const handleImageSelected = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (file) insertImageFromFile(file);
    },
    [insertImageFromFile],
  );

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

          {toolbar.image && (
            <Toggle
              size="sm"
              pressed={false}
              className="h-7 w-7 p-0 rounded-md"
              aria-label="Insert image"
              onPressedChange={() => fileInputRef.current?.click()}
            >
              <ImagePlus className="h-3.5 w-3.5" />
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

      {toolbar.image && (
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleImageSelected}
        />
      )}

      {/* Editable area */}
      <div
        ref={editorRef}
        contentEditable={!disabled}
        className="overflow-y-auto px-3 py-2 text-sm outline-none focus:ring-0 [&_a]:text-primary [&_a]:underline [&_img]:max-w-full [&_img]:h-auto [&_img]:rounded-md [&_img]:my-1"
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
