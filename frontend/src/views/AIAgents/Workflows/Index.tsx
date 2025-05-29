import React, { useEffect } from "react";
import { SidebarProvider, useSidebar } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import GraphFlow from "./GraphFlow";
import { PanelLeft } from "lucide-react";
import { Button } from "@/components/button";
import { registerAllNodeTypes } from "./nodeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import { ReactFlowProvider } from "reactflow";
import { useParams } from "react-router-dom";
import AgentForm, { AgentFormPage } from "../components/AgentForm";

// Initialize node types
registerAllNodeTypes();

// Verify registration
console.log(
  "LangGraph View - Node types registered on init:",
  nodeRegistry.getAllNodeTypes().length
);
console.log("Node categories:", nodeRegistry.getAllCategories());

const LangGraphView: React.FC = () => {
  // const isMobile = useIsMobile();
  // const { agentId } = useParams();
  

  // Ensure node types are registered
  useEffect(() => {
    // Register again as a safety measure
    registerAllNodeTypes();
    console.log("Node types in effect:", nodeRegistry.getAllNodeTypes().length);
  }, []);

  // if (!agentId) {
  //   return <AgentFormPage />;
  // }

  return (
    <div className="min-h-screen flex w-full">
      {/* {!isMobile && <AppSidebar />} */}
      <main className="flex-1 bg-zinc-100 relative">
        <ReactFlowProvider>
          <GraphFlow/>
        </ReactFlowProvider>
      </main>
    </div>
  );
};


export default LangGraphView;
