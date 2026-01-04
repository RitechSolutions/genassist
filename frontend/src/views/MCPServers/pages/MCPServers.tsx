import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { MCPServer } from "@/interfaces/mcp-server.interface";
import { MCPServerCard } from "../components/MCPServerCard";
import { MCPServerDialog } from "../components/MCPServerDialog";

export default function MCPServersPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [serverToEdit, setServerToEdit] = useState<MCPServer | null>(null);
  const [updatedServer, setUpdatedServer] = useState<MCPServer | null>(null);

  const handleServerSaved = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleServerUpdated = (server: MCPServer) => {
    setUpdatedServer(server);
  };

  const handleCreateServer = () => {
    setDialogMode("create");
    setServerToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditServer = (server: MCPServer) => {
    setDialogMode("edit");
    setServerToEdit(server);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <div className="px-6 py-4 w-full">
        <PageHeader
          title="MCP Servers"
          subtitle="Manage MCP servers and expose workflows as tools"
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search MCP servers..."
          actionButtonText="Add New MCP Server"
          onActionClick={handleCreateServer}
        />

        <div className="w-full mt-4">
          <MCPServerCard
            searchQuery={searchQuery}
            refreshKey={refreshKey}
            onEditServer={handleEditServer}
            updatedServer={updatedServer}
          />
        </div>
      </div>

      <MCPServerDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onServerSaved={handleServerSaved}
        onServerUpdated={handleServerUpdated}
        serverToEdit={serverToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}

