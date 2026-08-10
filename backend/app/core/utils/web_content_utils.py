"""Pure python extraction helpers for scraped HTML: links, metadata, main content."""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment

from app.core.utils.html_utils import html2markdown

_HTTP_SCHEMES = frozenset({"http", "https"})
_SKIP_LINK_PREFIXES = ("#", "javascript:", "mailto:", "tel:")

# Tags that never carry readable content
_NOISE_TAGS = ("script", "style", "noscript", "template", "svg", "head", "link", "meta", "iframe", "img")
# Page chrome dropped for main-content extraction. <header> is kept: article titles live there
_CHROME_TAGS = ("nav", "footer", "aside")
# Empty links html2text leaves where an image used to be, e.g. [](https://site/x).
_EMPTY_LINK_RE = re.compile(r"!?\[[ \t]*\]\([^)\s]*\)")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "lxml")


def _meta(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str | None:
    tag = soup.find("meta", attrs={"name": name} if name else {"property": prop})
    content = tag.get("content") if tag else None
    content = content.strip() if content else ""
    return content or None


def _clean_soup(html: str, *, drop_chrome: bool) -> BeautifulSoup:
    soup = _soup(html)
    tags = list(_NOISE_TAGS)
    if drop_chrome:
        tags += list(_CHROME_TAGS)
    for tag in soup.find_all(tags):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    return soup


def clean_html(html: str, base_url: str, *, drop_chrome: bool = False) -> str:
    """Return sanitized body HTML for the node's ``html`` output."""
    soup = _clean_soup(html, drop_chrome=drop_chrome)
    for anchor in soup.find_all("a", href=True):
        anchor["href"] = urljoin(base_url, anchor["href"])
    body = soup.body or soup
    return str(body).strip()


def extract_links(html: str, base_url: str) -> list[str]:
    """Absolute http(s) links from ``<a href>``, deduped in document order.

    Skips fragments and non-navigational schemes (javascript/mailto/tel) and
    resolves relative hrefs against ``base_url``.
    """
    soup = _soup(html)
    seen: set[str] = set()
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(_SKIP_LINK_PREFIXES):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).scheme not in _HTTP_SCHEMES:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


def extract_metadata(
    html: str,
    final_url: str,
    content_type: str | None,
) -> dict[str, Any]:
    """Curated metadata keys plus every raw ``<meta>``/``<link rel>`` tag on the page."""
    soup = _soup(html)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None
    language = lang.strip() if lang else None

    # single pass over <link> tags: pick the first canonical/icon and collect every rel for the raw sweep
    canonical = None
    favicon = None
    link_rels: list[tuple[str, str]] = []
    for link in soup.find_all("link"):
        rels = link.get("rel") or []
        if isinstance(rels, str):
            rels = rels.split()
        rels = [value.lower() for value in rels]
        href = (link.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(final_url, href)
        if canonical is None and "canonical" in rels:
            canonical = absolute
        if favicon is None and "icon" in rels:
            favicon = absolute
        link_rels.extend((rel, absolute) for rel in rels)
    if favicon is None:
        favicon = urljoin(final_url, "/favicon.ico")

    og_image = _meta(soup, prop="og:image")

    curated = {
        "title": title or None,
        "description": _meta(soup, name="description"),
        "language": language,
        "sourceURL": final_url,
        "contentType": content_type,
        "ogTitle": _meta(soup, prop="og:title"),
        "ogDescription": _meta(soup, prop="og:description"),
        "ogImage": urljoin(final_url, og_image) if og_image else None,
        "favicon": favicon,
        "canonical": canonical,
    }

    merged: dict[str, Any] = dict(curated)
    # charset/http-equiv metas carry no name/property/content and are skipped
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property") or tag.get("itemprop")
        content = tag.get("content")
        if key and content and content.strip():
            merged.setdefault(key.strip(), content.strip())
    for rel, absolute in link_rels:
        merged.setdefault(rel, absolute)
    return merged


def _tidy_markdown(markdown: str) -> str:
    # drop the empty image-links html2text leaves behind, then re-collapse blank lines
    markdown = _EMPTY_LINK_RE.sub("", markdown)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()


# Below this word count chrome-strip may have under-extracted, so readability is tried
_THIN_CONTENT_WORDS = 200


def _readability_main_content(html: str, base_url: str) -> tuple[str, str] | None:
    """Readability-scored main content, or ``None`` when it can't help."""
    if not html or not html.strip():
        return None
    from readability import Document

    try:
        summary_html = Document(html).summary(html_partial=True)
    except ValueError:
        # readability raises Unparseable (a ValueError) on pages it can't score
        return None
    alt_html = clean_html(summary_html, base_url)  # readability already dropped nav/footer
    alt_md = _tidy_markdown(html2markdown(alt_html, base_url=base_url))
    return (alt_md, alt_html) if alt_md.strip() else None


def extract_main_content(html: str, base_url: str) -> tuple[str, str]:
    """Return ``(markdown, cleaned_html)`` for the page's main content."""
    cleaned = clean_html(html, base_url, drop_chrome=True)
    markdown = _tidy_markdown(html2markdown(cleaned, base_url=base_url))
    if len(markdown.split()) >= _THIN_CONTENT_WORDS:
        return markdown, cleaned
    # Only swap when readability itself clears the substance bar chrome-strip missed;
    rescued = _readability_main_content(html, base_url)
    if rescued and len(rescued[0].split()) >= _THIN_CONTENT_WORDS:
        return rescued
    return markdown, cleaned
