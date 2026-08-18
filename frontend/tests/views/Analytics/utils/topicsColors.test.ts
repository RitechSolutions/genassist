import { describe, expect, it } from "vitest";
import { getTopicColorMap } from "@/views/Analytics/utils/topicsColors";
import { TOPIC_COLORS } from "@/views/Analytics/constants";

describe("getTopicColorMap", () => {
  it("returns an empty map for no topics", () => {
    expect(getTopicColorMap([])).toEqual({});
  });

  it("assigns colors in alphabetical (locale) order", () => {
    const map = getTopicColorMap(["banana", "apple", "cherry"]);
    expect(map).toEqual({
      apple: TOPIC_COLORS[0],
      banana: TOPIC_COLORS[1],
      cherry: TOPIC_COLORS[2],
    });
  });

  it("deduplicates topics without consuming an extra color slot", () => {
    const map = getTopicColorMap(["b", "a", "a"]);
    expect(map).toEqual({
      a: TOPIC_COLORS[0],
      b: TOPIC_COLORS[1],
    });
  });

  it("cycles back through the palette once it is exhausted", () => {
    const topics = Array.from({ length: 11 }, (_, i) =>
      `t${String(i).padStart(2, "0")}`,
    );
    const map = getTopicColorMap(topics);
    // 11th sorted topic wraps to palette index 0.
    expect(TOPIC_COLORS.length).toBe(10);
    expect(map["t10"]).toBe(TOPIC_COLORS[0]);
    expect(map["t10"]).toBe(map["t00"]);
    expect(map["t09"]).toBe(TOPIC_COLORS[9]);
  });

  it("does not mutate the input array", () => {
    const input = ["c", "a", "b"];
    getTopicColorMap(input);
    expect(input).toEqual(["c", "a", "b"]);
  });
});
