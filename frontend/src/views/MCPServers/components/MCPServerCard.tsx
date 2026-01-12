import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { MCPServer } from "@/interfaces/mcp-server.interface";
import { getAllMCPServers, deleteMCPServer } from "@/services/mcpServer";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";
import { MCPServerDetailsDialog } from "./MCPServerDetailsDialog";

interface Props {
  searchQuery: string;
  refreshKey?: number;
  onEditServer: (server: MCPServer) => void;
  updatedServer?: MCPServer | null;
}

export function MCPServerCard({
  searchQuery,
  refreshKey = 0,
  onEditServer,
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

  const filtered = servers.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.description && s.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const headers = ["Name", "Workflows", "Status", "Created", "Actions"];

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

