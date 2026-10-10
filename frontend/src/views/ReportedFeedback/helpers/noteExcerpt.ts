const EXCERPT_LEAD = 30;

/** Starts the note shortly before the match, so the matched word survives the cell's two-line clamp */
export function noteExcerpt(note: string, search: string): string {
  const at = note.toLowerCase().indexOf(search.toLowerCase());
  return at > EXCERPT_LEAD ? `…${note.slice(at - EXCERPT_LEAD)}` : note;
}
