import React, { useEffect } from "react";
import { SidebarProvider, useSidebar } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import GraphFlow from "./GraphFlow";
import { PanelLeft } from "lucide-react";
import { Button } from "@/components/button";
import { registerAllNodeTypes } from "./nodeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import { ReactFlowProvider } from 'reactflow';

// Initialize node types
registerAllNodeTypes();

// Verify registration
console.log("LangGraph View - Node types registered on init:", nodeRegistry.getAllNodeTypes().length);
console.log("Node categories:", nodeRegistry.getAllCategories());

const LangGraphContent: React.FC = () => {
  const isMobile = useIsMobile();
  const { toggleSidebar } = useSidebar();
  
  // Ensure node types are registered
  useEffect(() => {
    // Register again as a safety measure
    registerAllNodeTypes();
    console.log("Node types in effect:", nodeRegistry.getAllNodeTypes().length);
  }, []);
  
  return (
    <div className="min-h-screen flex w-full">
      {!isMobile && <AppSidebar />}
      <main className="flex-1 bg-zinc-100 relative">
        <Button 
          variant="ghost" 
          size="icon" 
          className="absolute top-4 left-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md"
          onClick={toggleSidebar}
        >
          <PanelLeft className="h-4 w-4" />
          <span className="sr-only">Toggle Sidebar</span>
        </Button>
        <ReactFlowProvider>
          <GraphFlow />
        </ReactFlowProvider>
      </main>
    </div>
  );
};

const LangGraphView: React.FC = () => {
  return (
    <SidebarProvider>
      <LangGraphContent />
    </SidebarProvider>
  );
};

export default LangGraphView;
