import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Chat from './components/Chat';
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import IntegrationCodePage from '@/views/AIAgents/components/IntegrationCodePage';
import ChatAsCustomer from "@/views/AIAgents/components/Customer/ChatAsCustomer"; 
import AgentStudioPage from './Workflows/Index';
// import Tools from '../Tools/Index';

const AIAgentsView: React.FC = () => {
  const isMobile = useIsMobile();
  
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0">
          <div className="flex-1">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                {/* <Route path="/tools" element={<Tools />} /> */}

                <Route path="chat/:agentId/:threadId" element={<Chat />} />
                <Route path="new" element={<AgentStudioPage />} />
                <Route path="workflow/:agentId" element={<AgentStudioPage />} />
                <Route path="integration/:agentId" element={<IntegrationCodePage />} />
                <Route path="chat-as-customer/:agentId" element={<ChatAsCustomer />} />
              </Routes>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default AIAgentsView;
