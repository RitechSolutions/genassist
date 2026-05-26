/**
 * Normalize disclaimer HTML for storage and plugin rendering.
 *
 * ContentEditable entity-escapes angle brackets when users type or paste markup
 * like `<a href="...">`. Translation textarea values stay unescaped. This decodes
 * escaped tags and parses markup into proper DOM HTML (same shape as translations).
 */
export function normalizeDisclaimerHtml(html: string): string {
  if (!html) return "";

  const decodeEscapedMarkup = (source: string): string => {
    if (!/&lt;\s*\/?\s*[a-z]/i.test(source)) return source;
    const decoder = document.createElement("textarea");
    decoder.innerHTML = source;
    return decoder.value;
  };

  const container = document.createElement("div");
  container.innerHTML = decodeEscapedMarkup(html.trim());

  const serialized = container.innerHTML;
  if (
    serialized === "<br>" ||
    serialized.replace(/<[^>]*>/g, "").trim() === ""
  ) {
    return "";
  }

  return serialized;
}
