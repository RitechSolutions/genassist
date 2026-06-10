import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/button";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { MCPServer } from "@/interfaces/mcp-server.interface";
import { getAllMCPServers, deleteMCPServer } from "@/services/mcpServer";
import { toast } from "react-hot-toast";
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
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [serverToDelete, setServerToDelete] = useState<MCPServer | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
  const [isDetailsDialogOpen, setIsDetailsDialogOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedServer) {
      setServers((prevServers) =>
        prevServers.map((server) =>
          server.id === updatedServer.id ? updatedServer : server
        )
      );
    }
  }, [updatedServer]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await getAllMCPServers();
      setServers(data);
    } catch (err) {
      toast.error("Failed to fetch MCP servers.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!serverToDelete) return;
    setIsDeleting(true);
    try {
      await deleteMCPServer(serverToDelete.id);
      toast.success("MCP server deleted successfully.");
      setServers((prev) => prev.filter((s) => s.id !== serverToDelete.id));
    } catch {
      toast.error("Failed to delete MCP server.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
    }
  };

  const filtered = servers.filter((s) => {
    const q = searchQuery.toLowerCase();
    const av = s.auth_values ?? {};
    const issuer =
      typeof av.oauth2_issuer_url === "string" ? av.oauth2_issuer_url.toLowerCase() : "";
    const scope =
      typeof av.oauth2_scope === "string" ? av.oauth2_scope.toLowerCase() : "";
    const cid =
      typeof av.oauth2_client_id === "string" ? av.oauth2_client_id.toLowerCase() : "";
    return (
      s.name.toLowerCase().includes(q) ||
      (s.description && s.description.toLowerCase().includes(q)) ||
      (issuer && issuer.includes(q)) ||
      (scope && scope.includes(q)) ||
      (cid && cid.includes(q))
    );
  });

  const headers = ["Name", "Auth", "Workflows", "Status", "Created", "Actions"];

  const handleRowClick = (server: MCPServer) => {
    setSelectedServerId(server.id);
    setIsDetailsDialogOpen(true);
  };

  const renderRow = (s: MCPServer) => (
    <TableRow 
      key={s.id}
      className="cursor-pointer hover:bg-gray-50"
      onClick={() => handleRowClick(s)}
    >
      <TableCell className="font-medium break-all">{s.name}</TableCell>
      <TableCell className="whitespace-nowrap">
        <Badge variant="outline" className="font-normal">
          {s.auth_type === "oauth2" ? "OAuth 2.0 / OIDC" : "API key"}
        </Badge>
      </TableCell>
      <TableCell className="truncate">
        {s.workflows.length === 0
          ? "No workflows"
          : `${s.workflows.length} workflow${s.workflows.length === 1 ? "" : "s"}`}
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={s.is_active === 1 ? "default" : "secondary"}>
          {s.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="truncate">{formatDate(s.created_at)}</TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <ActionButtons
          onEdit={() => onEditServer(s)}
          onDelete={() => {
            setServerToDelete(s);
            setIsDeleteDialogOpen(true);
          }}
          editTitle="Edit MCP Server"
          deleteTitle="Delete MCP Server"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filtered}
        loading={loading}
        error={null}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No MCP servers found"
        searchEmptyMessage="No matching MCP servers"
        emptyState={
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <Database className="h-12 w-12 text-gray-400" />
            </div>
            <h3 className="font-medium text-lg">
              {searchQuery ? "No matching MCP servers" : "No MCP servers found"}
            </h3>
            <p className="text-sm text-gray-500 max-w-sm px-4">
              {searchQuery
                ? "Try adjusting your search query."
                : "Add your first MCP server to connect external tools and capabilities."}
            </p>
            {!searchQuery && (
              <Button onClick={onCreateServer} className="rounded-full">
                <Plus className="h-4 w-4 mr-2" />
                Create your first MCP server
              </Button>
            )}
          </div>
        }
      />
      <MCPServerDetailsDialog
        isOpen={isDetailsDialogOpen}
        onOpenChange={setIsDetailsDialogOpen}
        serverId={selectedServerId}
        onEdit={onEditServer}
      />
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={serverToDelete?.name || ""}
        description={`This will permanently delete "${serverToDelete?.name}". This action cannot be undone.`}
      />
    </>
  );
}

