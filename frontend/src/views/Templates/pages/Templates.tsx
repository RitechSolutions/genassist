import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import { Plus, LayoutTemplate, ClipboardCheck } from "lucide-react";

import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { Button } from "@/components/button";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { cn } from "@/helpers/utils";
import { usePermissions } from "@/context/PermissionContext";
import { TemplateCard } from "../components/TemplateCard";
import { FeaturedTemplate } from "../components/FeaturedTemplate";
import { categoryColor } from "../templateMeta";
import {
  approveTemplate,
  deleteTemplate,
  getReviewQueue,
  getTemplates,
  installTemplate,
  publishTemplate,
  rejectTemplate,
  removeGlobalTemplate,
  unpublishTemplate,
} from "@/services/templates";
import { TemplateListItem } from "@/interfaces/template.interface";

type Tab = "all" | "official" | "community" | "mine" | "review";

export default function TemplatesPage() {
  const navigate = useNavigate();
  const permissions = usePermissions();
  const canApprove =
    permissions.includes("*") || permissions.includes("approve:template");

  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<Tab>("all");
  const [selectedCats, setSelectedCats] = useState<Set<string>>(new Set());
  const [installingId, setInstallingId] = useState<string | null>(null);

  const [reviewItems, setReviewItems] = useState<TemplateListItem[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [busyReviewId, setBusyReviewId] = useState<string | null>(null);

  const [publishTarget, setPublishTarget] = useState<TemplateListItem | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<TemplateListItem | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [removeTarget, setRemoveTarget] = useState<TemplateListItem | null>(null);
  const [removing, setRemoving] = useState(false);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      setTemplates(await getTemplates());
    } catch {
      toast.error("Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadReview = useCallback(async () => {
    setReviewLoading(true);
    try {
      setReviewItems(await getReviewQueue());
    } catch {
      toast.error("Failed to load the review queue");
    } finally {
      setReviewLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  useEffect(() => {
    if (tab === "review" && canApprove) loadReview();
  }, [tab, canApprove, loadReview]);

  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of templates) {
      if (t.category) counts.set(t.category, (counts.get(t.category) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([name, count]) => ({ name, count, color: categoryColor(name) }))
      .sort((a, b) => b.count - a.count);
  }, [templates]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return templates.filter((t) => {
      if (tab === "official" && !t.is_official) return false;
      if (tab === "community" && !t.is_global) return false;
      if (tab === "mine" && (t.is_official || t.is_global)) return false;
      if (selectedCats.size && !(t.category && selectedCats.has(t.category)))
        return false;
      if (!q) return true;
      return (
        t.title.toLowerCase().includes(q) ||
        (t.description || "").toLowerCase().includes(q) ||
        (t.category || "").toLowerCase().includes(q)
      );
    });
  }, [templates, tab, selectedCats, search]);

  const isDefaultView =
    tab === "all" && !search.trim() && selectedCats.size === 0;
  // "Most used": the most-installed community template.
  const featured = isDefaultView
    ? [...templates.filter((t) => t.is_global)].sort(
        (a, b) => b.install_count - a.install_count
      )[0] ?? null
    : null;
  const gridItems = featured
    ? filtered.filter((t) => t.id !== featured.id)
    : filtered;
  const showSaveTile =
    (tab === "all" || tab === "mine") && selectedCats.size === 0 && !search.trim();
  const isSearchingOrFiltering = search.trim() !== "" || selectedCats.size > 0;

  const toggleCat = (name: string) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleUse = async (template: TemplateListItem) => {
    setInstallingId(template.id);
    try {
      const res = await installTemplate(template.id);
      toast.success(
        `"${template.title}" added as an inactive draft — review it, then activate or delete it.`
      );
      navigate(`/ai-agents/workflow/${res.agent_id}?setup=true`);
    } catch {
      toast.error("Failed to create from template");
    } finally {
      setInstallingId(null);
    }
  };

  const handleDelete = async (template: TemplateListItem) => {
    try {
      await deleteTemplate(template.id);
      toast.success("Template deleted");
      setTemplates((prev) => prev.filter((t) => t.id !== template.id));
    } catch {
      toast.error("Failed to delete template");
    }
  };

  const handleUnpublish = async (template: TemplateListItem) => {
    try {
      await unpublishTemplate(template.id);
      toast.success("Removed from the global library");
      loadTemplates();
    } catch {
      toast.error("Failed to remove from the library");
    }
  };

  const confirmRemove = async () => {
    if (!removeTarget) return;
    setRemoving(true);
    try {
      await removeGlobalTemplate(removeTarget.id);
      toast.success("Removed from the library");
      setRemoveTarget(null);
      loadTemplates();
      if (tab === "review") loadReview();
    } catch {
      toast.error("Failed to remove");
    } finally {
      setRemoving(false);
    }
  };

  const confirmPublish = async () => {
    if (!publishTarget) return;
    setPublishing(true);
    try {
      await publishTemplate(publishTarget.id);
      toast.success("Submitted for review — a master admin will approve it.");
      setPublishTarget(null);
      loadTemplates();
    } catch {
      toast.error("Failed to submit for review");
    } finally {
      setPublishing(false);
    }
  };

  const handleApprove = async (template: TemplateListItem) => {
    setBusyReviewId(template.id);
    try {
      await approveTemplate(template.id);
      toast.success(`"${template.title}" published to all tenants`);
      loadReview();
      loadTemplates();
    } catch {
      toast.error("Failed to approve");
    } finally {
      setBusyReviewId(null);
    }
  };

  const confirmReject = async () => {
    if (!rejectTarget) return;
    setBusyReviewId(rejectTarget.id);
    try {
      await rejectTemplate(rejectTarget.id, rejectReason.trim() || undefined);
      toast.success("Template rejected");
      setRejectTarget(null);
      setRejectReason("");
      loadReview();
    } catch {
      toast.error("Failed to reject");
    } finally {
      setBusyReviewId(null);
    }
  };

  const hasOfficial = templates.some((t) => t.is_official);
  const tabs: { key: Tab; label: string }[] = [
    { key: "all", label: "All" },
    ...(hasOfficial ? [{ key: "official" as Tab, label: "Official" }] : []),
    { key: "community", label: "Community" },
    { key: "mine", label: "Mine" },
    ...(canApprove ? [{ key: "review" as Tab, label: "Review" }] : []),
  ];

  return (
    <PageLayout>
      <PageHeader
        title="Templates"
        subtitle="Start from a prebuilt workflow. Drop it in as a draft and make it yours."
        searchQuery={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search templates…"
      />

      {/* Filters */}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
          <TabsList>
            {tabs.map((t) => (
              <TabsTrigger key={t.key} value={t.key}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {tab !== "review" && categories.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {categories.map((c) => {
              const active = selectedCats.has(c.name);
              return (
                <button
                  key={c.name}
                  type="button"
                  onClick={() => toggleCat(c.name)}
                  aria-pressed={active}
                  style={{
                    ["--cat" as string]: c.color,
                    backgroundColor: active
                      ? "color-mix(in srgb, var(--cat) 12%, hsl(var(--card)))"
                      : undefined,
                  }}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12.5px] font-semibold transition-colors",
                    active
                      ? "border-[color:var(--cat)] text-foreground"
                      : "border-border bg-card text-muted-foreground hover:text-foreground"
                  )}
                >
                  <span
                    className="h-2.5 w-2.5 rounded-[3px]"
                    style={{ background: "var(--cat)" }}
                  />
                  {c.name}
                  <span className="text-[11px] font-bold tabular-nums text-muted-foreground/70">
                    {c.count}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Review queue */}
      {tab === "review" ? (
        <div className="mt-6">
          {reviewLoading ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-[230px] animate-pulse rounded-2xl border bg-muted/40"
                />
              ))}
            </div>
          ) : reviewItems.length === 0 ? (
            <div className="rounded-md border bg-card dark:bg-zinc-900 shadow-sm overflow-hidden">
              <ListEmptyState
                icon={<ClipboardCheck className="h-12 w-12 text-muted-foreground" />}
                title="Nothing to review"
                description="Published templates awaiting approval will appear here."
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {reviewItems.map((t) => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  onApprove={handleApprove}
                  onReject={setRejectTarget}
                  busy={busyReviewId === t.id}
                />
              ))}
            </div>
          )}
        </div>
      ) : loading ? (
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-[230px] animate-pulse rounded-2xl border bg-muted/40"
            />
          ))}
        </div>
      ) : (
        <div className="mt-6">
          {featured ? (
            <FeaturedTemplate
              template={featured}
              installs={featured.install_count}
              onUse={handleUse}
              installing={installingId === featured.id}
            />
          ) : null}

          {gridItems.length === 0 && !featured ? (
            <div className="rounded-md border bg-card dark:bg-zinc-900 shadow-sm overflow-hidden">
            <ListEmptyState
              icon={<LayoutTemplate className="h-12 w-12 text-muted-foreground" />}
              title={
                isSearchingOrFiltering
                  ? "No templates found"
                  : tab === "mine"
                    ? "No templates of your own yet"
                    : tab === "community"
                      ? "No community templates yet"
                      : tab === "official"
                        ? "No official templates yet"
                        : "No templates yet"
              }
              description={
                isSearchingOrFiltering
                  ? "No templates match your search or filters. Try a different query or clearing a filter."
                  : tab === "mine"
                    ? "Save an agent you've built as a template from Agent Studio to reuse it or publish it to every tenant."
                    : tab === "community"
                      ? "No community templates yet — publish one of yours to share it with every tenant."
                      : tab === "official"
                        ? "Official templates curated for your workspace will appear here."
                        : "Start from a prebuilt workflow, or save an agent you've built as your own template."
              }
              action={
                showSaveTile ? (
                  <Button
                    className="rounded-full"
                    onClick={() => navigate("/ai-agents")}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Save your own
                  </Button>
                ) : undefined
              }
            />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {gridItems.map((t) => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  onUse={handleUse}
                  onDelete={handleDelete}
                  onPublish={setPublishTarget}
                  onUnpublish={handleUnpublish}
                  onRemove={canApprove ? setRemoveTarget : undefined}
                  installing={installingId === t.id}
                />
              ))}

              {showSaveTile && (
                <button
                  type="button"
                  onClick={() => navigate("/ai-agents")}
                  className="group flex min-h-[230px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-transparent p-5 text-center transition-colors hover:border-primary/50"
                >
                  <span className="grid h-11 w-11 place-items-center rounded-xl border border-dashed border-border bg-muted/50 text-muted-foreground transition-colors group-hover:text-primary">
                    <Plus className="h-5 w-5" />
                  </span>
                  <span className="text-[16px] font-semibold text-foreground">
                    Save your own
                  </span>
                  <span className="max-w-[34ch] text-[13px] text-muted-foreground">
                    Turn any agent you&apos;ve built into a private template from
                    Agent Studio — reuse it or publish it to every tenant.
                  </span>
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        isOpen={!!publishTarget}
        onOpenChange={(open) => {
          if (!open) setPublishTarget(null);
        }}
        onConfirm={confirmPublish}
        isInProgress={publishing}
        primaryButtonText="Publish"
        title="Publish to the global library?"
        description="A master admin reviews it before other tenants can see it. Provider, knowledge base, and secret values are not shared."
        itemName={publishTarget?.title}
      />

      <ConfirmDialog
        isOpen={!!removeTarget}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
        onConfirm={confirmRemove}
        isInProgress={removing}
        primaryButtonText="Remove"
        title="Remove from the library?"
        description="This removes the community template for every tenant. Tenants that already installed it keep their agent."
        itemName={removeTarget?.title}
      />

      <Dialog
        open={!!rejectTarget}
        onOpenChange={(open) => {
          if (!open) {
            setRejectTarget(null);
            setRejectReason("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject template</DialogTitle>
            <DialogDescription>
              Optionally tell the author why “{rejectTarget?.title}” wasn&apos;t
              approved.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="reject-reason">Reason (optional)</Label>
            <Textarea
              id="reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Duplicates an existing template."
              maxLength={500}
            />
          </div>
          <DialogFooter className="mt-6">
            <Button
              variant="outline"
              onClick={() => {
                setRejectTarget(null);
                setRejectReason("");
              }}
              disabled={busyReviewId === rejectTarget?.id}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmReject}
              disabled={busyReviewId === rejectTarget?.id}
            >
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}
