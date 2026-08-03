import { Plus } from "lucide-react";
import { Button } from "@/components/button";
import { SearchInput } from "@/components/SearchInput";
import { PageHeader } from "@/components/PageHeader";
import { SectionTitle } from "@/components/Heading";

export type PanelVariant = "page" | "tab";

interface PanelHeaderProps {
  /**
   * "page" renders the full-size page header (used by the standalone routes).
   * "tab" renders a compact section header (used inside the Settings tabs).
   */
  variant: PanelVariant;
  title: string;
  subtitle: string;
  searchQuery?: string;
  onSearchChange?: (query: string) => void;
  searchPlaceholder?: string;
  /** Secondary (outline) button rendered between the search input and the primary action. */
  secondaryActionText?: string;
  onSecondaryAction?: () => void;
  actionButtonText?: string;
  onActionClick?: () => void;
}

/**
 * Shared header for the Settings feature panels. Renders the large page header
 * on standalone routes and a compact section header when embedded in the
 * tabbed Settings page, so a single panel component serves both entry points.
 */
export function PanelHeader({
  variant,
  title,
  subtitle,
  searchQuery,
  onSearchChange,
  searchPlaceholder,
  secondaryActionText,
  onSecondaryAction,
  actionButtonText,
  onActionClick,
}: PanelHeaderProps) {
  if (variant === "page") {
    return (
      <PageHeader
        title={title}
        subtitle={subtitle}
        searchQuery={searchQuery ?? ""}
        onSearchChange={onSearchChange ?? (() => {})}
        searchPlaceholder={searchPlaceholder ?? ""}
        secondaryActionButtonText={secondaryActionText}
        onSecondaryActionClick={onSecondaryAction}
        actionButtonText={actionButtonText}
        onActionClick={onActionClick}
      />
    );
  }

  const hasSecondary = Boolean(secondaryActionText && onSecondaryAction);
  const hasPrimary = Boolean(actionButtonText && onActionClick);

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:flex-wrap">
      <div className="min-w-0">
        <SectionTitle className="text-lg sm:text-xl animate-fade-down">{title}</SectionTitle>
        <p className="text-sm text-muted-foreground animate-fade-up">{subtitle}</p>
      </div>
      {(onSearchChange || hasSecondary || hasPrimary) && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4 w-full sm:w-auto">
          {onSearchChange && (
            <SearchInput
              value={searchQuery ?? ""}
              onChange={onSearchChange}
              placeholder={searchPlaceholder}
            />
          )}
          {(hasSecondary || hasPrimary) && (
            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
              {hasSecondary && (
                <Button
                  type="button"
                  variant="outline"
                  className="flex items-center gap-2 w-full sm:w-auto justify-center rounded-full"
                  onClick={onSecondaryAction}
                >
                  {secondaryActionText}
                </Button>
              )}
              {hasPrimary && (
                <Button
                  className="flex items-center gap-2 w-full sm:w-auto justify-center rounded-full"
                  onClick={onActionClick}
                >
                  <Plus className="w-4 h-4" />
                  {actionButtonText}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
