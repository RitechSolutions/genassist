export const formatCallDuration = (time: string | number | null | undefined): string => {
  if (typeof time === 'number') {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      return `${hours}h ${remainingMinutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  }
  
  if (!time || typeof time !== "string") return "0m";

  const timeParts = time.split(":").map(Number);
  if (timeParts.length !== 3 || timeParts.some(isNaN)) {
    return "0m";
  }

  const [hours, minutes, seconds] = timeParts;
  const totalMinutes = hours * 60 + minutes + (seconds > 0 ? 1 : 0);

  return totalMinutes >= 60 ? `${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m` : `${totalMinutes}m`;
};

// Matches the backend's `str(timedelta(...))` output, which grows a day prefix
// past 24h: "0:08:34", "23:59:59", "1 day, 0:00:00", "2 days, 7:33:20".
const DURATION_STRING_RE = /^(?:(\d+)\s+days?,\s*)?(\d+):([0-5]?\d):([0-5]?\d)$/;

export const parseDurationToSeconds = (time: string | number | null | undefined): number | null => {
  if (typeof time === "number") {
    return Number.isFinite(time) && time >= 0 ? Math.floor(time) : null;
  }

  if (!time || typeof time !== "string") return null;

  const match = DURATION_STRING_RE.exec(time.trim());
  if (!match) return null;

  const [, days, hours, minutes, seconds] = match;
  return Number(days ?? 0) * 86400 + Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds);
};

// Exact duration — no rounding to the nearest minute, seconds always shown.
export const formatExactDuration = (time: string | number | null | undefined): string => {
  const totalSeconds = parseDurationToSeconds(time);
  if (totalSeconds === null) return "0s";

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
};

export const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const callTime = new Date(timestamp);
  const differenceInSeconds = Math.floor((now.getTime() - callTime.getTime()) / 1000);

  const ago = (count: number, unit: string) =>
    `${count} ${count === 1 ? unit : `${unit}s`} ago`;

  if (differenceInSeconds < 60) return "Just now";
  if (differenceInSeconds < 3600) return `${Math.floor(differenceInSeconds / 60)} min ago`;
  if (differenceInSeconds < 86400) return ago(Math.floor(differenceInSeconds / 3600), "hour");
  if (differenceInSeconds < 604800) return ago(Math.floor(differenceInSeconds / 86400), "day");
  return ago(Math.floor(differenceInSeconds / 604800), "week");
};

// Operator KPI averages arrive from the backend as pre-formatted percent strings
// ("86.0%"), so any arithmetic on them has to strip the suffix first — otherwise
// Number("86.0%") is NaN and the NaN propagates into the rendered value.
export const parsePercentValue = (value: string | number | null | undefined): number | null => {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;

  const stripped = value.trim().replace(/%$/, "").trim();
  if (stripped === "") return null; // Number("") is 0, which would read as a real 0%

  const parsed = Number(stripped);
  return Number.isFinite(parsed) ? parsed : null;
};

export const formatPercentage = (value: number | string | undefined | null): string => {
  if (value === undefined || value === null || isNaN(Number(value))) {
    return "0%";
  }
  
  return `${Math.round(Number(value) * 100)}%`;
};

export const getInitials = (firstName = "", lastName = ""): string => {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}; 