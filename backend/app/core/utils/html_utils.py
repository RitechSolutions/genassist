import re

# Strips the optional title from an inline link: [text](url "title") -> [text](url)
_LINK_TITLE_RE = re.compile(r'(\]\(\S+?)\s+"[^"]*"(\))')


def _normalize_whitespace(s: str) -> str:
    s = re.sub(r"[ \t]+\n", "\n", s)   # strip trailing spaces before newlines
    s = re.sub(r"\n{3,}", "\n\n", s)   # collapse 3+ blank lines to 2
    s = re.sub(r"[ \t]{2,}", " ", s)   # collapse runs of spaces/tabs (does NOT touch newlines)
    return s.strip()


def _strip_link_titles(md: str) -> str:
    return _LINK_TITLE_RE.sub(r"\1\2", md)


def html2markdown(html: str, base_url: str | None = None) -> str:
    """Convert HTML to Markdown.
    ``base_url`` resolves relative hrefs to absolute URLs.
    """
    import html2text as _html2text

    h = _html2text.HTML2Text(baseurl=base_url or "")
    h.ignore_links = False   # keep links as [text](url)
    h.ignore_images = True
    h.body_width = 0         # no hard wraps
    h.unicode_snob = True    # keep é, ü, —, © etc. instead of ASCII-mangling them
    return _normalize_whitespace(_strip_link_titles(h.handle(html or "")))
