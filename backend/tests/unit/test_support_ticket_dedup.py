from app.services.support_ticket_dedup import compute_fingerprint, normalize_title


def test_normalize_title_strips_punctuation():
    assert normalize_title("  Hello, World!! ") == "hello world"


def test_fingerprint_stable_for_same_input():
    a = compute_fingerprint("Login fails", "bug", ["auth"])
    b = compute_fingerprint("Login fails", "bug", ["auth"])
    assert a == b


def test_fingerprint_differs_by_type():
    a = compute_fingerprint("Login fails", "bug")
    b = compute_fingerprint("Login fails", "feature")
    assert a != b
