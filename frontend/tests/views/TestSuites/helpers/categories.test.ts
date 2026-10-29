import { describe, expect, it, vi } from "vitest";
import {
  ALL_CATEGORIES,
  NO_CATEGORY,
  categoryOption,
  categoryQuery,
  matchesCategory,
  pickerChoices,
  runAllScope,
  tidyCategory,
} from "@/views/TestSuites/helpers/categories";

describe("categories", () => {
  it("tidy spaces as the server saves them", () => {
    expect(tidyCategory("  Refund   requests ")).toBe("Refund requests");
  });

  it("list the picker's choices from the tidied text", () => {
    // Extra spaces still offer to add the tidied name.
    expect(pickerChoices("  Refund   flows ", "", [])).toEqual({ typed: "Refund flows", isNew: true, shown: [] });
    // Part of a name finds it, in any case.
    expect(pickerChoices(" REFUND ", "", ["Escalation", "Refund flows"]).shown).toEqual(["Refund flows"]);
    // The same name in another case is picked, not added again.
    expect(pickerChoices("refund flows", "", ["Refund flows"]).isNew).toBe(false);
    // One added in the form but not saved yet is listed first.
    expect(pickerChoices("", "Billing", ["Refund flows"]).shown).toEqual(["Billing", "Refund flows"]);
  });

  it("ask the API for a category, for none set, or for every one", () => {
    expect(categoryQuery(ALL_CATEGORIES)).toEqual({});
    expect(categoryQuery(NO_CATEGORY)).toEqual({ uncategorized: true });
    expect(categoryQuery(categoryOption("Refunds"))).toEqual({ category: "Refunds" });
    // A category named like a choice is still that category.
    expect(categoryQuery(categoryOption("none"))).toEqual({ category: "none" });
  });

  it("say which evaluations Run all starts", () => {
    expect(runAllScope(ALL_CATEGORIES, "Parker")).toBe("every evaluation of Parker");
    expect(runAllScope(categoryOption("Refunds"), "Parker")).toBe(
      "the evaluations of Parker in the category “Refunds”",
    );
    expect(runAllScope(NO_CATEGORY, "Parker")).toBe("the evaluations of Parker that have no category");
  });

  it("filter a list kept in the page", () => {
    expect(matchesCategory(null, ALL_CATEGORIES)).toBe(true);
    expect(matchesCategory(null, NO_CATEGORY)).toBe(true);
    expect(matchesCategory("Refunds", NO_CATEGORY)).toBe(false);
    expect(matchesCategory("Refunds", categoryOption("refunds"))).toBe(true);
    expect(matchesCategory("Escalation", categoryOption("Refunds"))).toBe(false);
  });

  it("ignore case as the database does, in any browser language", () => {
    // A Turkish browser's toLocaleLowerCase turns "I" into "ı"; matching must not depend on it.
    const toLocaleLowerCase = String.prototype.toLocaleLowerCase;
    const turkish = vi.spyOn(String.prototype, "toLocaleLowerCase").mockImplementation(function (this: string) {
      return toLocaleLowerCase.call(this, "tr-TR");
    });
    try {
      expect(matchesCategory("INVOICES", categoryOption("invoices"))).toBe(true);
      expect(pickerChoices("invoices", "", ["INVOICES"])).toEqual({
        typed: "invoices",
        isNew: false,
        shown: ["INVOICES"],
      });
      // The database lowers one letter at a time: "İ" to "i" and a final "Σ" to "σ".
      expect(matchesCategory("İADE", categoryOption("iade"))).toBe(true);
      expect(pickerChoices("iade", "", ["İADE"]).isNew).toBe(false);
      expect(pickerChoices("οδοσ", "", ["ΟΔΟΣ"]).isNew).toBe(false);
    } finally {
      turkish.mockRestore();
    }
  });
});
