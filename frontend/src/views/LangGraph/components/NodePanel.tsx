import React from 'react';
import { Button } from "@/components/button";
import { X, MessageCircle, Brain, FileText, MessageSquare, Globe, Database } from "lucide-react";
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from "@/components/card";
import nodeRegistry from "../registry/nodeRegistry";
import { getNodeColors } from "../utils/nodeColors";

interface NodePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddNode: (nodeType: string) => void;
}

const NodePanel: React.FC<NodePanelProps> = ({
  isOpen,
  onClose,
  onAddNode
}) => {
  const nodeCategories = nodeRegistry.getAllCategories();
  
  // Get node icon component
  const getNodeIcon = (icon: string, nodeType: string) => {
    const colors = getNodeColors(nodeType);
    switch (icon) {
      case 'MessageCircle':
        return <MessageCircle className={`h-4 w-4 ${colors.panelIcon}`} />;
      case 'Brain':
        return <Brain className={`h-4 w-4 ${colors.panelIcon}`} />;
      case 'FileText':
        return <FileText className={`h-4 w-4 ${colors.panelIcon}`} />;
      case 'MessageSquare':
        return <MessageSquare className={`h-4 w-4 ${colors.panelIcon}`} />;
      case 'Globe':
        return <Globe className={`h-4 w-4 ${colors.panelIcon}`} />;
      case 'Database':
        return <Database className={`h-4 w-4 ${colors.panelIcon}`} />;
      default:
        return <div className="h-4 w-4 bg-gray-300 rounded" />;
    }
  };

  return (
    <div 
      className={`absolute top-0 right-0 h-full w-64 bg-white shadow-lg transition-transform duration-300 border-l ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div className="flex flex-col h-full">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-md font-semibold">Available Nodes</h3>
            <Button 
              onClick={onClose}
              size="icon" 
              variant="ghost"
              className="h-8 w-8 hover:bg-gray-100 rounded-full"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          {nodeCategories.length === 0 ? (
            <div className="text-sm text-gray-500">Loading node categories...</div>
          ) : (
            nodeCategories.map((category) => {
              const nodesInCategory = nodeRegistry.getNodeTypesByCategory(category);
              if (nodesInCategory.length === 0) return null;
              
              return (
                <div key={category} className="mb-4">
                  <h4 className="text-sm font-medium capitalize mb-2">{category}</h4>
                  <div className="space-y-3">
                    {nodesInCategory.map((nodeType) => (
                      <Card 
                        key={nodeType.type} 
                        className="cursor-pointer hover:bg-gray-50" 
                        onClick={() => onAddNode(nodeType.type)}
                      >
                        <CardHeader className="p-3 pb-1 flex flex-row items-center gap-2">
                          {getNodeIcon(nodeType.icon, nodeType.type)}
                          <CardTitle className="text-sm font-medium">{nodeType.label}</CardTitle>
                        </CardHeader>
                        <CardContent className="p-3 pt-1">
                          <CardDescription className="text-xs">
                            {nodeType.description}
                          </CardDescription>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default NodePanel; 