"""Unit tests for query-aware markdown chunk selection."""

from app.core.utils.content_relevance import select_relevant_content, strip_invisible


def _filler(word: str, size: int = 680) -> str:
    """Neutral paragraph of ~size chars; ~680 keeps it a standalone chunk (merges would pass 700)."""
    sentence = f"General {word} notes archive routine updates without surprises. "
    return (sentence * (size // len(sentence) + 1))[:size].strip()


# selection


def test_heading_glued_to_following_block():
    md = "\n\n".join(
        [
            "# Setup",
            "Install the package with pip and configure credentials before first use.",
            _filler("alpha"),
            _filler("beta"),
        ]
    )
    out = select_relevant_content(md, "install package credentials", 300)
    assert "# Setup" in out
    assert "Install the package" in out
    assert len(out) <= 300


def test_selects_relevant_section_from_long_page():
    md = "\n\n".join(
        [
            _filler("alpha"),
            _filler("beta"),
            "## Pricing\n\nThe pro plan costs $99 per month with unlimited seats.",
            _filler("gamma"),
        ]
    )
    out = select_relevant_content(md, "pricing pro plan", 300)
    assert "$99" in out
    assert "alpha" not in out
    assert len(out) <= 300


def test_result_never_exceeds_budget():
    md = "\n\n".join(
        [_filler(word) for word in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")]
        + ["## Pricing\n\nThe pro plan costs $99 per month with unlimited seats."]
    )
    assert len(md) > 4000
    for budget in (50, 150, 300, 700, 2000, 4000):
        out = select_relevant_content(md, "pricing pro plan", budget)
        assert len(out) <= budget


def test_selected_chunks_keep_document_order():
    early = "Shipping options include ground delivery for most regions."
    late = "Express shipping and overnight shipping cost extra; shipping insurance is optional."
    md = "\n\n".join([early, _filler("alpha"), _filler("beta"), late, _filler("gamma")])
    out = select_relevant_content(md, "shipping", 700)
    assert "ground delivery" in out
    assert "Express shipping" in out
    assert out.index("ground delivery") < out.index("Express shipping")


def test_tie_scores_prefer_earlier_chunk():
    first = "Alpha section covers warranty terms for enrolled devices today."
    second = "Gamma section covers warranty terms for enrolled devices today."
    md = "\n\n".join([first, _filler("delta"), second, _filler("epsilon")])
    out = select_relevant_content(md, "warranty terms", 70)
    assert "Alpha" in out
    assert "Gamma" not in out


def test_duplicate_chunks_selected_once():
    dup = "Overnight shipping rates stay flat at $42 for domestic parcels."
    md = "\n\n".join([_filler("alpha"), dup, _filler("beta"), dup])
    out = select_relevant_content(md, "overnight shipping rates", 400)
    assert out.count("$42") == 1


def test_oversized_block_split_on_sentences():
    opening = "Opening line about corporate history and heritage values."
    matching = "Refund policy grants a full refund within thirty days of purchase."
    sentences = [opening] + [f"Neutral filler sentence number {i} covering assorted topics." for i in range(30)]
    sentences.insert(20, matching)
    md = " ".join(sentences) + "\n\n" + _filler("alpha")
    out = select_relevant_content(md, "refund policy", 700)
    assert "full refund within thirty days" in out
    assert opening not in out


def test_first_choice_larger_than_budget_is_truncated():
    block = ("Quantum pricing tiers scale with usage volume across accounts. " * 11).strip()
    md = "\n\n".join([_filler("alpha"), block, _filler("beta")])
    out = select_relevant_content(md, "quantum pricing tiers", 50)
    assert out == block[:50]


# fallbacks


def test_stopword_only_query_falls_back():
    md = "\n\n".join([_filler("alpha"), _filler("beta"), _filler("gamma")])
    assert select_relevant_content(md, "what is the", 200) == md[:200]


def test_single_char_query_falls_back():
    md = "\n\n".join([_filler("alpha"), _filler("beta")])
    assert select_relevant_content(md, "q", 200) == md[:200]


def test_zero_match_query_falls_back():
    md = "\n\n".join([_filler("alpha"), _filler("beta")])
    assert select_relevant_content(md, "zzqx unmatched", 200) == md[:200]


def test_ubiquitous_term_without_distinguishing_signal_falls_back():
    md = "\n\n".join(
        [
            "Acme ships widgets worldwide and Acme leads the market.",
            _filler("alpha") + " Acme remains involved.",
            _filler("beta") + " Acme remains committed.",
            "Copyright Acme. Acme and the Acme logo are trademarks of Acme Incorporated.",
        ]
    )
    assert select_relevant_content(md, "acme", 200) == md[:200]


def test_exact_phrase_overrides_flat_term_distribution():
    md = "\n\n".join(
        [
            _filler("alpha") + " Acme documents exist while the plan details vary by region.",
            "The acme plan tier costs $49 monthly.",
            _filler("beta") + " Acme grows steadily and every plan evolves.",
        ]
    )
    out = select_relevant_content(md, "acme plan", 200)
    assert "$49" in out
    assert "alpha" not in out


def test_heading_match_passes_low_information_gate():
    md = "\n\n".join(
        [
            _filler("alpha") + " Widgets ship weekly.",
            "## Widgets catalog\n\nBrowse every widgets model with detailed specifications and photos.",
            _filler("beta") + " Widgets sell well.",
        ]
    )
    out = select_relevant_content(md, "widgets", 300)
    assert "specifications" in out
    assert "alpha" not in out


# markdown links


def test_url_query_scores_visible_text_not_link_destinations():
    link_chunk = " ".join(f"[Post {i}](https://acme.com/blog/{i})" for i in range(1, 30)) + " Latest roundup entries."
    visible_chunk = "Acme pricing starts at $10 per seat with volume discounts."
    md = "\n\n".join([link_chunk, _filler("alpha"), visible_chunk])
    out = select_relevant_content(md, "https://acme.com pricing", 200)
    assert "$10" in out
    assert "roundup" not in out


def test_output_preserves_markdown_links_verbatim():
    target = "See the [pricing guide](https://acme.com/pricing) for tier comparisons and costs."
    md = "\n\n".join([_filler("alpha"), target, _filler("beta")])
    out = select_relevant_content(md, "pricing guide tier", 200)
    assert "[pricing guide](https://acme.com/pricing)" in out


# boundaries


def test_empty_inputs_return_empty():
    assert select_relevant_content("", "anything", 500) == ""
    assert select_relevant_content("   \n\n  ", "anything", 500) == ""
    assert select_relevant_content("content here", "anything", 0) == ""


def test_whole_page_within_budget_returned_verbatim():
    md = "## Pricing\n\nPlans start at $5."
    assert select_relevant_content(md, "pricing", 4000) == md


def test_unicode_query_and_text():
    target = "Les coûts d'expédition s'élèvent à 42 € pour les commandes internationales."
    md = "\n\n".join([_filler("alpha"), target, _filler("beta")])
    out = select_relevant_content(md, "coûts expédition", 200)
    assert "42 €" in out


# section integrity


def test_sections_do_not_merge_across_headings():
    md = "\n\n".join(
        [
            "### PayPal\n\n" + "PayPal is a global online payments platform used across many markets today. " * 2,
            "### Payline Data\n\n" + "Payline delivers flexible friendly payment solutions for growing teams. " * 2,
        ]
    )
    out = select_relevant_content(md, "payline flexible payment solutions", 250)
    assert "Payline delivers flexible" in out
    assert "### Payline Data" in out
    assert "PayPal is a global" not in out


def test_continuation_chunk_regains_its_heading():
    body = "General background about the company history and mission today. " * 12
    md = "## Returns\n\n" + body + "\n\nRefund policy grants a full refund within thirty days."
    out = select_relevant_content(md, "refund policy thirty days", 300)
    assert "Refund policy grants" in out
    assert "## Returns" in out
    assert len(out) <= 300


def test_elision_marker_separates_nonadjacent_chunks():
    early = "Alpha pricing tier costs ten dollars monthly per seat."
    mid = "General filler about unrelated onboarding steps and tutorials here. " * 12
    late = "Beta pricing tier costs twenty dollars monthly per seat."
    md = "\n\n".join([early, mid, late])
    out = select_relevant_content(md, "pricing tier costs", 300)
    assert "Alpha pricing" in out
    assert "Beta pricing" in out
    assert "[...]" in out
    assert out.index("Alpha") < out.index("[...]") < out.index("Beta")


def test_structural_budget_keeps_markers_and_headings_intact():
    s1 = "## First\n\nAlpha ratio measures one hundred units precisely today."
    mid = "Filler about unrelated onboarding tutorials and setup steps here. " * 12
    s2 = "## Second\n\nAlpha ratio measures two hundred units precisely today."
    md = "\n\n".join([s1, mid, s2])
    for budget in range(40, 260, 10):
        out = select_relevant_content(md, "alpha ratio hundred", budget)
        assert len(out) <= budget
        stripped = out.replace("[...]", "")
        assert "[" not in stripped and "]" not in stripped
        for line in out.splitlines():
            if line.startswith("#"):
                assert line in ("## First", "## Second")


# invisible characters


def test_strip_invisible_removes_standalone_runs():
    assert strip_invisible("a\n\n‍​\n\nb") == "a\n\nb"


def test_strip_invisible_removes_line_leading_run():
    assert strip_invisible("intro\n\n‍**Headquarters:** Chicago") == "intro\n\n**Headquarters:** Chicago"


def test_strip_invisible_preserves_emoji_zwj():
    family = "\U0001f468‍\U0001f469‍\U0001f467"
    assert strip_invisible(f"Team {family} rocks") == f"Team {family} rocks"


def test_standalone_zero_width_absent_from_selection():
    md = "\n\n".join(
        [
            "## Overview\n\nThe pricing plans cover every tier with clear billing details.",
            "‍",
            "Extra pricing notes describe discounts and billing cycles thoroughly enough.",
        ]
    )
    out = select_relevant_content(md, "pricing billing details", 120)
    assert "‍" not in out
    assert len(out) <= 120
