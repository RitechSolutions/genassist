import { useState, useEffect, useMemo } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { ToolCard } from "../components/ToolsCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Plus, Loader2 } from "lucide-react";
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
import { toast } from "react-hot-toast";
import { SearchInput } from "@/components/SearchInput";

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
        toast.error("Failed to fetch tools.");
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
      toast.success("Tool deleted successfully.");
      setRefreshKey((v) => v + 1);
    } catch {
      toast.error("Failed to delete tool.");
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
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-6">
            <header className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold">Tools</h1>
                <p className="text-muted-foreground">
                  View and manage the tools
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <SearchInput
                  value={searchQuery}
                  onChange={setSearchQuery}
                  placeholder="Search tools…"
                  className="w-full sm:w-64"
                />

                <Select
                  value={filterType}
                  onValueChange={(val) =>
                    setFilterType(val as "all" | "api" | "function")
                  }
                >
                  <SelectTrigger className="w-full bg-white">
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
                  className="flex items-center gap-2 bg-black text-white font-semibold py-3 px-5 rounded-full hover:opacity-90 transition"
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
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
