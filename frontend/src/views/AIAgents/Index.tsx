import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Chat from './components/Chat';
import AgentForm from './components/AgentForm';
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import IntegrationCodePage from '@/views/AIAgents/components/IntegrationCodePage';
import ChatAsCustomer from "@/views/AIAgents/components/Customer/ChatAsCustomer"; 

const AIAgentsView: React.FC = () => {
  const isMobile = useIsMobile();
  
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="chat/:agentId/:threadId" element={<Chat />} />
                <Route path="new" element={<AgentForm />} />
                <Route path="edit/:agentId" element={<AgentForm />} />
                <Route path="integration/:agentId" element={<IntegrationCodePage />} />
                <Route path="chat-as-customer/:agentId" element={<ChatAsCustomer />} />
              </Routes>
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default AIAgentsView;
