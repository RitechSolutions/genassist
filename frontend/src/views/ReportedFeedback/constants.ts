import { IssueCategory } from "@/services/issueStatuses";

/**
 * Pill classes per palette name the API accepts
 */
export const STATUS_COLOR_CLASSES: Record<string, string> = {
  amber: "border-amber-300 bg-amber-50 text-amber-700",
  blue: "border-blue-300 bg-blue-50 text-blue-700",
  purple: "border-purple-300 bg-purple-50 text-purple-700",
  teal: "border-teal-300 bg-teal-50 text-teal-700",
  emerald: "border-emerald-300 bg-emerald-50 text-emerald-700",
  zinc: "border-zinc-300 bg-zinc-100 text-zinc-600",
  red: "border-red-300 bg-red-50 text-red-700",
  orange: "border-orange-300 bg-orange-50 text-orange-700",
  sky: "border-sky-300 bg-sky-50 text-sky-700",
  pink: "border-pink-300 bg-pink-50 text-pink-700",
};

export const CATEGORY_META: Record<IssueCategory, { label: string }> = {
  todo: { label: "To Do" },
  in_progress: { label: "In Progress" },
  done: { label: "Done" },
};
