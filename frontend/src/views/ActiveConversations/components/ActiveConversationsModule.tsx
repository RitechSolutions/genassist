import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "@/components/card";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import {
  getSentimentFromHostility,
  HOSTILITY_POSITIVE_MAX,
  HOSTILITY_NEUTRAL_MAX,
} from "@/views/Transcripts/helpers/formatting";
import type { TranscriptEntry } from "@/interfaces/transcript.interface";
import { fetchTopicsReport } from "@/services/metrics";
import ActiveConversationsHeader from "./ActiveConversationsHeader";
import ActiveConversationsSummary from "./ActiveConversationsSummary";
import ActiveConversationsList from "./ActiveConversationsList";
import type {
  NormalizedConversation,
  SentimentFilter,
} from "../helpers/activeConversations.types";

const isHighHostility = (score: number): boolean =>
  getSentimentFromHostility(score) === "negative";

const parseTimestampMs = (value: string | undefined): number => {
  if (!value) return 0;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? ms : 0;
};

type Props = {
  title?: string;
  items: ActiveConversation[];
  isLoading: boolean;
  error: Error | null;
  onRetry?: () => void;
  onItemClick?: (item: ActiveConversation) => void;
  totalCount?: number;
};


export function ActiveConversationsModule({
  title = "Active Conversations",
  items,
  isLoading,
  error,
  onRetry,
  onItemClick,
  totalCount,
}: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [categories, setCategories] = useState<string[]>([]);

  const rawSentiment = (searchParams.get("sentiment") || "all").toLowerCase();
  const sentimentParam = (rawSentiment === "positive"
    ? "good"
    : rawSentiment === "negative"
    ? "bad"
    : rawSentiment) as SentimentFilter;
  const categoryParam = (searchParams.get("category") || "all");
  const includeFeedbackParam = (searchParams.get("include_feedback") || "false").toLowerCase() === "true";

  useEffect(() => {
    let mounted = true;
    fetchTopicsReport()
      .then((report) => {
        if (!mounted || !report) return;
        const topics = Object.keys(report.details || {});
        if (topics.length > 0) setCategories(["all", ...topics]);
        else setCategories(["all", "booking", "billing", "tech support"]);
      })
      .catch(() => setCategories(["all", "booking", "billing", "tech support"]));
    return () => {
      mounted = false;
    };
  }, []);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (key === "sentiment") {
      if (value === "" || value === "all") {
        next.delete("sentiment");
        next.delete("hostility_positive_max");
        next.delete("hostility_neutral_max");
      } else {
        const apiSentiment = value === "good" ? "positive" : value === "bad" ? "negative" : value;
        next.set("sentiment", apiSentiment);
        next.set("hostility_positive_max", String(HOSTILITY_POSITIVE_MAX));
        next.set("hostility_neutral_max", String(HOSTILITY_NEUTRAL_MAX));
      }
    } else if (key === "include_feedback") {
      if (value === "true" || value === "false") {
        next.set("include_feedback", value);
      } else {
        next.delete("include_feedback");
      }
    } else {
      if (value === "" || value === "all") next.delete(key);
      else next.set(key, value);
    }
    if (key !== "page") next.set("page", "1");
    setSearchParams(next, { replace: true });
  };

  const normalized: NormalizedConversation[] = useMemo(() => {
    return (items || []).map((item, index) => {
      const hostility = Number(item.in_progress_hostility_score || 0);
      const eff = getSentimentFromHostility(hostility);
      return {
        ...item,
        idx: index + 1,
        effectiveSentiment: eff as "positive" | "neutral" | "negative",
      };
    });
  }, [items]);

  const globalTotal = typeof totalCount === "number" ? totalCount : normalized.length;
  const globalCounts = useMemo(() => {
    let good = 0, neutral = 0, bad = 0;
    for (const i of normalized) {
      if (i.effectiveSentiment === "positive") good++;
      else if (i.effectiveSentiment === "neutral") neutral++;
      else bad++;
    }
    return { bad, neutral, good };
  }, [normalized]);

  const filtered = useMemo(() => {
    if (sentimentParam === "all") return normalized;
    const wanted = sentimentParam === "good" ? "positive" : sentimentParam === "bad" ? "negative" : "neutral";
    return normalized.filter((i) => i.effectiveSentiment === wanted);
  }, [normalized, sentimentParam]);

  const total = filtered.length;

  // Get sentiment priority: Bad (negative) = 0, Neutral = 1, Good (positive) = 2
  const getSentimentPriority = (sentiment: string): number => {
    if (sentiment === "negative") return 0; // Bad first
    if (sentiment === "neutral") return 1;   // Neutral second
    return 2; // Good (positive) last
  };

  // Sort by worst sentiment first (Bad → Neutral → Good), then by newest timestamp
  const ordered = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const aSentiment = a.effectiveSentiment || "";
      const bSentiment = b.effectiveSentiment || "";
      const aPriority = getSentimentPriority(aSentiment);
      const bPriority = getSentimentPriority(bSentiment);

      // First sort by sentiment priority (Bad first, then Neutral, then Good)
      if (aPriority !== bPriority) {
        return aPriority - bPriority;
      }

      // Within the same sentiment, sort by newest first (most recent timestamp)
      const timeDiff = parseTimestampMs(b.timestamp) - parseTimestampMs(a.timestamp);
      if (timeDiff !== 0) return timeDiff;

      // Fallback: use ID for consistent ordering
      return (b.id || "").localeCompare(a.id || "");
    });
  }, [filtered]);

  // Show only the last 3 conversations
  const pageItems = ordered.slice(0, 3);

  return (
    <Card className="p-6 mb-5 shadow-sm animate-fade-up bg-white border border-border rounded-xl">
      <ActiveConversationsHeader title={title} />

      <div className="flex gap-6">
        {/* Left Section - Sentiment Summary */}
        <div className="w-60 shrink-0">
          <ActiveConversationsSummary total={globalTotal} counts={globalCounts} loading={isLoading} />
        </div>

        {/* Right Section - Conversation List */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex flex-col rounded-2xl overflow-hidden bg-muted/40 min-w-0 w-full">
            <ActiveConversationsList
              items={pageItems.map((i) => ({ ...i, transcript: getLatestMessagePreview(i.transcript) }))}
              isLoading={isLoading}
              error={error}
              onRetry={onRetry}
              onClickRow={(row) => onItemClick?.(row as unknown as ActiveConversation)}
            />
          </div>
        </div>
      </div>
    </Card>
  );
}

export default ActiveConversationsModule;

function getLatestMessagePreview(transcript: string | TranscriptEntry[] | unknown): string {
  if (!transcript) return "";
  if (Array.isArray(transcript)) {
    if (transcript.length === 0) return "";
    const last = transcript[transcript.length - 1] as Partial<TranscriptEntry>;
    const speaker = (last && (last as Partial<TranscriptEntry>).speaker) ? String((last as Partial<TranscriptEntry>).speaker) : "";
    const text = (last && (last as Partial<TranscriptEntry>).text) ? String((last as Partial<TranscriptEntry>).text) : "";
    return speaker ? `${capitalize(speaker)}: ${text}` : text;
  }
  if (typeof transcript === "string") {
    try {
      const parsed = JSON.parse(transcript);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const last: TranscriptEntry = parsed[parsed.length - 1] as TranscriptEntry;
        const speaker = (last.speaker || "").toString();
        const text = (last.text || "").toString();
        return speaker ? `${capitalize(speaker)}: ${text}` : text;
      }
    } catch {
      // ignore
    }
    return transcript;
  }
  return "";
}

function capitalize(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}