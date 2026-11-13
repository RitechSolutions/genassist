import { describe, expect, it } from "vitest";
import { mentionedIds, removeMention, tokenizeComposerText , hasMention } from "@/components/assistantComposerTokens";

const nodes = [
  { id: "a", name: "Support" },
  { id: "b", name: "Support Agent" },
  { id: "c", name: "Message Classifier" },
];
const commands = [{ name: "optimize" }, { name: "explain" }];

describe("tokenizeComposerText", () => {
  it("marks a leading known command and every @mention, longest name first", () => {
    const tokens = tokenizeComposerText("/optimize remove @Message Classifier and keep @Support Agent", nodes, commands);
    expect(tokens).toEqual([
      { kind: "command", text: "/optimize", name: "optimize" },
      { kind: "text", text: " remove " },
      { kind: "mention", text: "@Message Classifier", id: "c", name: "Message Classifier" },
      { kind: "text", text: " and keep " },
      { kind: "mention", text: "@Support Agent", id: "b", name: "Support Agent" },
    ]);
  });

  it("leaves unknown commands, mid-text slashes and partial names as plain text", () => {
    expect(tokenizeComposerText("/nope hi", nodes, commands)).toEqual([{ kind: "text", text: "/nope hi" }]);
    expect(tokenizeComposerText("a /optimize b", nodes, commands)).toEqual([{ kind: "text", text: "a /optimize b" }]);
    expect(tokenizeComposerText("@Supporter", nodes)).toEqual([{ kind: "text", text: "@Supporter" }]);
    expect(tokenizeComposerText("/optimizer", nodes, commands)).toEqual([{ kind: "text", text: "/optimizer" }]);
    expect(tokenizeComposerText("", nodes, commands)).toEqual([]);
  });

  it("reproduces the text exactly, so the highlight layer lines up with the textarea", () => {
    const text = "/explain  @Support\n\n@support agent?";
    const joined = tokenizeComposerText(text, nodes, commands).map((t) => t.text).join("");
    expect(joined).toBe(text);
  });
});

describe("mentionedIds / removeMention", () => {
  it("lists ids once, in order, case-insensitively", () => {
    expect(mentionedIds("@support agent then @Support and @Support Agent", nodes)).toEqual(["b", "a"]);
  });

  it("takes a mention out without leaving double spaces", () => {
    expect(removeMention("fix @Support Agent and @Support please", "Support Agent")).toBe("fix and @Support please");
    expect(removeMention("@Support Agent fix it", "Support Agent")).toBe("fix it");
  });
});


describe("hasMention", () => {
  it("finds the exact @Name, case-insensitively, and not a longer name it starts", () => {
    expect(hasMention("Explain @Expense Policy please", "Expense Policy")).toBe(true);
    expect(hasMention("explain @expense policy", "Expense Policy")).toBe(true);
    expect(hasMention("Explain @Expense Policy-v2", "Expense Policy")).toBe(false);
    expect(hasMention("Explain @Expense", "Expense Policy")).toBe(false);
    expect(hasMention("", "Expense Policy")).toBe(false);
  });
});
