import { describe, expect, it } from "vitest";
import {
  backFromConversation,
  isComparing,
  locationFromParams,
  paramsFromLocation,
} from "@/views/TestSuites/helpers/resultsLocation";
import { runResultsVersion } from "@/views/TestSuites/hooks/useRunConversations";

describe("where a reader is in a run's results", () => {
  it("round-trips through the URL", () => {
    const view = { runId: "r1", conversation: "c1", compareWith: "r0" };
    expect(paramsFromLocation(view).toString()).toBe("run=r1&conversation=c1&compare=r0");
    expect(locationFromParams(paramsFromLocation(view))).toEqual(view);
    expect(locationFromParams(new URLSearchParams("conversation=c1"))).toBeNull();
    expect(paramsFromLocation(null).toString()).toBe("");
  });

  it("keeps a comparison that waits for its second run", () => {
    const waiting = { runId: "r1", compareWith: "" };
    expect(paramsFromLocation(waiting).toString()).toBe("run=r1&compare=");
    expect(locationFromParams(paramsFromLocation(waiting))).toEqual(waiting);
    expect(isComparing(waiting)).toBe(true);
    expect(isComparing({ runId: "r1" })).toBe(false);
  });

  it("goes back from a conversation to where it was opened", () => {
    expect(backFromConversation({ runId: "r1", conversation: "c1", compareWith: "r0" })).toEqual({
      runId: "r1",
      compareWith: "r0",
    });
    expect(backFromConversation({ runId: "r1", conversation: "c1" })).toEqual({ runId: "r1" });
  });

  it("reloads results when a conversation finishes or the run ends, not on every turn", () => {
    const run = (status: string, conversations_done: number, turns_done: number) => ({
      suite_id: "s",
      workflow_id: "w",
      status,
      techniques: [],
      progress: { conversations_done, conversations_total: 4, turns_done, turns_total: 9 },
    });
    expect(runResultsVersion(run("running", 1, 3))).toBe(runResultsVersion(run("running", 1, 4)));
    expect(runResultsVersion(run("running", 1, 4))).not.toBe(runResultsVersion(run("running", 2, 5)));
    expect(runResultsVersion(run("running", 4, 9))).not.toBe(runResultsVersion(run("completed", 4, 9)));
  });
});
