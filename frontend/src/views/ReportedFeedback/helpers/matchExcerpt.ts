import { escapeRegExp } from "lodash";

const EXCERPT_LEAD = 30;

/** Starts the text shortly before the match, so the matched word survives the cell's truncation */
export function matchExcerpt(text: string, search: string): string {
  const at = text.search(new RegExp(escapeRegExp(search), "i"));
  return at > EXCERPT_LEAD ? `…${text.slice(at - EXCERPT_LEAD)}` : text;
}

/** Splits the text around every match of the search, flagging the matched parts */
export function splitMatches(
  text: string,
  search: string,
): { text: string; match: boolean }[] {
  if (!search) return [{ text, match: false }];
  // The capture group keeps each match in the split, at the odd indexes
  return text
    .split(new RegExp(`(${escapeRegExp(search)})`, "gi"))
    .map((part, i) => ({ text: part, match: i % 2 === 1 }));
}
