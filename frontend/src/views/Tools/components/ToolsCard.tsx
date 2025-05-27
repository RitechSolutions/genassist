import { Card } from "@/components/card";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Loader2, Trash2, Pencil } from "lucide-react";
import { Tool } from "@/interfaces/tool.interface";
import { useNavigate } from "react-router-dom";

interface ToolCardProps {
  tools: Tool[];
  searchQuery: string;
  onEditTool: (tool: Tool) => void;
  onDeleteTool: (id: string) => void;
  loading: boolean;
  error?: string | null;
}

export function ToolCard({
  tools,
  searchQuery,
  onEditTool,
  onDeleteTool,
  loading,
  error,
}: ToolCardProps) {
  const navigate = useNavigate(); 
  const handleEdit = (tool: Tool) => {
    navigate(`/tools/edit/${tool.id}`);
  };

  const filtered = tools.filter(
    (t) =>
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.id && t.id.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  if (loading) {
    return (
      <Card className="p-8 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-8">
        <p className="text-center text-red-500">{error}</p>
      </Card>
    );
  }

  if (filtered.length === 0) {
    return (
      <Card className="p-8">
        <p className="text-center text-muted-foreground">
          {searchQuery ? "No tools matching your search" : "No tools found"}
        </p>
      </Card>
    );
  }

  return (
    <Card className="divide-y divide-gray-200 rounded-lg bg-white">
      {filtered.map((tool) => (
        <div
          key={tool.id}
          className="flex justify-between items-start px-6 py-4"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold">{tool.name}</h3>
              <Badge variant="outline" className="bg-[#F1F1F1] border-transparent">{tool.type}</Badge>
            </div>
            {tool.id && (
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-gray-700">ID:</span>{" "}
                <span className="truncate">{tool.id}</span>
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-gray-700">Description:</span>{" "}
              <span className="text-wrap">{tool.description.length < 255 ? tool.description : tool.description + '...'}</span>
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleEdit(tool)}
              title="Edit Tool"
            >
              <Pencil className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => tool.id && onDeleteTool(tool.id)}
              title="Delete Tool"
              disabled={!tool.id}
            >
              <Trash2 className="w-4 h-4 text-red-500" />
            </Button>
          </div>
        </div>
      ))}
    </Card>
  );
}
