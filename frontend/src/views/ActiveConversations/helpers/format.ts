import { formatDuration as sharedFormatDuration } from "@/helpers/duration";

export const formatDuration = (seconds: number | undefined): string => {
	return sharedFormatDuration(seconds ?? 0);
};

export const formatDateTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (isToday) {
    return `Today, ${timeStr}`;
  }

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday, ${timeStr}`;
  }

  const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
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

      return date.toTimeString().split(" ")[0];
    } catch (error) {
      return "";
    }
  };