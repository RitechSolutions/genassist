import React, { useState } from 'react';
import { Position, NodeProps } from 'reactflow';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { getHandlerPosition, HandleTooltip } from '../../components/HandleTooltip';
import { LLMModelNodeData } from '../../types/nodes';
import { ModelConfig, ModelConfiguration } from '../../components/ModelConfiguration';

const LLMModelNode: React.FC<NodeProps<LLMModelNodeData>> = ({ id, data, selected }) => {
  const [config, setConfig] = useState<ModelConfig>({
    providerId: data.providerId || 'openai',
  });
  const [mode, setMode] = useState<'normal' | 'json-parsing'>(data.jsonParsing ? 'json-parsing' : 'normal');


  const sourceHandlers = data.handlers?.filter(
    (handler) => handler.type === "source"
  );
  const targetHandlers = data.handlers?.filter(
    (handler) => handler.type === "target"
  );
  return (
    <>
      <div className={`bg-white border-2 rounded-md p-4 w-80 ${selected ? 'border-blue-500' : 'border-gray-200'}`}>
        <div className="flex justify-between items-center mb-3">
          <div className="font-semibold">LLM Model Configuration</div>
         
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
        </div>
        
        {/* Render all handlers */}
        {sourceHandlers?.map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === 'source' ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: getHandlerPosition(index, sourceHandlers.length) }}
          />
        ))}
        {targetHandlers?.map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === 'source' ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: getHandlerPosition(index, targetHandlers.length) }}
          />
        ))}
      </div>
    </>
  );
};

export default LLMModelNode; 