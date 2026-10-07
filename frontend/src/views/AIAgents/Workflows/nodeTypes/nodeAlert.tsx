import { CircleAlert } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { renderIcon } from "../utils/iconUtils";

interface NodeAlertProps {
  missingFields: string[];
  onFix?: () => void;
  onTest?: () => void;
}

export const NodeAlert: React.FC<NodeAlertProps> = ({
  missingFields,
  onFix,
  onTest,
}) => {
  const hasMissingFields = missingFields && missingFields.length > 0;
  const message = hasMissingFields
    ? `Missing: ${missingFields.join(", ")}`
    : "Node not yet tested";
  const actionText = hasMissingFields ? "Add" : "Test";
  const handleClick = hasMissingFields ? onFix : onTest;

  return (
    <div className="flex items-center gap-3 p-4 mx-0.5 mb-0.5 mt-1 bg-destructive rounded-sm text-destructive-foreground nodrag nopan pointer-events-auto">
      <div className="flex items-center justify-center">
        {renderIcon("CircleAlert")}
      </div>
      <div className="flex-1 flex items-center">{message}</div>
      <div className="flex items-center justify-center">
        <span className="underline cursor-pointer" onClick={handleClick}>
          {actionText}
        </span>
      </div>
    </div>
  );
};

// Compact-view counterpart of NodeAlert: the alert badge on the icon tile, with
// the same message and Add/Test action surfaced in a hover tooltip.
export const CompactNodeAlert: React.FC<NodeAlertProps> = ({
  missingFields,
  onFix,
  onTest,
}) => {
  const hasMissingFields = missingFields && missingFields.length > 0;
  const actionText = hasMissingFields ? "Add" : "Test";
  const handleClick = hasMissingFields ? onFix : onTest;

  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="absolute bottom-2.5 right-2.5 inline-flex nodrag nopan pointer-events-auto">
            <CircleAlert className="h-5 w-5 text-red-500" />
          </span>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          className="w-60 rounded-lg border-red-200 p-0 shadow-lg dark:border-red-900/60"
        >
          <div className="flex items-start gap-2.5 p-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-950">
              <CircleAlert className="h-4 w-4 text-red-600 dark:text-red-400" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold leading-5 text-foreground">
                {hasMissingFields
                  ? "Missing required fields"
                  : "Node not yet tested"}
              </div>
              {hasMissingFields ? (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {missingFields.map((field) => (
                    <span
                      key={field}
                      className="rounded-md bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-300"
                    >
                      {field}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="mt-0.5 text-xs text-muted-foreground">
                  Run a test to validate this node.
                </div>
              )}
            </div>
          </div>
          {handleClick && (
            <div className="flex justify-end border-t border-border px-3 py-2">
              <button
                type="button"
                className="text-sm font-medium text-red-600 underline underline-offset-2 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                onClick={handleClick}
              >
                {actionText}
              </button>
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
