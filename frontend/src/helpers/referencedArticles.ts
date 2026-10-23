/** A knowledge-base hit shown in the agent response log. */
export interface ReferencedArticle {
  id: string;
  title: string | null;
  score: number | null;
  kbId: string | null;
  source: string | null;
  nodeName: string | null;
  legacy: boolean;
}

export interface ReferencedArticles {
  articles: ReferencedArticle[];
  kbCalls: number;
  failedCalls: number;
}

const KB_NODE_TYPE = "knowledgeBaseNode";
const LEGACY_ERROR_PREFIX = "Error querying knowledge base";
const RESULT_HEADER = /^--- Result \d+ \(Score: (\S+), Source: (.*)\) ---$/gm;

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const textOrNull = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value : null;

const kbIdOf = (id: string): string | null => id.match(/^KB:([^#]+)#/)?.[1] ?? null;

function nodeExecutionMap(parsed: unknown): UnknownRecord {
  if (!isRecord(parsed)) return {};
  const candidates = [
    isRecord(parsed.row_agent_response) ? parsed.row_agent_response.state : undefined,
    parsed.state,
    parsed,
  ];
  for (const bag of candidates) {
    if (isRecord(bag) && isRecord(bag.nodeExecutionStatus)) {
      return bag.nodeExecutionStatus;
    }
  }
  return {};
}

function fromSources(sources: unknown[], nodeName: string | null): ReferencedArticle[] {
  return sources.filter(isRecord).flatMap((source) => {
    const id = textOrNull(source.id);
    if (!id) return [];
    return [
      {
        id,
        title: textOrNull(source.title),
        score: typeof source.score === "number" ? source.score : null,
        kbId: textOrNull(source.kb_id) ?? kbIdOf(id),
        source: textOrNull(source.source),
        nodeName,
        legacy: false,
      },
    ];
  });
}

function fromResultText(text: string, nodeName: string | null): ReferencedArticle[] {
  const headers = [...text.matchAll(RESULT_HEADER)];
  return headers.flatMap((header, index) => {
    const start = (header.index ?? 0) + header[0].length;
    const end = headers[index + 1]?.index ?? text.length;
    const block = text.slice(start, end);
    const id = block.match(/^ID: (.*)$/m)?.[1]?.trim();
    if (!id) return [];
    const score = Number.parseFloat(header[1]);
    return [
      {
        id,
        title: null,
        score: Number.isFinite(score) ? score : null,
        kbId: kbIdOf(id),
        source: textOrNull(header[2]),
        nodeName,
        legacy: true,
      },
    ];
  });
}

/**
 * Articles returned by every knowledge-base node run in an agent response log,
 * archived re-runs included, deduped by id (best score kept), best first.
 */
export function extractReferencedArticles(parsed: unknown): ReferencedArticles {
  const best = new Map<string, ReferencedArticle>();
  let kbCalls = 0;
  let failedCalls = 0;

  for (const entry of Object.values(nodeExecutionMap(parsed))) {
    if (!isRecord(entry) || entry.type !== KB_NODE_TYPE) continue;
    kbCalls += 1;
    const failed =
      entry.status === "failed" ||
      (typeof entry.output === "string" && entry.output.startsWith(LEGACY_ERROR_PREFIX));
    if (failed) {
      failedCalls += 1;
      continue;
    }
    const nodeName = textOrNull(entry.name);
    const found = Array.isArray(entry.sources)
      ? fromSources(entry.sources, nodeName)
      : typeof entry.output === "string"
        ? fromResultText(entry.output, nodeName)
        : [];
    for (const article of found) {
      const current = best.get(article.id);
      if (!current || (article.score ?? -Infinity) > (current.score ?? -Infinity)) {
        best.set(article.id, article);
      }
    }
  }

  const articles = [...best.values()].sort(
    (a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity),
  );
  return { articles, kbCalls, failedCalls };
}
