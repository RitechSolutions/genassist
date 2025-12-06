import React, { useEffect } from "react";
import { GraphFlow } from "./GraphFlow";
import { registerAllNodeTypes } from "./nodeTypes";
import nodeRegistry from "./registry/nodeRegistry";
import { ReactFlowProvider } from "reactflow";

// Initialize node types
registerAllNodeTypes();

const AgentStudioPage: React.FC = () => {

  // Ensure node types are registered
  useEffect(() => {
    // Register again as a safety measure
    registerAllNodeTypes();
  }, []);


  return (
    <div className="min-h-screen flex w-full">
      <main className="flex-1 bg-zinc-100 relative">
        <ReactFlowProvider>
          <GraphFlow/>
        </ReactFlowProvider>
      </main>
    </div>
  );
};


export default AgentStudioPage;
