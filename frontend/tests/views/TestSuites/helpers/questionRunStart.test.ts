import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/services/testSuites", () => ({
  getQuestionRunStatus: vi.fn(),
  writeQuestionsFromKnowledgeBase: vi.fn(),
}));

import type { QuestionRunStatus } from "@/interfaces/testSuite.interface";
import { getQuestionRunStatus, writeQuestionsFromKnowledgeBase } from "@/services/testSuites";
import { IDLE_RUN } from "@/views/TestSuites/helpers/questionRun";
import { startQuestionRun } from "@/views/TestSuites/helpers/questionRunStart";

const readStatus = vi.mocked(getQuestionRunStatus);
const sendStart = vi.mocked(writeQuestionsFromKnowledgeBase);
const payload = { knowledge_base_id: "kb-mine", llm_provider_id: "model-1", sample_size: null };
const run = (fields: Partial<QuestionRunStatus>): QuestionRunStatus => ({ ...IDLE_RUN, ...fields });

beforeEach(() => vi.clearAllMocks());

describe("startQuestionRun", () => {
  it("starts the run when nothing holds the dataset", async () => {
    const queued = run({ status: "queued", run_id: "r1", knowledge_base_id: "kb-mine" });
    readStatus.mockResolvedValue(IDLE_RUN);
    sendStart.mockResolvedValue(queued);

    expect(await startQuestionRun("s1", payload)).toEqual({ run: queued, wasAlreadyRunning: false });
    expect(sendStart).toHaveBeenCalledWith("s1", payload);
  });

  it("starts the run after an earlier one has ended", async () => {
    const queued = run({ status: "queued", run_id: "r2", knowledge_base_id: "kb-mine" });
    readStatus.mockResolvedValue(run({ status: "succeeded", run_id: "r1", knowledge_base_id: "kb-mine" }));
    sendStart.mockResolvedValue(queued);

    expect(await startQuestionRun("s1", payload)).toEqual({ run: queued, wasAlreadyRunning: false });
  });

  it("does not ask for a start while a run holds the dataset, even from the same knowledge base", async () => {
    const theirs = run({ status: "running", run_id: "r9", knowledge_base_id: "kb-mine" });
    readStatus.mockResolvedValue(theirs);

    expect(await startQuestionRun("s1", payload)).toEqual({ run: theirs, wasAlreadyRunning: true });
    expect(sendStart).not.toHaveBeenCalled();
  });

  it("says a run was already in progress when the server answers with another knowledge base's run", async () => {
    const theirs = run({ status: "queued", run_id: "r9", knowledge_base_id: "kb-theirs" });
    readStatus.mockResolvedValue(IDLE_RUN);
    sendStart.mockResolvedValue(theirs);

    expect(await startQuestionRun("s1", payload)).toEqual({ run: theirs, wasAlreadyRunning: true });
  });

  it("still asks for a start when the status cannot be read", async () => {
    const queued = run({ status: "queued", run_id: "r1", knowledge_base_id: "kb-mine" });
    readStatus.mockResolvedValue(null);
    sendStart.mockResolvedValue(queued);

    expect((await startQuestionRun("s1", payload)).wasAlreadyRunning).toBe(false);
  });

  it("fails when the server gives no answer to the start", async () => {
    readStatus.mockResolvedValue(IDLE_RUN);
    sendStart.mockResolvedValue(null);

    await expect(startQuestionRun("s1", payload)).rejects.toThrow("The run did not start.");
  });
});
