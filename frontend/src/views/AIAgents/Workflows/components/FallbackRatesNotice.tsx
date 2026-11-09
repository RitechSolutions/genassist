import { AlertTriangle, X } from "lucide-react";

import { ManageCostsLink } from "@/components/ManageCostsLink";
import { useDismissibleNotice } from "@/hooks/useDismissibleNotice";

const NOTICE = "workflow-test-fallback-rates";

interface FallbackRatesNoticeProps {
  models: string[];
}

export function FallbackRatesNotice({ models }: FallbackRatesNoticeProps) {
  const notice = useDismissibleNotice(NOTICE, JSON.stringify(models));

  if (!notice.visible) return null;

  return (
    <div className="mb-3 flex items-center gap-3 rounded-lg border border-amber-500/35 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span className="flex-1">
        <span className="font-semibold">
          Test run costs use bundled fallback rates unless you add your own.
        </span>{" "}
        They may differ from what your provider charges.
      </span>
      <ManageCostsLink />
      <button
        type="button"
        onClick={notice.dismiss}
        aria-label="Dismiss fallback rates notice"
        className="shrink-0 rounded p-0.5 opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
