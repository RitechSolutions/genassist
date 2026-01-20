import { AgentConfig } from "@/services/api";
import { AgentFormDialog } from  "@/views/AIAgents/components/AgentForm";
import { useState } from "react";

const AgentTopPanel = ({data, onUpdated}: {data?: AgentConfig, onUpdated?: () => void}) => {
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    return (
        <>
          <div 
            className="flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm rounded-full shadow-sm px-6 w-full max-w-[360px] h-[44px] cursor-pointer hover:shadow-md transition-shadow gap-0.5"
            onClick={() => setIsEditDialogOpen(true)}
          >
            <div className="text-sm font-bold text-gray-900 truncate w-full text-center">
              {data?.name}
            </div>
            <div className="text-xs font-normal text-gray-500 truncate w-full text-center">
              {data?.description}
            </div>
          </div>
          <AgentFormDialog
            isOpen={isEditDialogOpen}
            onClose={() => {
                setIsEditDialogOpen(false)
                onUpdated?.()
            }}
            data={{id: data?.id, name: data?.name, description: data?.description, welcome_message: data?.welcome_message, welcome_title: data?.welcome_title, thinking_phrase_delay: data?.thinking_phrase_delay, possible_queries: data?.possible_queries, thinking_phrases: data?.thinking_phrases, token_based_auth: data?.token_based_auth}}
          />
        </>
      );
    
};

export default AgentTopPanel;

