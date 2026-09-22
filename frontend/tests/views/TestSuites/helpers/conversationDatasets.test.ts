import { describe, it, expect } from "vitest";
import {
  ADD_TO_DATASET_PERMISSION,
  MAX_CONVERSATION_DATASETS,
  canAddConversationToDataset,
  datasetTurnsById,
  describeDatasetAddConfirm,
  describeDatasetAddPlan,
  describeDatasetMembership,
  filterDatasets,
  planDatasetAdd,
  selectAllDatasets,
  summarizeDatasetAddOutcome,
  toggleDataset,
} from "@/views/TestSuites/helpers/conversationDatasets";
import {
  areAllSelected,
  countHiddenSelections,
} from "@/views/TestSuites/helpers/conversationImportSelection";
import type {
  AddConversationToDatasetsResult,
  ConversationDataset,
  ConversationDatasetResult,
} from "@/interfaces/testSuite.interface";

const dataset = (
  overrides: Partial<ConversationDataset> = {},
): ConversationDataset => ({
  suite_id: "s1",
  name: "Refunds",
  turns: 0,
  ...overrides,
});

const outcome = (
  overrides: Partial<AddConversationToDatasetsResult> = {},
): AddConversationToDatasetsResult => ({
  results: [],
  imported: 0,
  replaced: 0,
  failed: 0,
  ...overrides,
});

const entry = (
  overrides: Partial<ConversationDatasetResult> = {},
): ConversationDatasetResult => ({
  suite_id: "s1",
  status: "imported",
  turns: 2,
  ...overrides,
});

const names = (pairs: [string, string][]) => new Map(pairs);

describe("toggleDataset", () => {
  it("adds a dataset that is not selected", () => {
    expect([...toggleDataset(new Set(), "s1")]).toEqual(["s1"]);
  });

  it("removes a dataset that is already selected", () => {
    expect([...toggleDataset(new Set(["s1", "s2"]), "s1")]).toEqual(["s2"]);
  });

  it("returns a new Set rather than mutating the old one", () => {
    const before = new Set(["s1"]);
    const after = toggleDataset(before, "s2");
    expect(before.has("s2")).toBe(false);
    expect(after).not.toBe(before);
  });

  it("refuses to select past the cap", () => {
    const full = new Set(["a", "b"]);
    expect(toggleDataset(full, "c", 2)).toBe(full);
  });

  it("still deselects when at the cap", () => {
    expect([...toggleDataset(new Set(["a", "b"]), "a", 2)]).toEqual(["b"]);
  });

  it("caps at the API limit by default", () => {
    expect(MAX_CONVERSATION_DATASETS).toBe(50);
  });
});

describe("selectAllDatasets", () => {
  it("selects every dataset it is handed", () => {
    expect([...selectAllDatasets(new Set(), ["s1", "s2"])]).toEqual(["s1", "s2"]);
  });

  it("keeps picks that are not in the visible list", () => {
    const next = selectAllDatasets(new Set(["hidden"]), ["s1"]);
    expect([...next].sort()).toEqual(["hidden", "s1"]);
  });

  it("is a no-op for datasets already selected", () => {
    expect([...selectAllDatasets(new Set(["s1"]), ["s1", "s2"])]).toEqual([
      "s1",
      "s2",
    ]);
  });

  it("fills up to the cap rather than refusing the whole group", () => {
    const next = selectAllDatasets(new Set(["a"]), ["b", "c", "d"], 3);
    expect(next.size).toBe(3);
  });

  it("returns a new Set rather than mutating the old one", () => {
    const before = new Set(["s1"]);
    const after = selectAllDatasets(before, ["s2"]);
    expect(before.has("s2")).toBe(false);
    expect(after).not.toBe(before);
  });

  it("selecting all of a filtered view leaves the full list partly selected", () => {
    // What the toolbar relies on: Select all speaks for the search results, so
    // the button must stay enabled once the filter is cleared.
    const visible = ["s1", "s2"];
    const everything = ["s1", "s2", "s3"];
    const next = selectAllDatasets(new Set(), visible);
    expect(areAllSelected(visible, next)).toBe(true);
    expect(areAllSelected(everything, next)).toBe(false);
    expect(countHiddenSelections(next, visible)).toBe(0);
    expect(countHiddenSelections(next, ["s1"])).toBe(1);
  });
});

