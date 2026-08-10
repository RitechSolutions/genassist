import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { Webhook } from "@/interfaces/webhook.interface";
import { getAllWebhooks, deleteWebhook } from "@/services/webhook";
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
  ];

  return (
    <EntityTableCard<Webhook>
      entityName="webhook"
      searchQuery={searchQuery}
      searchFields={["name", "url"]}
      refreshKey={refreshKey}
      updatedItem={updatedWebhook}
      fetchFn={getAllWebhooks}
      deleteFn={(w) => deleteWebhook(w.id)}
      getItemName={(w) => w.name}
      deleteDescription={(w) =>
        `This will permanently delete "${w.name}". This action cannot be undone.`
      }
      emptyMessage="No webhooks found"
      notFoundMessage="No matching webhooks"
      emptyState={{
        icon: <Radio className="h-12 w-12 text-muted-foreground" />,
        title: "No webhooks found",
        searchTitle: "No matching webhooks",
        description:
          "Create your first webhook to start sending events to external systems.",
        searchDescription: "Try adjusting your search query.",
        action: (
          <Button onClick={onCreateWebhook} className="rounded-full">
            <Plus className="h-4 w-4 mr-2" />
            Create your first webhook
          </Button>
        ),
      }}
      columns={columns}
      rowActions={{
        onEdit: onEditWebhook,
        editTitle: "Edit Webhook",
        deleteTitle: "Delete Webhook",
      }}
    />
  );
}
