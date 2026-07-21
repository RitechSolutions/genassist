import React from "react";
import {
  ArrowRight,
  BadgeCheck,
  Globe,
  Loader2,
  Pencil,
  Trash2,
  Undo2,
  Upload,
} from "lucide-react";
import { cn } from "@/helpers/utils";
import { Button } from "@/components/button";
import { TemplateListItem } from "@/interfaces/template.interface";
import { capabilities, categoryColor, iconFor } from "../templateMeta";

interface TemplateCardProps {
  template: TemplateListItem;
  onUse?: (template: TemplateListItem) => void;
  onDelete?: (template: TemplateListItem) => void;
  onPublish?: (template: TemplateListItem) => void;
  onUnpublish?: (template: TemplateListItem) => void;
  onRemove?: (template: TemplateListItem) => void;
  onApprove?: (template: TemplateListItem) => void;
  onReject?: (template: TemplateListItem) => void;
  installing?: boolean;
  busy?: boolean;
}

const STATUS_PILL: Record<string, { label: string; cls: string }> = {
  pending: { label: "Pending review", cls: "bg-orange-50 text-orange-700" },
  approved: { label: "Published", cls: "bg-green-50 text-green-700" },
  rejected: { label: "Rejected", cls: "bg-red-50 text-red-700" },
};

export function TemplateCard({
  template,
  onUse,
  onDelete,
  onPublish,
  onUnpublish,
  onRemove,
  onApprove,
  onReject,
  installing,
  busy,
}: TemplateCardProps) {
  const Icon = iconFor(template.icon);
  const color = categoryColor(template.category);
  const caps = capabilities(template.node_types).slice(0, 3);

  const reviewMode = !!onApprove;
  const published =
    template.publish_status === "pending" ||
    template.publish_status === "approved";
  const publishable =
    !!onPublish && !template.is_official && !template.is_global && !published;
  const unpublishable =
    !!onUnpublish && !template.is_official && !template.is_global && published;
  const statusPill =
    template.publish_status && !template.is_global
      ? STATUS_PILL[template.publish_status]
      : null;

  return (
    <div
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border bg-card p-5 shadow-sm",
        "transition-all duration-200 hover:-translate-y-1 hover:shadow-xl hover:border-[color:var(--cat)]"
      )}
      style={{ ["--cat" as string]: color }}
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <Icon
            className="h-5 w-5 flex-none"
            style={{ color: "var(--cat)" }}
          />
          <h3 className="truncate text-[16px] font-semibold leading-tight tracking-tight text-foreground">
            {template.title}
          </h3>
        </div>
        <div className="flex-none">
          {template.is_official ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-bold text-brand-600">
              <BadgeCheck className="h-3 w-3" />
              Official
            </span>
          ) : template.is_global ? (
            <span className="inline-flex items-center gap-1 rounded-full border bg-muted/60 px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              <Globe className="h-3 w-3" />
              Community
            </span>
          ) : statusPill ? (
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                statusPill.cls
              )}
            >
              {statusPill.label}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              <Pencil className="h-2.5 w-2.5" />
              My template
            </span>
          )}
        </div>
      </div>

      {template.category ? (
        <div
          className="mb-2 text-[11px] font-bold uppercase tracking-wide"
          style={{ color: "var(--cat)" }}
        >
          {template.category}
        </div>
      ) : (
        <div className="mb-2" />
      )}

      <p
        className={cn(
          "mb-4 line-clamp-2 min-h-[3em] text-[13.5px]",
          template.description
            ? "text-muted-foreground"
            : "italic text-muted-foreground/60"
        )}
      >
        {template.description || "No description yet."}
      </p>

      {caps.length ? (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {caps.map((cap) => (
            <span
              key={cap}
              className="rounded-md border bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] font-medium text-muted-foreground"
            >
              {cap}
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-muted-foreground/80">
          {reviewMode && template.source_tenant ? (
            <>
              from <b className="text-muted-foreground">{template.source_tenant}</b> ·{" "}
            </>
          ) : null}
          <b className="text-muted-foreground tabular-nums">{template.node_count}</b> steps
          {template.install_count > 0 ? (
            <>
              {" · "}
              <b className="text-muted-foreground tabular-nums">
                {template.install_count}
              </b>{" "}
              installs
            </>
          ) : null}
        </span>

        {reviewMode ? (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="rounded-lg"
              onClick={() => onReject?.(template)}
              disabled={busy}
            >
              Reject
            </Button>
            <Button
              size="sm"
              className="rounded-lg"
              onClick={() => onApprove?.(template)}
              disabled={busy}
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Approve"}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            {unpublishable ? (
              <button
                type="button"
                onClick={() => onUnpublish?.(template)}
                aria-label="Remove from the global library"
                title="Remove from the global library"
                className="grid h-9 w-9 place-items-center rounded-lg border bg-card text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                <Undo2 className="h-4 w-4" />
              </button>
            ) : publishable ? (
              <button
                type="button"
                onClick={() => onPublish?.(template)}
                aria-label="Publish to all tenants"
                title="Publish to all tenants"
                className="grid h-9 w-9 place-items-center rounded-lg border bg-card text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                <Upload className="h-4 w-4" />
              </button>
            ) : null}
            {onRemove && template.is_global ? (
              <button
                type="button"
                onClick={() => onRemove(template)}
                aria-label="Remove from the global library"
                title="Remove from the global library"
                className="grid h-9 w-9 place-items-center rounded-lg border bg-card text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            ) : null}
            {onDelete && !template.is_official && !template.is_global ? (
              <button
                type="button"
                onClick={() => onDelete(template)}
                aria-label="Delete template"
                className="grid h-9 w-9 place-items-center rounded-lg border bg-card text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            ) : null}
            {onUse ? (
              <Button
                size="sm"
                className="gap-1.5 rounded-lg"
                onClick={() => onUse(template)}
                disabled={installing}
              >
                {installing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    Use
                    <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                  </>
                )}
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
