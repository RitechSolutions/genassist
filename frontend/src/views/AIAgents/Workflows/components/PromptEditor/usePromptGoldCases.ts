import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listTestCases } from "@/services/testSuites";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type { CasesState } from "../../utils/promptEditorGates";
import {
  splitCasesByConversation,
  type CaseSplitResult,
} from "../../utils/caseSplit";
import { canonicalJson, type CaseRow } from "../../utils/promptEditorRuns";

export interface PromptGoldCasesState {
  casesState: CasesState;
  /** `canonicalJson(caseRows)`; null while the cases are unloaded or unreadable */
  caseRowsKey: string | null;
  split: CaseSplitResult;
}

/** The linked gold dataset as the measurement side needs it: gate status, key material
 *  for staleness, and the development/hold-out split */
export const usePromptGoldCases = (
  goldSuiteId: string | null,
  canReadCases: boolean,
): PromptGoldCasesState => {
  const goldCasesQuery = useQuery({
    queryKey: ["goldCases", goldSuiteId],
    queryFn: () => listTestCases(goldSuiteId!),
    enabled: !!goldSuiteId && canReadCases,
  });

  // Gate distinguishes forbidden/failed reads from empty datasets
  const casesState: CasesState = {
    status:
      !goldSuiteId || !canReadCases
        ? "idle"
        : goldCasesQuery.isPending
          ? "pending"
          : goldCasesQuery.isError
            ? "error"
            : goldCasesQuery.data === null
              ? "forbidden"
              : "success",
    count: goldCasesQuery.data?.length ?? 0,
  };

  // Null is a forbidden or unloaded dataset, which is distinct key material from
  // a loaded but empty one. A case without an id cannot be selected or compared
  const caseRows: CaseRow[] | null = useMemo(() => {
    const data = goldCasesQuery.data;
    if (!Array.isArray(data)) return null;
    return data
      .filter((c): c is TestCase & { id: string } => !!c.id)
      .map((c) => ({
        id: c.id,
        input_data: c.input_data,
        expected_output: c.expected_output ?? null,
        source_conversation_id: c.source_conversation_id ?? null,
        turn_index: c.turn_index ?? null,
      }))
      .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  }, [goldCasesQuery.data]);

  // Memoised so a keystroke re-keys only the small run object, not the whole dataset
  const caseRowsKey = useMemo(
    () => (caseRows === null ? null : canonicalJson(caseRows)),
    [caseRows],
  );

  const split = useMemo(
    () => splitCasesByConversation(caseRows ?? []),
    [caseRows],
  );

  return { casesState, caseRowsKey, split };
};
