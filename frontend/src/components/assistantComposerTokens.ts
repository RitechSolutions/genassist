/**
 * Splits what the person typed in the assistant composer into plain text and
 * the tokens shown as badges: a leading "/command" and every "@Name" that is
 * a known mentionable. Pure, so the highlight layer and tests share it.
 */

export type ComposerToken =
  | { kind: "text"; text: string }
  | { kind: "command"; text: string; name: string }
  | { kind: "mention"; text: string; id: string; name: string };

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function tokenizeComposerText(
  value: string,
  mentionables: ReadonlyArray<{ id: string; name: string }> = [],
  commands: ReadonlyArray<{ name: string }> = []
): ComposerToken[] {
  if (!value) return [];
  const tokens: ComposerToken[] = [];
  let rest = value;

  if (commands.length) {
    const match = /^\/([a-z]+)(?=\s|$)/i.exec(rest);
    const command = match && commands.find((c) => c.name === match[1].toLowerCase());
    if (match && command) {
      tokens.push({ kind: "command", text: match[0], name: command.name });
      rest = rest.slice(match[0].length);
    }
  }

  const named = mentionables.filter((m) => m.name.trim().length > 0);
  if (!named.length) {
    if (rest) tokens.push({ kind: "text", text: rest });
    return tokens;
  }
  // Longer names first, so "@Support Agent" is not read as "@Support".
  const byLength = [...named].sort((a, b) => b.name.length - a.name.length);
  const pattern = new RegExp(`@(${byLength.map((m) => escapeRegExp(m.name)).join("|")})(?![\\w-])`, "gi");
  let last = 0;
  for (const match of rest.matchAll(pattern)) {
    const index = match.index ?? 0;
    const mention = byLength.find((m) => m.name.toLowerCase() === match[1].toLowerCase());
    if (!mention) continue;
    if (index > last) tokens.push({ kind: "text", text: rest.slice(last, index) });
    tokens.push({ kind: "mention", text: match[0], id: mention.id, name: mention.name });
    last = index + match[0].length;
  }
  if (last < rest.length) tokens.push({ kind: "text", text: rest.slice(last) });
  return tokens;
}

/** Ids of the mentionables named in the text, in order of first appearance. */
export function mentionedIds(
  value: string,
  mentionables: ReadonlyArray<{ id: string; name: string }>
): string[] {
  const ids: string[] = [];
  for (const token of tokenizeComposerText(value, mentionables)) {
    if (token.kind === "mention" && !ids.includes(token.id)) ids.push(token.id);
  }
  return ids;
}

/** Whether the text still carries an "@Name" for that mentionable. */
export function hasMention(value: string, name: string): boolean {
  return new RegExp(`@${escapeRegExp(name)}(?![\\w-])`, "i").test(value);
}

/** The text with every "@Name" of that mentionable taken out (and doubled spaces collapsed). */
export function removeMention(value: string, name: string): string {
  const pattern = new RegExp(`@${escapeRegExp(name)}(?![\\w-])\\s?`, "gi");
  return value.replace(pattern, "").replace(/[ \t]{2,}/g, " ").replace(/^ /, "");
}
