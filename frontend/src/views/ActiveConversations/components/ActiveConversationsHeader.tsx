import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { InfoIcon } from "lucide-react";
import { Link } from "react-router-dom";
import type { SentimentFilter } from "../helpers/activeConversations.types";
import { Switch } from "@/components/switch";

interface HeaderProps {
  title: string;
  sentiment: SentimentFilter;
  category: string;
  categories: string[];
  includeFeedback?: boolean;
  onChange: (key: "sentiment" | "category" | "include_feedback", value: string) => void;
}

const SENTIMENT_OPTIONS: { label: string; value: SentimentFilter }[] = [
  { label: "All Sentiments", value: "all" },
  { label: "Good", value: "good" },
  { label: "Neutral", value: "neutral" },
  { label: "Bad", value: "bad" },
];

export function ActiveConversationsHeader({ title, sentiment, category, categories, includeFeedback = false, onChange }: HeaderProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4 md:mb-6">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Badge className="text-xs bg-green-600">Live</Badge>
        <div className="relative group">
          <InfoIcon className="w-4 h-4 text-gray-400 cursor-help" />
          <div className="absolute z-10 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg">
            Real-time conversations that require your attention
            <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-800"></div>
          </div>
        </div>
      </div>
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
        <Select value={sentiment} onValueChange={(v) => onChange("sentiment", v)}>
          <SelectTrigger className="w-full sm:w-[170px]">
            <SelectValue placeholder="All Sentiments" />
          </SelectTrigger>
          <SelectContent>
            {SENTIMENT_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={category} onValueChange={(v) => onChange("category", v)}>
          <SelectTrigger className="w-full sm:w-[170px]">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent>
            {(categories.length ? categories : ["all", "Product Inquiry", "Technical Support", "Billing Questions", "Other"]).map((c) => {
              const value = String(c);
              const label = value === "all" ? "All Categories" : value;
              return (
                <SelectItem key={value} value={value}>{label}</SelectItem>
              );
            })}
          </SelectContent>
        </Select>

        <div className="hidden sm:block h-6 w-px bg-border mx-1" />
        <Link to="/transcripts?status=in_progress&status=takeover" className="sm:ml-1">
          <Button variant="ghost" size="sm" className="rounded-md px-3 w-full sm:w-auto">View all</Button>
        </Link>
      </div>
    </div>
  );
}

export default ActiveConversationsHeader;