import { describe, expect, it } from "vitest";
import type { QuestionRunStatus } from "@/interfaces/testSuite.interface";
import {
  IDLE_RUN,
  NO_ARTICLES_NOTE,
  canStartRun,
  describeEstimate,
  describeOutcome,
  describeProgress,
  afterFailedCheck,
  afterStatusAnswer,
  estimateNote,
  followedRunAfter,
  isRunInProgress,
  knowledgeBaseNameOf,
  listPlaceholder,
  nextStatusCheckMs,
  progressPercent,
  sampleSizeOf,
  showsRunView,
  startFallbackText,
  statusProblemNote,
  usableEstimate,
} from "@/views/TestSuites/helpers/questionRun";

const run = (fields: Partial<QuestionRunStatus>): QuestionRunStatus => ({ ...IDLE_RUN, ...fields });

describe("isRunInProgress", () => {
  it("is true while the run is queued or running", () => {
    expect(isRunInProgress(run({ status: "queued" }))).toBe(true);
    expect(isRunInProgress(run({ status: "running" }))).toBe(true);
  });

  it("is false when there is no run or it has ended", () => {
    expect(isRunInProgress(undefined)).toBe(false);
    expect(isRunInProgress(IDLE_RUN)).toBe(false);
    expect(isRunInProgress(run({ status: "succeeded" }))).toBe(false);
    expect(isRunInProgress(run({ status: "stopped" }))).toBe(false);
    expect(isRunInProgress(run({ status: "failed" }))).toBe(false);
  });
});

describe("knowledgeBaseNameOf", () => {
  const listed = [{ id: "kb1", name: "Help centre" }, { id: "kb2", name: "Billing" }];

  it("names the knowledge base the run writes from", () => {
    expect(knowledgeBaseNameOf(run({ status: "running", knowledge_base_id: "kb2" }), listed)).toBe("Billing");
  });

  it("is null when the knowledge base is not listed or the run names none", () => {
    expect(knowledgeBaseNameOf(run({ status: "running", knowledge_base_id: "gone" }), listed)).toBeNull();
    expect(knowledgeBaseNameOf(IDLE_RUN, listed)).toBeNull();
  });
});

describe("sampleSizeOf", () => {
  it("reads an empty field as all articles", () => {
    expect(sampleSizeOf("")).toBeNull();
    expect(sampleSizeOf("   ")).toBeNull();
  });

  it("reads a whole number above zero", () => {
    expect(sampleSizeOf(" 20 ")).toBe(20);
  });

  it("rejects zero, fractions, signs and words", () => {
    expect(sampleSizeOf("0")).toBeUndefined();
    expect(sampleSizeOf("2.5")).toBeUndefined();
    expect(sampleSizeOf("-3")).toBeUndefined();
    expect(sampleSizeOf("ten")).toBeUndefined();
  });
});

describe("describeEstimate", () => {
  it("names the articles and both kinds of model call", () => {
    const estimate = { articles: 1200, writing_calls: 1200, judging_calls_at_most: 12000 };
    expect(describeEstimate(estimate)).toBe(
      "1,200 articles. Up to 1,200 writing calls and 12,000 checking calls to the model.",
    );
  });

  it("uses the singular for one", () => {
    const estimate = { articles: 1, writing_calls: 1, judging_calls_at_most: 1 };
    expect(describeEstimate(estimate)).toBe("1 article. Up to 1 writing call and 1 checking call to the model.");
  });

  it("says when the knowledge base has nothing to read", () => {
    const estimate = { articles: 0, writing_calls: 0, judging_calls_at_most: 0 };
    expect(describeEstimate(estimate)).toBe(NO_ARTICLES_NOTE);
  });
});

