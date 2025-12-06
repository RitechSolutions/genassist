import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { Webhook } from "@/interfaces/webhook.interface";
import { getAllWebhooks, deleteWebhook } from "@/services/webhook";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";

interface Props {
  searchQuery: string;
  refreshKey?: number;
  onEditWebhook: (webhook: Webhook) => void;
  updatedWebhook?: Webhook | null;
}

export function WebhookCard({
  searchQuery,
  refreshKey = 0,
  onEditWebhook,
  updatedWebhook = null,
}: Props) {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [webhookToDelete, setWebhookToDelete] = useState<Webhook | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedWebhook) {
      setWebhooks((prevWebhooks) =>
        prevWebhooks.map((webhook) =>
          webhook.id === updatedWebhook.id ? updatedWebhook : webhook
        )
      );
    }
  }, [updatedWebhook]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await getAllWebhooks();
      setWebhooks(data);
    } catch (err) {
      toast.error("Failed to fetch webhooks.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!webhookToDelete) return;
    setIsDeleting(true);
    try {
      await deleteWebhook(webhookToDelete.id);
      toast.success("Webhook deleted successfully.");
      setWebhooks((prev) => prev.filter((s) => s.id !== webhookToDelete.id));
    } catch {
      toast.error("Failed to delete webhook.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
    }
  };

  const filtered = webhooks.filter(
    (w) =>
      w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.url.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const headers = ["Name", "URL", "Method", "Status", "Created", "Actions"];

  const renderRow = (w: Webhook) => (
    <TableRow key={w.id}>
      <TableCell className="font-medium break-all">{w.name}</TableCell>
      <TableCell className="font-mono truncate">{w.url}</TableCell>
      <TableCell className="truncate">{w.method}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={w.is_active === 1 ? "default" : "secondary"}>
          {w.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="truncate">{formatDate(w.created_at)}</TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEditWebhook(w)}
          onDelete={() => {
            setWebhookToDelete(w);
            setIsDeleteDialogOpen(true);
          }}
          editTitle="Edit Webhook"
          deleteTitle="Delete Webhook"
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
        emptyMessage="No webhooks found"
        searchEmptyMessage="No matching webhooks"
      />
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={webhookToDelete?.name || ""}
        description={`This will permanently delete "${webhookToDelete?.name}". This action cannot be undone.`}
      />
    </>
  );
}
