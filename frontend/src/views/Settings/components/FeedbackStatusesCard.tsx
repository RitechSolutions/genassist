import { useState } from "react";
import { ArrowDown, ArrowUp, ListChecks, Loader2, Pencil } from "lucide-react";
import { toast } from "react-hot-toast";

import { Card } from "@/components/card";
import { ListEmptyState } from "@/components/ListEmptyState";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Switch } from "@/components/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { extractErrorMessage } from "@/helpers/apiError";
import { cn } from "@/helpers/utils";
import {
  IssueStatus,
  reorderIssueStatuses,
  updateIssueStatus,
} from "@/services/issueStatuses";
import { CATEGORY_META } from "@/views/ReportedFeedback/constants";
import { useIssueStatuses } from "@/views/ReportedFeedback/hooks/useIssueStatuses";
import {
  activeStatuses,
  statusMeta,
} from "@/views/ReportedFeedback/helpers/issueStatuses";
import { DEFAULT_STATUS_KEY, moveStatus } from "../helpers/issueStatusForm";

interface FeedbackStatusesCardProps {
  onEditStatus: (status: IssueStatus) => void;
  onChanged: () => Promise<unknown>;
}

export function FeedbackStatusesCard({
  onEditStatus,
  onChanged,
}: FeedbackStatusesCardProps) {
  const { data: statuses = [], isLoading, isError } = useIssueStatuses();
  const [saving, setSaving] = useState(false);

  const save = async (
    action: () => Promise<unknown>,
    failure: string,
    success?: string,
  ) => {
    setSaving(true);
    try {
      await action();
      if (success) toast.success(success);
    } catch (err) {
      toast.error(extractErrorMessage(err, failure));
    } finally {
      await onChanged();
      setSaving(false);
    }
  };

  const handleToggleActive = (status: IssueStatus, active: boolean) =>
    save(
      () => updateIssueStatus(status.id, { is_active: active ? 1 : 0 }),
      "Failed to update the status.",
      `"${status.label}" ${active ? "activated" : "deactivated"}.`,
    );

  const handleMove = (status: IssueStatus, direction: -1 | 1) => {
    const keys = moveStatus(statuses, status.key, direction);
    if (keys)
      void save(
        () => reorderIssueStatuses(keys),
        "Failed to reorder the statuses.",
      );
  };

  if (isLoading) {
    return (
      <Card className="dark:bg-zinc-900 p-8 flex justify-center items-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="dark:bg-zinc-900 p-8">
        <div className="text-center text-red-500">
          Failed to load the statuses.
        </div>
      </Card>
    );
  }

  const active = activeStatuses(statuses);
  const retired = statuses.filter((status) => status.is_active !== 1);

  return (
    <Card className="dark:bg-zinc-900 overflow-hidden shadow-sm">
      {statuses.length === 0 ? (
        <ListEmptyState
          icon={<ListChecks className="h-12 w-12 text-muted-foreground" />}
          title="No statuses yet"
          description="Add the statuses used to triage reported feedback."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Order</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...active, ...retired].map((status) => {
              const isActive = status.is_active === 1;
              const index = active.indexOf(status);
              const isDefault = status.key === DEFAULT_STATUS_KEY;
              return (
                <TableRow
                  key={status.id}
                  className={isActive ? undefined : "text-muted-foreground"}
                >
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={cn(
                        statusMeta(statuses, status.key).className,
                        !isActive && "opacity-60",
                      )}
                    >
                      {status.label}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs">{status.key}</code>
                  </TableCell>
                  <TableCell>
                    {CATEGORY_META[status.category]?.label ?? status.category}
                  </TableCell>
                  <TableCell>
                    <span
                      className="inline-flex"
                      title={
                        isDefault
                          ? "The default status cannot be deactivated"
                          : undefined
                      }
                    >
                      <Switch
                        checked={isActive}
                        disabled={isDefault || saving}
                        onCheckedChange={(checked) =>
                          handleToggleActive(status, checked)
                        }
                        aria-label={`Active: ${status.label}`}
                      />
                    </span>
                  </TableCell>
                  <TableCell>
                    {isActive && (
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleMove(status, -1)}
                          disabled={saving || index === 0}
                          title="Move up"
                        >
                          <ArrowUp className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleMove(status, 1)}
                          disabled={saving || index === active.length - 1}
                          title="Move down"
                        >
                          <ArrowDown className="w-4 h-4" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditStatus(status)}
                      title="Edit Status"
                    >
                      <Pencil className="w-4 h-4 text-foreground" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}
