import { describe, expect, it } from "vitest";
import { planRendering } from "@/views/AIAgents/Workflows/components/diff/FieldChangeRow";

const SHORT_PROMPT = "You are a helpful support assistant.";
const EXTENDED_PROMPT = `${SHORT_PROMPT} Always answer in the customer's own language, keep the reply under five sentences, and never promise a refund without checking the order status first.`;

describe("planRendering", () => {
  it("renders an extended prompt inline at the editor's threshold", () => {
    expect(planRendering(SHORT_PROMPT, EXTENDED_PROMPT, 0.15).kind).toBe("inline");
  });

  it("still treats the same pair as replaced at the default threshold", () => {
    expect(planRendering(SHORT_PROMPT, EXTENDED_PROMPT).kind).toBe("replaced");
  });

  it("treats an unrelated prompt as replaced", () => {
    expect(
      planRendering(
        SHORT_PROMPT,
        "Translate the incoming message into formal Japanese and return only the translation.",
        0.15,
      ).kind,
    ).toBe("replaced");
  });

  it("keeps short single-line values on the scalar row", () => {
    expect(planRendering("draft", "final", 0.15).kind).toBe("scalar");
  });
});
