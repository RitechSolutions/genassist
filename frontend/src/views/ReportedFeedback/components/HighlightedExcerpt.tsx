import { matchExcerpt, splitMatches } from "../helpers/matchExcerpt";

export function HighlightedExcerpt({
  text,
  search,
}: {
  text: string;
  search: string;
}) {
  return (
    <>
      {splitMatches(matchExcerpt(text, search), search).map((part, i) =>
        part.match ? (
          <mark
            key={i}
            className="rounded-sm bg-primary/15 text-foreground box-decoration-clone dark:bg-primary/30"
          >
            {part.text}
          </mark>
        ) : (
          part.text
        ),
      )}
    </>
  );
}
