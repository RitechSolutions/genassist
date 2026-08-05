import React, { useMemo, useRef, useState } from "react";
import { AlertTriangle, ChevronLeft, FileJson, Loader2, Upload } from "lucide-react";
import toast from "react-hot-toast";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  EvaluationBundle,
  EvaluationImportPreview,
  EvaluationImportResult,
} from "@/interfaces/evalBundle.interface";
import { EvaluationToolCatalog } from "@/interfaces/testEvaluation.interface";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import {
  getEvaluationToolCatalog,
  importEvaluation,
  previewEvaluationImport,
} from "@/services/testEvaluations";
import { nodeRefKey, parseBundleFile } from "../helpers/evalBundle";
import { groupWorkflowVersions } from "../helpers/workflowVersions";
import { ImportMappingTable } from "./ImportMappingTable";
import { WorkflowVersionPicker } from "./WorkflowVersionPicker";

type ImportStep = "file" | "workflow" | "review";

interface ImportEvaluationDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  workflows: WorkflowMinimal[];
  onImported: (result: EvaluationImportResult) => void;
}

/** Prefer the specific reason over the generic message: import errors name the
 * reference that could not be re-linked, which is what the user must act on. */
const apiErrorDetail = (error: unknown): string | undefined => {
  const data = (
    error as { response?: { data?: { error?: unknown; error_detail?: unknown } } }
  )?.response?.data;
  for (const candidate of [data?.error_detail, data?.error]) {
    if (typeof candidate === "string" && candidate.trim()) return candidate;
  }
  return undefined;
};

