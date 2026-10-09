import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { IssueStatus } from "@/services/issueStatuses";
import { FeedbackStatusesCard } from "../components/FeedbackStatusesCard";
import { FeedbackStatusDialog } from "../components/FeedbackStatusDialog";
import { PanelHeader } from "./PanelHeader";

export function FeedbackStatusesPanel() {
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [statusToEdit, setStatusToEdit] = useState<IssueStatus | null>(null);

  const refreshStatuses = () =>
    queryClient.invalidateQueries({ queryKey: ["issue-statuses"] });

  const handleCreateStatus = () => {
    setDialogMode("create");
    setStatusToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditStatus = (status: IssueStatus) => {
    setDialogMode("edit");
    setStatusToEdit(status);
    setIsDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <PanelHeader
        variant="tab"
        title="Feedback Status"
        subtitle="Statuses used to triage reported feedback. Non-active statuses stay on existing items but cannot be chosen again."
        actionButtonText="Add Status"
        onActionClick={handleCreateStatus}
      />

      <FeedbackStatusesCard
        onEditStatus={handleEditStatus}
        onChanged={refreshStatuses}
      />

      <FeedbackStatusDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onStatusSaved={refreshStatuses}
        statusToEdit={statusToEdit}
        mode={dialogMode}
      />
    </div>
  );
}