describe("filterDatasets", () => {
  const all = [
    dataset({ suite_id: "s1", name: "Refunds" }),
    dataset({ suite_id: "s2", name: "Billing", description: "Invoice questions" }),
  ];

  it("returns everything for an empty query", () => {
    expect(filterDatasets(all, "   ")).toEqual(all);
  });

  it("matches on name, ignoring case", () => {
    expect(filterDatasets(all, "REFUND").map((d) => d.suite_id)).toEqual(["s1"]);
  });

  it("matches on description too", () => {
    expect(filterDatasets(all, "invoice").map((d) => d.suite_id)).toEqual(["s2"]);
  });

  it("returns nothing when nothing matches", () => {
    expect(filterDatasets(all, "shipping")).toEqual([]);
  });
});

describe("datasetTurnsById", () => {
  it("keeps only datasets that already hold turns", () => {
    const map = datasetTurnsById([
      dataset({ suite_id: "s1", turns: 3 }),
      dataset({ suite_id: "s2", turns: 0 }),
    ]);
    expect(map.get("s1")).toBe(3);
    expect(map.has("s2")).toBe(false);
  });
});

describe("planDatasetAdd", () => {
  it("counts an untouched dataset as an add", () => {
    expect(planDatasetAdd(["s1"], new Map())).toEqual({
      total: 1,
      added: 1,
      refreshed: 0,
      replacedTurns: 0,
    });
  });

  it("counts a dataset that already holds the conversation as a replacement", () => {
    expect(planDatasetAdd(["s1"], new Map([["s1", 4]]))).toEqual({
      total: 1,
      added: 0,
      refreshed: 1,
      replacedTurns: 4,
    });
  });

  it("sums the replaced turns across a mixed selection", () => {
    const plan = planDatasetAdd(
      ["s1", "s2", "s3"],
      new Map([
        ["s1", 2],
        ["s3", 5],
      ]),
    );
    expect(plan).toEqual({
      total: 3,
      added: 1,
      refreshed: 2,
      replacedTurns: 7,
    });
  });
});

describe("describeDatasetAddConfirm", () => {
  const plan = (
    overrides: Partial<{
      total: number;
      added: number;
      refreshed: number;
      replacedTurns: number;
    }> = {},
  ) => ({
    total: 1,
    added: 1,
    refreshed: 0,
    replacedTurns: 0,
    ...overrides,
  });

  it("keeps the button singular for one dataset", () => {
    const copy = describeDatasetAddConfirm(plan());
    expect(copy.title).toBe("Add to 1 dataset");
    expect(copy.primaryButtonText).toBe("Add to Dataset");
  });

  it("makes the button plural for several datasets", () => {
    const copy = describeDatasetAddConfirm(plan({ total: 3, added: 3 }));
    expect(copy.title).toBe("Add to 3 datasets");
    expect(copy.primaryButtonText).toBe("Add to Datasets");
  });

  it("switches the button to Replace once anything is being replaced", () => {
    const copy = describeDatasetAddConfirm(
      plan({ total: 2, added: 1, refreshed: 1, replacedTurns: 3 }),
    );
    expect(copy.title).toBe("Add to 2 datasets, replacing 1");
    expect(copy.primaryButtonText).toBe("Add and Replace");
  });

  it("titles a single replacement in the singular", () => {
    const copy = describeDatasetAddConfirm(
      plan({ total: 1, added: 0, refreshed: 1, replacedTurns: 2 }),
    );
    expect(copy.title).toBe("Add to 1 dataset, replacing 1");
  });

  // The bug this helper exists to prevent: a singular title over a plural button.
  it("never disagrees with its own title on number", () => {
    for (const total of [1, 2, 7]) {
      const copy = describeDatasetAddConfirm(plan({ total, added: total }));
      const titleIsPlural = copy.title.includes("datasets");
      const buttonIsPlural = copy.primaryButtonText.includes("Datasets");
      expect(buttonIsPlural).toBe(titleIsPlural);
    }
  });
});

