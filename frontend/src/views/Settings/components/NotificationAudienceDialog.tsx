import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Save, UserRound, Users, UsersRound } from "lucide-react";

import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { RadioGroup, RadioGroupItem } from "@/components/radio-group";
import type { User } from "@/interfaces/user.interface";
import type { UserGroup } from "@/interfaces/userGroup.interface";
import type {
  NotificationTypeTargeting,
  NotificationTypeTargetingPayload,
} from "@/services/notificationAdminTargeting";
import { cn } from "@/helpers/utils";

export type NotificationAudienceTypeKey =
  | "conversation_started"
  | "conversation_hostility"
  | "conversation_finalized_hostility"
  | "workflow_failed";

const TYPE_META: Record<
  NotificationAudienceTypeKey,
  { title: string; description: string }
> = {
  conversation_started: {
    title: "Conversation started",
    description: "Choose who may receive alerts when a new conversation begins.",
  },
  conversation_hostility: {
    title: "High hostility detected",
    description: "Choose who may receive alerts when a live conversation hits high hostility.",
  },
  conversation_finalized_hostility: {
    title: "Live conversation finalized",
    description:
      "Choose who may receive alerts when a high-hostility conversation is finalized.",
  },
  workflow_failed: {
    title: "Workflow run failed",
    description:
      "Choose who may receive tenant-level alerts for failed pipeline or test runs.",
  },
};

type AudienceMode = "all" | "users" | "groups";

function deriveMode(t: NotificationTypeTargeting): AudienceMode {
  if (t.allowAllTenantUsers) return "all";
  if (t.userIds.length && t.groupIds.length) return "users";
  if (t.userIds.length) return "users";
  if (t.groupIds.length) return "groups";
  return "users";
}

export interface NotificationAudienceDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  typeKey: NotificationAudienceTypeKey | null;
  targeting: NotificationTypeTargeting | undefined;
  users: User[];
  groups: UserGroup[];
  onSave: (typeKey: string, payload: NotificationTypeTargetingPayload) => Promise<void>;
  savingTypeKey: string | null;
  isSaving: boolean;
}

