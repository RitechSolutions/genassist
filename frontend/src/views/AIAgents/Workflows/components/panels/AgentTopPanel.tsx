import { AgentConfig } from "@/services/api";
import { AgentFormDialog } from  "@/views/AIAgents/components/AgentForm";
import { useState } from "react";

const AgentTopPanel = ({data, onUpdated}: {data?: AgentConfig, onUpdated?: () => void}) => {
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    return (
        <>
          <div 
            className="flex items-center justify-center bg-white/80 backdrop-blur-sm rounded-md shadow-sm p-2 min-w-[300px] cursor-pointer hover:bg-white/90 transition-colors"
            onClick={() => setIsEditDialogOpen(true)}
          >
            <div className="flex flex-col items-center text-center">
                <div className="text-sm font-bold">{data?.name}</div>
                <div className="text-sm font-light">{data?.description.slice(0, 100)}...</div>
            </div>
          </div>
          <AgentFormDialog
            isOpen={isEditDialogOpen}
            onClose={() => {
                setIsEditDialogOpen(false)
                onUpdated?.()
            }}
            data={{id: data?.id, name: data?.name, description: data?.description, welcome_message: data?.welcome_message, welcome_title: data?.welcome_title, thinking_phrase_delay: data?.thinking_phrase_delay, possible_queries: data?.possible_queries, thinking_phrases: data?.thinking_phrases}}
          />
        </>
      );
    
};

export default AgentTopPanel;