describe("describeDatasetAddPlan", () => {
  it("says only that turns are added when nothing is replaced", () => {
    const copy = describeDatasetAddPlan({
      total: 2,
      added: 2,
      refreshed: 0,
      replacedTurns: 0,
    });
    expect(copy).toBe(
      "This adds the conversation's turns to 2 datasets, keeping everything already there.",
    );
  });

  it("reads correctly for a single fresh dataset", () => {
    const copy = describeDatasetAddPlan({
      total: 1,
      added: 1,
      refreshed: 0,
      replacedTurns: 0,
    });
    expect(copy).toBe(
      "This adds the conversation's turns to 1 dataset, keeping everything already there.",
    );
  });

  it("warns about lost edits when only replacements are selected", () => {
    const copy = describeDatasetAddPlan({
      total: 1,
      added: 0,
      refreshed: 1,
      replacedTurns: 3,
    });
    expect(copy).toContain("3 turns in 1 dataset already holding this conversation");
    expect(copy).toContain("will be replaced from the transcript");
    expect(copy).toContain("Any edits made to those turns are lost");
    expect(copy).not.toContain("This adds the conversation to");
  });

  it("agrees grammatically when several datasets are replaced", () => {
    const copy = describeDatasetAddPlan({
      total: 2,
      added: 0,
      refreshed: 2,
      replacedTurns: 7,
    });
    expect(copy).toContain(
      "7 turns in 2 datasets already holding this conversation will be replaced",
    );
  });

  it("says replaced, never refreshed", () => {
    const copy = describeDatasetAddPlan({
      total: 2,
      added: 1,
      refreshed: 1,
      replacedTurns: 2,
    });
    expect(copy).not.toMatch(/refresh/i);
  });

  it("states both halves of a mixed selection", () => {
    const copy = describeDatasetAddPlan({
      total: 3,
      added: 2,
      refreshed: 1,
      replacedTurns: 1,
    });
    expect(copy).toContain("This adds the conversation to 2 datasets.");
    expect(copy).toContain("1 turn in 1 dataset");
  });

  it("agrees on both halves of a mixed selection with several refreshes", () => {
    const copy = describeDatasetAddPlan({
      total: 3,
      added: 1,
      refreshed: 2,
      replacedTurns: 4,
    });
    expect(copy).toBe(
      "This adds the conversation to 1 dataset. 4 turns in 2 datasets already holding this conversation will be replaced from the transcript. Any edits made to those turns are lost, and past evaluation results stop matching them.",
    );
  });
});

