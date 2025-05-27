import React, { useState } from 'react';
import { Label } from '@/components/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Input } from '@/components/input';
import { Slider } from '@/components/slider';
import { getNodeColors } from '../utils/nodeColors';
import { Switch } from '@/components/switch';
import { useQuery } from '@tanstack/react-query';
import { getAllLLMProviders } from '@/services/llmProviders';
import { LLMProvider } from '@/interfaces/llmProvider.interface';


export interface LocalModelConfig {
  provider?: string;
  model?: string;
  apiKey?: string;
  temperature?: number;
  maxTokens?: number;
}
export interface ModelConfig {
  providerId: string;
  localConfig?: LocalModelConfig;
}

export interface ModelConfigurationProps {
  id: string;
  config: ModelConfig;
  onConfigChange: (config: ModelConfig) => void;
  useExistingProvider?: boolean;
}

export const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'mistral', label: 'Mistral AI' },
  { value: 'custom', label: 'Custom Provider' }
];

export const getModelOptions = (provider: string) => {
  switch (provider) {
    case 'openai':
      return [
        { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
        { value: 'gpt-4', label: 'GPT-4' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' }
      ];
    case 'anthropic':
      return [
        { value: 'claude-2', label: 'Claude 2' },
        { value: 'claude-instant', label: 'Claude Instant' },
        { value: 'claude-3-opus', label: 'Claude 3 Opus' },
        { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' }
      ];
    case 'mistral':
      return [
        { value: 'mistral-7b', label: 'Mistral 7B' },
        { value: 'mistral-medium', label: 'Mistral Medium' },
        { value: 'mistral-large', label: 'Mistral Large' }
      ];
    default:
      return [
        { value: 'custom-model', label: 'Custom Model' }
      ];
  }
};

export const ModelConfiguration: React.FC<ModelConfigurationProps> = ({
  id,
  config,
  onConfigChange,
  useExistingProvider = true
}) => {
  const colors = getNodeColors('llmModelNode');

  const { data: providers = [] } = useQuery({
    queryKey: ['llmProviders'],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter(p => p.is_active === 1)
  });

  const handleChange = (key: keyof LocalModelConfig, value: string | number | boolean) => {
    onConfigChange({
      ...config,
      localConfig: {
        ...config.localConfig,
        [key]: value
      }
    });
  };

  const handleProviderSelect = (providerId: string) => {
    const provider = providers.find(p => p.id === providerId);
    if (provider) {
      onConfigChange({
        ...config,
        providerId,
        localConfig: {
          provider: provider.llm_model_provider,
          model: provider.llm_model,
          apiKey: provider.connection_data.api_key as string,
          temperature: provider.connection_data.temperature as number ?? 0.7,
          maxTokens: provider.connection_data.max_tokens as number ?? 1024
        }
      });
    }
  };

  const providerId = config.providerId;
  const localConfig = config.localConfig;
  return (
    <div className="space-y-4">
      {useExistingProvider ? (
        <div className="space-y-2">
          <Label htmlFor={`provider-select-${id}`}>Select Provider</Label>
          <Select 
            value={providerId} 
            onValueChange={handleProviderSelect}
          >
            <SelectTrigger id={`provider-select-${id}`}>
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              {providers.map(provider => (
                <SelectItem key={provider.id} value={provider.id}>
                  {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : (
        <>
          {/* Provider Selection */}
          <div className="space-y-2">
            <Label htmlFor={`provider-${id}`}>Provider</Label>
            <Select 
              value={localConfig.provider} 
              onValueChange={value => handleChange('provider', value)}
            >
              <SelectTrigger id={`provider-${id}`}>
                <SelectValue placeholder="Select provider" />
              </SelectTrigger>
              <SelectContent>
                {providerOptions.map(option => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          {/* Model Selection */}
          <div className="space-y-2">
            <Label htmlFor={`model-${id}`}>Model</Label>
            <Select 
              value={localConfig.model} 
              onValueChange={value => handleChange('model', value)}
            >
              <SelectTrigger id={`model-${id}`}>
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {getModelOptions(localConfig.provider).map(option => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          {/* API Key */}
          <div className="space-y-2">
            <Label htmlFor={`apiKey-${id}`}>API Key</Label>
            <Input
              id={`apiKey-${id}`}
              type="password"
              value={localConfig.apiKey}
              onChange={e => handleChange('apiKey', e.target.value)}
              placeholder="Enter API key..."
            />
          </div>
          
          {/* Temperature */}
          <div className="space-y-2">
            <Label htmlFor={`temperature-${id}`}>Temperature: {localConfig.temperature}</Label>
            <Slider
              id={`temperature-${id}`}
              min={0}
              max={1}
              step={0.1}
              value={[localConfig.temperature]}
              onValueChange={values => handleChange('temperature', values[0])}
              className={`${colors.focus}`}
            />
          </div>
          
          {/* Max Tokens */}
          <div className="space-y-2">
            <Label htmlFor={`maxTokens-${id}`}>Max Tokens: {localConfig.maxTokens}</Label>
            <Slider
              id={`maxTokens-${id}`}
              min={1}
              max={4096}
              step={1}
              value={[localConfig.maxTokens]}
              onValueChange={values => handleChange('maxTokens', values[0])}
              className={`${colors.header}`}
            />
          </div>
        </>
      )}
    </div>
  );
}; 