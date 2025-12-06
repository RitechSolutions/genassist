import React from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/select';
import { Switch } from '@/components/switch';
import { Lightbulb } from 'lucide-react';

export interface LightRag {
  enabled: boolean;
  search_mode: string;
  [key: string]: unknown;
}

interface LightRagConfigFormProps {
  lightRagConfig: LightRag;
  onChange: (updatedConfig: LightRag) => void;
}

const LightRagConfigForm: React.FC<LightRagConfigFormProps> = ({ lightRagConfig, onChange }) => {
  const handleLightRagChange = (name: string, value: unknown) => {
    onChange({
      ...lightRagConfig,
      [name]: value
    });
  };

  return (
    <div className="bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-gray-500" />
          <div>
            <div className="font-medium">LightRAG</div>
            <p className="text-sm text-gray-500">
              Enable LightRAG for advanced retrieval capabilities
            </p>
          </div>
        </div>
        <Switch
          checked={lightRagConfig.enabled || false}
          onCheckedChange={(checked) => handleLightRagChange('enabled', checked)}
        />
      </div>

      {lightRagConfig.enabled && (
        <div className="p-4 pt-0 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Search Mode
            </label>
            <Select
              value={lightRagConfig.search_mode || 'mix'}
              onValueChange={(value) => handleLightRagChange('search_mode', value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select search mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="naive">Naive</SelectItem>
                <SelectItem value="local">Local</SelectItem>
                <SelectItem value="global">Global</SelectItem>
                <SelectItem value="hybrid">Hybrid</SelectItem>
                <SelectItem value="mix">Mix (Recommended)</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500 mt-2">
              Mix mode integrates knowledge graph and vector retrieval for best results.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default LightRagConfigForm;
