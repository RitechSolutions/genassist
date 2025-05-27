import { AIAgent } from "@/interfaces/ai-agent.interface";

export interface AIProvider {
  id: string;
  name: string;
  models: AIModel[];
}

export interface AIModel {
  id: string;
  name: string;
  providerId: string;
}

export const aiProviders: AIProvider[] = [
  {
    id: "openai",
    name: "OpenAI",
    models: []
  },
  {
    id: "anthropic",
    name: "Anthropic",
    models: []
  },
  {
    id: "google",
    name: "Google",
    models: []
  },
  {
    id: "mistral",
    name: "Mistral AI",
    models: []
  }
];

export const aiModels: AIModel[] = [
  { id: "gpt-4o", name: "GPT-4o", providerId: "openai" },
  { id: "gpt-4", name: "GPT-4", providerId: "openai" },
  { id: "gpt-3.5-turbo", name: "GPT-3.5 Turbo", providerId: "openai" },
  
  { id: "claude-3-opus", name: "Claude 3 Opus", providerId: "anthropic" },
  { id: "claude-3-sonnet", name: "Claude 3 Sonnet", providerId: "anthropic" },
  { id: "claude-3-haiku", name: "Claude 3 Haiku", providerId: "anthropic" },
  
  { id: "gemini-pro", name: "Gemini Pro", providerId: "google" },
  { id: "gemini-ultra", name: "Gemini Ultra", providerId: "google" },
  
  { id: "mistral-large", name: "Mistral Large", providerId: "mistral" },
  { id: "mistral-medium", name: "Mistral Medium", providerId: "mistral" },
  { id: "mistral-small", name: "Mistral Small", providerId: "mistral" }
];

aiProviders.forEach(provider => {
  provider.models = aiModels.filter(model => model.providerId === provider.id);
});

const mockAgents: AIAgent[] = [
  {
    id: "1",
    name: "Top Agent",
    provider: "OpenAI",
    model: "gpt-4o",
    files: [
      { id: "1", name: "Document 1" },
      { id: "2", name: "Document 2" },
    ],
    filesCount: 5,
    systemPrompt: "You are a helpful customer service assistant."
  },
  {
    id: "2",
    name: "Sales Agent",
    provider: "Anthropic",
    model: "claude-3-opus",
    files: [
      { id: "3", name: "Sales script" },
    ],
    filesCount: 1,
    systemPrompt: "You are a sales assistant focused on helping customers find the right products."
  },
  {
    id: "3",
    name: "Support Agent",
    provider: "Google",
    model: "gemini-pro",
    files: [
      { id: "4", name: "FAQ" },
      { id: "5", name: "Troubleshooting guide" },
      { id: "6", name: "Return policy" },
    ],
    filesCount: 3,
    systemPrompt: "You are a technical support specialist helping customers resolve issues."
  }
];

export const getProviders = async (): Promise<AIProvider[]> => {
  return Promise.resolve(aiProviders);
};

export const getModelsByProvider = async (providerId: string): Promise<AIModel[]> => {
  const provider = aiProviders.find(p => p.id === providerId);
  return Promise.resolve(provider?.models || []);
};

export const getAllAgents = async (): Promise<AIAgent[]> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(mockAgents);
    }, 500);
  });
};

export const getAgentById = async (id: string): Promise<AIAgent | undefined> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      const agent = mockAgents.find(agent => agent.id === id);
      resolve(agent);
    }, 500);
  });
};

export const createAgent = async (agentData: Omit<AIAgent, 'id'>): Promise<AIAgent> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      const newAgent: AIAgent = {
        ...agentData,
        id: Math.random().toString(36).substring(2, 11),
        files: agentData.files || [],
        filesCount: agentData.files?.length || 0,
      };
      resolve(newAgent);
    }, 500);
  });
};

export const updateAgent = async (id: string, agentData: Partial<AIAgent>): Promise<AIAgent> => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const agentIndex = mockAgents.findIndex(agent => agent.id === id);
      
      if (agentIndex === -1) {
        reject(new Error("Agent not found"));
        return;
      }
      
      const updatedAgent = {
        ...mockAgents[agentIndex],
        ...agentData,
        id
      };
      resolve(updatedAgent);
    }, 500);
  });
};

export const deleteAgent = async (id: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const agentIndex = mockAgents.findIndex(agent => agent.id === id);
      
      if (agentIndex === -1) {
        reject(new Error("Agent not found"));
        return;
      }
      resolve();
    }, 500);
  });
}; 