import { useQuery } from "@tanstack/react-query";

import { fetchTopicOptions } from "@/services/topicOptions";

/** Configured and default conversation topics for the topic filters. */
export const useTopicOptions = () =>
  useQuery({
    queryKey: ["topic-options"],
    queryFn: fetchTopicOptions,
  });
