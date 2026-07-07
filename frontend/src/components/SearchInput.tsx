import { Search } from "lucide-react";
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
  const trimmed = value.trim();
  // Empty is always valid (clears the search); otherwise enforce the minimum.
  const canSubmit = trimmed.length === 0 || trimmed.length >= minLength;
  const showMinHint = trimmed.length > 0 && trimmed.length < minLength;

  const submit = () => {
    if (onSearch && canSubmit) onSearch(trimmed);
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
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full pl-10 pr-4 py-2 border rounded-full focus:outline-none focus:ring-2 focus:ring-primary bg-white"
          />
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
        <p className="mt-1 pl-3 text-xs text-gray-500">
          Enter at least {minLength} characters to search.
        </p>
      )}
    </div>
  );
};
