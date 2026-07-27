import { AgentConfig } from "@/services/api";
import { AgentFormDialog } from  "@/views/AIAgents/components/AgentForm";
import { useState } from "react";
import {
  DEFAULT_NODE_STYLE,
  WorkflowNodeStyle,
} from "@/interfaces/workflow.interface";
import { useWorkflow } from "../../context/WorkflowContext";

const AgentTopPanel = ({data, onUpdated}: {data?: AgentConfig, onUpdated?: () => void}) => {
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

    // Live workflow + setter from context — the sheet's "Advanced" tab hosts the
    // Workflow Settings (node style), which is persisted with the workflow.
    const { workflow: contextWorkflow, setWorkflow } = useWorkflow();
    const nodeStyle = contextWorkflow?.settings?.nodeStyle ?? DEFAULT_NODE_STYLE;

    const handleNodeStyleChange = (style: WorkflowNodeStyle) => {
      setWorkflow((prev) =>
        prev
          ? { ...prev, settings: { ...prev.settings, nodeStyle: style } }
          : prev
      );
    };

    return (
        <>
          <div 
            className="flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm rounded-full shadow-sm px-6 w-full max-w-[360px] h-[44px] cursor-pointer hover:shadow-md transition-shadow gap-0.5"
            onClick={() => setIsEditDialogOpen(true)}
          >
            <div className="text-sm font-bold text-foreground truncate w-full text-center">
              {data?.name}
            </div>
            <div className="text-xs font-normal text-muted-foreground truncate w-full text-center">
              {data?.description}
            </div>
          </div>
          <AgentFormDialog
            isOpen={isEditDialogOpen}
            onClose={() => {
                setIsEditDialogOpen(false)
                onUpdated?.()
            }}
            data={{id: data?.id, name: data?.name, description: data?.description, welcome_message: data?.welcome_message, welcome_title: data?.welcome_title, input_disclaimer_html: data?.input_disclaimer_html, thinking_phrase_delay: data?.thinking_phrase_delay, possible_queries: data?.possible_queries, thinking_phrases: data?.thinking_phrases, greet_on_start: data?.greet_on_start, greeting_prompt: data?.greeting_prompt, llm_analyst_id: data?.llm_analyst_id}}
            nodeStyle={nodeStyle}
            onNodeStyleChange={handleNodeStyleChange}
          />
        </>
      );
    
};

export default AgentTopPanel;

