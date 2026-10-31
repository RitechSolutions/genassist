import { formatDuration as sharedFormatDuration } from "@/helpers/duration";
import {
  calendarDayNumber,
  dateParts,
  displayTimeZone,
} from "@/helpers/timeZone";

export const formatDuration = (seconds: number | undefined): string => {
	return sharedFormatDuration(seconds ?? 0);
};

export const formatDateTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  const daysAgo = calendarDayNumber(new Date()) - calendarDayNumber(date);
  const timeZone = displayTimeZone();

  const timeStr = date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  });

  if (daysAgo === 0) {
    return `Today, ${timeStr}`;
  }

  if (daysAgo === 1) {
    return `Yesterday, ${timeStr}`;
  }

  const dateStr = date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    timeZone,
  });
  return `${dateStr}, ${timeStr}`;
};

 export const formatMessageTime = (
    createTime: string | number | undefined
  ): string => {
    if (!createTime) return "";

    try {
      let date: Date;

      if (typeof createTime === "number") {
        date = new Date(createTime * 1000);
      }
      else if (typeof createTime === "string") {
        if (createTime.includes("T") || createTime.includes(" ")) {
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

      const { hours, minutes, seconds } = dateParts(date);
      return [hours, minutes, seconds]
        .map((part) => String(part).padStart(2, "0"))
        .join(":");
    } catch (error) {
      return "";
    }
  };