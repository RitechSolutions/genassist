import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import JsonViewer from "@/components/JsonViewer";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { ChevronLeft, Play } from "lucide-react";
import {
  getTestRun,
  listTestCases,
  listResultsForRun,
  listTestSuites,
  startTestRun,
} from "@/services/testSuites";
import { getAllWorkflows } from "@/services/workflows";
import {
  getTestEvaluationById,
  appendRunToEvaluation,
} from "@/services/testEvaluations";
import { TestResult, TestRun, TestSuite } from "@/interfaces/testSuite.interface";
import { Workflow } from "@/interfaces/workflow.interface";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const EvaluationDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { evaluationId } = useParams<{ evaluationId: string }>();
  const [isRunning, setIsRunning] = useState(false);
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
        getAllWorkflows(),
      ]);
      const suiteData = (suites ?? []).find((item) => item.id === evaluation.suite_id);
      setSuite(suiteData ?? null);
      const workflowData = (workflows ?? []).find(
        (item: Workflow) => item.id === evaluation.workflow_id,
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
      if (!evaluation?.run_ids?.length) {
        setRuns([]);
        return;
      }
      const runData = await Promise.all(
        evaluation.run_ids.map((runId) => getTestRun(runId)),
      );
      setRuns(
        runData
          .filter(Boolean)
          .sort(
            (a, b) =>
              new Date(b?.created_at ?? 0).getTime() -
              new Date(a?.created_at ?? 0).getTime(),
          ) as TestRun[],
      );
    };
    loadRuns();
  }, [evaluation]);

  useEffect(() => {
    const loadSelectedRunResults = async () => {
      if (!selectedRunId) return;
      const data = await listResultsForRun(selectedRunId);
      setResultsByRun((prev) => ({ ...prev, [selectedRunId]: data ?? [] }));
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
      }
    } finally {
      setIsRunning(false);
    }
  };

  const selectedRun = runs.find((run) => run.id === selectedRunId);
  const selectedRunResults = selectedRunId ? resultsByRun[selectedRunId] ?? [] : [];

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
          <Button variant="ghost" onClick={() => navigate("/tests/evaluations")}>
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
            <Button onClick={handleRunEvaluation} disabled={isRunning}>
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
          <h2 className="text-lg font-semibold mb-3">Previous Executions</h2>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {runs.map((run) => (
              <button
                key={run.id}
                type="button"
                className="w-full text-left border rounded p-3 hover:bg-gray-50"
                onClick={() => {
                  setSelectedRunId(run.id ?? null);
                  setIsRunDetailsOpen(true);
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="font-medium">Run #{run.id?.slice(-4)}</div>
                  <Badge variant="outline">{run.status}</Badge>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {new Date(run.created_at ?? "").toLocaleString()}
                </div>
                {run.summary_metrics && (
                  <div className="mt-1 flex flex-wrap gap-1 text-[11px]">
                    {Object.entries(
                      run.summary_metrics as Record<
                        string,
                        { accuracy?: number; avg_score?: number; cases?: number }
                      >,
                    ).map(([tech, summary]) => {
                      const acc = typeof summary.accuracy === "number" ? summary.accuracy : null;
                      let colorClasses =
                        "bg-gray-100 text-gray-700 border border-gray-200";
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
                          {acc !== null && (
                            <span>{Math.round(acc * 100)}%</span>
                          )}
                        </span>
                      );
                    })}
                  </div>
                )}
              </button>
            ))}
            {runs.length === 0 && (
              <div className="text-sm text-gray-400">No executions yet.</div>
            )}
          </div>
        </div>

        <Dialog open={isRunDetailsOpen && !!selectedRun} onOpenChange={setIsRunDetailsOpen}>
          <DialogContent className="w-[95vw] max-w-5xl h-[85vh] max-h-[85vh] overflow-hidden p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
              <DialogTitle>
                Run Details {selectedRun ? `#${selectedRun.id?.slice(-4)}` : ""}
              </DialogTitle>
            </DialogHeader>
            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-4">
              {selectedRun && (
                <>
                  <div>
                    <div className="text-sm font-medium mb-2">Eval Metrics</div>
                    {selectedRun.summary_metrics ? (
                      <div className="space-y-1 text-xs text-gray-700">
                        {Object.entries(
                          selectedRun.summary_metrics as Record<
                            string,
                            { accuracy?: number; avg_score?: number; cases?: number }
                          >,
                        ).map(([tech, summary]) => (
                          <div
                            key={tech}
                            className="flex items-center justify-between rounded bg-gray-50 px-2 py-1"
                          >
                            <span className="font-semibold">{tech}</span>
                            <span>
                              {typeof summary.accuracy === "number" && (
                                <span className="mr-2">
                                  Accuracy {Math.round(summary.accuracy * 100)}%
                                </span>
                              )}
                              {typeof summary.avg_score === "number" && (
                                <span className="mr-2">
                                  Score {summary.avg_score.toFixed(2)}
                                </span>
                              )}
                              {typeof summary.cases === "number" && (
                                <span>{summary.cases} cases</span>
                              )}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <JsonViewer data={{}} />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-medium mb-1">
                      Agent Logs / Outputs
                    </div>
                    <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                      {selectedRunResults.map((result) => (
                        <div key={result.id} className="border rounded p-3 text-sm">
                          <div className="font-medium mb-1">
                            Case #{result.case_id?.slice(-4)}
                          </div>
                          {result.metrics && (
                            <div className="mb-2 flex flex-wrap gap-1 text-[11px] text-gray-700">
                              {Object.entries(result.metrics).map(
                                ([tech, metricValue]) => (
                                  <span
                                    key={tech}
                                    className={`inline-flex items-center rounded-full px-2 py-0.5 ${
                                      metricValue.passed
                                        ? "bg-green-50 text-green-700"
                                        : "bg-red-50 text-red-700"
                                    }`}
                                  >
                                    <span className="font-semibold mr-1">
                                      {tech}
                                    </span>
                                    {typeof metricValue.score === "number" && (
                                      <span>
                                        {metricValue.score <= 1
                                          ? `${Math.round(
                                              metricValue.score * 100,
                                            )}%`
                                          : metricValue.score.toFixed(2)}
                                      </span>
                                    )}
                                  </span>
                                ),
                              )}
                            </div>
                          )}
                          {result.metrics && (
                            <div className="mt-1 space-y-0.5 text-[11px] text-gray-500">
                              {Object.entries(result.metrics).map(
                                ([tech, metricValue]) =>
                                  metricValue.comment ? (
                                    <div key={`${result.id}-${tech}-comment`}>
                                      <span className="font-semibold mr-1">
                                        {tech}:
                                      </span>
                                      <span>{metricValue.comment}</span>
                                    </div>
                                  ) : null,
                              )}
                            </div>
                          )}
                          <div className="mt-3">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                setExpandedResultId(
                                  expandedResultId === result.id ? null : result.id ?? null,
                                )
                              }
                            >
                              {expandedResultId === result.id ? "Hide details" : "View details"}
                            </Button>
                          </div>
                          {expandedResultId === result.id && (
                            <div className="mt-3 space-y-2 text-xs">
                              <div className="text-gray-500 mb-1">Input Value</div>
                              <JsonViewer
                                data={
                                  ((result.case_id &&
                                    (inputByCaseId[result.case_id] as unknown)) ??
                                    {}) as unknown as never
                                }
                              />
                              <div className="text-gray-500 mt-2 mb-1">
                                Expected Output
                              </div>
                              <JsonViewer
                                data={
                                  ((result.case_id &&
                                    (expectedOutputByCaseId[
                                      result.case_id
                                    ] as unknown)) ??
                                    {}) as unknown as never
                                }
                              />
                              {result.actual_output &&
                              "value" in result.actual_output &&
                              Object.keys(result.actual_output).length === 1 ? (
                                <>
                                  <div className="text-gray-500 mt-2 mb-1">
                                    Output Value (text)
                                  </div>
                                  <div className="bg-gray-50 rounded p-2 whitespace-pre-wrap">
                                    {String(result.actual_output.value)}
                                  </div>
                                  <div className="text-gray-500 mt-2 mb-1">
                                    Output Value (JSON)
                                  </div>
                              <JsonViewer
                                data={(result.actual_output ?? {}) as unknown as never}
                              />
                                </>
                              ) : (
                                <>
                                  <div className="text-gray-500 mt-2 mb-1">
                                    Output Value
                                  </div>
                                  <JsonViewer
                                    data={(result.actual_output ?? {}) as unknown as never}
                                  />
                                </>
                              )}
                              <div className="text-gray-500 mt-2 mb-1">
                                Execution Trace
                              </div>
                              <JsonViewer
                                data={(result.execution_trace ?? {}) as unknown as never}
                              />
                              {result.error && (
                                <div className="text-red-600 mt-2">
                                  {result.error}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                      {selectedRunResults.length === 0 && (
                        <div className="text-sm text-gray-400">
                          No per-case logs available yet.
                        </div>
                      )}
                    </div>
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

