import React from 'react';
import { Checkbox } from '@/components/checkbox';
import { Input } from '@/components/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Database, GitBranchPlus, Lightbulb } from 'lucide-react';

interface VectorDB {
  enabled: boolean;
  type: string;
  collection_name: string;
  [key: string]: unknown;
}

interface GraphDB {
  enabled: boolean;
  type: string;
  [key: string]: unknown;
}

interface LightRAG {
  enabled: boolean;
  search_mode: string;
  [key: string]: unknown;
}

interface RagConfig {
  enabled: boolean;
  vector_db: VectorDB;
  graph_db: GraphDB;
  light_rag: LightRAG;
  [key: string]: unknown;
}

interface RagConfigFormProps {
  ragConfig: RagConfig;
  onChange: (updatedConfig: RagConfig) => void;
}

const RagConfigForm: React.FC<RagConfigFormProps> = ({ ragConfig, onChange }) => {
  const handleEnableChange = (checked: boolean) => {
    onChange({
      ...ragConfig,
      enabled: checked
    });
  };

  const handleVectorDbChange = (name: string, value: unknown) => {
    onChange({
      ...ragConfig,
      vector_db: {
        ...ragConfig.vector_db,
        [name]: value
      }
    });
  };

  const handleGraphDbChange = (name: string, value: unknown) => {
    onChange({
      ...ragConfig,
      graph_db: {
        ...ragConfig.graph_db,
        [name]: value
      }
    });
  };
  
  const handleLightRagChange = (name: string, value: unknown) => {
    onChange({
      ...ragConfig,
      light_rag: {
        ...ragConfig.light_rag,
        [name]: value
      }
    });
  };

  return (
    <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
      <div className="flex flex-col space-y-1.5 p-6">
        <h3 className="text-2xl font-semibold leading-none tracking-tight">RAG Configuration</h3>
        <p className="text-sm text-muted-foreground">
          Configure Retrieval Augmented Generation settings
        </p>
      </div>
      
      <div className="p-6 pt-0">
        <div className="flex items-center space-x-2 pb-4">
          <Checkbox
            id="rag_enabled"
            checked={ragConfig.enabled}
            onCheckedChange={handleEnableChange}
          />
          <label 
            htmlFor="rag_enabled" 
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Enable RAG
          </label>
        </div>
        
        {ragConfig.enabled && (
          <div className="space-y-6">
            <div className="rounded-md border p-4">
              <div className="flex items-center gap-2 mb-4">
                <Database className="h-5 w-5 text-muted-foreground" />
                <h4 className="text-sm font-semibold">Vector Database</h4>
              </div>
              
              <div className="flex items-center space-x-2 mb-4">
                <Checkbox
                  id="vector_db_enabled"
                  checked={ragConfig.vector_db.enabled}
                  onCheckedChange={(checked) => handleVectorDbChange('enabled', checked)}
                />
                <label 
                  htmlFor="vector_db_enabled" 
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Enable Vector Database
                </label>
              </div>
              
              {ragConfig.vector_db.enabled && (
                <div className="space-y-4 pl-6 border-l">
                  <div className="grid gap-2">
                    <label htmlFor="vector_db_type" className="text-sm font-medium leading-none">
                      Vector DB Type
                    </label>
                    <Select 
                      value={ragConfig.vector_db.type} 
                      onValueChange={(value) => handleVectorDbChange('type', value)}
                    >
                      <SelectTrigger id="vector_db_type" className="w-full">
                        <SelectValue placeholder="Select vector database type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="chroma">Chroma</SelectItem>
                        <SelectItem value="faiss">FAISS</SelectItem>
                        <SelectItem value="pinecone">Pinecone</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="grid gap-2">
                    <label htmlFor="collection_name" className="text-sm font-medium leading-none">
                      Collection Name
                    </label>
                    <Input
                      id="collection_name"
                      value={ragConfig.vector_db.collection_name}
                      onChange={(e) => handleVectorDbChange('collection_name', e.target.value)}
                      placeholder="Default: agent_id_collection"
                    />
                  </div>
                </div>
              )}
            </div>
            
            <div className="rounded-md border p-4">
              <div className="flex items-center gap-2 mb-4">
                <GitBranchPlus className="h-5 w-5 text-muted-foreground" />
                <h4 className="text-sm font-semibold">Graph Database</h4>
              </div>
              
              <div className="flex items-center space-x-2 mb-4">
                <Checkbox
                  id="graph_db_enabled"
                  checked={ragConfig.graph_db.enabled}
                  onCheckedChange={(checked) => handleGraphDbChange('enabled', checked)}
                />
                <label 
                  htmlFor="graph_db_enabled" 
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Enable Graph Database
                </label>
              </div>
              
              {ragConfig.graph_db.enabled && (
                <div className="space-y-4 pl-6 border-l">
                  <div className="grid gap-2">
                    <label htmlFor="graph_db_type" className="text-sm font-medium leading-none">
                      Graph DB Type
                    </label>
                    <Select 
                      value={ragConfig.graph_db.type} 
                      onValueChange={(value) => handleGraphDbChange('type', value)}
                    >
                      <SelectTrigger id="graph_db_type" className="w-full">
                        <SelectValue placeholder="Select graph database type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="neo4j">Neo4j</SelectItem>
                        <SelectItem value="networkx">NetworkX</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>
            
            <div className="rounded-md border p-4">
              <div className="flex items-center gap-2 mb-4">
                <Lightbulb className="h-5 w-5 text-muted-foreground" />
                <h4 className="text-sm font-semibold">LightRAG</h4>
              </div>
              
              <div className="flex items-center space-x-2 mb-4">
                <Checkbox
                  id="light_rag_enabled"
                  checked={ragConfig.light_rag?.enabled || false}
                  onCheckedChange={(checked) => handleLightRagChange('enabled', checked)}
                />
                <label 
                  htmlFor="light_rag_enabled" 
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Enable LightRAG
                </label>
              </div>
              
              {ragConfig.light_rag?.enabled && (
                <div className="space-y-4 pl-6 border-l">
                  <div className="grid gap-2">
                    <label htmlFor="light_rag_search_mode" className="text-sm font-medium leading-none">
                      Search Mode
                    </label>
                    <Select 
                      value={ragConfig.light_rag?.search_mode || 'mix'} 
                      onValueChange={(value) => handleLightRagChange('search_mode', value)}
                    >
                      <SelectTrigger id="light_rag_search_mode" className="w-full">
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
                    <p className="text-xs text-muted-foreground italic">
                      Mix mode integrates knowledge graph and vector retrieval for best results.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RagConfigForm; 