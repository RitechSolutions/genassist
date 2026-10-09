import { apiRequest } from "@/config/api";

export interface TopicOption {
  name: string;
  subtopics: string[];
}

export const fetchTopicOptions = async (): Promise<TopicOption[]> => {
  const response = await apiRequest<{ topics: TopicOption[] }>(
    "GET",
    "conversations/topic-options",
  );
  return Array.isArray(response?.topics) ? response.topics : [];
};
