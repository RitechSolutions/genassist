import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { Webhook } from "@/interfaces/webhook.interface";
import { WebhookCard } from "../components/WebhookCard";
import { WebhookDialog } from "../components/WebhookDialog";

export default function WebhooksPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [webhookToEdit, setWebhookToEdit] = useState<Webhook | null>(null);
  const [updatedWebhook, setUpdatedWebhook] = useState<Webhook | null>(null);

  const handleWebhookSaved = () => {
    setRefreshKey(prev => prev + 1);
  };

  const handleWebhookUpdated = (webhook: Webhook) => {
    setUpdatedWebhook(webhook);
  };

  const handleCreateWebhook = () => {
    setDialogMode("create");
    setWebhookToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditWebhook = (webhook: Webhook) => {
    setDialogMode("edit");
    setWebhookToEdit(webhook);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <div className="px-6 py-4 w-full"> {/* Add padding and full-width wrapper */}
        <PageHeader
          title="Webhooks"
          subtitle="Manage outgoing webhooks for event triggers"
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search webhooks..."
          actionButtonText="Add New Webhook"
          onActionClick={handleCreateWebhook}
        />

        <div className="w-full mt-4"> {/* Ensure WebhookCard fills space */}
          <WebhookCard
            searchQuery={searchQuery}
            refreshKey={refreshKey}
            onEditWebhook={handleEditWebhook}
            updatedWebhook={updatedWebhook}
          />
        </div>
      </div>

      <WebhookDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onWebhookSaved={handleWebhookSaved}
        onWebhookUpdated={handleWebhookUpdated}
        webhookToEdit={webhookToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
