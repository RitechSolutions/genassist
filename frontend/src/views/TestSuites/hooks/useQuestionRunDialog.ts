import { useEffect, useLayoutEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { KnowledgeItemMinimal } from "@/interfaces/knowledge.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type {
  QuestionRunStatus,
  TestSuite,
  WriteQuestionsPayload,
} from "@/interfaces/testSuite.interface";
import { getKnowledgeItemsMinimal } from "@/services/api";
import { getLLMProvidersMinimal } from "@/services/llmProviders";
import { estimateQuestionsFromKnowledgeBase } from "@/services/testSuites";
import { apiErrorDetail } from "../helpers/evalBundle";
import {
  type PickListState,
  canStartRun,
  describeOutcome,
  estimateNote,
  isRunInProgress,
  knowledgeBaseNameOf,
  sampleSizeOf,
  showsRunView,
  startFallbackText,
  usableEstimate,
} from "../helpers/questionRun";
import { startQuestionRun } from "../helpers/questionRunStart";

export interface QuestionRunForm {
  knowledgeBaseId: string;
  providerId: string;
  /** The number of articles as typed; empty means all of them. */
  sampleText: string;
}

/** A list the form picks from, how its loading went, and a way to load it again. */
export interface PickList<T> extends PickListState {
  items: T[];
  reload: () => void;
}

interface QuestionRunDialogInput {
  open: boolean;
  suite: TestSuite | null;
  /** The dataset's run in progress, else its last run's outcome. */
  run: QuestionRunStatus;
  onStarted: (run: QuestionRunStatus) => void;
}

const EMPTY_FORM: QuestionRunForm = { knowledgeBaseId: "", providerId: "", sampleText: "" };

const loadKnowledgeBases = async (): Promise<KnowledgeItemMinimal[]> => {
  const knowledgeBases = await getKnowledgeItemsMinimal();
  if (!knowledgeBases) throw new Error("The knowledge bases were not given.");
  return knowledgeBases;
};

const loadActiveModels = async (): Promise<LLMProviderMinimal[]> => {
  const providers = await getLLMProvidersMinimal();
  if (!providers) throw new Error("The models were not given.");
  return providers.filter((provider) => provider.is_active === 1);
};

/** One of the form's lists, asked for again on every open so a new entry is listed. */
const usePickList = <T,>(key: string, load: () => Promise<T[]>, open: boolean): PickList<T> => {
  // "Try again" is offered instead of repeating a failed load.
  const query = useQuery({ queryKey: [key], queryFn: load, enabled: open, staleTime: 0, retry: false });
  const items = query.data ?? [];
  return {
    items,
    count: items.length,
    isLoading: query.isLoading,
    hasFailed: query.isError,
    reload: () => void query.refetch(),
  };
};

/** The count of the picked knowledge base's articles, and what to show about it. */
const useArticleCount = (open: boolean, suiteId: string, form: QuestionRunForm) => {
  const sampleSize = sampleSizeOf(form.sampleText);
  const isSampleInvalid = sampleSize === undefined;
  const canCount = open && Boolean(suiteId) && Boolean(form.knowledgeBaseId) && !isSampleInvalid;
  const query = useQuery({
    queryKey: ["question-run-estimate", suiteId, form.knowledgeBaseId, sampleSize],
    queryFn: () => estimateQuestionsFromKnowledgeBase(suiteId, form.knowledgeBaseId, sampleSize),
    enabled: canCount,
    staleTime: 0,
    retry: false,
    // A recount on every return to the window would switch Start off while it runs.
    refetchOnWindowFocus: false,
  });
  const isCounting = query.isFetching;
  const wasNotAnswered = query.isError || (query.isSuccess && !query.data);
  const hasFailed = wasNotAnswered && !isCounting;
  const estimate = usableEstimate(isCounting, hasFailed, query.data);
  return {
    sampleSize,
    isSampleInvalid,
    estimate,
    hasFailed,
    note: isSampleInvalid ? null : estimateNote(form.knowledgeBaseId, isCounting, hasFailed, estimate),
    recount: () => void query.refetch(),
  };
};

/** Starting a run from the open dialog, and following it until the dialog is opened again. */
const useRunStart = (open: boolean, run: QuestionRunStatus, onStarted: (run: QuestionRunStatus) => void) => {
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState("");
  // Set once this open dialog has a run to follow, so its outcome stays on screen when it ends.
  const [followsRun, setFollowsRun] = useState(false);
  const [wasAlreadyRunning, setWasAlreadyRunning] = useState(false);

  // Cleared when the dialog opens, not when it closes: it stays clickable while it fades out.
  useLayoutEffect(() => {
    if (!open) return;
    setFollowsRun(false);
    setWasAlreadyRunning(false);
    setStartError("");
  }, [open]);

  useEffect(() => {
    if (open && isRunInProgress(run)) setFollowsRun(true);
  }, [open, run]);

  const start = async (suiteId: string, payload: WriteQuestionsPayload) => {
    setIsStarting(true);
    setStartError("");
    try {
      const answer = await startQuestionRun(suiteId, payload);
      setWasAlreadyRunning(answer.wasAlreadyRunning);
      setFollowsRun(true);
      onStarted(answer.run);
    } catch (error) {
      setStartError(apiErrorDetail(error) ?? startFallbackText(error));
    } finally {
      setIsStarting(false);
    }
  };

  return { isStarting, startError, followsRun, wasAlreadyRunning, start };
};

/** Everything the question-writing dialog shows and does, without its markup. */
export const useQuestionRunDialog = ({ open, suite, run, onStarted }: QuestionRunDialogInput) => {
  const [form, setForm] = useState<QuestionRunForm>(EMPTY_FORM);
  const suiteId = suite?.id ?? "";
  const knowledgeBases = usePickList("question-run-knowledge-bases", loadKnowledgeBases, open);
  const providers = usePickList("question-run-models", loadActiveModels, open);
  const count = useArticleCount(open, suiteId, form);
  const starting = useRunStart(open, run, onStarted);

  const canStart =
    open && canStartRun(form.knowledgeBaseId, form.providerId, count.sampleSize, count.estimate);
  const start = () => {
    if (!suiteId || count.isSampleInvalid) return;
    void starting.start(suiteId, {
      knowledge_base_id: form.knowledgeBaseId,
      llm_provider_id: form.providerId,
      sample_size: count.sampleSize,
    });
  };

  return {
    form,
    changeForm: (change: Partial<QuestionRunForm>) => setForm((current) => ({ ...current, ...change })),
    knowledgeBases,
    providers,
    count,
    canStart,
    start,
    isStarting: starting.isStarting,
    startError: starting.startError,
    wasAlreadyRunning: starting.wasAlreadyRunning,
    showsRun: showsRunView(run, starting.followsRun),
    lastOutcome: describeOutcome(run),
    knowledgeBaseName: knowledgeBaseNameOf(run, knowledgeBases.items),
  };
};
