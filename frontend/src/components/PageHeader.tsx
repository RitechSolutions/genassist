import { Plus } from "lucide-react";
import { Button } from "@/components/button";
import { SearchInput } from "@/components/SearchInput";

interface PageHeaderProps {
  title: string;
  subtitle: string;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchPlaceholder: string;
  actionButtonText: string;
  onActionClick: () => void;
}

export function PageHeader({
  title,
  subtitle,
  searchQuery,
  onSearchChange,
  searchPlaceholder,
  actionButtonText,
  onActionClick,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:flex-wrap">
      <div className="min-w-0">
        <h1 className="text-2xl md:text-3xl font-bold mb-1 animate-fade-down">{title}</h1>
        <p className="text-sm md:text-base text-muted-foreground animate-fade-up">{subtitle}</p>
      </div>
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4 w-full sm:w-auto">
        <SearchInput
          value={searchQuery}
          onChange={onSearchChange}
          placeholder={searchPlaceholder}
        />
        <Button className="flex items-center gap-2 w-full sm:w-auto justify-center rounded-full" onClick={onActionClick}>
          <Plus className="w-4 h-4" />
          {actionButtonText}
        </Button>
      </div>
    </div>
  );
}