export const ImportEvaluationDialog: React.FC<ImportEvaluationDialogProps> = ({
  isOpen,
  onOpenChange,
  workflows,
  onImported,
}) => {
  const [step, setStep] = useState<ImportStep>("file");
  const [bundle, setBundle] = useState<EvaluationBundle | null>(null);
  const [fileName, setFileName] = useState("");
  const [fileError, setFileError] = useState("");
  const [targetWorkflowId, setTargetWorkflowId] = useState("");
  const [preview, setPreview] = useState<EvaluationImportPreview | null>(null);
  const [catalog, setCatalog] = useState<EvaluationToolCatalog | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [picks, setPicks] = useState<Record<string, string>>({});
  const [dropUnresolved, setDropUnresolved] = useState(false);
  const [reuseDataset, setReuseDataset] = useState(true);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  // Bumped per preview request (and on reset) so a slow response for a
  // previously chosen workflow can never overwrite the current one.
  const previewRequestRef = useRef(0);

  const reset = () => {
    previewRequestRef.current += 1;
    setStep("file");
    setBundle(null);
    setFileName("");
    setFileError("");
    setTargetWorkflowId("");
    setPreview(null);
    setCatalog(null);
    setCatalogFailed(false);
    setPicks({});
    setDropUnresolved(false);
    setReuseDataset(true);
    setIsPreviewLoading(false);
    setPreviewError("");
    setIsImporting(false);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const workflowGroups = useMemo(() => groupWorkflowVersions(workflows), [workflows]);

  const handleFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (loadEvent) => {
      try {
        const parsed = parseBundleFile(String(loadEvent.target?.result ?? ""));
        setBundle(parsed);
        setFileName(file.name);
        setFileError("");
        preselectWorkflow(parsed);
      } catch (error) {
        setBundle(null);
        setFileName(file.name);
        setFileError(error instanceof Error ? error.message : "Could not read the file.");
      }
    };
    reader.readAsText(file);
  };

  const preselectWorkflow = (parsed: EvaluationBundle) => {
    const sourceName = parsed.source?.workflow_name?.trim().toLowerCase();
    const group = sourceName
      ? workflowGroups.find((g) => g.name.trim().toLowerCase() === sourceName)
      : undefined;
    // Land on the live version, which is what a plain run would execute; always
    // overwrite so a selection from a previously chosen file cannot survive.
    setTargetWorkflowId(group?.activeVersionId ?? group?.versions[0].id ?? "");
  };

  const loadPreview = async () => {
    if (!bundle || !targetWorkflowId) return;
    const requestId = ++previewRequestRef.current;
    setStep("review");
    setIsPreviewLoading(true);
    setPreviewError("");
    setPreview(null);
    setPicks({});
    setDropUnresolved(false);
    setReuseDataset(true);
    try {
      const [previewData, catalogData] = await Promise.all([
        previewEvaluationImport({ bundle, target_workflow_id: targetWorkflowId }),
        getEvaluationToolCatalog(targetWorkflowId).catch(() => null),
      ]);
      if (requestId !== previewRequestRef.current) return;
      setPreview(previewData);
      setCatalog(catalogData);
      // Without the catalog we cannot offer manual picks; say that rather than
      // letting each row claim the workflow is empty.
      setCatalogFailed(catalogData === null);
      // When nothing matched, importing without those checks is the sane
      // default — unless that would leave no checks at all, which import
      // refuses, so offering it would be a dead end.
      const nothingResolved =
        (previewData?.node_refs.length ?? 0) > 0 &&
        previewData!.node_refs.every((nodeRef) => nodeRef.status !== "resolved");
      setDropUnresolved(
        nothingResolved && !previewData?.dropping_all_would_empty,
      );
      if (!previewData) setPreviewError("Could not preview the import.");
    } catch (error) {
      if (requestId !== previewRequestRef.current) return;
      setPreviewError(apiErrorDetail(error) ?? "Could not preview the import.");
    } finally {
      if (requestId === previewRequestRef.current) setIsPreviewLoading(false);
    }
  };

  const unresolvedRefs = useMemo(() => {
    if (!preview) return [];
    return preview.node_refs.filter(
      (nodeRef) => nodeRef.status !== "resolved" && !picks[nodeRefKey(nodeRef)],
    );
  }, [preview, picks]);

  // Nothing at all matching means this is almost certainly the wrong workflow,
  // not a mapping exercise — say so rather than posing a row of unanswerable
  // questions.
  const looksLikeWrongWorkflow = Boolean(
    preview &&
      preview.node_refs.length > 0 &&
      preview.node_refs.every((nodeRef) => nodeRef.status !== "resolved"),
  );

  // Import refuses an evaluation with no checks left, so dropping is not a way
  // forward here and the checkbox must not pretend otherwise.
  const dropWouldEmpty = Boolean(preview?.dropping_all_would_empty);

  const canImport =
    Boolean(preview) &&
    !isImporting &&
    (unresolvedRefs.length === 0 || dropUnresolved);

  const handleImport = async () => {
    if (!bundle || !targetWorkflowId) return;
    setIsImporting(true);
    try {
      const existingDatasetId = preview?.existing_dataset?.id;
      const result = await importEvaluation({
        bundle,
        target_workflow_id: targetWorkflowId,
        existing_suite_id:
          reuseDataset && existingDatasetId ? existingDatasetId : undefined,
        resolutions: picks,
        drop_unresolved_rules: dropUnresolved,
      });
      if (!result) {
        toast.error("You don't have permission to import evaluations.");
        return;
      }
      const notes = [
        result.reused_dataset ? "reusing the existing dataset" : null,
        result.dropped_rules.length > 0
          ? `${result.dropped_rules.length} rule${
              result.dropped_rules.length !== 1 ? "s" : ""
            } dropped`
          : null,
      ].filter(Boolean);
      const suffix = notes.length > 0 ? ` (${notes.join(", ")})` : "";
      toast.success(`Evaluation imported${suffix}`);
      // These say what the import silently decided — e.g. that a reused dataset
      // has a different number of cases than the file — so they must not be
      // dropped just because the dialog is closing.
      for (const warning of result.warnings) {
        toast(warning, { icon: "⚠️", duration: 8000 });
      }
      handleOpenChange(false);
      onImported(result);
    } catch (error) {
      toast.error(apiErrorDetail(error) ?? "Failed to import evaluation");
    } finally {
      setIsImporting(false);
    }
  };

  const renderFileStep = () => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Upload an evaluation bundle exported from another environment. The
        evaluation, its dataset and its checks are recreated here; run history
        does not travel.
      </p>
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-8">
        <FileJson className="h-8 w-8 text-muted-foreground" />
        <Button variant="outline" className="relative">
          <Upload className="mr-2 h-4 w-4" />
          Choose bundle file
          <Input
            type="file"
            accept=".json,application/json"
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            onChange={handleFile}
          />
        </Button>
        {fileName && !fileError && (
          <span className="text-xs text-muted-foreground">{fileName}</span>
        )}
        {fileError && <span className="text-xs text-destructive">{fileError}</span>}
      </div>
      {bundle && (
        <div className="rounded-lg border bg-muted/40 p-4 text-sm space-y-1">
          <div className="font-medium">{bundle.evaluation.name}</div>
          <div className="text-muted-foreground">
            Dataset "{bundle.dataset.name}" · {bundle.dataset.cases.length} case
            {bundle.dataset.cases.length !== 1 ? "s" : ""} ·{" "}
            {bundle.evaluation.techniques.length} metric
            {bundle.evaluation.techniques.length !== 1 ? "s" : ""}
          </div>
          {bundle.source?.workflow_name && (
            <div className="text-muted-foreground">
              Exported from workflow "{bundle.source.workflow_name}"
              {bundle.source.workflow_version ? ` v${bundle.source.workflow_version}` : ""}
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderWorkflowStep = () => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Choose the workflow this evaluation should test. References in the
        bundle's checks are matched against it by name.
      </p>
      <div className="space-y-1.5">
        <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Target workflow
        </Label>
        <WorkflowVersionPicker
          workflows={workflows}
          selectedWorkflowId={targetWorkflowId}
          onSelect={setTargetWorkflowId}
        />
        {bundle?.source?.workflow_name && targetWorkflowId && (
          <p className="text-xs text-muted-foreground">
            Pre-selected by matching the exported workflow's name.
          </p>
        )}
      </div>
    </div>
  );

  const renderReviewStep = () => {
    if (isPreviewLoading) {
      return (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking the bundle against the target workflow…
        </div>
      );
    }
    if (previewError || !preview) {
      return (
        <div className="py-8 text-center text-sm text-destructive">
          {previewError || "Could not preview the import."}
        </div>
      );
    }
    return (
      <div className="space-y-4">
        <div className="rounded-lg border bg-muted/40 p-4 text-sm space-y-2">
          <div className="font-medium">{preview.evaluation_name}</div>
          {preview.existing_dataset ? (
            <div className="space-y-2">
              <div className="text-muted-foreground">
                A dataset named "{preview.existing_dataset.name}" already exists here.
              </div>
              <Select
                value={reuseDataset ? "reuse" : "create"}
                onValueChange={(value) => setReuseDataset(value === "reuse")}
              >
                <SelectTrigger className="h-8 w-full max-w-md">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="reuse">
                    Use the existing dataset ({preview.existing_dataset.case_count} case
                    {preview.existing_dataset.case_count !== 1 ? "s" : ""})
                  </SelectItem>
                  <SelectItem value="create">
                    Create a second dataset from the file ({preview.case_count} case
                    {preview.case_count !== 1 ? "s" : ""})
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="text-muted-foreground">
              Creates dataset "{preview.dataset_name}" with {preview.case_count} case
              {preview.case_count !== 1 ? "s" : ""}.
            </div>
          )}
        </div>

        {looksLikeWrongWorkflow && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 p-3">
            <div className="flex items-start gap-2 text-sm text-amber-900 dark:text-amber-200">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p>No references match this workflow.</p>
                <p className="mt-0.5 text-xs text-amber-800 dark:text-amber-300">
                  {bundle?.source?.workflow_name
                    ? `Exported from "${bundle.source.workflow_name}". `
                    : ""}
                  Go back to change the target, or import without these checks.
                </p>
              </div>
            </div>
          </div>
        )}

        {preview.node_refs.length > 0 && (
          <ImportMappingTable
            nodeRefs={preview.node_refs}
            catalog={catalog}
            catalogUnavailable={catalogFailed}
            picks={picks}
            onPick={(pickKey, targetId) =>
              setPicks((current) => ({ ...current, [pickKey]: targetId }))
            }
          />
        )}

        {preview.warnings.length > 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 p-3 space-y-1">
            {preview.warnings.map((warning) => (
              <div
                key={warning}
                className="flex items-start gap-2 text-xs text-amber-800 dark:text-amber-300"
              >
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                {warning}
              </div>
            ))}
          </div>
        )}

        {unresolvedRefs.length > 0 && dropWouldEmpty && (
          <p className="text-sm text-muted-foreground">
            Dropping the unmatched references would leave this evaluation with no
            checks, so it can't be imported against this workflow. Map them
            above, or go back and choose a different workflow.
          </p>
        )}

        {unresolvedRefs.length > 0 && !dropWouldEmpty && (
          <label className="flex items-start gap-2 text-sm">
            <Checkbox
              checked={dropUnresolved}
              onCheckedChange={(checked) => setDropUnresolved(checked === true)}
              className="mt-0.5"
            />
            <span>
              Drop the checks that use the {unresolvedRefs.length} reference
              {unresolvedRefs.length !== 1 ? "s" : ""} I haven't matched. The
              imported evaluation will check less than the original.
            </span>
          </label>
        )}
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import evaluation</DialogTitle>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto pr-1">
          {step === "file" && renderFileStep()}
          {step === "workflow" && renderWorkflowStep()}
          {step === "review" && renderReviewStep()}
        </div>

        <DialogFooter className="mt-2 gap-2 border-t pt-4">
          {step !== "file" && (
            <Button
              variant="ghost"
              className="mr-auto"
              onClick={() => setStep(step === "review" ? "workflow" : "file")}
              disabled={isImporting}
            >
              <ChevronLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
          )}
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          {step === "file" && (
            <Button disabled={!bundle} onClick={() => setStep("workflow")}>
              Next
            </Button>
          )}
          {step === "workflow" && (
            <Button disabled={!targetWorkflowId} onClick={() => void loadPreview()}>
              Next
            </Button>
          )}
          {step === "review" && (
            <Button disabled={!canImport} onClick={() => void handleImport()}>
              {isImporting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Import
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
