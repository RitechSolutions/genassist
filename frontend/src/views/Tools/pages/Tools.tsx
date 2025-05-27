import { useState, useEffect, useMemo } from "react";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { ToolCard } from "../components/ToolsCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus, Loader2, Loader } from "lucide-react";
import { Button } from "@/components/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { useNavigate } from "react-router-dom";
import { Tool } from "@/interfaces/tool.interface";
import { getAllTools, deleteTool } from "@/services/tools";
import {  toast } from "react-hot-toast";

export default function Tools() {
  const isMobile = useIsMobile();

  const [tools, setTools] = useState<Tool[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [toolToEdit, setToolToEdit] = useState<Tool | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<"all" | "api" | "function">(
    "all"
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await getAllTools();
        setTools(data);
      } catch {
        toast.error("Could not fetch tools");
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshKey]);

  const handleEdit = (tool: Tool) => {
    setDialogMode("edit");
    setToolToEdit(tool);
    setIsDialogOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTool(id);
      toast.success("Tool deleted");
      setRefreshKey((v) => v + 1);
    } catch {
      toast.error("Delete failed");
    }
  };

  const onSaved = () => setRefreshKey((v) => v + 1);
  const openCreate = () => {
    setDialogMode("create");
    setToolToEdit(null);
    setIsDialogOpen(true);
  };

  const filteredTools = useMemo(() => {
    return tools.filter((tool) => {
      const matchesText = tool.name
        .toLowerCase()
        .includes(searchQuery.toLowerCase());
      const matchesType = filterType === "all" || tool.type === filterType;
      return matchesText && matchesType;
    });
  }, [tools, searchQuery, filterType]);

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 bg-zinc-100 p-8">
          <div className="max-w-4xl mx-auto space-y-6">
            <header className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold">Tools</h1>
                <p className="text-muted-foreground">
                  View and manage the tools
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    type="text"
                    placeholder="Search tools…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary w-full sm:w-64"
                  />
                </div>

                <Select
                  value={filterType}
                  onValueChange={(val) =>
                    setFilterType(val as "all" | "api" | "function")
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="All Types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="api">API</SelectItem>
                    <SelectItem value="function">Python Function</SelectItem>
                  </SelectContent>
                </Select>

                <Button
                  onClick={() => navigate("/tools/create")}
                  className="flex items-center gap-2 bg-black text-white font-semibold py-3 px-5 rounded-md hover:opacity-90 transition"
                >
                  <Plus className="w-4 h-4" />
                  Add New
                </Button>
              </div>
            </header>

            {loading ? (
              <div className="flex justify-center items-center">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : (
              <ToolCard
                tools={filteredTools}
                loading={loading}
                error={error}
                searchQuery={searchQuery}
                onEditTool={handleEdit}
                onDeleteTool={handleDelete}
              />
            )}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
