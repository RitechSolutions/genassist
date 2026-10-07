import { describe, expect, it } from "vitest";
import {
  checkedAgainstLine,
  metricSourceLabel,
  usesExpectedOutput,
} from "@/views/TestSuites/helpers/metricSources";

describe("metricSourceLabel", () => {
  it("checks the output-match methods against the expected reply", () => {
    expect(metricSourceLabel("exact_match", undefined)).toBe("Expected reply");
    expect(metricSourceLabel("contains", {})).toBe("Expected reply");
    expect(metricSourceLabel("json_match", undefined)).toBe("Expected reply");
  });

  it("reads the source the wizard saves for NLI", () => {
    expect(metricSourceLabel("nli_eval", { evidence_source: "kb_retrievals" })).toBe(
      "Retrieved context",
    );
    expect(metricSourceLabel("nli_eval", { evidence_source: "expected_output" })).toBe(
      "Expected reply",
    );
  });

  it("reads the source the wizard saves for provenance", () => {
    expect(metricSourceLabel("provenance_eval", { context_source: "tool_events" })).toBe(
      "Tool results",
    );
    expect(
      metricSourceLabel("provenance_eval", { context_source: "conversation_context" }),
    ).toBe("Conversation so far");
  });

  it("prefers the new key over a legacy field", () => {
    expect(
      metricSourceLabel("nli_eval", {
        evidence_source: "conversation_context",
        evidence_field: "trace.retrievals",
      }),
    ).toBe("Conversation so far");
  });

  it("names known legacy fields and shows unknown ones as run data", () => {
    expect(metricSourceLabel("nli_eval", { evidence_field: "trace.retrievals" })).toBe(
      "Retrieved context",
    );
    expect(metricSourceLabel("provenance_eval", { context_field: "trace.nodes.x.output" })).toBe(
      "Run data: trace.nodes.x.output",
    );
  });

  it("falls back to the expected reply, like the backend, when nothing is set", () => {
    expect(metricSourceLabel("nli_eval", undefined)).toBe("Expected reply");
    expect(metricSourceLabel("provenance_eval", {})).toBe("Expected reply");
  });

  it("reads each LLM judge rule's source", () => {
    expect(metricSourceLabel("llm_judge", { rules: [{ source_type: "none" }] })).toBe(
      "Rubric only",
    );
    expect(metricSourceLabel("llm_judge", { rules: [{ source_type: "output" }] })).toBe(
      "The reply",
    );
    expect(
      metricSourceLabel("llm_judge", {
        rules: [
          { source_type: "kb_retrievals" },
          { source_type: "none" },
          { source_type: "kb_retrievals" },
        ],
      }),
    ).toBe("Retrieved context, Rubric only");
  });

  it("reads a legacy single-rubric judge config", () => {
    expect(metricSourceLabel("llm_judge", { rubric: "Polite?", source_field: "trace.session" })).toBe(
      "Conversation so far",
    );
    expect(metricSourceLabel("llm_judge", { rubric: "Polite?" })).toBe("Rubric only");
    expect(metricSourceLabel("llm_judge", undefined)).toBe("Rubric only");
  });

  it("keeps the configured-value labels", () => {
    expect(metricSourceLabel("not_contains", { phrases: ["secret"] })).toBe(
      "Configured forbidden phrases",
    );
    expect(metricSourceLabel("field_equals", { expected: "ok" })).toBe("Configured expected value");
    expect(metricSourceLabel("field_equals", {})).toBe("Expected reply");
  });

  it("has no source for methods that check the run itself", () => {
    expect(metricSourceLabel("no_errors", undefined)).toBeNull();
    expect(metricSourceLabel("tool_used", undefined)).toBeNull();
  });
});

describe("usesExpectedOutput", () => {
  it("is false when NLI or provenance grade against something else", () => {
    expect(usesExpectedOutput("nli_eval", { evidence_source: "kb_retrievals" })).toBe(false);
    expect(usesExpectedOutput("provenance_eval", { context_source: "tool_events" })).toBe(false);
    expect(usesExpectedOutput("nli_eval", { evidence_field: "trace.retrievals" })).toBe(false);
  });

  it("is true for the expected-reply default", () => {
    expect(usesExpectedOutput("nli_eval", {})).toBe(true);
    expect(usesExpectedOutput("exact_match", undefined)).toBe(true);
  });

  it("is true for an LLM judge rule that reads the expected reply", () => {
    expect(
      usesExpectedOutput("llm_judge", {
        rules: [{ source_type: "none" }, { source_type: "expected_output" }],
      }),
    ).toBe(true);
    expect(usesExpectedOutput("llm_judge", { rules: [{ source_type: "none" }] })).toBe(false);
  });
});

describe("checkedAgainstLine", () => {
  it("joins the comment and the source as two sentences", () => {
    expect(checkedAgainstLine("Outputs differ from expected.", "Expected reply")).toBe(
      "Outputs differ from expected. Checked against: Expected reply",
    );
    expect(checkedAgainstLine("score=0.41; threshold=0.50", "Retrieved context")).toBe(
      "score=0.41; threshold=0.50. Checked against: Retrieved context",
    );
  });

  it("shows only the source without a comment", () => {
    expect(checkedAgainstLine(null, "Rubric only")).toBe("Checked against: Rubric only");
    expect(checkedAgainstLine("  ", "Rubric only")).toBe("Checked against: Rubric only");
  });
});
