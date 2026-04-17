import React, { useEffect, useState, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import JsonViewer from "@/components/JsonViewer";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { ChevronLeft, Play, CheckCircle2, XCircle, ChevronDown, ChevronRight, AlertCircle, Loader2 } from "lucide-react";
import {
  getTestRun,
  getTestRunsBatch,
  listTestCases,
  listResultsForRun,
  listTestSuites,
  startTestRun,
} from "@/services/testSuites";
import { getWorkflowsMinimal } from "@/services/workflows";
import {
  getTestEvaluationById,
  appendRunToEvaluation,
} from "@/services/testEvaluations";
import { TestResult, TestRun, TestSuite } from "@/interfaces/testSuite.interface";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/skeleton";
import { Progress } from "@/components/progress";
import { cn } from "@/helpers/utils";

type ResultFilter = "all" | "passed" | "failed";

const RunStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const inProgress = status === "queued" || status === "running";
  return (
    <Badge variant="outline" className="flex items-center gap-1">
      {inProgress && <Loader2 className="h-3 w-3 animate-spin" />}
      {status}
    </Badge>
  );
};

const EvaluationDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { evaluationId } = useParams<{ evaluationId: string }>();
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [resultsByRun, setResultsByRun] = useState<Record<string, TestResult[]>>({});
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null);
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [workflowName, setWorkflowName] = useState<string>("Dataset default");
  const [expectedOutputByCaseId, setExpectedOutputByCaseId] = useState<
    Record<string, Record<string, unknown> | undefined>
  >({});
  const [inputByCaseId, setInputByCaseId] = useState<
    Record<string, Record<string, unknown> | undefined>
  >({});
  const [isRunDetailsOpen, setIsRunDetailsOpen] = useState(false);
  const [resultFilter, setResultFilter] = useState<ResultFilter>("all");
  const [isLoadingRuns, setIsLoadingRuns] = useState(true);

  const [evaluation, setEvaluation] = useState<
    Awaited<ReturnType<typeof getTestEvaluationById>>
  >(undefined);

  useEffect(() => {
    if (!evaluationId) return;
    getTestEvaluationById(evaluationId).then(setEvaluation);
  }, [evaluationId]);

  useEffect(() => {
    const loadContext = async () => {
      if (!evaluation) return;
      const [suites, workflows] = await Promise.all([
        listTestSuites(),
        getWorkflowsMinimal(),
      ]);
      const suiteData = (suites ?? []).find((item) => item.id === evaluation.suite_id);
      setSuite(suiteData ?? null);
      const workflowData = (workflows ?? []).find(
        (item: WorkflowMinimal) => item.id === evaluation.workflow_id,
      );
      setWorkflowName(workflowData?.name ?? "Dataset default");
    };
    loadContext();
  }, [evaluation]);

  useEffect(() => {
    const loadExpectedOutputs = async () => {
      if (!evaluation?.suite_id) {
        setExpectedOutputByCaseId({});
        return;
      }
      const cases = await listTestCases(evaluation.suite_id);
      const expectedMapping: Record<string, Record<string, unknown> | undefined> = {};
      const inputMapping: Record<string, Record<string, unknown> | undefined> = {};
      (cases ?? []).forEach((testCase) => {
        if (testCase.id) {
          expectedMapping[testCase.id] = testCase.expected_output;
          inputMapping[testCase.id] = testCase.input_data;
        }
      });
      setExpectedOutputByCaseId(expectedMapping);
      setInputByCaseId(inputMapping);
    };
    loadExpectedOutputs();
  }, [evaluation?.suite_id]);

  useEffect(() => {
    const loadRuns = async () => {
      setIsLoadingRuns(true);
      try {
        if (!evaluation?.run_ids?.length) {
          setRuns([]);
          return;
        }
        const runData = await getTestRunsBatch(evaluation.run_ids);
        setRuns(
          (runData ?? [])
            .filter(Boolean)
            .sort(
              (a, b) =>
                new Date(b?.created_at ?? 0).getTime() -
                new Date(a?.created_at ?? 0).getTime(),
            ) as TestRun[],
        );
      } finally {
        setIsLoadingRuns(false);
      }
    };
    loadRuns();
  }, [evaluation]);

  useEffect(() => {
    const loadSelectedRunResults = async () => {
      if (!selectedRunId) return;
      setIsLoadingResults(true);
      try {
        const data = await listResultsForRun(selectedRunId);
        setResultsByRun((prev) => ({ ...prev, [selectedRunId]: data ?? [] }));
      } finally {
        setIsLoadingResults(false);
      }
    };
    loadSelectedRunResults();
  }, [selectedRunId]);

  const handleRunEvaluation = async () => {
    if (!evaluation || !evaluationId) return;
    setIsRunning(true);
    try {
      let runMetadata = evaluation.input_metadata ?? undefined;
      if (runMetadata?.use_memory) {
        runMetadata = { ...runMetadata, thread_id: crypto.randomUUID() };
      }
      const created = await startTestRun(evaluation.suite_id, {
        techniques: evaluation.techniques,
        technique_configs: evaluation.technique_configs,
        workflow_id: evaluation.workflow_id,
        input_metadata: runMetadata,
      });
      if (created?.id) {
        await appendRunToEvaluation(evaluationId, created.id);
        setRuns((prev) => [created, ...prev]);
        setSelectedRunId(created.id);

        // Poll every 10 seconds until the run reaches a terminal state.
        const pollInterval = setInterval(async () => {
          const updated = await getTestRun(created.id);
          if (!updated) return;
          setRuns((prev) =>
            prev.map((r) => (r.id === updated.id ? (updated as TestRun) : r))
          );
          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(pollInterval);
            setIsRunning(false);
            const results = await listResultsForRun(created.id);
            setResultsByRun((prev) => ({ ...prev, [created.id]: results ?? [] }));
          }
        }, 10_000);
        // Return early — setIsRunning(false) is handled by the interval above.
        return;
      }
    } catch {
      // fall through to finally
    }
    setIsRunning(false);
  };

  const selectedRun = runs.find((run) => run.id === selectedRunId);
  const selectedRunResults = selectedRunId ? resultsByRun[selectedRunId] ?? [] : [];

  // Helper to determine if a result passed (all metrics passed) or failed
  const isResultPassed = (result: TestResult): boolean => {
    if (!result.metrics) return true; // No metrics means no failure
    return Object.values(result.metrics).every((m) => m.passed);
  };

  // Filter results based on selected filter
  const filteredResults = useMemo(() => {
    if (resultFilter === "all") return selectedRunResults;
    if (resultFilter === "passed") return selectedRunResults.filter(isResultPassed);
    return selectedRunResults.filter((r) => !isResultPassed(r));
  }, [selectedRunResults, resultFilter]);

  // Count passed and failed
  const passedCount = selectedRunResults.filter(isResultPassed).length;
  const failedCount = selectedRunResults.length - passedCount;

  if (!evaluation) {
    return (
      <PageLayout>
        <div className="space-y-4">
          <Button onClick={() => navigate("/tests/evaluations")} variant="outline">
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back to Evaluations
          </Button>
          <div className="bg-white rounded-lg border p-4">
            <div className="text-sm text-gray-600">Evaluation not found.</div>
          </div>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate("/tests/evaluations")} aria-label="Back to Evaluations">
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back to Evaluations
          </Button>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <h1 className="text-xl font-semibold text-gray-900">{evaluation.name}</h1>
              {evaluation.description && (
                <p className="text-xs text-gray-500">
                  {evaluation.description}
                </p>
              )}
            </div>
            <Button onClick={handleRunEvaluation} disabled={isRunning} aria-label="Execute evaluation">
              <Play className="h-4 w-4 mr-2" />
              {isRunning ? "Running..." : "Execute Evaluation"}
            </Button>
          </div>
        </div>

        <div className="bg-white rounded-lg border p-4 space-y-2">
          <div className="text-sm">
            <strong>Dataset:</strong> {suite?.name ?? evaluation.suite_id}
          </div>
          <div className="text-sm">
            <strong>Workflow:</strong> {workflowName}
          </div>
          <div className="text-sm flex items-center gap-2">
            <strong>Metrics:</strong>
            {evaluation.techniques.map((technique) => (
              <Badge key={technique} variant="secondary">
                {technique}
              </Badge>
            ))}
          </div>
          <div className="text-sm">
            <strong>Extra metadata:</strong>
            <div className="mt-2 bg-gray-50 rounded p-2">
              <JsonViewer data={(evaluation.input_metadata ?? {}) as unknown as never} />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Previous Executions</h2>
            <Badge variant="secondary" className="text-xs">
              {runs.length} run{runs.length !== 1 ? "s" : ""}
            </Badge>
          </div>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {isLoadingRuns ? (
              <>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="border rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-5 w-24" />
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </div>
                    <Skeleton className="h-3 w-32" />
                    <div className="flex gap-1">
                      <Skeleton className="h-5 w-20 rounded-full" />
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </div>
                  </div>
                ))}
              </>
            ) : runs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Play className="h-10 w-10 text-gray-300 mb-2" />
                <p className="text-sm text-gray-500">No executions yet</p>
                <p className="text-xs text-gray-400 mt-1">
                  Click "Execute Evaluation" to run your first test
                </p>
              </div>
            ) : (
              runs.map((run) => {
                const summaryMetrics = run.summary_metrics as Record<
                  string,
                  { accuracy?: number; avg_score?: number; cases?: number }
                > | undefined;
                const avgAccuracy = summaryMetrics
                  ? Object.values(summaryMetrics)
                      .filter((m) => typeof m.accuracy === "number")
                      .reduce((sum, m, _, arr) => sum + (m.accuracy ?? 0) / arr.length, 0)
                  : null;

                return (
                  <button
                    key={run.id}
                    type="button"
                    className="w-full text-left border rounded-lg p-3 hover:bg-gray-50 transition-colors"
                    onClick={() => {
                      setSelectedRunId(run.id ?? null);
                      setIsRunDetailsOpen(true);
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="font-medium">Run #{run.id?.slice(-4)}</div>
                        {avgAccuracy !== null && (
                          <div className="flex items-center gap-1">
                            <Progress
                              value={avgAccuracy * 100}
                              className={cn(
                                "h-1.5 w-16",
                                avgAccuracy >= 0.9 ? "[&>div]:bg-green-500" : avgAccuracy >= 0.7 ? "[&>div]:bg-amber-500" : "[&>div]:bg-red-500"
                              )}
                            />
                            <span className={cn(
                              "text-xs font-medium",
                              avgAccuracy >= 0.9 ? "text-green-600" : avgAccuracy >= 0.7 ? "text-amber-600" : "text-red-600"
                            )}>
                              {Math.round(avgAccuracy * 100)}%
                            </span>
                          </div>
                        )}
                      </div>
                      <RunStatusBadge status={run.status} />
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {new Date(run.created_at ?? "").toLocaleString()}
                    </div>
                    {summaryMetrics && (
                      <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                        {Object.entries(summaryMetrics).map(([tech, summary]) => {
                          const acc = typeof summary.accuracy === "number" ? summary.accuracy : null;
                          let colorClasses = "bg-gray-100 text-gray-700 border border-gray-200";
                          if (acc !== null) {
                            if (acc >= 0.9) {
                              colorClasses = "bg-green-50 text-green-700 border border-green-200";
                            } else if (acc >= 0.7) {
                              colorClasses = "bg-amber-50 text-amber-700 border border-amber-200";
                            } else {
                              colorClasses = "bg-red-50 text-red-700 border border-red-200";
                            }
                          }
                          return (
                            <span
                              key={tech}
                              className={`inline-flex items-center rounded-full px-2 py-0.5 ${colorClasses}`}
                            >
                              <span className="font-semibold mr-1">{tech}</span>
                              {acc !== null && <span>{Math.round(acc * 100)}%</span>}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>

        <Dialog open={isRunDetailsOpen && !!selectedRun} onOpenChange={(open) => {
          setIsRunDetailsOpen(open);
          if (!open) setResultFilter("all");
        }}>
          <DialogContent className="w-[95vw] max-w-5xl h-[85vh] max-h-[85vh] overflow-hidden p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-4 shrink-0 border-b">
              <div className="flex items-center justify-between">
                <DialogTitle>
                  Run Details {selectedRun ? `#${selectedRun.id?.slice(-4)}` : ""}
                </DialogTitle>
                {selectedRun && <RunStatusBadge status={selectedRun.status} />}
              </div>
              {selectedRun?.created_at && (
                <p className="text-xs text-gray-500 mt-1">
                  {new Date(selectedRun.created_at).toLocaleString()}
                </p>
              )}
            </DialogHeader>
            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-4">
              {selectedRun && (
                <>
                  {/* Summary metrics with progress bars */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-sm font-medium mb-3">Evaluation Summary</div>
                    {selectedRun.summary_metrics ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {Object.entries(
                          selectedRun.summary_metrics as Record<
                            string,
                            { accuracy?: number; avg_score?: number; cases?: number }
                          >,
                        ).map(([tech, summary]) => {
                          const acc = typeof summary.accuracy === "number" ? summary.accuracy : null;
                          return (
                            <div
                              key={tech}
                              className="bg-white rounded-lg border p-3"
                            >
                              <div className="text-xs font-medium text-gray-600 mb-2">{tech}</div>
                              {acc !== null && (
                                <div className="space-y-1">
                                  <div className="flex items-center justify-between">
                                    <span className={cn(
                                      "text-lg font-semibold",
                                      acc >= 0.9 ? "text-green-600" : acc >= 0.7 ? "text-amber-600" : "text-red-600"
                                    )}>
                                      {Math.round(acc * 100)}%
                                    </span>
                                    {typeof summary.cases === "number" && (
                                      <span className="text-xs text-gray-500">{summary.cases} cases</span>
                                    )}
                                  </div>
                                  <Progress
                                    value={acc * 100}
                                    className={cn(
                                      "h-2",
                                      acc >= 0.9 ? "[&>div]:bg-green-500" : acc >= 0.7 ? "[&>div]:bg-amber-500" : "[&>div]:bg-red-500"
                                    )}
                                  />
                                </div>
                              )}
                              {typeof summary.avg_score === "number" && (
                                <div className="text-sm mt-1">
                                  Avg Score: <span className="font-medium">{summary.avg_score.toFixed(2)}</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500">No metrics available</div>
                    )}
                  </div>

                  {/* Results with filter tabs */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-sm font-medium">Test Results</div>
                      <Tabs value={resultFilter} onValueChange={(v) => setResultFilter(v as ResultFilter)}>
                        <TabsList className="h-8">
                          <TabsTrigger value="all" className="text-xs px-3 py-1">
                            All ({selectedRunResults.length})
                          </TabsTrigger>
                          <TabsTrigger value="passed" className="text-xs px-3 py-1">
                            <CheckCircle2 className="h-3 w-3 mr-1 text-green-600" />
                            Passed ({passedCount})
                          </TabsTrigger>
                          <TabsTrigger value="failed" className="text-xs px-3 py-1">
                            <XCircle className="h-3 w-3 mr-1 text-red-600" />
                            Failed ({failedCount})
                          </TabsTrigger>
                        </TabsList>
                      </Tabs>
                    </div>

                    {isLoadingResults ? (
                      <div className="space-y-3">
                        {[1, 2, 3].map((i) => (
                          <div key={i} className="border rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <Skeleton className="h-5 w-24" />
                              <div className="flex gap-2">
                                <Skeleton className="h-5 w-16 rounded-full" />
                                <Skeleton className="h-5 w-16 rounded-full" />
                              </div>
                            </div>
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-3/4 mt-2" />
                          </div>
                        ))}
                      </div>
                    ) : filteredResults.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-8 text-center">
                        <AlertCircle className="h-10 w-10 text-gray-300 mb-2" />
                        <p className="text-sm text-gray-500">
                          {resultFilter === "all"
                            ? "No test results available yet."
                            : resultFilter === "passed"
                            ? "No passed test cases."
                            : "No failed test cases."}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                        {filteredResults.map((result) => {
                          const passed = isResultPassed(result);
                          const isExpanded = expandedResultId === result.id;

                          return (
                            <div
                              key={result.id}
                              className={cn(
                                "border rounded-lg overflow-hidden transition-colors",
                                passed ? "border-l-2 border-l-green-500" : "border-l-2 border-l-red-500"
                              )}
                            >
                              {/* Result header - always visible */}
                              <button
                                type="button"
                                className="w-full p-3 text-left hover:bg-gray-50 transition-colors"
                                onClick={() => setExpandedResultId(isExpanded ? null : result.id ?? null)}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    {passed ? (
                                      <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                                    ) : (
                                      <XCircle className="h-4 w-4 text-red-600 shrink-0" />
                                    )}
                                    <span className="font-medium text-sm">
                                      Case #{result.case_id?.slice(-4)}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    {result.metrics && (
                                      <div className="flex flex-wrap gap-1">
                                        {Object.entries(result.metrics).map(
                                          ([tech, metricValue]) => (
                                            <span
                                              key={tech}
                                              className={cn(
                                                "inline-flex items-center rounded-full px-2 py-0.5 text-[10px]",
                                                metricValue.passed
                                                  ? "bg-green-50 text-green-700"
                                                  : "bg-red-50 text-red-700"
                                              )}
                                            >
                                              <span className="font-semibold mr-1">{tech}</span>
                                              {typeof metricValue.score === "number" && (
                                                <span>
                                                  {metricValue.score <= 1
                                                    ? `${Math.round(metricValue.score * 100)}%`
                                                    : metricValue.score.toFixed(2)}
                                                </span>
                                              )}
                                            </span>
                                          ),
                                        )}
                                      </div>
                                    )}
                                    {isExpanded ? (
                                      <ChevronDown className="h-4 w-4 text-gray-400" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4 text-gray-400" />
                                    )}
                                  </div>
                                </div>

                                {/* Comments preview */}
                                {!isExpanded && result.metrics && (
                                  <div className="mt-1 text-[11px] text-gray-500 line-clamp-1">
                                    {Object.entries(result.metrics)
                                      .filter(([, m]) => m.comment)
                                      .map(([tech, m]) => `${tech}: ${m.comment}`)
                                      .join(" | ")}
                                  </div>
                                )}
                              </button>

                              {/* Expanded content */}
                              {isExpanded && (
                                <div className="border-t bg-gray-50 p-4 space-y-4">
                                  {/* Metric comments */}
                                  {result.metrics && (
                                    <div className="space-y-1">
                                      {Object.entries(result.metrics).map(
                                        ([tech, metricValue]) =>
                                          metricValue.comment ? (
                                            <div key={`${result.id}-${tech}-comment`} className="text-xs">
                                              <span className="font-semibold text-gray-700">{tech}:</span>{" "}
                                              <span className="text-gray-600">{metricValue.comment}</span>
                                            </div>
                                          ) : null,
                                      )}
                                    </div>
                                  )}

                                  {/* Input/Output comparison */}
                                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                    <div>
                                      <div className="text-xs font-medium text-gray-600 mb-1 flex items-center gap-1">
                                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                                        Input
                                      </div>
                                      <div className="bg-white rounded border p-2 text-xs">
                                        <JsonViewer
                                          data={
                                            ((result.case_id &&
                                              (inputByCaseId[result.case_id] as unknown)) ??
                                              {}) as unknown as never
                                          }
                                        />
                                      </div>
                                    </div>
                                    <div>
                                      <div className="text-xs font-medium text-gray-600 mb-1 flex items-center gap-1">
                                        <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                                        Expected Output
                                      </div>
                                      <div className="bg-white rounded border p-2 text-xs">
                                        <JsonViewer
                                          data={
                                            ((result.case_id &&
                                              (expectedOutputByCaseId[result.case_id] as unknown)) ??
                                              {}) as unknown as never
                                          }
                                        />
                                      </div>
                                    </div>
                                  </div>

                                  <div>
                                    <div className="text-xs font-medium text-gray-600 mb-1 flex items-center gap-1">
                                      <span className={cn(
                                        "w-1.5 h-1.5 rounded-full",
                                        passed ? "bg-green-500" : "bg-red-500"
                                      )}></span>
                                      Actual Output
                                    </div>
                                    <div className={cn(
                                      "bg-white rounded border p-2 text-xs",
                                      !passed && "border-red-200"
                                    )}>
                                      {result.actual_output &&
                                      "value" in result.actual_output &&
                                      Object.keys(result.actual_output).length === 1 ? (
                                        <div className="whitespace-pre-wrap">
                                          {String(result.actual_output.value)}
                                        </div>
                                      ) : (
                                        <JsonViewer
                                          data={(result.actual_output ?? {}) as unknown as never}
                                        />
                                      )}
                                    </div>
                                  </div>

                                  {result.execution_trace && Object.keys(result.execution_trace).length > 0 && (
                                    <div>
                                      <div className="text-xs font-medium text-gray-600 mb-1">
                                        Execution Trace
                                      </div>
                                      <div className="bg-white rounded border p-2 text-xs">
                                        <JsonViewer
                                          data={(result.execution_trace ?? {}) as unknown as never}
                                        />
                                      </div>
                                    </div>
                                  )}

                                  {result.error && (
                                    <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
                                      <div className="font-medium mb-1">Error</div>
                                      {result.error}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </PageLayout>
  );
};

export default EvaluationDetailPage;

