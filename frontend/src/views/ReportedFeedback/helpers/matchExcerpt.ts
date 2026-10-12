import { escapeRegExp } from "lodash";

const EXCERPT_LEAD = 30;

/** Starts the text shortly before the match, so the matched word survives the cell's truncation */
export function matchExcerpt(text: string, search: string): string {
  const at = text.search(new RegExp(escapeRegExp(search), "i"));
  return at > EXCERPT_LEAD ? `…${text.slice(at - EXCERPT_LEAD)}` : text;
}

/** Splits the text around every match of the search, so the matches sit at the odd indexes */
export function splitMatches(text: string, search: string): string[] {
  return search ? text.split(new RegExp(`(${escapeRegExp(search)})`, "gi")) : [text];
}
