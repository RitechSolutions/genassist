import { describe, expect, it } from "vitest";

import { ReadReceiptState } from "../types";
import { mergeReadState } from "./useChat";

const AT_EARLY = "2026-08-13T10:00:00Z";
const AT_LATE = "2026-08-13T10:05:00Z";
const SUP_A = "11111111-1111-1111-1111-111111111111";
const SUP_B = "22222222-2222-2222-2222-222222222222";

describe("mergeReadState", () => {
  it("returns prev when next is null/undefined", () => {
    const prev: ReadReceiptState = { customer_last_read_sequence: 3 };
    expect(mergeReadState(prev, null)).toBe(prev);
    expect(mergeReadState(prev, undefined)).toBe(prev);
  });

  it("returns next when prev is null", () => {
    const next: ReadReceiptState = { supervisor_last_read_sequence: 7 };
    expect(mergeReadState(null, next)).toBe(next);
  });

  it("advances each role's marker forward", () => {
    const prev: ReadReceiptState = {
      customer_last_read_sequence: 2,
      customer_last_read_at: AT_EARLY,
    };
    const next: ReadReceiptState = {
      customer_last_read_sequence: 5,
      customer_last_read_at: AT_LATE,
    };
    const merged = mergeReadState(prev, next);
    expect(merged?.customer_last_read_sequence).toBe(5);
    expect(merged?.customer_last_read_at).toBe(AT_LATE); // timestamp of the winning (higher) seq
  });

  it("never regresses on an out-of-order (older) update", () => {
    const prev: ReadReceiptState = {
      supervisor_last_read_sequence: 9,
      supervisor_last_read_at: AT_LATE,
      supervisor_user_id: SUP_B,
    };
    // A stale event arrives late carrying an earlier position.
    const stale: ReadReceiptState = {
      supervisor_last_read_sequence: 4,
      supervisor_last_read_at: AT_EARLY,
      supervisor_user_id: SUP_A,
    };
    const merged = mergeReadState(prev, stale);
    expect(merged?.supervisor_last_read_sequence).toBe(9); // kept, not moved back
    expect(merged?.supervisor_last_read_at).toBe(AT_LATE); // timestamp of the higher seq
    expect(merged?.supervisor_user_id).toBe(SUP_B); // identity of the higher seq
  });

  it("takes the supervisor identity/timestamp of the higher sequence when advancing", () => {
    const prev: ReadReceiptState = {
      supervisor_last_read_sequence: 1,
      supervisor_last_read_at: AT_EARLY,
      supervisor_user_id: SUP_A,
    };
    const next: ReadReceiptState = {
      supervisor_last_read_sequence: 6,
      supervisor_last_read_at: AT_LATE,
      supervisor_user_id: SUP_B,
    };
    const merged = mergeReadState(prev, next);
    expect(merged?.supervisor_last_read_sequence).toBe(6);
    expect(merged?.supervisor_user_id).toBe(SUP_B);
    expect(merged?.supervisor_last_read_at).toBe(AT_LATE);
  });

  it("merges roles independently (one advances while the other regresses)", () => {
    const prev: ReadReceiptState = {
      customer_last_read_sequence: 5,
      supervisor_last_read_sequence: 2,
    };
    const next: ReadReceiptState = {
      customer_last_read_sequence: 3, // older — must not regress
      supervisor_last_read_sequence: 7, // newer — advances
    };
    const merged = mergeReadState(prev, next);
    expect(merged?.customer_last_read_sequence).toBe(5);
    expect(merged?.supervisor_last_read_sequence).toBe(7);
  });

  it("treats a null/absent sequence as no marker (adopts the other side's)", () => {
    const prev: ReadReceiptState = { customer_last_read_sequence: null };
    const next: ReadReceiptState = { customer_last_read_sequence: 4 };
    expect(mergeReadState(prev, next)?.customer_last_read_sequence).toBe(4);
    expect(mergeReadState(next, prev)?.customer_last_read_sequence).toBe(4);
  });
});
