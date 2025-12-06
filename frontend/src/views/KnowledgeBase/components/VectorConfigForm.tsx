import React from 'react';
import { Input } from '@/components/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/select';
import { Switch } from '@/components/switch';
import { Database } from 'lucide-react';

export interface Vector {
  enabled: boolean;
  type: string;
  collection_name: string;
  [key: string]: unknown;
}

interface VectorConfigFormProps {
  vectorConfig: Vector;
  onChange: (updatedConfig: Vector) => void;
}

const VectorConfigForm: React.FC<VectorConfigFormProps> = ({ vectorConfig, onChange }) => {
  const handleVectorChange = (name: string, value: unknown) => {
    onChange({
      ...vectorConfig,
      [name]: value
    });
  };

  return (
    <div className="bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-gray-500" />
          <div>
            <div className="font-medium">Vector Database</div>
            <p className="text-sm text-gray-500">
              Enable vector database for semantic search
            </p>
          </div>
        </div>
        <Switch
          checked={vectorConfig.enabled || false}
          onCheckedChange={(checked) => handleVectorChange('enabled', checked)}
        />
      </div>

      {vectorConfig.enabled && (
        <div className="p-4 pt-0 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Vector DB Type
            </label>
            <Select
              value={vectorConfig.type || ''}
              onValueChange={(value) => handleVectorChange('type', value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select vector database type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="chroma">Chroma</SelectItem>
                <SelectItem value="faiss">FAISS</SelectItem>
                <SelectItem value="pinecone">Pinecone</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Collection Name
            </label>
            <Input
              value={vectorConfig.collection_name || ''}
              onChange={(e) => handleVectorChange('collection_name', e.target.value)}
              placeholder="Default: agent_id_collection"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default VectorConfigForm;
