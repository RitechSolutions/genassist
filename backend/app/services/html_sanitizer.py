"""Allowlist-based HTML sanitizer for user-authored rich-text fields.

Help Center rich-text fields (description, repro steps, system info, acceptance
criteria) are authored in a contentEditable editor and stored as HTML, then
rendered back in the UI and pushed to Azure DevOps work item HTML fields. This
strips anything outside a conservative allowlist (scripts, event handlers,
javascript: URLs, etc.) so stored markup is safe to render.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Comment

# Tags kept as-is. Anything else is unwrapped (its text content is preserved)
# unless it is in _DROP_TAGS, which are removed entirely.
_ALLOWED_TAGS = {
    "p", "br", "div", "span", "b", "strong", "i", "em", "u", "s", "strike",
    "a", "img", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "code", "pre",
}

# Tags removed together with their contents.
_DROP_TAGS = {"script", "style", "iframe", "object", "embed", "link", "meta", "form"}

_ALLOWED_ATTRS = {
    "a": {"href", "target", "rel", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "span": {"style"},
    "div": {"style"},
    "p": {"style"},
}

_SAFE_URL_SCHEMES = ("http://", "https://", "mailto:", "data:image/")


def _is_safe_url(value: str) -> bool:
    candidate = (value or "").strip().lower()
    if not candidate:
        return False
    if candidate.startswith(("/", "#")):
        return True
    return candidate.startswith(_SAFE_URL_SCHEMES)


def _sanitize_style(value: str) -> str:
    """Keep only a small set of harmless inline style properties (font-size)."""
    kept = []
    for declaration in (value or "").split(";"):
        if ":" not in declaration:
            continue
        prop, _, val = declaration.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if prop == "font-size" and "url(" not in val.lower() and "expression" not in val.lower():
            kept.append(f"{prop}: {val}")
    return "; ".join(kept)


def sanitize_html(value: str | None) -> str:
    """Return a sanitized copy of ``value`` keeping only allowlisted markup."""
    if not value:
        return ""

    soup = BeautifulSoup(value, "html.parser")

    # Strip comments.
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag in list(soup.find_all(True)):
        name = (tag.name or "").lower()
        if name in _DROP_TAGS:
            tag.decompose()
            continue
        if name not in _ALLOWED_TAGS:
            tag.unwrap()
            continue

        allowed = _ALLOWED_ATTRS.get(name, set())
        for attr in list(tag.attrs):
            attr_lower = attr.lower()
            if attr_lower.startswith("on") or attr_lower not in allowed:
                del tag.attrs[attr]
                continue
            val = tag.attrs[attr]
            if attr_lower in ("href", "src"):
                if not _is_safe_url(str(val)):
                    del tag.attrs[attr]
            elif attr_lower == "style":
                cleaned = _sanitize_style(str(val))
                if cleaned:
                    tag.attrs[attr] = cleaned
                else:
                    del tag.attrs[attr]

        # Links always open safely in a new tab.
        if name == "a" and tag.get("href"):
            tag.attrs["target"] = "_blank"
            tag.attrs["rel"] = "noopener noreferrer"

    return str(soup).strip()
