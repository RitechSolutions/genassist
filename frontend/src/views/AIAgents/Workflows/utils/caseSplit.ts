import type { CaseRow } from "./promptEditorRuns";
import { MAX_CHECK_CASES } from "./promptEditorTechniques";

/** Dev cases inlined; only hold-out measures. Larger hold-out starves optimizer */
export const DEFAULT_HOLDOUT_SHARE = 0.5;

export interface CaseSplitResult {
  dev: CaseRow[];
  holdout: CaseRow[];
  groups: number;
  feasible: boolean;
  /** Why the split is unavailable, for the toggle's tooltip */
  reason: string | null;
}

interface CaseGroup {
  key: string;
  cases: CaseRow[];
}

/** One conversation = one thread. Both UUIDs (prevents duplicate counting) */
const groupKeyOf = (row: CaseRow): string =>
  String(row.source_conversation_id ?? row.id);

/** Tie-break; uuid7 ids would bias newest cases */
const hashKey = (key: string): number => {
  let hash = 0;
  for (let index = 0; index < key.length; index += 1) {
    hash = (hash * 31 + key.charCodeAt(index)) | 0;
  }
  return hash >>> 0;
};

const groupCases = (cases: readonly CaseRow[]): CaseGroup[] => {
  const ordered = [...cases].sort((a, b) => {
    const keyA = groupKeyOf(a);
    const keyB = groupKeyOf(b);
    if (keyA !== keyB) return keyA < keyB ? -1 : 1;
    const turnA = a.turn_index ?? 0;
    const turnB = b.turn_index ?? 0;
    if (turnA !== turnB) return turnA - turnB;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });

  const groups: CaseGroup[] = [];
  for (const row of ordered) {
    const key = groupKeyOf(row);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.cases.push(row);
    else groups.push({ key, cases: [row] });
  }
  return groups;
};

const infeasible = (
  cases: readonly CaseRow[],
  groups: number,
  reason: string,
): CaseSplitResult => ({
  dev: [...cases],
  holdout: [],
  groups,
  feasible: false,
  reason,
});

/** Split dataset into dev and hold-out by case count (not group %)
* Keeps conversations intact */
export const splitCasesByConversation = (
  cases: readonly CaseRow[],
  holdoutShare = DEFAULT_HOLDOUT_SHARE,
  maxHoldout = MAX_CHECK_CASES,
): CaseSplitResult => {
  const groups = groupCases(cases);
  const TOO_FEW = "Needs at least four conversations or cases.";
  if (groups.length < 4) return infeasible(cases, groups.length, TOO_FEW);

  const target = Math.min(
    maxHoldout,
    Math.max(1, Math.round(holdoutShare * cases.length)),
  );
  // A conversation longer than the cap can never be held out whole
  const eligible = groups
    .filter((group) => group.cases.length <= maxHoldout)
    .sort(
      (a, b) =>
        b.cases.length - a.cases.length || hashKey(a.key) - hashKey(b.key),
    );
  // Reserve two groups for development up front
  const maxTake = groups.length - 2;

  const taken = new Set<string>();
  let held = 0;
  const take = (group: CaseGroup) => {
    taken.add(group.key);
    held += group.cases.length;
  };

  // Largest first, so the quota fills in as few groups as possible
  for (const group of eligible) {
    if (taken.size >= maxTake) break;
    if (held + group.cases.length <= target) take(group);
  }
  if (taken.size < 2) {
    const smallestFirst = eligible
      .filter((group) => !taken.has(group.key))
      .sort(
        (a, b) =>
          a.cases.length - b.cases.length || hashKey(a.key) - hashKey(b.key),
      );
    for (const group of smallestFirst) {
      if (taken.size >= 2) break;
      if (held + group.cases.length <= maxHoldout) take(group);
    }
  }

  if (taken.size < 2)
    return infeasible(
      cases,
      groups.length,
      `The shortest conversations do not fit a ${maxHoldout}-case hold-out.`,
    );

  return {
    dev: groups.filter((g) => !taken.has(g.key)).flatMap((g) => g.cases),
    holdout: groups.filter((g) => taken.has(g.key)).flatMap((g) => g.cases),
    groups: groups.length,
    feasible: true,
    reason: null,
  };
};
