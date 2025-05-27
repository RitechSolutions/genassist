import React, { useState, useEffect, useCallback } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { ScrollArea } from '@/components/scroll-area';
import { Save, Play } from 'lucide-react';
import { TestDialog, TestInputField } from '../components/TestDialog';
import { HandleTooltip } from '../components/HandleTooltip';
import { createSimpleSchema } from '../types/schemas';
import { LLMModelNodeData } from '../types/nodes';
import { ModelConfig, ModelConfiguration } from '../components/ModelConfiguration';

const LLMModelNode: React.FC<NodeProps<LLMModelNodeData>> = ({ id, data, selected }) => {
  const [config, setConfig] = useState<ModelConfig>({
    providerId: data.providerId || 'openai',
    localConfig: {
     ...data.localConfig
    }
  });
  const [inputText, setInputText] = useState(data.inputText || '');
  const [outputText, setOutputText] = useState(data.outputText || '');
  const [mode, setMode] = useState<'normal' | 'json-parsing'>(data.jsonParsing ? 'json-parsing' : 'normal');
  const [isDirty, setIsDirty] = useState(false);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [testOutput, setTestOutput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mark form as dirty when any field changes
  useEffect(() => {
    setIsDirty(true);
  }, [config, inputText, mode]);

  // Save changes
  const saveChanges = useCallback(() => {
    if (data.updateNodeData) {
      // Create input schema
      const inputSchema = createSimpleSchema({
        prompt: { type: 'string', required: true, description: 'The prompt to send to the model' }
      });

      // Create output schema based on the selected mode
      const outputSchema = createSimpleSchema({
        response: { 
          type: mode === 'json-parsing' ? 'object' : 'string', 
          required: true, 
          description: `The model's response in ${mode === 'json-parsing' ? 'JSON' : 'text'} format` 
        },
        metadata: { 
          type: 'object', 
          required: false, 
          description: 'Additional metadata about the response' 
        }
      });

      data.updateNodeData<LLMModelNodeData>(id, {
        handlers: [
          {
            id: 'input',
            type: 'target',
            compatibility: 'text',
            schema: inputSchema
          },
          {
            id: 'output',
            type: 'source',
            compatibility: mode === 'json-parsing' ? 'json' : 'text',
            schema: outputSchema
          }
        ],
        label: 'LLM Model',
        ...config,
        inputText,
        outputText,
        jsonParsing: mode === 'json-parsing'
      });
    }
    setIsDirty(false);
  }, [id, data, config, inputText, mode]);

  // Handle receiving input
  const onInputReceived = useCallback((text: string) => {
    setInputText(text);
    // Here you would normally call the LLM
    // For now we'll just echo the input
    setOutputText(`Processed input: ${text}`);
  }, []);

  // Register the input handler
  useEffect(() => {
    if (data.onInputReceived !== onInputReceived) {
      data.onInputReceived = onInputReceived;
    }
  }, [data, onInputReceived]);

  // Test the node
  const handleTest = async (inputs: Record<string, string>) => {
    setIsLoading(true);
    setError(null);
    try {
      const testInput = inputs.prompt || '';
      
      // Simulate LLM response
      const output = {
        response: mode === 'json-parsing' 
          ? { 
              message: `Processed input: ${testInput}`,
              confidence: 0.95
            }
          : `Processed input: ${testInput}`,
        metadata: {
          model: config.localConfig?.model,
          provider: config.localConfig?.provider,
          timestamp: new Date().toISOString()
        }
      };
      
      setTestOutput(JSON.stringify(output, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred during testing');
    } finally {
      setIsLoading(false);
    }
  };

  // Define input fields for testing
  const inputFields: TestInputField[] = [
    {
      id: 'prompt',
      label: 'Test Prompt',
      type: 'text',
      placeholder: 'Enter a test prompt...',
      required: true
    }
  ];

  return (
    <>
      <div className={`bg-white border-2 rounded-md p-4 w-80 ${selected ? 'border-blue-500' : 'border-gray-200'}`}>
        <div className="flex justify-between items-center mb-3">
          <div className="font-semibold">LLM Model Configuration</div>
          {/* <div className="flex space-x-1">
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-6 w-6" 
              title="Test node"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={saveChanges}
              disabled={!isDirty}
              className={`h-6 w-6 ${isDirty ? 'text-blue-500' : 'text-gray-400'}`}
              title={isDirty ? "Save changes" : "No changes to save"}
            >
              <Save className="h-4 w-4" />
            </Button>
          </div> */}
        </div>
        
        <div className="space-y-4">
          {/* Model Configuration */}
          <ModelConfiguration
            id={id}
            config={config}
            onConfigChange={setConfig}
          />

          {/* Mode Selection */}
          <div className="flex justify-between items-center">
            <Label className="font-medium text-sm">Mode</Label>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={mode === 'normal' ? 'default' : 'outline'}
                className="h-7 px-2 text-xs"
                onClick={() => setMode('normal')}
              >
                Normal
              </Button>
              <Button
                size="sm"
                variant={mode === 'json-parsing' ? 'default' : 'outline'}
                className="h-7 px-2 text-xs"
                onClick={() => setMode('json-parsing')}
              >
                JSON Parsing
              </Button>
            </div>
          </div>

          {/* Input/Output Display */}
          {inputText && (
            <div className="space-y-2 pt-2 border-t border-gray-200">
              <Label>Input</Label>
              <ScrollArea className="h-32 border rounded-md p-2 bg-gray-50">
                <div className="text-sm whitespace-pre-wrap">{inputText}</div>
              </ScrollArea>
            </div>
          )}

          {outputText && (
            <div className="space-y-2 pt-2 border-t border-gray-200">
              <Label>Output</Label>
              <ScrollArea className="h-32 border rounded-md p-2 bg-blue-50">
                <div className="text-sm whitespace-pre-wrap">{outputText}</div>
              </ScrollArea>
            </div>
          )}
        </div>
        
        {/* Render all handlers */}
        {data.handlers?.filter(handler => handler.type === 'source').map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === 'source' ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: `${(index+1) * (100/data.handlers.length)}%` }}
          />
        ))}
        {data.handlers?.filter(handler => handler.type === 'target').map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === 'source' ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: `${(index+1) * (100/data.handlers.length)}%` }}
          />
        ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title="Test LLM Model"
        description="Test the LLM model with a sample prompt"
        inputFields={inputFields}
        onRun={handleTest}
        output={testOutput}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default LLMModelNode; 