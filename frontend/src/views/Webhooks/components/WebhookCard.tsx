import { useEffect, useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { Webhook } from "@/interfaces/webhook.interface";
import { getAllWebhooks, deleteWebhook } from "@/services/webhook";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";
import { Plus, Radio } from "lucide-react";

interface Props {
  searchQuery: string;
  refreshKey?: number;
  onEditWebhook: (webhook: Webhook) => void;
  onCreateWebhook: () => void;
  updatedWebhook?: Webhook | null;
}

export function WebhookCard({
  searchQuery,
  refreshKey = 0,
  onEditWebhook,
  onCreateWebhook,
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

  const columns: Column<Webhook>[] = [
    {
      header: "Name",
      key: "name",
      cell: (w) => w.name,
      className: "font-medium break-all",
    },
    {
      header: "URL",
      key: "url",
      cell: (w) => w.url,
      className: "font-mono truncate",
    },
    {
      header: "Method",
      key: "method",
      cell: (w) => w.method,
      className: "truncate",
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (w) => (
        <Badge variant={w.is_active === 1 ? "default" : "secondary"}>
          {w.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Created",
      key: "created_at",
      cell: (w) => formatDate(w.created_at),
      className: "truncate",
    },
    {
      header: "Actions",
      key: "actions",
      cell: (w) => (
        <ActionButtons
          onEdit={() => onEditWebhook(w)}
          onDelete={() => {
            setWebhookToDelete(w);
            setIsDeleteDialogOpen(true);
          }}
          editTitle="Edit Webhook"
          deleteTitle="Delete Webhook"
        />
      ),
    },
  ];

  return (
    <>
      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        error={null}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No webhooks found"
        notFoundMessage="No matching webhooks"
        emptyState={
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <Radio className="h-12 w-12 text-gray-400" />
            </div>
            <h3 className="font-medium text-lg">
              {searchQuery ? "No matching webhooks" : "No webhooks found"}
            </h3>
            <p className="text-sm text-gray-500 max-w-sm px-4">
              {searchQuery
                ? "Try adjusting your search query."
                : "Create your first webhook to start sending events to external systems."}
            </p>
            {!searchQuery && (
              <Button onClick={onCreateWebhook} className="rounded-full">
                <Plus className="h-4 w-4 mr-2" />
                Create your first webhook
              </Button>
            )}
          </div>
        }
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
