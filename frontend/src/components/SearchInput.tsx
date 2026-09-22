import { useRef } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/helpers/utils";
import { Button } from "@/components/button";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  /**
   * When provided, the input switches to "submit" mode: typing no longer
   * triggers a search on every keystroke. Instead the search is committed
   * only when the user presses Enter or clicks the search button. Used to
   * avoid expensive backend queries on partial input.
   */
  onSearch?: (value: string) => void;
  /**
   * Minimum number of (trimmed) characters required before a search can be
   * submitted. An empty value is always allowed (to clear the search).
   * Only applies when `onSearch` is provided.
   */
  minLength?: number;
}

export const SearchInput = ({
  value,
  onChange,
  placeholder = "Search...",
  className,
  onSearch,
  minLength = 0,
}: SearchInputProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const trimmed = value.trim();
  // Empty is always valid (clears the search); otherwise enforce the minimum.
  const canSubmit = trimmed.length === 0 || trimmed.length >= minLength;
  const showMinHint = trimmed.length > 0 && trimmed.length < minLength;

  const submit = () => {
    if (onSearch && canSubmit) onSearch(trimmed);
  };

  const clear = () => {
    onChange("");
    // Submit mode does not react to typing, so clearing has to commit as well
    // or the results would keep showing the old query.
    if (onSearch) onSearch("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (onSearch && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={cn("w-full sm:w-[260px]", className)}>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-5 h-5" />
          <input
            ref={inputRef}
            type="text"
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full pl-10 pr-9 py-2 border rounded-full focus:outline-none focus:ring-2 focus:ring-primary bg-card"
          />
          {value && (
            <button
              type="button"
              onClick={clear}
              aria-label="Clear search"
              className="absolute right-3 top-1/2 -translate-y-1/2 flex h-4 w-4 items-center justify-center rounded-full bg-muted-foreground/40 text-background transition-colors hover:bg-muted-foreground/60"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        {onSearch && (
          <Button
            type="button"
            onClick={submit}
            disabled={!canSubmit}
            className="rounded-full shrink-0"
          >
            Search
          </Button>
        )}
      </div>
      {showMinHint && (
        <p className="mt-1 pl-3 text-xs text-muted-foreground">
          Enter at least {minLength} characters to search.
        </p>
      )}
    </div>
  );
};
