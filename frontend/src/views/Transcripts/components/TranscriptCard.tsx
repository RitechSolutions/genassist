import { Badge } from "@/components/badge";
import { Transcript } from "@/interfaces/transcript.interface";
import { getSentimentStyles, getEffectiveSentiment } from "../helpers/formatting";
import { getTranscriptPreview } from "../helpers/parser";
import { Radio } from "lucide-react";

interface TranscriptCardProps {
  transcript: Transcript;
  onClick: (transcript: Transcript) => void;
  className?: string;
}

export function TranscriptCard({ transcript, onClick, className = "" }: TranscriptCardProps) {
  if (!transcript || !transcript.metadata || !transcript.metrics) {
    return (
      <div className={`p-4 rounded-lg bg-red-50 text-red-700 ${className}`}>
        Invalid transcript data
      </div>
    );
  }

  const isCall = Boolean(transcript?.recording_id);
  const isLive = transcript?.status === "in_progress" || transcript?.status === "takeover";

  return (
    <div
      className={`p-4 flex flex-col rounded-lg bg-secondary/50 cursor-pointer hover:bg-secondary/70 transition-colors ${className}`}
      onClick={() => onClick(transcript)}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {isCall ? "Call" : "Chat"} #{(transcript?.metadata?.title ?? "----").slice(0, 4)|| "Untitled"}{" "} 
          </span>
          {isLive && (
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 flex items-center gap-1 animate-pulse">
              <Radio className="w-3 h-3" />
              <span>Live</span>
            </Badge>
          )}
        </div>
        <Badge variant="secondary" className={getSentimentStyles(getEffectiveSentiment(transcript))}>
          {getEffectiveSentiment(transcript).charAt(0).toUpperCase() +
            getEffectiveSentiment(transcript).slice(1)}
        </Badge>
      </div>
      <div className="text-sm text-muted-foreground truncate" dangerouslySetInnerHTML={{ __html: getTranscriptPreview(transcript) as string }}></div>
    </div>
  );
}
