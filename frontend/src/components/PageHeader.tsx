import { Search, Plus } from "lucide-react";
import { Button } from "@/components/button";

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
        <div className="relative w-full sm:w-[260px]">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <Button className="flex items-center gap-2 w-full sm:w-auto justify-center" onClick={onActionClick}>
          <Plus className="w-4 h-4" />
          {actionButtonText}
        </Button>
      </div>
    </div>
  );
}