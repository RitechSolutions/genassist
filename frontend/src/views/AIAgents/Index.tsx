import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Chat from './components/Chat';
import { useIsMobile } from "@/hooks/useMobile";
import ChatAsCustomer from "@/views/AIAgents/components/Customer/ChatAsCustomer"; 
import SecurityPage from "@/views/AIAgents/components/Customer/SecurityPage";
import SchedulingPage from "@/views/AIAgents/Scheduling/SchedulingPage";
import AgentStudioPage from './Workflows/Index';
// import Tools from '../Tools/Index';

const AIAgentsView: React.FC = () => {
  const isMobile = useIsMobile();
  
  return (
    <div className="flex-1">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        {/* <Route path="/tools" element={<Tools />} /> */}

        <Route path="chat/:agentId/:threadId" element={<Chat />} />
        <Route path="new" element={<AgentStudioPage />} />
        <Route path="workflow/:agentId" element={<AgentStudioPage />} />
        <Route path="integration/:agentId" element={<ChatAsCustomer />} />
        <Route path="security/:agentId" element={<SecurityPage />} />
        <Route path="scheduling/:agentId" element={<SchedulingPage />} />
      </Routes>
    </div>
  );
};

export default AIAgentsView;
