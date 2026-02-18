// Format response time from percentage to milliseconds
export const formatResponseTime = (responseTimeStr: string): string => {
  // Parse percentage value (e.g., "85.50%" -> 85.50)
  const percentageMatch = responseTimeStr.match(/(\d+\.?\d*)/);
  if (!percentageMatch) return "0ms";

  const percentage = parseFloat(percentageMatch[1]);
  // Convert percentage to milliseconds (0-100% -> 0-1000ms scale)
  const milliseconds = Math.round(percentage * 10);

  return `${milliseconds}ms`;
};
