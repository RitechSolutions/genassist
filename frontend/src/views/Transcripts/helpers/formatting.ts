import { Transcript } from "@/interfaces/transcript.interface";

// Hostility constants for live conversations
export const HOSTILITY_POSITIVE_MAX = 20;
export const HOSTILITY_NEUTRAL_MAX = 49;

// Derives sentiment from hostility score for live conversations
export const getSentimentFromHostility = (hostilityScore: number): string => {
  if (hostilityScore <= HOSTILITY_POSITIVE_MAX) {
    return 'positive';
  } else if (hostilityScore <= HOSTILITY_NEUTRAL_MAX) {
    return 'neutral';
  } else {
    return 'negative';
  }
};

// Gets the effective sentiment for a transcript
export const getEffectiveSentiment = (transcript: Transcript): string => {
  const isLive = transcript?.status === "in_progress" || transcript?.status === "takeover";
  
  if (isLive) {
    // Sentiment from hostility score
    const hostilityScore = transcript.in_progress_hostility_score ?? transcript.metrics?.in_progress_hostility_score ?? 0;
    return getSentimentFromHostility(hostilityScore);
  }
  
  // Existing sentiment for finalized conversations
  return transcript.metrics?.sentiment || "neutral";
};

export const getSentimentStyles = (sentiment: string = ""): string => {
  switch ((sentiment || "").toLowerCase()) {
    case 'positive':
      return 'bg-green-100 text-green-800';
    case 'neutral':
      return 'bg-yellow-100 text-yellow-800';
    case 'negative':
      return 'bg-red-100 text-red-800';
    case 'very-bad':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

import { formatDuration as sharedFormatDuration } from "@/helpers/duration";

export const formatDuration = (durationInSeconds: number = 0): string => {
  return sharedFormatDuration(durationInSeconds);
};

export const formatCallTimestamp = (startTimeSeconds: number = 0): string => {
  if (isNaN(startTimeSeconds) || startTimeSeconds < 0) {
    return "00:00";
  }
  
  const minutes = Math.floor(startTimeSeconds / 60);
  const seconds = Math.floor(startTimeSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

export const formatDateTime = (dateString: string = ""): string => {
  try {
    if (!dateString) return "N/A";
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return "Invalid Date";
    
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    return dateString || "N/A";
  }
};

export const formatMetric = (value: number = 0, precision: number = 1): string => {
  if (typeof value !== 'number' || isNaN(value)) {
    return "0.0";
  }
  return value.toFixed(precision);
};

export const getTranscriptTypeLabel = (transcript: Transcript): string => {
  if (!transcript || !transcript.metadata) {
    return "Unknown";
  }
  return transcript.metadata.customer_speaker ? "Call" : "Chat";
}; 

export const formatMessageTime = (createTime: string | number | undefined): string => {
  if (!createTime) return "";
  
  try {
    let date: Date;
    
    if (typeof createTime === 'number') {
      date = new Date(createTime * 1000);
    } 
    else if (typeof createTime === 'string') {
      if (createTime.includes('T') || createTime.includes(' ')) {
        date = new Date(createTime);
      } else {
        const timestamp = parseInt(createTime, 10);
        if (!isNaN(timestamp)) {
          date = new Date(timestamp * 1000);
        } else {
          return "";
        }
      }
    } else {
      return "";
    }
    
    if (isNaN(date.getTime())) return "";
    
    return date.toTimeString().split(' ')[0];
  } catch (error) {
    return "";
  }
};