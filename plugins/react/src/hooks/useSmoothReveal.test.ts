import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DRAIN_MS,
  MAX_REVEAL_CHARS_PER_SECOND,
  REVEAL_CHARS_PER_SECOND,
  Reveal,
  advance,
  retarget,
  useSmoothReveal,
  visibleText,
} from "./useSmoothReveal";

const IDLE: Reveal = { text: "", live: false, pos: 0, drainCps: null };
const words = (count: number) => Array.from({ length: count }, (_, i) => `word${i % 10}`).join(" ");

function run(reveal: Reveal, ms: number): Reveal {
  for (let t = 0; t < ms; t += 16) reveal = advance(reveal, Math.min(16, ms - t));
  return reveal;
}

describe("smooth reveal", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reveals live text at the base pace and only in whole words", () => {
    const text = words(30);
    const reveal = run(retarget(IDLE, text, true), 250);

    expect(reveal.pos).toBeCloseTo(REVEAL_CHARS_PER_SECOND / 4, 0);
    const shown = visibleText(reveal);
    expect(shown.length).toBeGreaterThan(reveal.pos - 6);
    expect(text.charAt(shown.length)).toBe(" ");
  });

  it("speeds up when it falls behind, but never past the cap on long replies", () => {
    const behind = run(retarget(IDLE, words(120), true), 100);
    expect(behind.pos).toBeGreaterThan(REVEAL_CHARS_PER_SECOND / 10 + 5);

    const farBehind = run(retarget(IDLE, words(600), true), 1000);
    expect(farBehind.pos).toBeCloseTo(MAX_REVEAL_CHARS_PER_SECOND, 0);
  });

  it("keeps its place when live text grows", () => {
    let reveal = run(retarget(IDLE, words(10), true), 100);
    const before = reveal.pos;
    reveal = retarget(reveal, words(40), true);

    expect(reveal.pos).toBe(before);
  });

  it("hands over to the saved reply without a jump and finishes within DRAIN_MS", () => {
    const text = words(600);
    const live = run(retarget(IDLE, text, true), 200);
    const saved = retarget(live, text, false);

    expect(visibleText(saved)).toBe(visibleText(live));
    expect(visibleText(run(saved, DRAIN_MS + 16))).toBe(text);
  });

  it("shows the last word as soon as a caught-up turn is done", () => {
    const live = run(retarget(IDLE, "It is sunny.", true), 1000);
    expect(visibleText(live)).toBe("It is");

    expect(visibleText(retarget(live, "It is sunny.", false))).toBe("It is sunny.");
  });

  it("restarts when a tool starts and the next model call streams new text", () => {
    let reveal = run(retarget(IDLE, "Let me check the weather for you", true), 100);
    reveal = retarget(reveal, "", true);
    expect(reveal.pos).toBe(0);

    reveal = retarget(reveal, "It is sunny in Tirana today", true);
    expect(visibleText(reveal)).toBe("");
  });

  it("shows replies at once when nothing was streamed", () => {
    const history = retarget(IDLE, "Welcome back!", false);
    expect(visibleText(history)).toBe("Welcome back!");

    const toolOnly = retarget(retarget(history, "", true), "Your order has shipped.", false);
    expect(visibleText(toolOnly)).toBe("Your order has shipped.");
  });

  it("does not stall on text without spaces", () => {
    const text = "灯塔是一座高塔，塔顶装有强光灯，为夜间航行的船只指引方向。".repeat(4);
    const reveal = run(retarget(IDLE, text, true), 200);

    expect(visibleText(reveal).length).toBeGreaterThan(40);
  });

  it("reveals at once when the visitor prefers reduced motion", () => {
    const render = () => renderToString(createElement(() => useSmoothReveal("Hello world", true)));
    expect(render()).toBe("");

    vi.stubGlobal("window", { matchMedia: () => ({ matches: true }) });
    expect(render()).toBe("Hello world");
  });
});
