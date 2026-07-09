"""Pure python extraction helpers for scraped HTML: links, metadata, main content."""

import re
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
    # fall back to the stdlib parser when it is unavailable
    try:
        return BeautifulSoup(html or "", "lxml")
    except Exception:
        return BeautifulSoup(html or "", "html.parser")


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


def extract_links(
    html: str,
    base_url: str,
    *,
    same_origin_only: bool = False,
    limit: int = 200,
) -> list[str]:
    """Absolute http(s) links from ``<a href>``, deduped in document order.

    Skips fragments and non-navigational schemes (javascript/mailto/tel); resolves
    relative hrefs against ``base_url`` and optionally keeps only same-origin links.
    """
    soup = _soup(html)
    base_netloc = urlparse(base_url).netloc
    seen: set[str] = set()
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(_SKIP_LINK_PREFIXES):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in _HTTP_SCHEMES:
            continue
        if same_origin_only and parsed.netloc != base_netloc:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
        if len(links) >= limit:
            break
    return links


def extract_metadata(
    html: str,
    final_url: str,
    status_code: int | None,
    content_type: str | None,
) -> dict:
    """Curated metadata keys plus every raw ``<meta>``/``<link rel>`` tag on the page.

    The 11 curated keys are authoritative and always present (missing values are
    ``None``): ``sourceURL``/``statusCode``/``contentType`` are threaded from the fetch
    result; ``ogImage``/``canonical``/``favicon`` are absolutized against ``final_url``.
    Remaining tags are swept in afterwards (``og:title``, ``twitter:card``, …) without
    overriding a curated key
    """
    soup = _soup(html)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None
    language = lang.strip() if lang else None

    canonical = None
    favicon = None
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        if isinstance(rel, str):
            rel = rel.split()
        rel = [value.lower() for value in rel]
        href = (link.get("href") or "").strip()
        if not href:
            continue
        if canonical is None and "canonical" in rel:
            canonical = urljoin(final_url, href)
        if favicon is None and "icon" in rel:
            favicon = urljoin(final_url, href)
    if favicon is None:
        favicon = urljoin(final_url, "/favicon.ico")

    og_image = _meta(soup, prop="og:image")

    curated = {
        "title": title or None,
        "description": _meta(soup, name="description"),
        "language": language,
        "sourceURL": final_url,
        "statusCode": status_code,
        "contentType": content_type,
        "ogTitle": _meta(soup, prop="og:title"),
        "ogDescription": _meta(soup, prop="og:description"),
        "ogImage": urljoin(final_url, og_image) if og_image else None,
        "favicon": favicon,
        "canonical": canonical,
    }

    merged: dict = dict(curated)
    # charset/http-equiv metas carry no name/property/content and are skipped
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property") or tag.get("itemprop")
        content = tag.get("content")
        if key and content and content.strip():
            merged.setdefault(key.strip(), content.strip())
    for link in soup.find_all("link"):
        rels = link.get("rel") or []
        if isinstance(rels, str):
            rels = rels.split()
        href = (link.get("href") or "").strip()
        if not href:
            continue
        for rel in rels:
            merged.setdefault(rel.lower(), urljoin(final_url, href))
    return merged


def _tidy_markdown(markdown: str) -> str:
    # drop the empty image-links html2text leaves behind, then re-collapse blank lines
    markdown = _EMPTY_LINK_RE.sub("", markdown)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()


def extract_main_content(html: str, base_url: str) -> tuple[str, str]:
    """Return ``(markdown, cleaned_html)`` for the page's main content.

    Strips scripts/styles/svg/images and page chrome (nav/footer/aside)
    while keeping the article ``<header>`` and body sections, then converts to markdown.
    """
    cleaned = clean_html(html, base_url, drop_chrome=True)
    return _tidy_markdown(html2markdown(cleaned, base_url=base_url)), cleaned
