import { describe, expect, it } from "vitest";
import { extractReferencedArticles } from "@/helpers/referencedArticles";

const KB = "6f1c2d3e-0000-4000-8000-00000000abcd";

const log = (nodeExecutionStatus: Record<string, unknown>) => ({
  row_agent_response: { state: { nodeExecutionStatus } },
});

const legacyText = [
  "Found 2 results:\n",
  `--- Result 1 (Score: 0.812, Source: vector) ---\nID: KB:${KB}#article_101\nContent: How to get a refund\n\nOpen the app and tap Parking history.\n`,
  `--- Result 2 (Score: 0.400, Source: vector) ---\nID: KB:${KB}#s3_faq.pdf\nContent: Frequently asked questions\nMore text\n`,
].join("\n");

describe("extractReferencedArticles", () => {
  it("reads recorded sources, best score first", () => {
    const result = extractReferencedArticles(
      log({
        kb: {
          type: "knowledgeBaseNode",
          name: "Help Center",
          output: "ignored when sources exist",
          sources: [
            { id: `KB:${KB}#article_7`, title: null, url: null, score: 0.3, source: "legra", kb_id: KB },
            {
              id: `KB:${KB}#article_9`,
              title: "Refunds",
              url: "https://help.example.com/articles/9",
              score: 0.9,
              source: "vector",
              kb_id: KB,
            },
          ],
        },
        llm: { type: "agentNode", output: "Hi" },
      }),
    );

    expect(result.kbCalls).toBe(1);
    expect(result.failedCalls).toBe(0);
    expect(result.articles).toEqual([
      {
        id: `KB:${KB}#article_9`,
        title: "Refunds",
        score: 0.9,
        kbId: KB,
        source: "vector",
        nodeName: "Help Center",
        legacy: false,
      },
      expect.objectContaining({ id: `KB:${KB}#article_7`, title: null, legacy: false }),
    ]);
  });

  it("parses the result text of old logs into ids, without guessing titles", () => {
    const { articles, kbCalls } = extractReferencedArticles(
      log({ kb: { type: "knowledgeBaseNode", output: legacyText } }),
    );

    expect(kbCalls).toBe(1);
    expect(articles).toEqual([
      expect.objectContaining({
        id: `KB:${KB}#article_101`,
        title: null,
        score: 0.812,
        kbId: KB,
        source: "vector",
        legacy: true,
      }),
      expect.objectContaining({ id: `KB:${KB}#s3_faq.pdf`, title: null, score: 0.4, legacy: true }),
    ]);
  });

  it("counts archived re-runs as separate lookups and keeps an id's best score", () => {
    const { articles, kbCalls } = extractReferencedArticles(
      log({
        kb_0: { type: "knowledgeBaseNode", sources: [{ id: "doc-1", score: 0.7 }] },
        kb: { type: "knowledgeBaseNode", sources: [{ id: "doc-1", score: 0.2 }, { id: "doc-2", score: 0.5 }] },
      }),
    );

    expect(kbCalls).toBe(2);
    expect(articles.map((a) => [a.id, a.score])).toEqual([
      ["doc-1", 0.7],
      ["doc-2", 0.5],
    ]);
  });

  it("finds the map in a builder test response (state at the top level)", () => {
    const { kbCalls, articles } = extractReferencedArticles({
      state: { nodeExecutionStatus: { kb: { type: "knowledgeBaseNode", sources: [{ id: "doc-1" }] } } },
    });
    expect(kbCalls).toBe(1);
    expect(articles[0]).toMatchObject({ id: "doc-1", score: null, kbId: null });
  });

  it("reports a lookup without hits apart from no lookup at all", () => {
    expect(
      extractReferencedArticles(log({ kb: { type: "knowledgeBaseNode", output: "No results found." } })),
    ).toEqual({ articles: [], kbCalls: 1, failedCalls: 0 });
    expect(extractReferencedArticles(log({ llm: { type: "agentNode", output: "Hi" } }))).toEqual({
      articles: [],
      kbCalls: 0,
      failedCalls: 0,
    });
  });

  it("counts failed lookups apart from lookups without hits", () => {
    const result = extractReferencedArticles(
      log({
        kb_0: { type: "knowledgeBaseNode", status: "failed", output: null, error: "Vector DB down" },
        kb: { type: "knowledgeBaseNode", output: "Error querying knowledge base: timeout" },
      }),
    );
    expect(result).toEqual({ articles: [], kbCalls: 2, failedCalls: 2 });
  });

  it("returns nothing for input that is not a log object", () => {
    for (const input of [null, "text", 42, [], { state: "x" }]) {
      expect(extractReferencedArticles(input)).toEqual({ articles: [], kbCalls: 0, failedCalls: 0 });
    }
  });
});
