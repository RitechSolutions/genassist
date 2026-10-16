export const TOPIC_SEPARATOR = ">";

export const DEFAULT_ANALYST_TOPICS = [
  "Product Inquiry",
  "Technical Support",
  "Billing Questions",
  "Other",
];

export interface TopicRow {
  name: string;
  subtopics: string[];
}

const keyOf = (value: string) => value.trim().toLowerCase();

const isReserved = (value: string) => keyOf(value) === "all";

export function parseTopicRows(value: unknown): TopicRow[] {
  if (!Array.isArray(value)) return [];
  const rows: TopicRow[] = [];
  for (const entry of value) {
    if (typeof entry !== "string") continue;
    const at = entry.indexOf(TOPIC_SEPARATOR);
    const name = (at === -1 ? entry : entry.slice(0, at)).trim();
    const subtopic = at === -1 ? "" : entry.slice(at + 1).trim();
    if (!name) continue;
    let row = rows.find((existing) => keyOf(existing.name) === keyOf(name));
    if (!row) {
      row = { name, subtopics: [] };
      rows.push(row);
    }
    if (subtopic && !row.subtopics.some((s) => keyOf(s) === keyOf(subtopic))) {
      row.subtopics.push(subtopic);
    }
  }
  return rows;
}

export function serializeTopicRows(rows: TopicRow[]): string[] {
  return rows.flatMap((row) => {
    const name = row.name.trim();
    if (!name) return [];
    return [
      name,
      ...row.subtopics.map(
        (subtopic) => `${name} ${TOPIC_SEPARATOR} ${subtopic}`,
      ),
    ];
  });
}

export function topicNameError(
  name: string,
  rows: TopicRow[],
  excludeIndex?: number,
): string | null {
  if (!name.trim()) return "Name is required";
  if (name.includes(TOPIC_SEPARATOR))
    return `Names cannot contain ${TOPIC_SEPARATOR}`;
  if (isReserved(name)) return '"all" is reserved';
  const clash = rows.some(
    (row, i) => i !== excludeIndex && keyOf(row.name) === keyOf(name),
  );
  return clash ? "This topic already exists" : null;
}

export function applySubtopicEdit(
  previous: string[],
  next: string[],
): string[] {
  const kept = next.filter((subtopic) => previous.includes(subtopic));
  const result = [...kept];
  for (const raw of next) {
    if (previous.includes(raw)) continue;
    const subtopic = raw.trim();
    if (!subtopic || subtopic.includes(TOPIC_SEPARATOR) || isReserved(subtopic))
      continue;
    if (result.some((existing) => keyOf(existing) === keyOf(subtopic)))
      continue;
    result.push(subtopic);
  }
  return result;
}
