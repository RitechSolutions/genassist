import React from "react";
import { Loader2, Pencil, Play, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { Progress } from "@/components/progress";
import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";
import { EntityTitle } from "./EntityTitle";
import { accuracyColorClass } from "../helpers/evaluationMetrics";

interface EvaluationListRowProps {
  evaluation: TestEvaluationConfig;
  avgAccuracy: number | null;
  isRunning: boolean;
  lastRunStatus?: string;
  onOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onRun: (e: React.MouseEvent) => void;
}

export const EvaluationListRow: React.FC<EvaluationListRowProps> = ({
  evaluation,
  avgAccuracy,
  isRunning,
  lastRunStatus,
  onOpen,
  onEdit,
  onDelete,
  onRun,
}) => (
  <div className="w-full py-4 px-6 text-left hover:bg-gray-50 transition-colors">
    <div className="flex items-center justify-between gap-4">
      <button type="button" onClick={onOpen} className="flex-1 min-w-0 text-left">
        <div className="flex items-center gap-2">
          <EntityTitle>{evaluation.name}</EntityTitle>
          <Badge variant="secondary" className="shrink-0 text-[10px] px-1.5">
            EVAL
          </Badge>
        </div>
        <p className="text-sm text-gray-500 mt-1 line-clamp-1">
          {evaluation.description || "No description"}
        </p>

        {isRunning ? (
          <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-blue-600">
            <Loader2 className="h-3 w-3 animate-spin" />
            {lastRunStatus === "queued" ? "Queued" : "Running…"}
          </div>
        ) : lastRunStatus === "failed" ? (
          <div className="mt-2 text-xs font-medium text-red-600">Last run failed</div>
        ) : avgAccuracy !== null ? (
          <div className="flex items-center gap-2 mt-2">
            <Progress value={avgAccuracy * 100} className="h-2 w-32 bg-gray-100" />
            <span className={`text-xs font-medium ${accuracyColorClass(avgAccuracy)}`}>
              {Math.round(avgAccuracy * 100)}% accuracy
            </span>
            <span className="text-xs text-gray-400">
              ({evaluation.run_ids.length} run{evaluation.run_ids.length !== 1 ? "s" : ""})
            </span>
          </div>
        ) : (
          <div className="mt-2 text-xs text-gray-400">Not run yet</div>
        )}

        <div className="flex flex-wrap items-center gap-1 mt-2">
          <span className="text-xs text-gray-500 mr-1">Metrics:</span>
          {evaluation.techniques.map((tech) => (
            <Badge key={tech} variant="outline" className="text-[10px] px-1.5 py-0">
              {tech}
            </Badge>
          ))}
        </div>
      </button>

      <div className="flex items-center gap-1 shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label="Edit evaluation"
          onClick={onEdit}
        >
          <Pencil className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label="Delete evaluation"
          onClick={onDelete}
        >
          <Trash2 className="h-4 w-4 text-red-500" />
        </Button>
        <Button size="sm" className="ml-1" disabled={isRunning} onClick={onRun}>
          <Play className="h-3.5 w-3.5 mr-1" />
          {isRunning ? "Running..." : "Run"}
        </Button>
      </div>
    </div>
  </div>
);
