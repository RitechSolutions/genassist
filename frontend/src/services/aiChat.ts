import { apiRequest } from "@/config/api";

export const askAIQuestion = async (
  conversation_id: string,
  question: string
) => {
  try {
    const response = await apiRequest<{ answer: string }>(
      "post",
      "/audio/ask_question",
      {
        conversation_id,
        question,
      }
    );
    return response ?? { answer: "Sorry, I couldn't process your request." };
  } catch (error) {
    console.error("Error in AI Chat request:", error);
    return { answer: "Sorry, I couldn't process your request." };
  }
};
