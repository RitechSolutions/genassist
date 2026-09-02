import { describe, expect, it } from "vitest";
import {
  createConversationAnalysis,
  getLatestTranscript,
} from "@/views/Operators/utils/operatorAnalysis";
import type { Operator } from "@/interfaces/operator.interface";
import type { BackendTranscript } from "@/interfaces/transcript.interface";

function makeTranscript(overrides: Partial<BackendTranscript>): BackendTranscript {
  return {
    id: "t",
    created_at: "2023-01-01T00:00:00Z",
    duration: 0,
    agent_ratio: 0,
    customer_ratio: 0,
    ...overrides,
  } as unknown as BackendTranscript;
}

function makeOperator(overrides: Partial<Operator>): Operator {
  return {
    firstName: "Ada",
    lastName: "Lovelace",
    ...overrides,
  } as Operator;
}

describe("getLatestTranscript", () => {
  it("returns null when there are no transcripts", () => {
    expect(getLatestTranscript([])).toBeNull();
  });

  it("returns the single transcript when there is only one", () => {
    const only = makeTranscript({ id: "solo" });
    expect(getLatestTranscript([only])).toBe(only);
  });

  it("returns the transcript with the most recent created_at", () => {
    const older = makeTranscript({ id: "old", created_at: "2021-01-01T00:00:00Z" });
    const newest = makeTranscript({ id: "new", created_at: "2023-05-05T00:00:00Z" });
    const middle = makeTranscript({ id: "mid", created_at: "2022-02-02T00:00:00Z" });
    expect(getLatestTranscript([older, newest, middle])).toBe(newest);
  });

  it("does not mutate the input array order", () => {
    const a = makeTranscript({ id: "a", created_at: "2021-01-01T00:00:00Z" });
    const b = makeTranscript({ id: "b", created_at: "2023-01-01T00:00:00Z" });
    const input = [a, b];
    getLatestTranscript(input);
    expect(input).toEqual([a, b]);
  });
});

describe("createConversationAnalysis", () => {
  it("passes through duration and ratios and uses the transcript's own satisfaction", () => {
    const transcript = makeTranscript({
      duration: 123,
      created_at: "2023-03-03T00:00:00Z",
      agent_ratio: 0.4,
      customer_ratio: 0.6,
      analysis: { customer_satisfaction: 7 } as BackendTranscript["analysis"],
    });
    const operator = makeOperator({
      operator_statistics: { avg_customer_satisfaction: 90 },
    });

    expect(createConversationAnalysis(transcript, operator)).toEqual({
      duration: 123,
      created_at: "2023-03-03T00:00:00Z",
      agent_ratio: 0.4,
      customer_ratio: 0.6,
      analysis: { customer_satisfaction: 7 },
    });
  });

  it("falls back to the operator average (divided by 10) when the transcript has no satisfaction", () => {
    const transcript = makeTranscript({});
    const operator = makeOperator({
      operator_statistics: { avg_customer_satisfaction: 90 },
    });
    expect(
      createConversationAnalysis(transcript, operator).analysis
        .customer_satisfaction,
    ).toBe(9);
  });

  it("uses the 8.6 default when neither transcript satisfaction nor operator statistics exist", () => {
    const transcript = makeTranscript({});
    const operator = makeOperator({});
    expect(
      createConversationAnalysis(transcript, operator).analysis
        .customer_satisfaction,
    ).toBe(8.6);
  });

  it("treats an operator average of 0 as a real value (0), not the 8.6 default", () => {
    const transcript = makeTranscript({});
    const operator = makeOperator({
      operator_statistics: { avg_customer_satisfaction: 0 },
    });
    expect(
      createConversationAnalysis(transcript, operator).analysis
        .customer_satisfaction,
    ).toBe(0);
  });

  it("preserves a transcript satisfaction of 0 rather than falling back", () => {
    const transcript = makeTranscript({
      analysis: { customer_satisfaction: 0 } as BackendTranscript["analysis"],
    });
    const operator = makeOperator({
      operator_statistics: { avg_customer_satisfaction: 90 },
    });
    expect(
      createConversationAnalysis(transcript, operator).analysis
        .customer_satisfaction,
    ).toBe(0);
  });
});
