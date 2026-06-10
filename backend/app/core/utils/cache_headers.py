from __future__ import annotations


def no_store_headers(*, vary: str = "Authorization, Cookie, Origin") -> dict[str, str]:
    """
    Conservative cache headers for authenticated / user-specific responses.

    - Prevents shared/proxy caches from storing responses.
    - Prevents browsers from reusing content after logout/user switch.
    """
    return {
        "Cache-Control": "private, no-store",
        "Pragma": "no-cache",
        "Expires": "0",
        "Vary": vary,
    }

