import React, { useState, useEffect, useCallback, useRef } from "react";
import { cn } from "@/helpers/utils";
import { AlertCircle, Check, Copy, WrapText } from "lucide-react";
import { Button } from "@/components/button";

interface JsonInputProps {
  value: string;
  onChange: (value: string) => void;
  onValidChange?: (isValid: boolean, parsed: unknown) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
  disabled?: boolean;
  allowEmpty?: boolean;
  label?: string;
  description?: string;
}

interface ValidationResult {
  isValid: boolean;
  error?: string;
  errorLine?: number;
  errorColumn?: number;
  parsed?: unknown;
}

const validateJson = (value: string, allowEmpty: boolean): ValidationResult => {
  const trimmed = value.trim();

  if (!trimmed) {
    return allowEmpty
      ? { isValid: true, parsed: undefined }
      : { isValid: false, error: "JSON is required" };
  }

  try {
    const parsed = JSON.parse(trimmed);
    return { isValid: true, parsed };
  } catch (e) {
    if (e instanceof SyntaxError) {
      const posMatch = e.message.match(/at position (\d+)/);
      const lineColMatch = e.message.match(/at line (\d+) column (\d+)/);

      let errorLine: number | undefined;
      let errorColumn: number | undefined;

      if (lineColMatch) {
        errorLine = parseInt(lineColMatch[1], 10);
        errorColumn = parseInt(lineColMatch[2], 10);
      } else if (posMatch) {
        const pos = parseInt(posMatch[1], 10);
        const lines = trimmed.substring(0, pos).split("\n");
        errorLine = lines.length;
        errorColumn = lines[lines.length - 1].length + 1;
      }

      const friendlyError = e.message
        .replace(/^JSON\.parse: /, "")
        .replace(/at position \d+/, errorLine ? `at line ${errorLine}` : "")
        .replace(/at line (\d+) column (\d+)/, "at line $1, column $2");

      return { isValid: false, error: friendlyError, errorLine, errorColumn };
    }
    return { isValid: false, error: "Invalid JSON" };
  }
};

const formatJson = (value: string): string => {
  try {
    const parsed = JSON.parse(value.trim());
    return JSON.stringify(parsed, null, 2);
  } catch {
    return value;
  }
};

const minifyJson = (value: string): string => {
  try {
    const parsed = JSON.parse(value.trim());
    return JSON.stringify(parsed);
  } catch {
    return value;
  }
};

// Syntax highlight JSON string
const highlightJson = (text: string): React.ReactNode[] => {
  if (!text) return [];

  const result: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  const addText = (content: string, className?: string) => {
    if (content) {
      result.push(
        <span key={key++} className={className}>
          {content}
        </span>
      );
    }
  };

  while (i < text.length) {
    const char = text[i];

    // Whitespace
    if (/\s/.test(char)) {
      let whitespace = "";
      while (i < text.length && /\s/.test(text[i])) {
        whitespace += text[i];
        i++;
      }
      addText(whitespace);
      continue;
    }

    // String (key or value)
    if (char === '"') {
      let str = '"';
      i++;
      while (i < text.length && text[i] !== '"') {
        if (text[i] === "\\") {
          str += text[i] + (text[i + 1] || "");
          i += 2;
        } else {
          str += text[i];
          i++;
        }
      }
      str += '"';
      i++;

      // Check if this is a key (followed by colon)
      let j = i;
      while (j < text.length && /\s/.test(text[j])) j++;
      const isKey = text[j] === ":";

      addText(str, isKey ? "text-blue-600" : "text-red-600");
      continue;
    }

    // Number
    if (/[-\d]/.test(char)) {
      let num = "";
      while (i < text.length && /[-\d.eE+]/.test(text[i])) {
        num += text[i];
        i++;
      }
      addText(num, "text-green-600");
      continue;
    }

    // Boolean or null
    if (text.slice(i, i + 4) === "true") {
      addText("true", "text-blue-600");
      i += 4;
      continue;
    }
    if (text.slice(i, i + 5) === "false") {
      addText("false", "text-blue-600");
      i += 5;
      continue;
    }
    if (text.slice(i, i + 4) === "null") {
      addText("null", "text-gray-500");
      i += 4;
      continue;
    }

    // Brackets and punctuation
    if (/[{}\[\]:,]/.test(char)) {
      addText(char, "text-gray-600");
      i++;
      continue;
    }

    // Any other character
    addText(char);
    i++;
  }

  return result;
};

