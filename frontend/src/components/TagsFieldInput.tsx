import { useRef, useState } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/badge";
import { cn } from "@/helpers/utils";
import type { FieldValue } from '@/interfaces/dynamicFormSchemas.interface';

function normalizeTagsValue(value: FieldValue, fallback: FieldValue): string[] {
  const v = value ?? fallback;
  if (Array.isArray(v)) {
    return v.map((x) => String(x).trim()).filter(Boolean);
  }
  if (v === undefined || v === null || v === '') {
    return [];
  }
  if (typeof v === 'string') {
    return v
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
  }
  return [String(v).trim()].filter(Boolean);
}

export function TagsFieldInput({
  id,
  value,
  fieldDefault,
  placeholder,
  onChange,
}: {
  id: string;
  value: FieldValue;
  fieldDefault?: FieldValue;
  placeholder?: string;
  onChange: (next: string[]) => void;
}) {
  const tags = normalizeTagsValue(value, fieldDefault);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const pushTokens = (raw: string) => {
    const parts = raw
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    if (parts.length === 0) return;
    const seen = new Set(tags);
    const next = [...tags];
    for (const p of parts) {
      if (!seen.has(p)) {
        seen.add(p);
        next.push(p);
      }
    }
    onChange(next);
  };

  const commitDraft = () => {
    const t = draft.trim();
    if (t) {
      pushTokens(t);
      setDraft('');
    }
  };

  return (
    <div
      className={cn(
        'flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-full border border-input bg-transparent px-2 py-1.5 text-base ring-offset-background',
        'focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2',
        'md:text-sm'
      )}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          inputRef.current?.focus();
        }
      }}
    >
      {tags.map((tag, i) => (
        <Badge
          key={`${tag}-${i}`}
          variant="secondary"
          className="max-w-full gap-0.5 truncate rounded-md py-0 pl-2 pr-0.5 font-normal"
        >
          <span className="truncate">{tag}</span>
          <button
            type="button"
            className="rounded-sm p-0.5 hover:bg-muted"
            aria-label={`Remove ${tag}`}
            onClick={() => onChange(tags.filter((_, j) => j !== i))}
          >
            <X className="h-3.5 w-3.5 shrink-0 opacity-70" />
          </button>
        </Badge>
      ))}
      <input
        ref={inputRef}
        id={id}
        type="text"
        className="min-w-[8rem] flex-1 bg-transparent px-1 py-0.5 outline-none placeholder:text-muted-foreground"
        value={draft}
        placeholder={tags.length === 0 ? placeholder : undefined}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            commitDraft();
            return;
          }
          if (e.key === 'Backspace' && draft === '' && tags.length > 0) {
            e.preventDefault();
            onChange(tags.slice(0, -1));
          }
        }}
        onBlur={() => {
          commitDraft();
        }}
        onPaste={(e) => {
          const text = e.clipboardData.getData('text');
          if (text.includes(',')) {
            e.preventDefault();
            pushTokens(text);
            setDraft('');
          }
        }}
      />
    </div>
  );
}
