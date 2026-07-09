"""Unit tests for the scraped-content extraction helpers."""

from app.core.utils.web_content_utils import (
    _THIN_CONTENT_WORDS,
    clean_html,
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
            <meta property="og:site_name" content="Example Site">
            <meta name="twitter:card" content="summary_large_image">
            <link rel="canonical" href="/canonical-path">
            <link rel="shortcut icon" href="/custom.ico">
        </head>
        <body></body>
        </html>
    """
    meta = extract_metadata(html, "https://example.com/some/page", "text/html")

    # curated keys stay authoritative with their derived/absolutized values
    assert meta["title"] == "My Page"
    assert meta["description"] == "A description"
    assert meta["language"] == "en-US"
    assert meta["sourceURL"] == "https://example.com/some/page"
    assert meta["contentType"] == "text/html"
    assert meta["ogTitle"] == "OG Title"
    assert meta["ogDescription"] == "OG Desc"
    assert meta["ogImage"] == "https://example.com/img/hero.png"
    assert meta["favicon"] == "https://example.com/custom.ico"
    assert meta["canonical"] == "https://example.com/canonical-path"

    # raw tag names are swept in alongside the curated keys
    assert meta["twitter:card"] == "summary_large_image"
    assert meta["og:site_name"] == "Example Site"
    assert meta["og:title"] == "OG Title"


def test_metadata_missing_values_are_none_and_favicon_falls_back():
    meta = extract_metadata("<html><head></head><body>hi</body></html>", "https://example.com/x", None)
    assert meta["title"] is None
    assert meta["description"] is None
    assert meta["language"] is None
    assert meta["ogTitle"] is None
    assert meta["ogImage"] is None
    assert meta["canonical"] is None
    assert meta["favicon"] == "https://example.com/favicon.ico"
    assert meta["sourceURL"] == "https://example.com/x"
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
            that chrome-strip clearly keeps this block as the primary content region.</p>
        </article>
        <footer>Copyright 2026 Example Inc</footer>
        </body></html>
    """
    markdown, cleaned_html = extract_main_content(html, _BASE)
    assert "First paragraph" in markdown
    assert "Home About Contact" not in markdown
    assert "Copyright" not in markdown
    assert cleaned_html != ""


def test_main_content_thin_page_returns_cleaned_body():
    markdown, cleaned_html = extract_main_content("<html><body><p>Hi</p></body></html>", _BASE)
    assert "Hi" in markdown
    assert "Hi" in cleaned_html


def test_main_content_keeps_header_and_drops_chrome():
    html = (
        "<html><body><nav><a href='/x'>Menu</a></nav>"
        "<header><h1>Hero Title</h1><p>Tagline sentence.</p></header>"
        "<main><p>Body paragraph with content.</p></main>"
        "<footer>Footer links</footer></body></html>"
    )
    markdown, _ = extract_main_content(html, _BASE)
    assert "Hero Title" in markdown
    assert "Tagline sentence" in markdown
    assert "Menu" not in markdown
    assert "Footer links" not in markdown


def test_main_content_readability_rescues_content():
    # body lives inside an <aside> that chrome-strip drops, leaving thin output;
    # readability rescues it because it recovers strictly more words
    body = " ".join(f"Paragraph sentence number {i} carries genuine article prose." for i in range(40))
    html = f"""
        <html><body>
        <nav>Home About Contact</nav>
        <p>Tiny intro.</p>
        <aside><article><h1>Rescued Headline</h1><p>{body}</p></article></aside>
        <footer>Copyright 2026</footer>
        </body></html>
    """
    markdown, cleaned_html = extract_main_content(html, _BASE)
    assert "Rescued Headline" in markdown
    assert "genuine article prose" in markdown
    assert len(markdown.split()) >= _THIN_CONTENT_WORDS
    assert "Rescued Headline" in cleaned_html


def test_main_content_empty_html_falls_back_without_raising():
    markdown, cleaned_html = extract_main_content("", _BASE)
    assert markdown == ""
    assert cleaned_html == ""


# clean_html


def test_clean_html_strips_noise_and_keeps_body_content():
    raw = (
        "<html><head><title>T</title><style>.x{color:red}</style></head>"
        "<body><script>var a=1</script><svg><path d='M0'/></svg>"
        "<h1>Title</h1><p>Keep me</p><img src='/a.png'></body></html>"
    )
    out = clean_html(raw, "https://example.com/")
    assert "<h1>Title</h1>" in out
    assert "Keep me" in out
    for gone in ("<script", "<style", "<svg", "<img", "<head"):
        assert gone not in out


def test_clean_html_absolutizes_links_and_drops_chrome_on_request():
    raw = "<body><nav><a href='/menu'>Menu</a></nav><a href='/post'>Post</a><footer>Foot</footer></body>"
    kept = clean_html(raw, "https://example.com/")
    assert 'href="https://example.com/post"' in kept
    assert "Menu" in kept
    dropped = clean_html(raw, "https://example.com/", drop_chrome=True)
    assert "Menu" not in dropped
    assert "Foot" not in dropped
