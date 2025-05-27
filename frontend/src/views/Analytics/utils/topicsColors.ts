import { TOPIC_COLORS } from "../constants";

export function getTopicColorMap(topics: string[]): Record<string, string> {
  const updatedMap: Record<string, string> = {};

  const sortedTopics = [...topics].sort((a, b) => a.localeCompare(b));

  let colorIndex = 0;

  for (const topic of sortedTopics) {
    if (!updatedMap[topic]) {
      updatedMap[topic] = TOPIC_COLORS[colorIndex % TOPIC_COLORS.length];
      colorIndex++;
    }
  }

  return updatedMap;
}