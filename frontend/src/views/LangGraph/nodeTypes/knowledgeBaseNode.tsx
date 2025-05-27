import React, { useState, useEffect } from 'react';
import { Handle, Position, NodeProps, useReactFlow } from 'reactflow';
import { Input } from '@/components/input';
import { Textarea } from '@/components/textarea';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { Checkbox } from '@/components/checkbox';
import { ScrollArea } from '@/components/scroll-area';
import { TestDialog } from '@/views/LangGraph/components/TestDialog';
import { HandleTooltip } from '@/views/LangGraph/components/HandleTooltip';
import { KnowledgeBaseNodeData } from '@/views/LangGraph/types/nodes';
import { createSimpleSchema } from '@/views/LangGraph/types/schemas';
import { useToast } from '@/components/use-toast';
import { Database, Play, Save, X } from 'lucide-react';
import { getAllKnowledgeItems } from '@/services/api';
import { KnowledgeItem } from '@/interfaces/knowledge.interface';
import { testKnowledgeBase } from '@/services/workflows';
import { getNodeColors } from '../utils/nodeColors';

const KnowledgeBaseNode: React.FC<NodeProps<KnowledgeBaseNodeData>> = ({ id, data, selected }) => {
  const { getEdges } = useReactFlow();
  const [name, setName] = useState(data.name || 'Knowledge Base');
  const [description, setDescription] = useState(data.description || 'Query multiple knowledge bases');
  const [selectedBases, setSelectedBases] = useState<string[]>(data.selectedBases || []);
  const [query, setQuery] = useState(data.query || '');
  const [output, setOutput] = useState(data.output || '');
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableBases, setAvailableBases] = useState<KnowledgeItem[]>([]);

  const { toast } = useToast();

  const colors = getNodeColors('knowledgeBaseNode');

  // Save configuration whenever relevant state changes
  useEffect(() => {
    saveConfiguration();
  }, [name, description, selectedBases]);

  useEffect(() => {
    const loadKnowledgeBases = async () => {
      try {
        const bases = await getAllKnowledgeItems();

        setAvailableBases(bases);
      } catch (err) {
        console.error('Failed to load knowledge bases:', err);
        toast({
          title: 'Error',
          description: 'Failed to load knowledge bases',
          variant: 'destructive',
        });
      }
    };
    loadKnowledgeBases();
  }, []);

  const saveConfiguration = () => {
    // Create input schema with query
    const inputSchema = createSimpleSchema({
      query: { type: 'string', description: 'Query to search in knowledge bases', required: true }
    });

    // Create output schema with output
    const outputSchema = createSimpleSchema({
      output: { type: 'string', description: 'Search results from knowledge bases', required: true }
    });

    if (data.updateNodeData) {
      const updatedData: Partial<KnowledgeBaseNodeData> = {
        name,
        description,
        selectedBases,
        query,
        output,
        inputSchema,
        outputSchema,
        label: name // Ensure label is always set to match name

      };
      
      data.updateNodeData(id, updatedData);
    }
  };

  const handleTest = async (inputs: Record<string, string>) => {
    setIsLoading(true);
    setError(null);
    try {
      const results = await testKnowledgeBase(inputs.query, data);
      setOutput(JSON.stringify(results, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleBase = (baseId: string) => {
    setSelectedBases(prev =>
      prev.includes(baseId)
        ? prev.filter(id => id !== baseId)
        : [...prev, baseId]
    );
  };

  return (
    <>
      <div className={`border-2 rounded-md bg-white shadow-md w-[400px] ${selected ? 'border-blue-500' : 'border-gray-200'}`}>
        {/* Node header */}
        <div className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}>
          <div className="flex items-center">
            <Database className={`h-4 w-4 text-white mr-2`} />
            <Input 
              value={name}
              onChange={e => setName(e.target.value)}
              className={`text-sm font-medium h-6 py-0 bg-transparent border-transparent ${colors.focus} text-white ${colors.placeholder}`}
              maxLength={40}
            />
          </div>
          <div className="flex space-x-1">
            <Button 
              size="icon" 
              variant="ghost" 
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Test knowledge base query"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
            <Button 
              size="icon" 
              variant="ghost" 
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Save configuration"
              onClick={saveConfiguration}
            >
              <Save className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        
        {/* Node content */}
        <div className="p-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Describe what this knowledge base node does"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Knowledge Bases</Label>
              <ScrollArea className="h-32 border rounded-md p-2">
                <div className="space-y-2">
                  {availableBases.map(base => (
                    <div key={base.id} className="flex items-center space-x-2">
                      <Checkbox
                        id={`kb-${base.id}`}
                        checked={selectedBases.includes(base.id)}
                        onCheckedChange={() => toggleBase(base.id)}
                      />
                      <Label htmlFor={`kb-${base.id}`} className="text-sm">{base.name}</Label>
                    </div>
                  ))}
                </div>
              </ScrollArea>
              <div className="text-xs text-gray-500">
                Select knowledge bases to query
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="query">Query Template</Label>
              <Textarea
                id="query"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Enter a query template"
                className="h-20 font-mono text-xs"
              />
              <div className="text-xs text-gray-500">
                Use @variable to define dynamic parameters
              </div>
            </div>
          </div>
        </div>
        
        
        {/* Output handle */}
        {data.handlers
          ?.filter((handler) => handler.type === "source")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={
                handler.type === "source" ? Position.Right : Position.Left
              }
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
        {data.handlers
          ?.filter((handler) => handler.type === "target")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={
                handler.type === "source" ? Position.Right : Position.Left
              }
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test ${name}`}
        description="Enter a query to test against selected knowledge bases"
        inputFields={[
          {
            id: 'query',
            label: 'Query',
            type: 'text',
            required: true,
            placeholder: 'Enter your query',
          },
        ]}
        onRun={handleTest}
        output={output}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default KnowledgeBaseNode; 