import { apiRequest } from "@/config/api";
import type {
  CreateTestCasePayload,
  CreateTestSuitePayload,
  StartTestRunPayload,
  TestCase,
  TestResult,
  TestRun,
  TestSuite,
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

export const startTestRun = (suiteId: string, payload: StartTestRunPayload) =>
  apiRequest<TestRun>(
    "POST",
    `${BASE}/suites/${suiteId}/runs`,
    payload as unknown as Record<string, unknown>,
  );

export const listTestRunsForSuite = (suiteId: string) =>
  apiRequest<TestRun[]>("GET", `${BASE}/suites/${suiteId}/runs`);

export const getTestRun = (runId: string) =>
  apiRequest<TestRun>("GET", `${BASE}/runs/${runId}`);

export const listResultsForRun = (runId: string) =>
  apiRequest<TestResult[]>("GET", `${BASE}/runs/${runId}/results`);

