import { describe, it, expect } from "vitest";
import type { Node } from "reactflow";
import { getCopyName, withCopyNames } from "@/views/AIAgents/Workflows/utils/nodeNaming";

const node = (id: string, name?: string): Node =>
  ({ id, type: "agentNode", position: { x: 0, y: 0 }, data: name === undefined ? {} : { name } }) as Node;

describe("getCopyName", () => {
  it("appends (1) to the first copy", () => {
    expect(getCopyName("Sub-Agent", ["Sub-Agent"])).toBe("Sub-Agent (1)");
  });

  it("uses the next free counter", () => {
    expect(getCopyName("Sub-Agent", ["Sub-Agent", "Sub-Agent (1)"])).toBe("Sub-Agent (2)");
  });

  it("continues the series when copying a numbered node", () => {
    expect(getCopyName("Sub-Agent (1)", ["Sub-Agent", "Sub-Agent (1)"])).toBe("Sub-Agent (2)");
  });

  it("fills a gap left by a deleted copy", () => {
    expect(getCopyName("Sub-Agent", ["Sub-Agent", "Sub-Agent (2)"])).toBe("Sub-Agent (1)");
  });

  it("keeps a name that is only a counter", () => {
    expect(getCopyName("(1)", ["(1)"])).toBe("(1) (1)");
  });
});

describe("withCopyNames", () => {
  it("numbers copies against the canvas and each other", () => {
    const existing = [node("a", "Sub-Agent"), node("b", "Router")];
    const copies = withCopyNames([node("c", "Sub-Agent"), node("d", "Sub-Agent"), node("e", "Router")], existing);
    expect(copies.map((n) => n.data.name)).toEqual(["Sub-Agent (1)", "Sub-Agent (2)", "Router (1)"]);
  });

  it("leaves unnamed nodes untouched and does not mutate the input", () => {
    const unnamed = node("c");
    const named = node("d", "Sub-Agent");
    const [first, second] = withCopyNames([unnamed, named], [named]);
    expect(first).toBe(unnamed);
    expect(second.data.name).toBe("Sub-Agent (1)");
    expect(named.data.name).toBe("Sub-Agent");
  });
});