export const JsonInput: React.FC<JsonInputProps> = ({
  value,
  onChange,
  onValidChange,
  placeholder = '{\n  "key": "value"\n}',
  rows = 5,
  className,
  disabled = false,
  allowEmpty = false,
  label,
  description,
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const [copied, setCopied] = useState(false);
  const [validation, setValidation] = useState<ValidationResult>(() =>
    validateJson(value, allowEmpty)
  );
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLPreElement>(null);

  const validate = useCallback((val: string) => {
    const result = validateJson(val, allowEmpty);
    setValidation(result);
    onValidChange?.(result.isValid, result.parsed);
    return result;
  }, [allowEmpty, onValidChange]);

  useEffect(() => {
    validate(value);
  }, [value, validate]);

  // Sync scroll between textarea and highlight overlay
  const handleScroll = () => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
  };

  const handleBlur = () => {
    setIsFocused(false);
    // Auto-format on blur if valid
    if (validation.isValid && value.trim()) {
      const formatted = formatJson(value);
      if (formatted !== value) {
        onChange(formatted);
      }
    }
  };

  const handleFormat = () => {
    if (validation.isValid && value.trim()) {
      onChange(formatJson(value));
    }
  };

  const handleMinify = () => {
    if (validation.isValid && value.trim()) {
      onChange(minifyJson(value));
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access denied
    }
  };

  const showError = !validation.isValid && value.trim().length > 0;
  const showValid = validation.isValid && value.trim().length > 0;
  const lineCount = value.split("\n").length;

  return (
    <div className={className}>
      {/* Header */}
      {(label || showValid || showError) && (
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {label && (
              <label className="text-sm font-medium text-gray-700">{label}</label>
            )}
            {showValid && (
              <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                <Check className="h-3 w-3" />
                Valid
              </span>
            )}
            {showError && (
              <span className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                <AlertCircle className="h-3 w-3" />
                Invalid
              </span>
            )}
          </div>
          {showValid && (
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleMinify}
                className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700"
              >
                Minify
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleFormat}
                className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700"
              >
                <WrapText className="h-3 w-3 mr-1" />
                Format
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700"
              >
                <Copy className="h-3 w-3 mr-1" />
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>
          )}
        </div>
      )}

      {description && (
        <p className="text-xs text-gray-500 mb-2">{description}</p>
      )}

      {/* Editor */}
      <div
        className={cn(
          "relative rounded-lg overflow-hidden border transition-all",
          isFocused && "ring-2 ring-primary/20 border-primary",
          showError && !isFocused && "border-red-300",
          showValid && !isFocused && "border-green-300",
          !showError && !showValid && !isFocused && "border-gray-200"
        )}
      >
        {/* Line numbers + Editor area */}
        <div className="flex">
          {/* Line numbers gutter */}
          {rows > 3 && (
            <div
              className="flex-shrink-0 bg-gray-100 border-r border-gray-200 text-right select-none px-2 py-3"
              style={{ minWidth: "2.5rem" }}
              aria-hidden="true"
            >
              {Array.from({ length: Math.max(lineCount, rows) }, (_, i) => (
                <div
                  key={i}
                  className={cn(
                    "text-xs leading-5 font-mono",
                    i < lineCount ? "text-gray-400" : "text-transparent",
                    validation.errorLine === i + 1 && "text-red-500 font-semibold"
                  )}
                >
                  {i + 1}
                </div>
              ))}
            </div>
          )}

          {/* Editor container */}
          <div className="flex-1 relative">
            {/* Syntax highlighted overlay */}
            <pre
              ref={highlightRef}
              className={cn(
                "absolute inset-0 p-3 text-sm font-mono leading-5 whitespace-pre-wrap break-words overflow-hidden pointer-events-none",
                "bg-transparent m-0"
              )}
              style={{ tabSize: 2 }}
              aria-hidden="true"
            >
              {value ? highlightJson(value) : (
                <span className="text-gray-400">{placeholder}</span>
              )}
            </pre>

            {/* Actual textarea (transparent text) */}
            <textarea
              ref={textareaRef}
              value={value}
              onChange={handleChange}
              onFocus={() => setIsFocused(true)}
              onBlur={handleBlur}
              onScroll={handleScroll}
              placeholder=""
              disabled={disabled}
              spellCheck={false}
              className={cn(
                "w-full bg-gray-50/80 p-3 text-sm font-mono leading-5 resize-none outline-none",
                "text-transparent caret-gray-800 selection:bg-blue-200 selection:text-transparent",
                disabled && "bg-gray-100 cursor-not-allowed"
              )}
              style={{
                minHeight: `${rows * 1.25 + 1.5}rem`,
                tabSize: 2,
              }}
            />
          </div>
        </div>

        {/* Status bar */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-gray-100 border-t border-gray-200 text-xs text-gray-500">
          <span>
            {lineCount} line{lineCount !== 1 ? "s" : ""}
            {value.trim() && ` · ${value.trim().length} chars`}
          </span>
          <span className="font-mono text-gray-400">JSON</span>
        </div>
      </div>

      {/* Error message */}
      {showError && (
        <div className="mt-2 p-2 rounded-md bg-red-50 border border-red-200">
          <p className="text-xs text-red-700 font-medium flex items-start gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>{validation.error}</span>
          </p>
          {validation.errorLine && (
            <p className="text-xs text-red-600 mt-1 ml-5">
              Check line {validation.errorLine}
              {validation.errorColumn && `, column ${validation.errorColumn}`}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default JsonInput;
