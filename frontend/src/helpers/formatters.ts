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

export const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const callTime = new Date(timestamp);
  const differenceInSeconds = Math.floor((now.getTime() - callTime.getTime()) / 1000);

  if (differenceInSeconds < 60) return "Just now";
  if (differenceInSeconds < 3600) return `${Math.floor(differenceInSeconds / 60)} min ago`;
  if (differenceInSeconds < 86400) return `${Math.floor(differenceInSeconds / 3600)} hours ago`;
  if (differenceInSeconds < 604800) return `${Math.floor(differenceInSeconds / 86400)} days ago`;
  return `${Math.floor(differenceInSeconds / 604800)} weeks ago`;
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