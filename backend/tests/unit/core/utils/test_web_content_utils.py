"""Unit tests for the scraped-content extraction helpers."""

from app.core.utils.web_content_utils import (
    extract_links,
    extract_main_content,
    extract_metadata,
)

_BASE = "https://example.com/page"


# extract_links


def test_links_are_absolutized_deduped_and_ordered():
    html = """
        <a href="/a">A</a>
        <a href="/b">B</a>
        <a href="/a">A again</a>
        <a href="https://other.com/x">X</a>
    """
    assert extract_links(html, _BASE) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://other.com/x",
    ]


def test_links_skip_fragments_and_non_navigational_schemes():
    html = """
        <a href="#top">frag</a>
        <a href="javascript:void(0)">js</a>
        <a href="mailto:x@y.com">mail</a>
        <a href="tel:+123">tel</a>
        <a href="ftp://f.com/z">ftp</a>
        <a href="/real">real</a>
    """
    assert extract_links(html, _BASE) == ["https://example.com/real"]


def test_links_same_origin_only_drops_foreign_hosts():
    html = '<a href="/local">L</a><a href="https://other.com/x">X</a>'
    assert extract_links(html, _BASE, same_origin_only=True) == ["https://example.com/local"]


def test_links_respect_limit():
    html = '<a href="/a">A</a><a href="/b">B</a><a href="/c">C</a>'
    assert extract_links(html, _BASE, limit=2) == [
        "https://example.com/a",
        "https://example.com/b",
    ]


# extract_metadata


def test_metadata_parses_all_tags_and_absolutizes():
    html = """
        <html lang="en-US">
        <head>
            <title>  My Page  </title>
            <meta name="description" content="A description">
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Desc">
            <meta property="og:image" content="/img/hero.png">
            <link rel="canonical" href="/canonical-path">
            <link rel="shortcut icon" href="/custom.ico">
        </head>
        <body></body>
        </html>
    """
    meta = extract_metadata(html, "https://example.com/some/page", 200, "text/html")
    assert meta == {
        "title": "My Page",
        "description": "A description",
        "language": "en-US",
        "sourceURL": "https://example.com/some/page",
        "statusCode": 200,
        "contentType": "text/html",
        "ogTitle": "OG Title",
        "ogDescription": "OG Desc",
        "ogImage": "https://example.com/img/hero.png",
        "favicon": "https://example.com/custom.ico",
        "canonical": "https://example.com/canonical-path",
    }


def test_metadata_missing_values_are_none_and_favicon_falls_back():
    meta = extract_metadata("<html><head></head><body>hi</body></html>", "https://example.com/x", None, None)
    assert meta["title"] is None
    assert meta["description"] is None
    assert meta["language"] is None
    assert meta["ogTitle"] is None
    assert meta["ogImage"] is None
    assert meta["canonical"] is None
    assert meta["favicon"] == "https://example.com/favicon.ico"
    assert meta["sourceURL"] == "https://example.com/x"
    assert meta["statusCode"] is None
    assert meta["contentType"] is None


# extract_main_content


def test_main_content_extracts_article_and_returns_cleaned_html():
    html = """
        <html><body>
        <nav>Home About Contact Login</nav>
        <article>
            <h1>The Headline</h1>
            <p>First paragraph with enough words to be recognized as the main content of
            the page, containing several sentences, commas, and genuinely meaningful text.</p>
            <p>Second paragraph continues the article body with more substantial prose so
            that readability confidently scores this block as the primary content region.</p>
        </article>
        <footer>Copyright 2026 Example Inc</footer>
        </body></html>
    """
    markdown, cleaned_html = extract_main_content(html, _BASE)
    assert "First paragraph" in markdown
    assert cleaned_html != ""


def test_main_content_thin_page_falls_back_to_full_dom():
    markdown, cleaned_html = extract_main_content("<html><body><p>Hi</p></body></html>", _BASE)
    assert "Hi" in markdown
    assert cleaned_html == ""  # below min_chars -> full-DOM fallback, no cleaned html


def test_main_content_empty_html_falls_back_without_raising():
    markdown, cleaned_html = extract_main_content("", _BASE)
    assert markdown == ""
    assert cleaned_html == ""