describe("estimateNote", () => {
  const estimate = { articles: 3, writing_calls: 3, judging_calls_at_most: 30 };

  it("shows nothing before a knowledge base is picked", () => {
    expect(estimateNote("", false, false, undefined)).toBeNull();
  });

  it("says the articles are being counted until the estimate arrives", () => {
    expect(estimateNote("kb", true, false, undefined)).toEqual({ text: "Counting the articles...", isProblem: false });
    expect(estimateNote("kb", false, false, undefined)?.text).toBe("Counting the articles...");
  });

  it("says when the count failed", () => {
    expect(estimateNote("kb", false, true, undefined)).toEqual({
      text: "The articles could not be counted.",
      isProblem: true,
    });
  });

  it("gives the estimate once it is known", () => {
    expect(estimateNote("kb", false, false, estimate)).toEqual({
      text: "3 articles. Up to 3 writing calls and 30 checking calls to the model.",
      isProblem: false,
    });
  });

  it("marks a knowledge base with nothing to read as a problem", () => {
    expect(estimateNote("kb", false, false, { ...estimate, articles: 0 })).toEqual({
      text: NO_ARTICLES_NOTE,
      isProblem: true,
    });
  });
});

describe("canStartRun", () => {
  const estimate = { articles: 3, writing_calls: 3, judging_calls_at_most: 30 };

  it("allows a start with both picks, a valid number and articles to read", () => {
    expect(canStartRun("kb", "model", null, estimate)).toBe(true);
    expect(canStartRun("kb", "model", 2, estimate)).toBe(true);
  });

  it("blocks a start without a knowledge base or a model", () => {
    expect(canStartRun("", "model", null, estimate)).toBe(false);
    expect(canStartRun("kb", "", null, estimate)).toBe(false);
  });

  it("blocks a start while the number of articles is not valid", () => {
    expect(canStartRun("kb", "model", undefined, estimate)).toBe(false);
  });

  it("blocks a start before the estimate arrives or when it finds no articles", () => {
    expect(canStartRun("kb", "model", null, undefined)).toBe(false);
    expect(canStartRun("kb", "model", null, { ...estimate, articles: 0 })).toBe(false);
  });
});

describe("progressPercent", () => {
  it("counts failed articles as finished", () => {
    expect(progressPercent(run({ articles_total: 90, articles_done: 40, articles_failed: 5 }))).toBe(50);
  });

  it("is zero before the articles are counted", () => {
    expect(progressPercent(run({ status: "queued" }))).toBe(0);
  });

  it("never passes 100", () => {
    expect(progressPercent(run({ articles_total: 2, articles_done: 2, articles_failed: 1 }))).toBe(100);
  });
});

describe("describeProgress", () => {
  it("says a queued run is waiting", () => {
    expect(describeProgress(run({ status: "queued" }))).toBe("Waiting for its turn to start.");
  });

  it("says the knowledge base is being read before the articles are counted", () => {
    expect(describeProgress(run({ status: "running" }))).toBe("Reading the knowledge base.");
  });

  it("gives the articles done and the questions so far", () => {
    const running = run({
      status: "running",
      articles_total: 90,
      articles_done: 11,
      articles_failed: 1,
      messages_added: 18,
      messages_dropped: 6,
    });
    expect(describeProgress(running)).toBe("12 of 90 articles done. 18 questions added, 6 left out.");
  });
});

describe("describeOutcome", () => {
  it("is null while no run has ended", () => {
    expect(describeOutcome(IDLE_RUN)).toBeNull();
    expect(describeOutcome(run({ status: "running" }))).toBeNull();
  });

  it("gives the counts of a run that succeeded", () => {
    const done = run({ status: "succeeded", messages_added: 142, messages_dropped: 38 });
    expect(describeOutcome(done)).toEqual({ text: "Done. 142 questions added, 38 left out.", isProblem: false });
  });

  it("adds the articles that failed", () => {
    const done = run({ status: "succeeded", messages_added: 1, messages_dropped: 0, articles_failed: 2 });
    expect(describeOutcome(done)?.text).toBe("Done. 1 question added, 0 left out. 2 articles failed.");
  });

  it("gives the reason of a stopped run with what it kept", () => {
    const stopped = run({
      status: "stopped",
      error: "Stopped at the time limit; the questions written so far were added.",
      messages_added: 30,
      messages_dropped: 4,
    });
    expect(describeOutcome(stopped)).toEqual({
      text: "Stopped at the time limit; the questions written so far were added. 30 questions added, 4 left out.",
      isProblem: true,
    });
  });

  it("gives only the reason of a failed run that added nothing", () => {
    const failed = run({ status: "failed", error: "This knowledge base has no stored articles to read." });
    expect(describeOutcome(failed)).toEqual({
      text: "This knowledge base has no stored articles to read.",
      isProblem: true,
    });
  });

  it("falls back to a general reason when the run gave none", () => {
    expect(describeOutcome(run({ status: "failed" }))?.text).toBe("The run did not finish.");
  });
});

