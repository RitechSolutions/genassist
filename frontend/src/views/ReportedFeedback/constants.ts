import { FeedbackStatus } from "@/services/reportedFeedback";

export const STATUS_META: Record<
  FeedbackStatus,
  { label: string; className: string }
> = {
  open: {
    label: "Open",
    className: "border-amber-300 bg-amber-50 text-amber-700",
  },
  in_progress: {
    label: "In Progress",
    className: "border-blue-300 bg-blue-50 text-blue-700",
  },
  resolved: {
    label: "Resolved",
    className: "border-emerald-300 bg-emerald-50 text-emerald-700",
  },
  wont_fix: {
    label: "Won't Fix",
    className: "border-zinc-300 bg-zinc-100 text-zinc-600",
  },
};

export const STATUS_ORDER: FeedbackStatus[] = [
  "open",
  "in_progress",
  "resolved",
  "wont_fix",
];
