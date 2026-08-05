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
  EvaluationBundleSet,
  EvaluationImportPreview,
  EvaluationImportResult,
  EvaluationSetImportPreview,
  EvaluationSetImportResult,
} from "@/interfaces/evalBundle.interface";
import { EvaluationToolCatalog } from "@/interfaces/testEvaluation.interface";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import {
  getEvaluationToolCatalog,
  importEvaluation,
  importEvaluationSet,
  previewEvaluationImport,
  previewEvaluationSetImport,
} from "@/services/testEvaluations";
import {
  apiErrorDetail,
  bundleSetCaseCount,
  nodeRefKey,
  parseBundleFile,
} from "../helpers/evalBundle";
import { groupWorkflowVersions } from "../helpers/workflowVersions";
import { ImportMappingTable } from "./ImportMappingTable";
import { ImportSetResults } from "./ImportSetResults";
import { ImportSetReview } from "./ImportSetReview";
import { WorkflowVersionPicker } from "./WorkflowVersionPicker";

type ImportStep = "file" | "workflow" | "review" | "results";

interface ImportEvaluationDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  workflows: WorkflowMinimal[];
  onImported: (result: EvaluationImportResult) => void;
  onSetImported?: (result: EvaluationSetImportResult) => void;
}

export const ImportEvaluationDialog: React.FC<ImportEvaluationDialogProps> = ({
  isOpen,
  onOpenChange,
  workflows,
  onImported,
  onSetImported,
}) => {
  const [step, setStep] = useState<ImportStep>("file");
  const [bundle, setBundle] = useState<EvaluationBundle | null>(null);
  const [bundleSet, setBundleSet] = useState<EvaluationBundleSet | null>(null);
  const [fileName, setFileName] = useState("");
  const [fileError, setFileError] = useState("");
  const [targetWorkflowId, setTargetWorkflowId] = useState("");
  const [preview, setPreview] = useState<EvaluationImportPreview | null>(null);
  const [batchPreview, setBatchPreview] = useState<EvaluationSetImportPreview | null>(null);
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [batchResult, setBatchResult] = useState<EvaluationSetImportResult | null>(null);
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
  // True only while a batch import is awaiting its response.
  const batchInFlight = useRef(false);

  const reset = () => {
    previewRequestRef.current += 1;
    setStep("file");
    setBundle(null);
    setBundleSet(null);
    setFileName("");
    setFileError("");
    setTargetWorkflowId("");
    setPreview(null);
    setBatchPreview(null);
    setSelectedItems(new Set());
    setBatchResult(null);
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
    // Closing mid-batch would leave it running with nothing to report it: the
    // evaluations land, but the page never learns to refresh. Guarded by a ref
    // rather than isImporting, because the single-evaluation path closes the
    // dialog itself while its own import is still marked in flight.
    if (!open && batchInFlight.current) return;
    if (!open) {
      // Whatever the batch already did stays done, even when the dialog is
      // dismissed from the results step — the page must reflect it.
      if (batchResult) onSetImported?.(batchResult);
      reset();
    }
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
        setBundle(parsed.kind === "single" ? parsed.bundle : null);
        setBundleSet(parsed.kind === "set" ? parsed.bundleSet : null);
        setFileName(file.name);
        setFileError("");
        preselectWorkflow(
          parsed.kind === "single" ? parsed.bundle.source : parsed.bundleSet.source,
        );
      } catch (error) {
        setBundle(null);
        setBundleSet(null);
        setFileName(file.name);
        setFileError(error instanceof Error ? error.message : "Could not read the file.");
      }
    };
    reader.readAsText(file);
  };

  const preselectWorkflow = (source: EvaluationBundle["source"] | undefined) => {
    const sourceName = source?.workflow_name?.trim().toLowerCase();
    const group = sourceName
      ? workflowGroups.find((g) => g.name.trim().toLowerCase() === sourceName)
      : undefined;
    // Land on the live version, which is what a plain run would execute; always
    // overwrite so a selection from a previously chosen file cannot survive.
    setTargetWorkflowId(group?.activeVersionId ?? group?.versions[0].id ?? "");
  };

  const startPreviewRequest = () => {
    const requestId = ++previewRequestRef.current;
    setStep("review");
    setIsPreviewLoading(true);
    setPreviewError("");
    setPreview(null);
    setBatchPreview(null);
    setPicks({});
    setDropUnresolved(false);
    setReuseDataset(true);
    return requestId;
  };

  const loadPreview = async () => {
    if (!bundle || !targetWorkflowId) return;
    const requestId = startPreviewRequest();
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

  const loadBatchPreview = async () => {
    if (!bundleSet || !targetWorkflowId) return;
    const requestId = startPreviewRequest();
    try {
      const [previewData, catalogData] = await Promise.all([
        previewEvaluationSetImport({
          bundle_set: bundleSet,
          target_workflow_id: targetWorkflowId,
        }),
        getEvaluationToolCatalog(targetWorkflowId).catch(() => null),
      ]);
      if (requestId !== previewRequestRef.current) return;
      setBatchPreview(previewData);
      setCatalog(catalogData);
      setCatalogFailed(catalogData === null);
      // Evaluations already on the target start unchecked, so importing twice
      // duplicates nothing unless the user opts a row back in.
      setSelectedItems(
        new Set(
          (previewData?.evaluations ?? []).flatMap((item, index) =>
            item.already_exists ? [] : [index],
          ),
        ),
      );
      const nothingResolved =
        (previewData?.node_refs.length ?? 0) > 0 &&
        previewData!.node_refs.every((nodeRef) => nodeRef.status !== "resolved");
      // Pre-tick dropping only when at least one evaluation would keep a check.
      setDropUnresolved(
        nothingResolved &&
          (previewData?.evaluations ?? []).some(
            (item) => !item.dropping_all_would_empty,
          ),
      );
      if (!previewData) setPreviewError("Could not preview the import.");
    } catch (error) {
      if (requestId !== previewRequestRef.current) return;
      setPreviewError(apiErrorDetail(error) ?? "Could not preview the import.");
    } finally {
      if (requestId === previewRequestRef.current) setIsPreviewLoading(false);
    }
  };

  const activeNodeRefs = bundleSet ? batchPreview?.node_refs : preview?.node_refs;

  const unresolvedRefs = useMemo(() => {
    return (activeNodeRefs ?? []).filter(
      (nodeRef) => nodeRef.status !== "resolved" && !picks[nodeRefKey(nodeRef)],
    );
  }, [activeNodeRefs, picks]);

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

  // Per evaluation, how many of ITS references are still unmatched. The set-wide
  // count would keep flagging a row whose own references the user already
  // mapped, just because a different row's are outstanding.
  const unresolvedCountByItem = useMemo(() => {
    const unresolvedKeys = new Set(unresolvedRefs.map(nodeRefKey));
    return (batchPreview?.evaluations ?? []).map(
      (item) =>
        (item.node_ref_keys ?? []).filter((key) => unresolvedKeys.has(key)).length,
    );
  }, [batchPreview, unresolvedRefs]);

  // Manual picks for each evaluation, so a preview-time verdict can be told
  // apart from one the user has since acted on.
  const pickedCountByItem = useMemo(
    () =>
      (batchPreview?.evaluations ?? []).map(
        (item) => (item.node_ref_keys ?? []).filter((key) => picks[key]).length,
      ),
    [batchPreview, picks],
  );

  // An evaluation cannot import if its own references are unmatched and either
  // dropping is off or dropping would leave it with nothing to grade. That last
  // flag is computed before any manual picks, so it only stands while the user
  // has mapped none of this evaluation's references — otherwise mapping one
  // could never unblock the row.
  // True when dropping the rest would leave this evaluation nothing to grade.
  // The badge and the Import button both read this, so they cannot disagree.
  const hasNoMatchingChecks = (index: number): boolean => {
    const item = batchPreview?.evaluations[index];
    if (!item || (unresolvedCountByItem[index] ?? 0) === 0) return false;
    return item.dropping_all_would_empty && (pickedCountByItem[index] ?? 0) === 0;
  };

  const isItemBlocked = (index: number): boolean => {
    if ((unresolvedCountByItem[index] ?? 0) === 0) return false;
    if (!dropUnresolved) return true;
    return hasNoMatchingChecks(index);
  };

  const hasImportableSelection = [...selectedItems].some(
    (index) => !isItemBlocked(index),
  );

  const canImportBatch =
    Boolean(batchPreview) &&
    selectedItems.size > 0 &&
    !isImporting &&
    hasImportableSelection;

  const toggleSelectedItem = (index: number) => {
    setSelectedItems((current) => {
      const next = new Set(current);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleBatchImport = async () => {
    if (!bundleSet || !targetWorkflowId || selectedItems.size === 0) return;
    const requestId = ++previewRequestRef.current;
    batchInFlight.current = true;
    setIsImporting(true);
    try {
      // The checkboxes are the skip decision: unchecked rows are not sent, and
      // a checked "already here" row is an explicit request for a copy.
      const result = await importEvaluationSet({
        bundle_set: bundleSet,
        target_workflow_id: targetWorkflowId,
        include: [...selectedItems].sort((a, b) => a - b),
        resolutions: picks,
        drop_unresolved_rules: dropUnresolved,
        skip_existing: false,
      });
      // The dialog cannot be closed mid-import, but a reset would still orphan
      // this response; never write it into a dialog that moved on.
      if (requestId !== previewRequestRef.current) return;
      if (!result) {
        toast.error("You don't have permission to import evaluations.");
        return;
      }
      setBatchResult(result);
      setStep("results");
    } catch (error) {
      if (requestId !== previewRequestRef.current) return;
      toast.error(apiErrorDetail(error) ?? "Failed to import evaluations");
    } finally {
      batchInFlight.current = false;
      if (requestId === previewRequestRef.current) setIsImporting(false);
    }
  };

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
      {bundleSet && (
        <div className="rounded-lg border bg-muted/40 p-4 text-sm space-y-1">
          <div className="font-medium">
            {bundleSet.evaluations.length} evaluation
            {bundleSet.evaluations.length !== 1 ? "s" : ""}
          </div>
          <div className="text-muted-foreground">
            {bundleSet.datasets.length} dataset
            {bundleSet.datasets.length !== 1 ? "s" : ""} ·{" "}
            {bundleSetCaseCount(bundleSet)} case
            {bundleSetCaseCount(bundleSet) !== 1 ? "s" : ""}
          </div>
          {bundleSet.source?.workflow_name && (
            <div className="text-muted-foreground">
              Exported from workflow "{bundleSet.source.workflow_name}"
              {bundleSet.source.workflow_version
                ? ` v${bundleSet.source.workflow_version}`
                : ""}
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderWorkflowStep = () => (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Choose the workflow {bundleSet ? "these evaluations" : "this evaluation"}{" "}
        should test. References in the bundle's checks are matched against it by
        name.
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
        {(bundle ?? bundleSet)?.source?.workflow_name && targetWorkflowId && (
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
    if (previewError || (!preview && !batchPreview)) {
      return (
        <div className="py-8 text-center text-sm text-destructive">
          {previewError || "Could not preview the import."}
        </div>
      );
    }
    if (bundleSet && batchPreview) {
      return (
        <ImportSetReview
          preview={batchPreview}
          sourceWorkflowName={bundleSet.source?.workflow_name}
          catalog={catalog}
          catalogUnavailable={catalogFailed}
          picks={picks}
          onPick={(pickKey, targetId) =>
            setPicks((current) => ({ ...current, [pickKey]: targetId }))
          }
          selected={selectedItems}
          onToggleItem={toggleSelectedItem}
          unresolvedCount={unresolvedRefs.length}
          noMatchingChecks={(batchPreview?.evaluations ?? []).map((_, index) =>
            hasNoMatchingChecks(index),
          )}
          dropUnresolved={dropUnresolved}
          onDropUnresolvedChange={setDropUnresolved}
        />
      );
    }
    if (!preview) return null;
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
          <DialogTitle>
            {bundleSet ? "Import evaluations" : "Import evaluation"}
          </DialogTitle>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto pr-1">
          {step === "file" && renderFileStep()}
          {step === "workflow" && renderWorkflowStep()}
          {step === "review" && renderReviewStep()}
          {step === "results" && batchResult && (
            <ImportSetResults result={batchResult} />
          )}
        </div>

        <DialogFooter className="mt-2 gap-2 border-t pt-4">
          {step !== "file" && step !== "results" && (
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
          {step !== "results" && (
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isImporting}
            >
              Cancel
            </Button>
          )}
          {step === "file" && (
            <Button disabled={!bundle && !bundleSet} onClick={() => setStep("workflow")}>
              Next
            </Button>
          )}
          {step === "workflow" && (
            <Button
              disabled={!targetWorkflowId}
              onClick={() => void (bundleSet ? loadBatchPreview() : loadPreview())}
            >
              Next
            </Button>
          )}
          {step === "review" && !bundleSet && (
            <Button disabled={!canImport} onClick={() => void handleImport()}>
              {isImporting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Import
            </Button>
          )}
          {step === "review" && bundleSet && (
            <Button disabled={!canImportBatch} onClick={() => void handleBatchImport()}>
              {isImporting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Import {selectedItems.size > 0 ? selectedItems.size : ""} evaluation
              {selectedItems.size !== 1 ? "s" : ""}
            </Button>
          )}
          {step === "results" && (
            <Button onClick={() => handleOpenChange(false)}>Done</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
