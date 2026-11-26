import { describe, expect, it } from "vitest";
import { deleteConfirmation, rejectionNote, withdrawConfirmation } from "@/views/Templates/templateCopy";

describe("deleteConfirmation", () => {
  it("names the template and says its shared copy goes for every tenant while installed agents keep working", () => {
    // Pending and approved get the same text, since the card's status can be stale.
    for (const publish_status of ["approved", "pending"]) {
      const { title, description } = deleteConfirmation({ title: "Support", publish_status });
      expect(title).toBe("Delete this template?");
      expect(description).toContain('permanently deletes "Support"');
      expect(description).toContain("published or waiting for review, is removed for every tenant");
      expect(description).toContain("keep working");
    }
  });

  it("does not mention a shared copy when there is none", () => {
    for (const publish_status of [null, undefined, "rejected"]) {
      const { description } = deleteConfirmation({ title: "Support", publish_status });
      expect(description).toContain('permanently deletes "Support"');
      expect(description).not.toContain("shared copy");
    }
  });
});

describe("withdrawConfirmation", () => {
  it("names the template and says publishing again means a new review", () => {
    const { title, description } = withdrawConfirmation({ title: "Support", publish_status: "approved" });
    expect(title).toBe("Withdraw from the library?");
    expect(description.startsWith('"Support" leaves the library and the review queue.')).toBe(true);
    expect(description).toContain("Publishing it again means a new review.");
  });

  it("reads as a sentence without a name", () => {
    expect(withdrawConfirmation({}).description.startsWith("This template leaves")).toBe(true);
  });
});

describe("rejectionNote", () => {
  const own = { is_global: false, publish_status: "rejected", rejection_reason: " Too vague " };

  it("shows the reason on the author's own rejected card", () => {
    expect(rejectionNote(own)).toBe("Too vague");
  });

  it("shows nothing on community cards, other states or an empty reason", () => {
    expect(rejectionNote({ ...own, is_global: true })).toBeNull();
    expect(rejectionNote({ ...own, publish_status: "pending" })).toBeNull();
    expect(rejectionNote({ ...own, rejection_reason: "  " })).toBeNull();
    expect(rejectionNote({ ...own, rejection_reason: null })).toBeNull();
  });
});
