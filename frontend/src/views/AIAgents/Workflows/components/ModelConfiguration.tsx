import React from "react";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { useQuery } from "@tanstack/react-query";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";

export interface ModelConfig {
  providerId: string;
}

export interface ModelConfigurationProps {
  id: string;
  config: ModelConfig;
  onConfigChange: (config: ModelConfig) => void;
}

export const ModelConfiguration: React.FC<ModelConfigurationProps> = ({
  id,
  config,
  onConfigChange,
}) => {

  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });

  const handleProviderSelect = (providerId: string) => {
    const provider = providers.find((p) => p.id === providerId);
    if (provider) {
      onConfigChange({
        ...config,
        providerId
      });
    }
  };

  const providerId = config.providerId;
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor={`provider-select-${id}`}>Select Provider</Label>
        <Select value={providerId} onValueChange={handleProviderSelect}>
          <SelectTrigger id={`provider-select-${id}`}>
            <SelectValue placeholder="Select provider" />
          </SelectTrigger>
          <SelectContent>
            {providers.map((provider) => (
              <SelectItem key={provider.id} value={provider.id}>
                {provider.name} ({provider.llm_model_provider} -{" "}
                {provider.llm_model})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
};
