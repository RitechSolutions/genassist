import type {
  QuestionRunStatus,
  WriteQuestionsPayload,
} from "@/interfaces/testSuite.interface";
import { getQuestionRunStatus, writeQuestionsFromKnowledgeBase } from "@/services/testSuites";
import { isRunInProgress } from "./questionRun";

export interface StartAnswer {
  run: QuestionRunStatus;
  /** True when another run already held the dataset, so the one asked for was not started. */
  wasAlreadyRunning: boolean;
}

/** Starts a run unless one already holds the dataset. */
export const startQuestionRun = async (
  suiteId: string,
  payload: WriteQuestionsPayload,
): Promise<StartAnswer> => {
  const current = await getQuestionRunStatus(suiteId);
  if (current && isRunInProgress(current)) return { run: current, wasAlreadyRunning: true };

  const answer = await writeQuestionsFromKnowledgeBase(suiteId, payload);
  if (!answer) throw new Error("The run did not start.");
  const isAnotherRun = answer.knowledge_base_id !== payload.knowledge_base_id;
  return { run: answer, wasAlreadyRunning: isAnotherRun };
};
