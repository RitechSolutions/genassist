import { cn } from "@/lib/utils";

// Chrome shared by <Textarea> and <RichTextarea>. No height here on purpose:
// height comes from `rows` alone, so a call site never has to out-shout a
// min-height. A fixed `h-*` in className would beat both — use `size` instead.
export const TEXTAREA_BASE_CLASS =
  "flex w-full rounded-3xl border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 resize-y";

export type TextareaSize =
  | "compact"
  | "hint"
  | "description"
  | "body"
  | "code"
  | "prompt"
  | "document";

interface TextareaSizePreset {
  rows: number;
  className?: string;
  spellCheck?: boolean;
}

// One entry per kind of field, so the same content is the same height everywhere.
export const TEXTAREA_SIZES: Record<TextareaSize, TextareaSizePreset> = {
  compact: { rows: 2 }, // a list or table row holding a short value
  hint: { rows: 3 }, // help text, a sentence or two
  description: { rows: 4 }, // an entity description, or one the model reads
  body: { rows: 6 }, // a message, ticket or email body
  code: { rows: 10, className: "font-mono text-xs", spellCheck: false }, // JSON, a template, an expression
  prompt: { rows: 12 }, // system/user prompts and instructions
  document: { rows: 16, className: "font-mono text-xs", spellCheck: false }, // a whole page or module
};

export const DEFAULT_TEXTAREA_SIZE: TextareaSize = "description";

export interface TextareaSizingProps {
  size?: TextareaSize;
  rows?: number;
}

// Turns a size preset into the props a textarea spreads. An explicit `rows`
// wins over the preset; `contentClassName` is the typography half only, for
// RichTextarea's highlight overlay, which must match the textarea's metrics.
export function resolveTextareaSizing({
  size,
  rows,
  className,
}: TextareaSizingProps & { className?: string }) {
  const preset = TEXTAREA_SIZES[size ?? DEFAULT_TEXTAREA_SIZE];
  const contentClassName = cn(preset.className, className);

  return {
    rows: rows ?? preset.rows,
    spellCheck: preset.spellCheck,
    contentClassName,
    className: cn(TEXTAREA_BASE_CLASS, contentClassName),
  };
}
