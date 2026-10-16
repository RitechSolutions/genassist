import { describe, expect, it } from "vitest";
import { planSections, sectionKeyFor } from "@/views/TestSuites/helpers/evaluationSections";

const rows = [
  { key: "w1", name: "Parker" },
  { key: "w2", name: "Northwind Billing" },
  { key: "unassigned", name: "Unassigned evaluations" },
];

const keys = (plan: ReturnType<typeof planSections>) => plan.sections.map((section) => section.row.key);

describe("planSections", () => {
  it("shows every workflow without a search, folded unless the person opened it", () => {
    const plan = planSections(rows, "", null, { w1: true, w2: false }, new Set());
    expect(keys(plan)).toEqual(["w1", "w2", "unassigned"]);
    expect(plan.sections.map((section) => section.open)).toEqual([true, false, false]);
    expect(plan.sections.every((section) => section.search === "" && section.matches === null)).toBe(true);
    expect(plan.searching).toBe(false);
  });

  it("opens a lone workflow unless the person folded it", () => {
    expect(planSections(rows.slice(0, 1), "", null, {}, new Set()).sections[0].open).toBe(true);
    expect(planSections(rows.slice(0, 1), "", null, { w1: false }, new Set()).sections[0].open).toBe(false);
  });

  it("shows a workflow whose name matches with all its evaluations, and one with matches with just those", () => {
    const plan = planSections(rows, " parker ", new Map([["w2", 2]]), { w1: false }, new Set());
    expect(keys(plan)).toEqual(["w1", "w2"]);
    const [byName, byEvaluations] = plan.sections;
    expect(byName).toMatchObject({ search: "", matches: null, open: true });
    expect(byEvaluations).toMatchObject({ search: "parker", matches: 2, open: true });
  });

  it("folds for the search only, and says when the search has not answered", () => {
    const waiting = planSections(rows, "billing", null, {}, new Set(["w2"]));
    expect(keys(waiting)).toEqual(["w2"]);
    expect(waiting.sections[0].open).toBe(false);
    expect(waiting.searching).toBe(true);
    const none = planSections(rows, "nothing", new Map(), {}, new Set());
    expect(none.sections).toEqual([]);
    expect(none.searching).toBe(false);
  });
});

describe("sectionKeyFor", () => {
  const sectionRows = [
    { key: "live-a", workflowId: "live-a" },
    { key: "unassigned", workflowId: null },
  ];
  const workflows = [
    { id: "live-a", agent_id: "agent-a" },
    { id: "old-a", agent_id: "agent-a" },
    { id: "other", agent_id: "agent-b" },
  ];

  it("finds a section by its key, or an older version's section through its agent", () => {
    expect(sectionKeyFor("live-a", sectionRows, workflows)).toBe("live-a");
    expect(sectionKeyFor("unassigned", sectionRows, workflows)).toBe("unassigned");
    expect(sectionKeyFor("old-a", sectionRows, workflows)).toBe("live-a");
    expect(sectionKeyFor("other", sectionRows, workflows)).toBeNull();
    expect(sectionKeyFor("unknown", sectionRows, workflows)).toBeNull();
  });
});
