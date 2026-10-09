import type { TopicOption } from "@/services/topicOptions";

/**
 * Sub-topics configured for `topic`; none for "all", an unknown topic or no topic.
 * A selected `current` that is no longer configured is kept so its filter stays visible.
 */
export function subtopicsFor(
  options: TopicOption[],
  topic: string | null,
  current: string | null = null,
): string[] {
  if (!topic || topic === "all") return [];
  const subtopics = options.find((option) => option.name === topic)?.subtopics ?? [];
  if (!current || current === "all" || subtopics.includes(current)) return subtopics;
  return [...subtopics, current];
}

/**
 * Keeps selected topics no longer configured for filtering old conversations.
 * Never adds "all" or blanks.
 */
export function withCurrentOption(
  options: TopicOption[],
  current: string | null,
): TopicOption[] {
  if (!current || current === "all") return options;
  if (options.some((option) => option.name === current)) return options;
  return [...options, { name: current, subtopics: [] }];
}
