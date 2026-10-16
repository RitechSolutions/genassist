import { useState } from "react";
import { parseISO } from "date-fns";
import toast from "react-hot-toast";
import { CalendarDays, Wrench, X } from "lucide-react";

import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Calendar } from "@/components/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";

import { ReportedFeedbackItem } from "@/services/reportedFeedback";
import { extractErrorMessage } from "@/helpers/apiError";
import {
  draftToPatch,
  formatDateOnly,
  isDraftDirty,
  toDateOnly,
  toDraft,
  TriageDraft,
} from "../helpers/triageDraft";
import { useIssuePatch } from "../hooks/useReportedFeedback";
import { SectionLabel } from "./SectionLabel";

export function TriageSection({ issue }: { issue: ReportedFeedbackItem }) {
  const [draft, setDraft] = useState<TriageDraft>(() => toDraft(issue));
  const saveTriage = useIssuePatch();
  const triageDirty = isDraftDirty(issue, draft);

  const save = () => {
    const submitted = draft;
    void saveTriage.mutateAsync({ issue, patch: draftToPatch(issue, draft) }).then(
      (saved) => {
        setDraft((current) => (current === submitted ? toDraft(saved) : current));
        toast.success("Triage saved");
      },
      (err) => toast.error(extractErrorMessage(err, "Failed to update feedback")),
    );
  };

  return (
    <section>
      <SectionLabel icon={Wrench}>Triage</SectionLabel>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="feedback-fix-version" className="text-xs">
            Fix version
          </Label>
          <Input
            id="feedback-fix-version"
            className="h-9"
            maxLength={100}
            placeholder="e.g. 2.4.1"
            value={draft.fix_version}
            onChange={(e) =>
              setDraft((current) => ({
                ...current,
                fix_version: e.target.value,
              }))
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Target rollout date</Label>
          <div className="flex items-center gap-1">
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 flex-1 justify-start gap-2 rounded-full font-normal"
                >
                  <CalendarDays className="h-4 w-4 text-muted-foreground" />
                  {draft.target_rollout_date ? (
                    formatDateOnly(draft.target_rollout_date)
                  ) : (
                    <span className="text-muted-foreground">
                      Pick a date
                    </span>
                  )}
                </Button>
              </PopoverTrigger>
              {/* Above DialogContent (z-[1300]). */}
              <PopoverContent
                className="z-[1400] w-auto p-0"
                align="start"
              >
                <Calendar
                  mode="single"
                  required
                  selected={
                    draft.target_rollout_date
                      ? parseISO(draft.target_rollout_date)
                      : undefined
                  }
                  defaultMonth={
                    draft.target_rollout_date
                      ? parseISO(draft.target_rollout_date)
                      : undefined
                  }
                  onSelect={(day) =>
                    setDraft((current) => ({
                      ...current,
                      target_rollout_date: day
                        ? toDateOnly(day)
                        : null,
                    }))
                  }
                  initialFocus
                />
              </PopoverContent>
            </Popover>
            {draft.target_rollout_date && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-full"
                title="Clear the target rollout date"
                aria-label="Clear the target rollout date"
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    target_rollout_date: null,
                  }))
                }
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
      <div className="mt-3 flex justify-end">
        <Button
          type="button"
          size="sm"
          className="rounded-full"
          disabled={!triageDirty || saveTriage.isPending}
          onClick={save}
        >
          {saveTriage.isPending ? "Saving..." : "Save"}
        </Button>
      </div>
    </section>
  );
}