describe("listPlaceholder", () => {
  const texts = ["Choose a model", "No active models yet"] as const;

  it("says the list is loading", () => {
    expect(listPlaceholder({ isLoading: true, hasFailed: false, count: 0 }, ...texts)).toBe("Loading...");
  });

  it("asks for a choice when there is something to pick", () => {
    expect(listPlaceholder({ isLoading: false, hasFailed: false, count: 2 }, ...texts)).toBe("Choose a model");
  });

  it("says the list is empty only when it loaded", () => {
    expect(listPlaceholder({ isLoading: false, hasFailed: false, count: 0 }, ...texts)).toBe("No active models yet");
  });

  it("says a failed load is a failure, not an empty list", () => {
    expect(listPlaceholder({ isLoading: false, hasFailed: true, count: 0 }, ...texts)).toBe("Could not be loaded");
  });

  it("keeps the earlier entries pickable when a later load fails", () => {
    expect(listPlaceholder({ isLoading: false, hasFailed: true, count: 2 }, ...texts)).toBe("Choose a model");
  });
});

describe("usableEstimate", () => {
  const estimate = { articles: 3, writing_calls: 3, judging_calls_at_most: 30 };

  it("is the answer of the last count", () => {
    expect(usableEstimate(false, false, estimate)).toEqual(estimate);
  });

  it("is nothing while a count is under way or after one failed, even with an older answer", () => {
    expect(usableEstimate(true, false, estimate)).toBeNull();
    expect(usableEstimate(false, true, estimate)).toBeNull();
  });

  it("is nothing before any count", () => {
    expect(usableEstimate(false, false, undefined)).toBeNull();
  });

  it("keeps Start off after a failed count", () => {
    expect(canStartRun("kb", "model", null, usableEstimate(false, true, estimate))).toBe(false);
  });
});

describe("showsRunView", () => {
  it("shows a run in progress whether or not the dialog started it", () => {
    expect(showsRunView(run({ status: "running" }), false)).toBe(true);
    expect(showsRunView(run({ status: "queued" }), true)).toBe(true);
  });

  it("keeps the outcome of a run the dialog followed", () => {
    expect(showsRunView(run({ status: "succeeded" }), true)).toBe(true);
    expect(showsRunView(run({ status: "failed" }), true)).toBe(true);
  });

  it("shows the form for an earlier run's outcome and when there is no run", () => {
    expect(showsRunView(run({ status: "succeeded" }), false)).toBe(false);
    expect(showsRunView(IDLE_RUN, false)).toBe(false);
    expect(showsRunView(IDLE_RUN, true)).toBe(false);
  });
});

describe("nextStatusCheckMs", () => {
  const running = run({ status: "running", run_id: "r1" });

  it("asks again every 5 seconds while a run is in progress", () => {
    expect(nextStatusCheckMs(afterStatusAnswer(running))).toBe(5000);
    expect(nextStatusCheckMs(afterStatusAnswer(run({ status: "queued" })))).toBe(5000);
  });

  it("stops when the last answer shows no run in progress", () => {
    expect(nextStatusCheckMs(undefined)).toBe(false);
    expect(nextStatusCheckMs(afterStatusAnswer(IDLE_RUN))).toBe(false);
    expect(nextStatusCheckMs(afterStatusAnswer(run({ status: "succeeded" })))).toBe(false);
  });

  it("slows down after a check that failed while a run was in progress", () => {
    expect(nextStatusCheckMs(afterFailedCheck(afterStatusAnswer(running)))).toBe(30000);
  });

  it("asks again when the very first check failed, since a run may be in progress", () => {
    expect(nextStatusCheckMs(afterFailedCheck(undefined))).toBe(30000);
  });

  it("does not keep asking after a failed check when the last answer showed no run", () => {
    expect(nextStatusCheckMs(afterFailedCheck(afterStatusAnswer(IDLE_RUN)))).toBe(false);
  });

  it("gives up after ten failed checks in a row", () => {
    let followed = afterStatusAnswer(running);
    for (let check = 0; check < 9; check += 1) followed = afterFailedCheck(followed);
    expect(nextStatusCheckMs(followed)).toBe(30000);
    expect(nextStatusCheckMs(afterFailedCheck(followed))).toBe(false);
  });

  it("starts counting again after a check that answered", () => {
    const failing = afterFailedCheck(afterFailedCheck(afterStatusAnswer(running)));
    expect(nextStatusCheckMs(failing)).toBe(30000);
    const recovered = afterStatusAnswer(running);
    expect(recovered.failedChecks).toBe(0);
    expect(nextStatusCheckMs(recovered)).toBe(5000);
    expect(nextStatusCheckMs(afterFailedCheck(recovered))).toBe(30000);
  });
});

