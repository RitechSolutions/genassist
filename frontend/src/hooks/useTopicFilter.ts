import { useState } from "react";

import { useTopicOptions } from "@/hooks/useTopicOptions";
import { subtopicsFor, withCurrentOption } from "@/helpers/topicOptions";

type TopicFilter = { topic: string; subtopic: string };

const sameTopic = (value: string | null | undefined, selected: string) =>
  (value ?? "").trim().toLowerCase() === selected.trim().toLowerCase();

/** Topic and sub-topic filter state with its choices; picking a topic clears the sub-topic */
export function useTopicFilter(initialTopic = "all", initialSubtopic = "all") {
  const [filter, setFilter] = useState<TopicFilter>({
    topic: initialTopic,
    subtopic: initialSubtopic,
  });
  const { data: topicOptions = [] } = useTopicOptions();
  const { topic } = filter;
  const subtopic = topic === "all" ? "all" : filter.subtopic;
  const topicChoices = withCurrentOption(topicOptions, topic);

  return {
    topic,
    subtopic,
    topicChoices,
    subtopicChoices: subtopicsFor(topicChoices, topic, subtopic),
    setFilter,
    changeTopic: (value: string) => setFilter({ topic: value, subtopic: "all" }),
    changeSubtopic: (value: string) =>
      setFilter((current) => ({ ...current, subtopic: value })),
    matches: (item?: { topic?: string | null; subtopic?: string | null }) =>
      (topic === "all" || sameTopic(item?.topic, topic)) &&
      (subtopic === "all" || sameTopic(item?.subtopic, subtopic)),
  };
}
