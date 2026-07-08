"""Pure python extraction helpers for scraped HTML: links, metadata, main content."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.core.utils.html_utils import html2markdown

_HTTP_SCHEMES = frozenset({"http", "https"})
_SKIP_LINK_PREFIXES = ("#", "javascript:", "mailto:", "tel:")


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
    """Fixed metadata key set for the node output (missing values are ``None``).

    ``sourceURL``/``statusCode``/``contentType`` are threaded from the fetch result;
    ``ogImage``/``canonical``/``favicon`` are absolutized against ``final_url``.
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

    return {
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


def extract_main_content(html: str, base_url: str, *, min_chars: int = 200) -> tuple[str, str]:
    """Return ``(markdown, cleaned_html)`` for the page's main content.

    Uses readability to strip boilerplate; falls back to the full DOM (with an empty
    cleaned_html) when readability raises or over-strips a thin page below ``min_chars``.
    """
    from readability import Document

    try:
        cleaned_html = Document(html or "", url=base_url).summary(html_partial=True)
        markdown = html2markdown(cleaned_html, base_url=base_url)
        if len(markdown.strip()) >= min_chars:
            return markdown, cleaned_html
    except Exception:
        pass
    return html2markdown(html or "", base_url=base_url), ""