export function NotificationAudienceDialog({
  isOpen,
  onOpenChange,
  typeKey,
  targeting,
  users,
  groups,
  onSave,
  savingTypeKey,
  isSaving,
}: NotificationAudienceDialogProps) {
  const meta = typeKey ? TYPE_META[typeKey] : null;
  const [mode, setMode] = useState<AudienceMode>("all");
  const [userIds, setUserIds] = useState<Set<string>>(new Set());
  const [groupIds, setGroupIds] = useState<Set<string>>(new Set());
  const [userQuery, setUserQuery] = useState("");

  useEffect(() => {
    if (!isOpen) {
      setUserQuery("");
      return;
    }
    if (!targeting) return;
    setMode(deriveMode(targeting));
    setUserIds(new Set(targeting.userIds));
    setGroupIds(new Set(targeting.groupIds));
  }, [isOpen, targeting]);

  const sortedUsers = useMemo(
    () =>
      [...users].sort((a, b) =>
        (a.username || "").localeCompare(b.username || "", undefined, {
          sensitivity: "base",
        }),
      ),
    [users],
  );

  const sortedGroups = useMemo(
    () =>
      [...groups].sort((a, b) =>
        (a.name || "").localeCompare(b.name || "", undefined, {
          sensitivity: "base",
        }),
      ),
    [groups],
  );

  const q = userQuery.trim().toLowerCase();
  const filteredUsers = useMemo(() => {
    if (!q) return sortedUsers;
    return sortedUsers.filter((u) => {
      const hay = `${u.username} ${u.email}`.toLowerCase();
      return hay.includes(q);
    });
  }, [sortedUsers, q]);

  const toggleUser = (id: string) => {
    setUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleGroup = (id: string) => {
    setGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    if (!typeKey) return;
    if (mode === "all") {
      try {
        await onSave(typeKey, {
          allowAllTenantUsers: true,
          userIds: [],
          groupIds: [],
        });
        toast.success("Audience updated");
        onOpenChange(false);
      } catch {
        toast.error("Could not update audience");
      }
      return;
    }
    if (mode === "users") {
      if (userIds.size === 0) {
        toast.error(
          "Select at least one user, or choose everyone or groups instead.",
        );
        return;
      }
      try {
        await onSave(typeKey, {
          allowAllTenantUsers: false,
          userIds: [...userIds],
          groupIds: [],
        });
        toast.success("Audience updated");
        onOpenChange(false);
      } catch {
        toast.error("Could not update audience");
      }
      return;
    }
    if (groupIds.size === 0) {
      toast.error(
        "Select at least one group, or choose everyone or users instead.",
      );
      return;
    }
    try {
      await onSave(typeKey, {
        allowAllTenantUsers: false,
        userIds: [],
        groupIds: [...groupIds],
      });
      toast.success("Audience updated");
      onOpenChange(false);
    } catch {
      toast.error("Could not update audience");
    }
  };

  const bothConfigured =
    targeting &&
    !targeting.allowAllTenantUsers &&
    targeting.userIds.length > 0 &&
    targeting.groupIds.length > 0;

  const rowSaving = Boolean(typeKey && isSaving && savingTypeKey === typeKey);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,44rem)] w-[min(100vw-1.5rem,42rem)] max-w-[min(100vw-1.5rem,42rem)] flex-col gap-0 overflow-y-auto overflow-x-visible p-6 sm:max-w-2xl">
        {meta && typeKey ? (
          <>
            <DialogHeader className="shrink-0 pr-8">
              <DialogTitle>{meta.title}</DialogTitle>
              <p className="text-sm text-muted-foreground">{meta.description}</p>
              <p className="text-xs text-muted-foreground border-t pt-3 mt-2">
                Administrator accounts always receive every notification type in the app
                and are not listed as selectable recipients.
              </p>
            </DialogHeader>

            {!targeting ? (
              <p className="text-sm text-muted-foreground py-4">Loading…</p>
            ) : (
              <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden py-2">
                {bothConfigured ? (
                  <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
                    This type is limited by both users and groups on the server. Saving
                    applies only the mode you choose below; the other list will be cleared.
                  </p>
                ) : null}

                <RadioGroup
                  value={mode}
                  onValueChange={(v) => setMode(v as AudienceMode)}
                  className="grid min-w-0 gap-3 py-2"
                >
                  <div
                    className={cn(
                      "flex min-w-0 gap-3 rounded-lg border border-transparent p-3 transition-colors",
                      mode === "all" && "border-border bg-muted/50",
                    )}
                  >
                    <RadioGroupItem value="all" id={`dlg-${typeKey}-all`} className="mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <Label
                        htmlFor={`dlg-${typeKey}-all`}
                        className="flex cursor-pointer items-center gap-2 font-normal"
                      >
                        <Users className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span>Everyone in the tenant</span>
                      </Label>
                      <p className="mt-1 pl-6 text-xs text-muted-foreground">
                        All users may receive this type (subject to their own toggles where
                        applicable).
                      </p>
                    </div>
                  </div>

                  <div
                    className={cn(
                      "flex min-w-0 gap-3 rounded-lg border border-transparent p-3 transition-colors",
                      mode === "users" && "border-border bg-muted/50",
                    )}
                  >
                    <RadioGroupItem value="users" id={`dlg-${typeKey}-users`} className="mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1 overflow-hidden">
                      <Label
                        htmlFor={`dlg-${typeKey}-users`}
                        className="flex cursor-pointer items-center gap-2 font-normal"
                      >
                        <UserRound className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span>Only selected users</span>
                      </Label>
                      <p className="mt-1 pl-6 text-xs text-muted-foreground">
                        Pick one or more non-admin users.
                      </p>
                      {mode === "users" ? (
                        <div className="mt-3 w-full min-w-0 space-y-2 pl-6 pr-0">
                          <Input
                            placeholder="Search by name or email…"
                            value={userQuery}
                            onChange={(e) => setUserQuery(e.target.value)}
                            className="h-9 w-full min-w-0 max-w-full"
                          />
                          <div className="max-h-60 w-full min-w-0 max-w-full space-y-1 overflow-y-auto overflow-x-hidden rounded-md border bg-background p-2">
                            {filteredUsers.length === 0 ? (
                              <p className="text-xs text-muted-foreground px-1 py-2">
                                No users match your search.
                              </p>
                            ) : (
                              filteredUsers.map((u) => {
                                const id = u.id;
                                if (!id) return null;
                                return (
                                  <label
                                    key={id}
                                    className="flex min-w-0 cursor-pointer items-start gap-2 rounded-sm px-1 py-1.5 text-sm hover:bg-muted/80"
                                  >
                                    <Checkbox
                                      checked={userIds.has(id)}
                                      onCheckedChange={() => toggleUser(id)}
                                      className="mt-0.5 shrink-0"
                                    />
                                    <span className="min-w-0 flex-1 leading-snug">
                                      <span className="block truncate font-medium">{u.username}</span>
                                      <span className="block truncate text-xs text-muted-foreground">
                                        {u.email}
                                      </span>
                                    </span>
                                  </label>
                                );
                              })
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div
                    className={cn(
                      "flex min-w-0 gap-3 rounded-lg border border-transparent p-3 transition-colors",
                      mode === "groups" && "border-border bg-muted/50",
                    )}
                  >
                    <RadioGroupItem
                      value="groups"
                      id={`dlg-${typeKey}-groups`}
                      className="mt-0.5 shrink-0"
                    />
                    <div className="min-w-0 flex-1 overflow-hidden">
                      <Label
                        htmlFor={`dlg-${typeKey}-groups`}
                        className="flex cursor-pointer items-center gap-2 font-normal"
                      >
                        <UsersRound className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span>Only selected groups</span>
                      </Label>
                      <p className="mt-1 pl-6 text-xs text-muted-foreground">
                        Members (and supervisors where applicable) of these groups may receive
                        this type.
                      </p>
                      {mode === "groups" ? (
                        <div className="mt-3 max-h-60 w-full min-w-0 space-y-1 overflow-y-auto overflow-x-hidden rounded-md border bg-background p-2 pl-6">
                          {sortedGroups.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No groups found.</p>
                          ) : (
                            sortedGroups.map((g) => (
                              <label
                                key={g.id}
                                className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-1.5 text-sm hover:bg-muted/80"
                              >
                                <Checkbox
                                  checked={groupIds.has(g.id)}
                                  onCheckedChange={() => toggleGroup(g.id)}
                                />
                                <span className="truncate">{g.name}</span>
                              </label>
                            ))
                          )}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </RadioGroup>
              </div>
            )}

            <DialogFooter className="mt-4 shrink-0 border-t border-border/60 pt-4 gap-2 sm:gap-0">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                loading={rowSaving}
                icon={<Save className="h-4 w-4" />}
                disabled={!targeting}
                onClick={() => void handleSave()}
              >
                Save audience
              </Button>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
