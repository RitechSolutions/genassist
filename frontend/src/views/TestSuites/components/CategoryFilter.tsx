import React from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { cn } from "@/helpers/utils";
import { ALL_CATEGORIES, NO_CATEGORY, categoryOption, categoryQuery } from "../helpers/categories";

interface CategoryFilterProps {
  value: string;
  onChange: (value: string) => void;
  categories: string[];
  className?: string;
}

/** Shows every category, those with none, or one category. */
export const CategoryFilter: React.FC<CategoryFilterProps> = ({ value, onChange, categories, className }) => {
  // A picked category stays listed while the list reloads without it.
  const picked = categoryQuery(value).category;
  const names = picked && !categories.includes(picked) ? [...categories, picked] : categories;
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={cn("w-full bg-card sm:w-44", className)} aria-label="Filter by category">
        <SelectValue placeholder="All categories" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_CATEGORIES}>All categories</SelectItem>
        {names.map((name) => (
          <SelectItem key={name} value={categoryOption(name)}>
            {name}
          </SelectItem>
        ))}
        <SelectItem value={NO_CATEGORY}>No category</SelectItem>
      </SelectContent>
    </Select>
  );
};