describe("summarizeDatasetAddOutcome", () => {
  it("names the dataset when exactly one succeeded", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({ results: [entry({ suite_id: "s1" })], imported: 1 }),
      names([["s1", "Refunds"]]),
    );
    expect(summary.anySucceeded).toBe(true);
    expect(summary.successMessage).toBe('Added the conversation to "Refunds".');
    expect(summary.errorMessage).toBeNull();
  });

  it("counts datasets when several succeeded", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({
        results: [entry({ suite_id: "s1" }), entry({ suite_id: "s2" })],
        imported: 2,
      }),
      names([
        ["s1", "Refunds"],
        ["s2", "Billing"],
      ]),
    );
    expect(summary.successMessage).toBe("Added the conversation to 2 datasets.");
  });

  it("says replaced when the only change was a re-import", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({
        results: [entry({ suite_id: "s1", status: "replaced" })],
        replaced: 1,
      }),
      names([["s1", "Refunds"]]),
    );
    expect(summary.successMessage).toBe(
      'Replaced the conversation in "Refunds".',
    );
  });

  it("splits the counts when a batch both adds and replaces", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({
        results: [
          entry({ suite_id: "s1" }),
          entry({ suite_id: "s2", status: "replaced" }),
        ],
        imported: 1,
        replaced: 1,
      }),
      names([
        ["s1", "Refunds"],
        ["s2", "Billing"],
      ]),
    );
    expect(summary.successMessage).toBe(
      "Added the conversation to 1 dataset and replaced it in 1.",
    );
  });

  it("names the single failure and its reason", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({
        results: [
          entry({ suite_id: "s1", status: "failed", turns: 0, detail: "Dataset not found." }),
        ],
        failed: 1,
      }),
      names([["s1", "Refunds"]]),
    );
    expect(summary.anySucceeded).toBe(false);
    expect(summary.successMessage).toBeNull();
    expect(summary.errorMessage).toBe(
      '"Refunds" could not be updated. Dataset not found.',
    );
    expect(summary.failures).toHaveLength(1);
  });

  it("collapses several failures into a count", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({
        results: [
          entry({ suite_id: "s1", status: "failed", turns: 0 }),
          entry({ suite_id: "s2", status: "failed", turns: 0 }),
        ],
        failed: 2,
      }),
      names([]),
    );
    expect(summary.errorMessage).toBe("2 datasets could not be updated.");
  });

  it("reports both halves of a partial run", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({
        results: [
          entry({ suite_id: "s1" }),
          entry({ suite_id: "s2", status: "failed", turns: 0, detail: "Dataset not found." }),
        ],
        imported: 1,
        failed: 1,
      }),
      names([
        ["s1", "Refunds"],
        ["s2", "Billing"],
      ]),
    );
    expect(summary.successMessage).toBe('Added the conversation to "Refunds".');
    expect(summary.errorMessage).toBe(
      '"Billing" could not be updated. Dataset not found.',
    );
  });

  it("falls back when a dataset name is unknown", () => {
    const summary = summarizeDatasetAddOutcome(
      outcome({ results: [entry({ suite_id: "s9" })], imported: 1 }),
      names([]),
    );
    expect(summary.successMessage).toBe('Added the conversation to "the dataset".');
  });
});

describe("canAddConversationToDataset", () => {
  it("allows a user holding the write permission", () => {
    expect(canAddConversationToDataset([ADD_TO_DATASET_PERMISSION], "c1")).toBe(
      true,
    );
  });

  it("allows an admin carrying only the wildcard", () => {
    expect(canAddConversationToDataset(["*"], "c1")).toBe(true);
  });

  it("refuses a user without the permission", () => {
    expect(canAddConversationToDataset(["read:conversation"], "c1")).toBe(false);
  });

  it("refuses the transformTranscript error stub", () => {
    expect(canAddConversationToDataset(["*"], "error")).toBe(false);
  });

  it("refuses a missing conversation id", () => {
    expect(canAddConversationToDataset(["*"], null)).toBe(false);
    expect(canAddConversationToDataset(["*"], undefined)).toBe(false);
    expect(canAddConversationToDataset(["*"], "")).toBe(false);
  });
});

describe("describeDatasetMembership", () => {
  it("states the turn count when the join date is unknown", () => {
    expect(
      describeDatasetMembership(dataset({ turns: 1, added_at: null })),
    ).toBe("Already holds 1 turn of this conversation.");
  });

  it("includes the join date when there is one", () => {
    const copy = describeDatasetMembership(
      dataset({ turns: 3, added_at: "2026-02-01T00:00:00Z" }),
    );
    expect(copy).toContain("Already holds 3 turns of this conversation, added ");
  });

  it("falls back when the join date cannot be parsed", () => {
    expect(
      describeDatasetMembership(dataset({ turns: 2, added_at: "not a date" })),
    ).toBe("Already holds 2 turns of this conversation.");
  });
});
