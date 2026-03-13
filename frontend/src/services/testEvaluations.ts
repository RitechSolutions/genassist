import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";

const STORAGE_KEY = "test_evaluations_v1";

const readAll = (): TestEvaluationConfig[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as TestEvaluationConfig[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const writeAll = (items: TestEvaluationConfig[]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
};

export const listTestEvaluations = (): TestEvaluationConfig[] => readAll();

export const getTestEvaluationById = (
  id: string,
): TestEvaluationConfig | undefined => {
  return readAll().find((item) => item.id === id);
};

export const createTestEvaluation = (
  item: Omit<TestEvaluationConfig, "id" | "run_ids" | "created_at" | "updated_at">,
): TestEvaluationConfig => {
  const now = new Date().toISOString();
  const created: TestEvaluationConfig = {
    ...item,
    id: crypto.randomUUID(),
    run_ids: [],
    created_at: now,
    updated_at: now,
  };
  const next = [created, ...readAll()];
  writeAll(next);
  return created;
};

export const appendRunToEvaluation = (
  evaluationId: string,
  runId: string,
): TestEvaluationConfig | undefined => {
  const all = readAll();
  const idx = all.findIndex((item) => item.id === evaluationId);
  if (idx < 0) return undefined;
  const existing = all[idx];
  const updated: TestEvaluationConfig = {
    ...existing,
    run_ids: [runId, ...existing.run_ids],
    updated_at: new Date().toISOString(),
  };
  all[idx] = updated;
  writeAll(all);
  return updated;
};

