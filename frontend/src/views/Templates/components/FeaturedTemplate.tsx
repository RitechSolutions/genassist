import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/button";
import { TemplateListItem } from "@/interfaces/template.interface";
import { capabilities, categoryColor, iconFor } from "../templateMeta";

interface FeaturedTemplateProps {
  template: TemplateListItem;
  installs?: number;
  onUse: (template: TemplateListItem) => void;
  installing?: boolean;
}

export function FeaturedTemplate({
  template,
  installs,
  onUse,
  installing,
}: FeaturedTemplateProps) {
  const Icon = iconFor(template.icon);
  const color = categoryColor(template.category);
  const caps = capabilities(template.node_types).slice(0, 4);

  return (
    <section
      className="relative mb-5 grid grid-cols-1 items-center gap-7 overflow-hidden rounded-[22px] border p-6 shadow-sm md:grid-cols-[1fr_auto]"
      style={{
        ["--cat" as string]: color,
        borderColor: "color-mix(in srgb, var(--cat) 30%, hsl(var(--border)))",
        background:
          "radial-gradient(120% 140% at 92% -20%, color-mix(in srgb, var(--cat) 16%, transparent), transparent 60%), hsl(var(--card))",
      }}
    >
      <div>
        <p
          className="mb-2.5 text-[11px] font-bold uppercase tracking-[0.16em]"
          style={{ color: "var(--cat)" }}
        >
          Most popular
        </p>
        <div className="mb-3 flex items-center gap-3">
          <Icon className="h-6 w-6 flex-none" style={{ color: "var(--cat)" }} />
          <div>
            <h2 className="text-[22px] font-extrabold leading-tight tracking-tight text-foreground">
              {template.title}
            </h2>
            {template.category ? (
              <div
                className="text-[11px] font-bold uppercase tracking-wide"
                style={{ color: "var(--cat)" }}
              >
                {template.category}
              </div>
            ) : null}
          </div>
        </div>
        <p className="mb-4 max-w-[52ch] text-[14px] text-muted-foreground">
          {template.description || "No description provided."}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            className="gap-2 rounded-lg text-white hover:opacity-90"
            style={{ background: "var(--cat)" }}
            onClick={() => onUse(template)}
            disabled={installing}
          >
            {installing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                Use
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
          {typeof installs === "number" ? (
            <span className="text-[13px] font-medium text-muted-foreground">
              {installs > 0
                ? `${installs} install${installs === 1 ? "" : "s"}`
                : "New"}
            </span>
          ) : null}
          {caps.length ? (
            <div className="flex flex-wrap gap-1.5">
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
        </div>
      </div>

      {/* decorative branch/merge diagram in the category hue */}
      <div
        className="hidden h-[150px] w-[230px] flex-none place-items-center rounded-2xl border md:grid"
        style={{
          color: "var(--cat)",
          borderColor: "hsl(var(--border))",
          background:
            "radial-gradient(circle, hsl(var(--muted-foreground) / 0.18) 1px, transparent 1.4px) 0 0 / 14px 14px, hsl(var(--muted) / 0.35)",
        }}
        aria-hidden="true"
      >
        <svg width="150" height="96" viewBox="0 0 150 96" fill="none">
          <rect x="6" y="38" width="34" height="20" rx="6" fill="color-mix(in srgb, currentColor 16%, transparent)" stroke="currentColor" />
          <rect x="58" y="12" width="34" height="20" rx="6" fill="color-mix(in srgb, currentColor 10%, transparent)" stroke="color-mix(in srgb, currentColor 55%, transparent)" />
          <rect x="58" y="64" width="34" height="20" rx="6" fill="color-mix(in srgb, currentColor 10%, transparent)" stroke="color-mix(in srgb, currentColor 55%, transparent)" />
          <rect x="110" y="38" width="34" height="20" rx="6" fill="currentColor" stroke="currentColor" />
          <path d="M40 48 C50 48 48 22 58 22" stroke="currentColor" strokeWidth="1.6" fill="none" />
          <path d="M40 48 C50 48 48 74 58 74" stroke="color-mix(in srgb, currentColor 55%, transparent)" strokeWidth="1.6" fill="none" />
          <path d="M92 22 C104 22 100 48 110 48" stroke="color-mix(in srgb, currentColor 55%, transparent)" strokeWidth="1.6" fill="none" />
          <path d="M92 74 C104 74 100 48 110 48" stroke="currentColor" strokeWidth="1.6" fill="none" />
        </svg>
      </div>
    </section>
  );
}
