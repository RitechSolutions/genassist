import { Coins, ExternalLink, Info, X } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/button";
import { usePermissions } from "@/context/PermissionContext";
import { cn } from "@/helpers/utils";
import { useDismissibleNotice } from "@/hooks/useDismissibleNotice";

const NOTICE = "workflow-test-fallback-rates";

interface FallbackRatesNoticeProps {
  models: string[];
}

export function FallbackRatesNotice({ models }: FallbackRatesNoticeProps) {
  const notice = useDismissibleNotice(NOTICE, JSON.stringify(models));
  const permissions = usePermissions();
  const canManageCosts =
    permissions.includes("*") || permissions.includes("read:llm_provider");

  if (!notice.visible) return null;

  return (
    <div className="mb-3 flex items-center gap-3 rounded-lg border border-border bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">
      <Info className="h-4 w-4 shrink-0" />
      <span>
        <span className="font-semibold text-foreground">
          Test run costs use bundled fallback rates unless you add your own.
        </span>{" "}
        They may differ from what your provider charges.
      </span>
      {canManageCosts && (
        <Link
          to="/llm-providers?manage=costs"
          target="_blank"
          rel="noopener noreferrer"
          className={buttonVariants({ variant: "outline", size: "sm", className: "ml-auto shrink-0" })}
        >
          <Coins />
          Manage costs
          <ExternalLink />
          <span className="sr-only">(opens in a new tab)</span>
        </Link>
      )}
      <button
        type="button"
        onClick={notice.dismiss}
        aria-label="Dismiss fallback rates notice"
        className={cn(
          "shrink-0 rounded p-0.5 opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          !canManageCosts && "ml-auto"
        )}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
