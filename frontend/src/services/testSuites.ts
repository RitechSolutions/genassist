import { apiRequest } from "@/config/api";
import type {
  AddConversationToDatasetsResult,
  ConversationDataset,
  CreateTestCasePayload,
  CreateTestSuitePayload,
  ImportCasesFromFilesResult,
  ImportFromConversationsResult,
  QuestionRunStatus,
  RunConversations,
  TestCase,
  TestResult,
  TestRun,
  TestSuite,
  WriteQuestionsEstimate,
  WriteQuestionsPayload,
} from "@/interfaces/testSuite.interface";

const BASE = "genagent/eval";

export const listTestSuites = () =>
  apiRequest<TestSuite[]>("GET", `${BASE}/suites`);

export const createTestSuite = (payload: CreateTestSuitePayload) =>
  apiRequest<TestSuite>(
    "POST",
    `${BASE}/suites`,
    payload as unknown as Record<string, unknown>,
  );

export const updateTestSuite = (
  suiteId: string,
  payload: Partial<CreateTestSuitePayload>,
) =>
  apiRequest<TestSuite>(
    "PATCH",
    `${BASE}/suites/${suiteId}`,
    payload as unknown as Record<string, unknown>,
  );

export const deleteTestSuite = (suiteId: string) =>
  apiRequest<void>("DELETE", `${BASE}/suites/${suiteId}`);

export const getTestSuite = (suiteId: string) =>
  apiRequest<TestSuite>("GET", `${BASE}/suites/${suiteId}`);

export const listTestCases = (suiteId: string) =>
  apiRequest<TestCase[]>("GET", `${BASE}/suites/${suiteId}/cases`);

export const addTestCase = (suiteId: string, payload: CreateTestCasePayload) =>
  apiRequest<TestCase>(
    "POST",
    `${BASE}/suites/${suiteId}/cases`,
    payload as unknown as Record<string, unknown>,
  );

export const updateTestCase = (caseId: string, payload: Partial<CreateTestCasePayload>) =>
  apiRequest<TestCase>(
    "PATCH",
    `${BASE}/cases/${caseId}`,
    payload as unknown as Record<string, unknown>,
  );

export const deleteTestCase = (caseId: string) =>
  apiRequest<void>("DELETE", `${BASE}/cases/${caseId}`);

export const importCasesFromConversation = (suiteId: string, conversationId: string) =>
  apiRequest<TestCase[]>(
    "POST",
    `${BASE}/suites/${suiteId}/cases/import-from-conversation`,
    { conversation_id: conversationId },
  );

export const importCasesFromConversations = (
  suiteId: string,
  conversationIds: string[],
) =>
  apiRequest<ImportFromConversationsResult>(
    "POST",
    `${BASE}/suites/${suiteId}/cases/import-from-conversations`,
    { conversation_ids: conversationIds },
  );

const datasetFilesForm = (files: File[]) => {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return form;
};

/** What importing these files would add, without saving anything. */
export const previewCasesFromFiles = (suiteId: string, files: File[]) =>
  apiRequest<ImportCasesFromFilesResult>(
    "POST",
    `${BASE}/suites/${suiteId}/cases/import-from-files/preview`,
    datasetFilesForm(files),
  );

export const importCasesFromFiles = (suiteId: string, files: File[]) =>
  apiRequest<ImportCasesFromFilesResult>(
    "POST",
    `${BASE}/suites/${suiteId}/cases/import-from-files`,
    datasetFilesForm(files),
  );

const questionsFromKnowledgeBase = (suiteId: string) =>
  `${BASE}/suites/${suiteId}/cases/import-from-knowledge-base`;

// A refused request is an error here, so the screen can say so instead of showing nothing.
const REFUSAL_IS_AN_ERROR = { rethrowForbidden: true };

/** How many articles the knowledge base holds and the model calls a run would make. */
export const estimateQuestionsFromKnowledgeBase = (
  suiteId: string,
  knowledgeBaseId: string,
  sampleSize?: number | null,
) => {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  if (sampleSize) params.set("sample_size", String(sampleSize));
  return apiRequest<WriteQuestionsEstimate>(
    "GET",
    `${questionsFromKnowledgeBase(suiteId)}/estimate?${params.toString()}`,
    undefined,
    {},
    REFUSAL_IS_AN_ERROR,
  );
};

/** Starts the run; while one is in progress the server answers with that run instead. */
export const writeQuestionsFromKnowledgeBase = (suiteId: string, payload: WriteQuestionsPayload) =>
  apiRequest<QuestionRunStatus>(
    "POST",
    questionsFromKnowledgeBase(suiteId),
    payload as unknown as Record<string, unknown>,
    {},
    REFUSAL_IS_AN_ERROR,
  );

export const getQuestionRunStatus = (suiteId: string) =>
  apiRequest<QuestionRunStatus>("GET", questionsFromKnowledgeBase(suiteId), undefined, {}, REFUSAL_IS_AN_ERROR);

/** Every dataset, with how much of this conversation each already holds. */
export const listDatasetsForConversation = (conversationId: string) =>
  apiRequest<ConversationDataset[]>(
    "GET",
    `${BASE}/conversations/${conversationId}/suites`,
  );

export const addConversationToDatasets = (
  conversationId: string,
  suiteIds: string[],
) =>
  apiRequest<AddConversationToDatasetsResult>(
    "POST",
    `${BASE}/conversations/${conversationId}/suites`,
    { suite_ids: suiteIds },
  );

export const removeConversationFromSuite = (suiteId: string, conversationId: string) =>
  apiRequest<void>(
    "DELETE",
    `${BASE}/suites/${suiteId}/conversations/${conversationId}`,
  );

export const listTestRunsForSuite = (suiteId: string) =>
  apiRequest<TestRun[]>("GET", `${BASE}/suites/${suiteId}/runs`);

export const getTestRun = (runId: string) =>
  apiRequest<TestRun>("GET", `${BASE}/runs/${runId}`);

export const getTestRunsBatch = (ids: string[]) =>
  apiRequest<TestRun[]>("POST", `${BASE}/runs/batch`, {
    ids,
  } as unknown as Record<string, unknown>);

export const listResultsForRun = (runId: string) =>
  apiRequest<TestResult[]>("GET", `${BASE}/runs/${runId}/results`);

export const getRunConversations = (runId: string) =>
  apiRequest<RunConversations>("GET", `${BASE}/runs/${runId}/conversations`);

export const getRunTurnTrace = (runId: string, caseId: string) =>
  apiRequest<{ execution_trace: Record<string, unknown> | null }>(
    "GET",
    `${BASE}/runs/${runId}/results/${caseId}/trace`,
  );

