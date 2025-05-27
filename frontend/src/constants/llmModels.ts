export const llmProviderModels: Record<string, string[]> = {
    openai: ["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
    anthropic: [
      "claude-3-5-sonnet",
      "claude-3-opus",
      "claude-3-haiku",
      "claude-2",
    ],
    ollama: [
      "llama3.1:8b",
      "llama3.1:70b",
      "mistral:7b",
      "mixtral:8x7b",
      "gemma:7b",
      "gemma:2b",
    ],
    google: ["gemini-pro", "gemini-ultra", "palm-2"],
  };
  
  export const llmProviderTypes = Object.keys(llmProviderModels);
  
  export const DEFAULT_LLM_ANALYST_ID = "00000196-02d3-6032-82f1-a5fca4a356ab";