import React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";

interface ExpectedArticlesFieldProps {
  articles: string[];
  onRemove: (position: number) => void;
}

/** The articles the knowledge search should find on a turn: shown, and removable, but never typed. */
export const ExpectedArticlesField: React.FC<ExpectedArticlesFieldProps> = ({ articles, onRemove }) => {
  if (!articles.length) return null;
  return (
    <div className="space-y-2">
      <Label className="text-xs">Expected articles</Label>
      <ul className="space-y-1">
        {articles.map((article, position) => (
          <li key={`${article}-${position}`} className="flex items-center justify-between gap-2 rounded-md border bg-background px-3 py-1.5 text-sm">
            <span className="min-w-0 break-words">{article}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              aria-label={`Remove expected article "${article}"`}
              onClick={() => onRemove(position)}
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </Button>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        An "Article found" check passes on this turn when the knowledge search finds any of them.
      </p>
    </div>
  );
};

export default ExpectedArticlesField;
