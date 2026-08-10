import { useState } from "react";
import { Column } from "@/components/ui/data-table";
import {
  EntityTableCard,
  EntityTableRenderHelpers,
} from "@/components/EntityTableCard";
import { ActionButtons } from "@/components/ActionButtons";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { MCPServer } from "@/interfaces/mcp-server.interface";
import { getAllMCPServers, deleteMCPServer } from "@/services/mcpServer";
import { formatDate } from "@/helpers/utils";
import { MCPServerDetailsDialog } from "./MCPServerDetailsDialog";
import { Database, Plus } from "lucide-react";

interface Props {
  searchQuery: string;
  refreshKey?: number;
  onEditServer: (server: MCPServer) => void;
  onCreateServer: () => void;
  updatedServer?: MCPServer | null;
}

export function MCPServerCard({
  searchQuery,
  refreshKey = 0,
  onEditServer,
  onCreateServer,
  updatedServer = null,
}: Props) {
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
  const [isDetailsDialogOpen, setIsDetailsDialogOpen] = useState(false);

  const handleRowClick = (server: MCPServer) => {
    setSelectedServerId(server.id);
    setIsDetailsDialogOpen(true);
  };

  const columns = ({
    requestDelete,
  }: EntityTableRenderHelpers<MCPServer>): Column<MCPServer>[] => [
    {
      header: "Name",
      key: "name",
      cell: (s) => s.name,
      className: "font-medium break-all",
    },
    {
      header: "Auth",
      key: "auth",
      className: "whitespace-nowrap",
      cell: (s) => (
        <Badge variant="outline" className="font-normal">
          {s.auth_type === "oauth2" ? "OAuth 2.0 / OIDC" : "API key"}
        </Badge>
      ),
    },
    {
      header: "Workflows",
      key: "workflows",
      className: "truncate",
      cell: (s) =>
        s.workflows.length === 0
          ? "No workflows"
          : `${s.workflows.length} workflow${s.workflows.length === 1 ? "" : "s"}`,
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (s) => (
        <Badge variant={s.is_active === 1 ? "default" : "secondary"}>
          {s.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Created",
      key: "created_at",
      cell: (s) => formatDate(s.created_at),
      className: "truncate",
    },
    {
      header: "Actions",
      key: "actions",
      cell: (s) => (
        <div onClick={(e) => e.stopPropagation()}>
          <ActionButtons
            onEdit={() => onEditServer(s)}
            onDelete={() => requestDelete(s)}
            editTitle="Edit MCP Server"
            deleteTitle="Delete MCP Server"
          />
        </div>
      ),
    },
  ];

  return (
    <>
      <EntityTableCard<MCPServer>
        entityName="MCP server"
        searchQuery={searchQuery}
        filterFn={(s, query) => {
          const q = query.toLowerCase();
          const av = s.auth_values ?? {};
          const issuer =
            typeof av.oauth2_issuer_url === "string"
              ? av.oauth2_issuer_url.toLowerCase()
              : "";
          const scope =
            typeof av.oauth2_scope === "string"
              ? av.oauth2_scope.toLowerCase()
              : "";
          const cid =
            typeof av.oauth2_client_id === "string"
              ? av.oauth2_client_id.toLowerCase()
              : "";
          return (
            s.name.toLowerCase().includes(q) ||
            Boolean(s.description && s.description.toLowerCase().includes(q)) ||
            Boolean(issuer && issuer.includes(q)) ||
            Boolean(scope && scope.includes(q)) ||
            Boolean(cid && cid.includes(q))
          );
        }}
        refreshKey={refreshKey}
        updatedItem={updatedServer}
        fetchFn={getAllMCPServers}
        deleteFn={(s) => deleteMCPServer(s.id)}
        getItemName={(s) => s.name}
        deleteDescription={(s) =>
          `This will permanently delete "${s.name}". This action cannot be undone.`
        }
        emptyMessage="No MCP servers found"
        notFoundMessage="No matching MCP servers"
        emptyState={{
          icon: <Database className="h-12 w-12 text-muted-foreground" />,
          title: "No MCP servers found",
          searchTitle: "No matching MCP servers",
          description:
            "Add your first MCP server to connect external tools and capabilities.",
          searchDescription: "Try adjusting your search query.",
          action: (
            <Button onClick={onCreateServer} className="rounded-full">
              <Plus className="h-4 w-4 mr-2" />
              Create your first MCP server
            </Button>
          ),
        }}
        columns={columns}
        onRowClick={handleRowClick}
      />
      <MCPServerDetailsDialog
        isOpen={isDetailsDialogOpen}
        onOpenChange={setIsDetailsDialogOpen}
        serverId={selectedServerId}
        onEdit={onEditServer}
      />
    </>
  );
}
