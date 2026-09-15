import { describe, expect, it } from "vitest";
import { buildVariableTree } from "@/helpers/variable-input/variableTree";
import {
  bindingChangeNote,
  comparePromptBindings,
  directPredecessorIds,
  fanInNote,
  readPromptBindings,
  scanBraceCandidates,
  unknownBindings,
} from "@/views/AIAgents/Workflows/utils/templateVariableDiagnostics";

const kindsOf = (text: string) =>
  scanBraceCandidates(text).findings.map((finding) => finding.kind);

describe("readPromptBindings", () => {
  it("reads the curly form the engine renders", () => {
    expect(readPromptBindings("Hi {{session.message}} and {{source.x}}")).toEqual([
      "session.message",
      "source.x",
    ]);
  });

  it("ignores params.get, which never resolves on a prompt field", () => {
    expect(readPromptBindings('params.get("topic")')).toEqual([]);
  });

  it("ignores a token with spaces, as the engine does", () => {
    expect(readPromptBindings("{{ session.message }}")).toEqual([]);
  });
});

describe("scanBraceCandidates", () => {
  it("flags spaces inside the braces", () => {
    expect(kindsOf("{{ session.message }}")).toEqual(["spaced"]);
  });

  it("leaves an array path alone", () => {
    expect(kindsOf("{{source.items[0].name}}")).toEqual([]);
  });

  it("flags a token broken across two lines", () => {
    expect(kindsOf("{{session.\nmessage}}")).toEqual(["multiline"]);
  });

  it("flags an opener that is never closed", () => {
    expect(kindsOf("say {{unclosed")).toEqual(["unclosed"]);
    expect(kindsOf("{{")).toEqual(["unclosed"]);
  });

  it("calls a spaced opener unclosed, because it never closed at all", () => {
    expect(kindsOf("{{ unclosed")).toEqual(["unclosed"]);
  });

  it("classifies a long well-formed token by its body, not by a scan window", () => {
    expect(kindsOf(`{{session.${"a".repeat(600)}}}`)).toEqual([]);
    expect(kindsOf(`{{ session.${"a".repeat(600)} }}`)).toEqual(["spaced"]);
  });

  it("reports one malformed token when a second opener interrupts the first", () => {
    expect(kindsOf("{{a {{b}}")).toEqual(["malformed"]);
  });

  it("flags an empty token", () => {
    expect(kindsOf("{{}}")).toEqual(["malformed"]);
  });

  it("leaves a closing pair with nothing open alone", () => {
    expect(kindsOf("a }} b")).toEqual([]);
  });

  it("stops at the cap on a very long broken prompt", () => {
    const scan = scanBraceCandidates("{{".repeat(100000));
    expect(scan.findings.length).toBe(50);
    expect(scan.truncated).toBe(true);
  });

  it("shortens the reported text so a long candidate stays readable", () => {
    const [finding] = scanBraceCandidates(`{{ ${"a".repeat(200)}`).findings;
    expect(finding.text.length).toBe(61);
    expect(finding.text.endsWith("…")).toBe(true);
  });
});

describe("unknownBindings", () => {
  it("says nothing when the node has no available data", () => {
    expect(unknownBindings(["session.message"], buildVariableTree(null))).toEqual([]);
  });

  it("says nothing about a root whose subtree has not been populated", () => {
    const tree = buildVariableTree({ session: { message: "hi" }, source: {} });
    expect(unknownBindings(["source.x"], tree)).toEqual([]);
  });

  it("reports a name the populated subtree does not offer", () => {
    const tree = buildVariableTree({ session: { message: "hi" } });
    expect(unknownBindings(["session.nope", "session.message"], tree)).toEqual([
      "session.nope",
    ]);
  });

  it("accepts any array index, bracketed or dotted, since the tree only samples one", () => {
    const tree = buildVariableTree({ source: { items: [{ name: "a" }] } });
    expect(
      unknownBindings(
        ["source.items[3].name", "source.items.0.name", "source.items.0"],
        tree,
      ),
    ).toEqual([]);
  });

  it("drops an unknown root, which the runtime may still resolve", () => {
    const tree = buildVariableTree({ session: { message: "hi" } });
    expect(unknownBindings(["state.counter"], tree)).toEqual([]);
  });
});

describe("directPredecessorIds", () => {
  it("counts only edges on the execution input handle", () => {
    const edges = [
      { source: "tool", target: "agent", targetHandle: "input_tools" },
      { source: "mcp", target: "agent", targetHandle: "input_tools" },
      { source: "sub", target: "agent", targetHandle: "input_sub_agents" },
      { source: "chat", target: "agent", targetHandle: "input" },
    ];
    expect(directPredecessorIds("agent", edges)).toEqual(["chat"]);
  });

  it("counts every execution input, whatever the source node is", () => {
    const edges = [
      { source: "a", target: "llm", targetHandle: "input" },
      { source: "b", target: "llm", targetHandle: "input" },
      { source: "c", target: "other", targetHandle: "input" },
    ];
    expect(directPredecessorIds("llm", edges)).toEqual(["a", "b"]);
  });

  it("counts no legacy handle, as the engine does not either", () => {
    const edges = [
      { source: "chat", target: "agent", targetHandle: "input_prompt" },
      { source: "tpl", target: "agent", targetHandle: "input_system_prompt" },
      { source: "old", target: "agent" },
    ];
    expect(directPredecessorIds("agent", edges)).toEqual([]);
  });
});

describe("fanInNote", () => {
  it("says nothing with a single predecessor", () => {
    expect(fanInNote(["source.text"], ["a"])).toBeNull();
  });

  it("warns when source is keyed by node id", () => {
    expect(fanInNote(["source.text"], ["a", "b"])).toMatch(/keyed by node id/);
  });

  it("says nothing when the reference already names a predecessor", () => {
    expect(fanInNote(["source.a.text"], ["a", "b"])).toBeNull();
  });
});

describe("comparePromptBindings", () => {
  it("reports a placeholder the suggestion dropped", () => {
    const changes = comparePromptBindings("Hi {{session.message}}", "Hi there");
    expect(changes.removed).toEqual(["session.message"]);
    expect(changes.added).toEqual([]);
    expect(bindingChangeNote(changes)).toBe(
      "The suggestion drops {{session.message}}.",
    );
  });

  it("reports only the broken tokens the suggestion introduced", () => {
    const changes = comparePromptBindings("Hi {{broken", "Hello {{ spaced }} {{broken");
    expect(changes.broken.map((finding) => finding.kind)).toEqual(["spaced"]);
  });

  it("says nothing when every placeholder survives", () => {
    const changes = comparePromptBindings("{{session.message}}", "Answer {{session.message}}");
    expect(bindingChangeNote(changes)).toBeNull();
  });
});
