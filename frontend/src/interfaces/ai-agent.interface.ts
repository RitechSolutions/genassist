export interface AIAgentFile {
  id: string;
  name: string;
}

export interface AIAgent {
  id: string;
  name: string;
  provider: string;
  model: string;
  files?: AIAgentFile[];
  filesCount: number;
  systemPrompt?: string;
} 