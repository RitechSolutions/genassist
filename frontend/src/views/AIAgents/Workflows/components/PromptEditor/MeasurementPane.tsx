import React, { useId, useState } from "react";
import { AlertCircle, CheckCircle2, Play, Sparkles } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { PromptEditorCapabilities } from "../../utils/promptEditorCapabilities";
import { EvaluateSection } from "./EvaluateSection";
import {
  measurementStatus,
  SECTION_LABEL,
  type MeasurementSection,
} from "./measurementStatus";
import { OptimizeSection } from "./OptimizeSection";
import type { PromptMeasurementState } from "./usePromptMeasurement";

interface MeasurementPaneProps {
  caps: PromptEditorCapabilities;
  measurement: PromptMeasurementState;
}

export const MeasurementPane: React.FC<MeasurementPaneProps> = ({
  caps,
  measurement,
}) => {
  const [selected, setSelected] = useState<MeasurementSection>("evaluate");
  const statusId = useId();
  const headingId = useId();

  const sections: MeasurementSection[] = [
    ...(caps.canEvaluate ? (["evaluate"] as const) : []),
    ...(caps.canOptimize ? (["optimize"] as const) : []),
  ];
  const active = sections.includes(selected) ? selected : sections[0];
  const status = measurementStatus(measurement);

  const statusLine = (section: MeasurementSection, withLabel: boolean) =>
    status[section] && (
      <p
        key={section}
        id={`${statusId}-${section}`}
        className="text-xs text-muted-foreground"
      >
        {withLabel ? `${SECTION_LABEL[section]}: ` : ""}
        {status[section]}
      </p>
    );

  // An Evaluate Suggested failure is raised from Optimize
  const banners = (measurement.error || measurement.successMessage) && (
    <div className="shrink-0 space-y-2 border-b p-3">
      {measurement.error && (
        <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{measurement.error}</span>
        </div>
      )}
      {measurement.successMessage && (
        <div className="flex items-center gap-2 text-green-700 dark:text-green-400 text-sm bg-green-50 dark:bg-green-500/15 border border-green-200 dark:border-green-500/30 rounded-md px-3 py-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{measurement.successMessage}</span>
        </div>
      )}
    </div>
  );

  const body = (section: MeasurementSection) => (
    <div className="space-y-4">
      {section === "evaluate" ? (
        <EvaluateSection measurement={measurement} />
      ) : (
        <OptimizeSection caps={caps} measurement={measurement} />
      )}
      {measurement.hasRuns && (
        <p className="text-xs text-muted-foreground">
          Results are kept while this editor is open.
        </p>
      )}
    </div>
  );

  if (sections.length === 1) {
    const only = sections[0];
    return (
      <section
        aria-labelledby={headingId}
        aria-describedby={status[only] ? `${statusId}-${only}` : undefined}
        className="flex h-full min-h-0 flex-col overflow-hidden"
      >
        <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2.5">
          <h3 id={headingId} className="text-sm font-medium">
            {SECTION_LABEL[only]}
          </h3>
          {statusLine(only, false)}
        </div>
        {banners}
        <div className="min-h-0 flex-1 overflow-y-auto p-3">{body(only)}</div>
      </section>
    );
  }

  return (
    <Tabs
      value={active}
      onValueChange={(v) => setSelected(v as MeasurementSection)}
      className="flex h-full min-h-0 flex-col overflow-hidden"
    >
      <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2">
        <TabsList className="h-9">
          <TabsTrigger
            value="evaluate"
            aria-describedby={
              status.evaluate ? `${statusId}-evaluate` : undefined
            }
            className="gap-1.5 px-3 text-xs"
          >
            <Play className="h-3.5 w-3.5" />
            Evaluate
          </TabsTrigger>
          <TabsTrigger
            value="optimize"
            aria-describedby={
              status.optimize ? `${statusId}-optimize` : undefined
            }
            className="gap-1.5 px-3 text-xs"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Optimize
          </TabsTrigger>
        </TabsList>
        {sections.map((section) => statusLine(section, true))}
      </div>
      {banners}

      {sections.map((section) => (
        <TabsContent
          key={section}
          value={section}
          forceMount
          hidden={active !== section}
          className="mt-0 min-h-0 flex-1 overflow-y-auto p-3"
        >
          {body(section)}
        </TabsContent>
      ))}
    </Tabs>
  );
};