describe("afterFailedCheck", () => {
  it("keeps the last answer and counts the failure", () => {
    const running = run({ status: "running", run_id: "r1" });
    expect(afterFailedCheck(afterStatusAnswer(running))).toEqual({ run: running, failedChecks: 1 });
    expect(afterFailedCheck(afterFailedCheck(afterStatusAnswer(running))).failedChecks).toBe(2);
  });

  it("counts a failure before any answer", () => {
    expect(afterFailedCheck(undefined)).toEqual({ run: null, failedChecks: 1 });
  });
});

describe("statusProblemNote", () => {
  const running = run({ status: "running", run_id: "r1" });

  it("says nothing while the status can be read", () => {
    expect(statusProblemNote(afterStatusAnswer(running))).toBeNull();
  });

  it("says nothing about a failed check when no run is known to be in progress", () => {
    expect(statusProblemNote(afterFailedCheck(undefined))).toBeNull();
    expect(statusProblemNote(afterFailedCheck(afterStatusAnswer(IDLE_RUN)))).toBeNull();
  });

  it("says the progress could not be read and that it checks again", () => {
    expect(statusProblemNote(afterFailedCheck(afterStatusAnswer(running)))?.text).toBe(
      "The run's progress could not be read. Checking again shortly.",
    );
  });

  it("asks for a reload once it has given up", () => {
    let followed = afterStatusAnswer(running);
    for (let check = 0; check < 10; check += 1) followed = afterFailedCheck(followed);
    expect(statusProblemNote(followed)?.text).toBe(
      "The run's progress could not be read. Reload the page to check again.",
    );
  });

});

describe("followedRunAfter", () => {
  const running = run({ status: "running", run_id: "r1" });
  const ended = run({ status: "succeeded", run_id: "r1" });

  it("follows a run seen in progress", () => {
    expect(followedRunAfter(null, running)).toEqual({ followedId: "r1", hasJustEnded: false });
  });

  it("reports the end of the followed run once", () => {
    expect(followedRunAfter("r1", ended)).toEqual({ followedId: null, hasJustEnded: true });
    expect(followedRunAfter(null, ended)).toEqual({ followedId: null, hasJustEnded: false });
  });

  it("does not take another run's outcome for the end of the followed one", () => {
    const other = run({ status: "succeeded", run_id: "r0" });
    expect(followedRunAfter("r1", other)).toEqual({ followedId: "r1", hasJustEnded: false });
  });

  it("reports no end when nothing was followed", () => {
    expect(followedRunAfter(null, IDLE_RUN)).toEqual({ followedId: null, hasJustEnded: false });
  });
});

describe("startFallbackText", () => {
  it("says the start was refused when the server refused it", () => {
    expect(startFallbackText({ response: { status: 403 } })).toBe(
      "You are not allowed to start a run on this dataset.",
    );
  });

  it("asks to try again for any other failure", () => {
    expect(startFallbackText({ response: { status: 500 } })).toBe("The run could not be started. Try again.");
    expect(startFallbackText(new Error("offline"))).toBe("The run could not be started. Try again.");
  });
});
