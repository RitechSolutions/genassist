"""Unit tests for the section-based text chunker and how its chunks are embedded."""

from types import SimpleNamespace

import pytest

from app.modules.data.config import KbRAGConfig
from app.modules.data.providers.models import DOCUMENT_TITLE_KEY
from app.modules.data.providers.vector.chunking.base import ChunkConfig
from app.modules.data.providers.vector.chunking.recursive import RecursiveChunker
from app.modules.data.providers.vector.chunking.sections import SectionChunker
from app.modules.data.providers.vector.provider import VectorProvider

TITLE = "Acme Bikes app guide"
GUIDE = f"""{TITLE}

This guide walks through the app.

## Unlocking

Tap a bike and then Unlock.

## Wallet

### Cards

Add a card in the wallet.

### Passes

A Day Pass allows 9 rides.
"""
LONG_SENTENCE = "The price depends on the pass you hold and on the length of the ride. "


def _chunker(chunk_size=1000, chunk_overlap=200):
    return ChunkConfig(type="sections", chunk_size=chunk_size, chunk_overlap=chunk_overlap).get()


def _chunks(text, title=TITLE, **settings):
    metadata = {"name": "Help centre"}
    if title:
        metadata[DOCUMENT_TITLE_KEY] = title
    return _chunker(**settings).chunk_text(text, metadata)


def test_strategy_is_available_from_the_config():
    assert isinstance(_chunker(), SectionChunker)


def test_saved_knowledge_base_settings_select_the_strategy():
    saved_settings = KbRAGConfig(vector={"enabled": True, "chunk_strategy": "sections", "chunk_size": 600, "chunk_overlap": 50})

    chunker = saved_settings.get_vector_config().chunking.get()

    assert isinstance(chunker, SectionChunker)
    assert (chunker.config.chunk_size, chunker.config.chunk_overlap) == (600, 50)


def test_each_section_becomes_one_chunk():
    contents = [chunk.content for chunk in _chunks(GUIDE)]

    assert contents == [
        f"{TITLE}\n\nThis guide walks through the app.",
        "## Unlocking\n\nTap a bike and then Unlock.",
        "## Wallet\n\n### Cards\n\nAdd a card in the wallet.",
        "### Passes\n\nA Day Pass allows 9 rides.",
    ]


def test_chunks_are_embedded_with_the_title_and_the_headings_above_them():
    passes = _chunks(GUIDE)[3]

    assert passes.embedding_text == f"{TITLE} > Wallet > Passes\n\n### Passes\n\nA Day Pass allows 9 rides."
    assert passes.metadata["section"] == "Wallet > Passes"
    assert passes.metadata[DOCUMENT_TITLE_KEY] == TITLE


def test_the_opening_chunk_is_not_labelled_with_the_title_it_starts_with():
    assert _chunks(GUIDE)[0].embedding_text is None


def test_a_title_repeated_as_a_heading_is_named_once_in_the_label():
    use = _chunks(f"{TITLE}\n\n# {TITLE}\n\nIntro.\n\n## Use\n\nRide.")[-1]

    assert use.embedding_text == f"{TITLE} > Use\n\n## Use\n\nRide."


def test_emphasis_marks_are_left_out_of_the_label():
    chunks = _chunks(f"{TITLE}\n\nIntro.\n\n### Sub _part_ of **snake_case**\n\nText.")

    assert chunks[1].metadata["section"] == "Sub part of snake_case"


def test_without_a_document_title_the_label_starts_at_the_first_heading():
    unlocking = _chunker().chunk_text(GUIDE, {"name": TITLE})[1]

    assert unlocking.embedding_text == "Unlocking\n\n## Unlocking\n\nTap a bike and then Unlock."


def test_a_document_that_opens_with_a_heading_uses_it_as_the_top_of_every_path():
    chunks = _chunks("# Refunds\n\nRefunds go back to the card.\n\n## How long\n\nFive working days.", title=None)

    assert [chunk.metadata["section"] for chunk in chunks] == ["Refunds", "Refunds > How long"]
    assert chunks[0].content == "# Refunds\n\nRefunds go back to the card."


def test_a_heading_without_text_is_joined_to_the_next_section():
    text = f"{TITLE}\n\nIntro.\n\n### Refunds take 5 working days\n\n### Contact us\n\nCall 555-0100."

    chunks = _chunks(text)

    assert chunks[1].content == "### Refunds take 5 working days\n\n### Contact us\n\nCall 555-0100."
    assert chunks[1].metadata["section"] == "Contact us"


def test_headings_at_the_end_without_text_are_kept():
    chunks = _chunks(f"{TITLE}\n\nIntro.\n\n## Returns\n\nBring it back.\n\n## Still need help?")

    assert chunks[-1].content == "## Still need help?"


def test_a_text_of_only_a_heading_still_gives_a_chunk():
    assert [chunk.content for chunk in _chunks("# Refunds", title=None)] == ["# Refunds"]


def test_a_title_line_on_its_own_is_joined_to_the_first_section():
    text = f"{TITLE}\n\n## Overview\n\nSome text.\n\n## Steps\n\nDo it."

    chunks = _chunks(text)

    assert [chunk.content for chunk in chunks] == [f"{TITLE}\n\n## Overview\n\nSome text.", "## Steps\n\nDo it."]
    assert chunks[0].embedding_text == f"{TITLE} > Overview\n\n{TITLE}\n\n## Overview\n\nSome text."


def test_no_text_is_lost():
    text = f"{TITLE}\n\n## Wallet\n\n### Cards\n\n### Passes\n\n## Returns\n\nBring it back.\n\n**Note**\n\n## Help"

    stored = "\n".join(chunk.content for chunk in _chunks(text))

    assert all(line in stored for line in text.splitlines() if line.strip())


def test_bold_lines_without_text_under_them_stay_in_the_section_they_sit_in():
    text = f"{TITLE}\n\nIntro.\n\n**Acme Depot**\n\n**12 Mill Lane**\n\n## Returns\n\nBring it back."

    chunks = _chunks(text)

    assert [chunk.content for chunk in chunks] == [
        f"{TITLE}\n\nIntro.\n\n**Acme Depot**\n\n**12 Mill Lane**",
        "## Returns\n\nBring it back.",
    ]


def test_a_bold_note_stays_with_the_section_it_ends():
    text = f"{TITLE}\n\nIntro.\n\n## Update\n\nOpen the app.\n\n**Note: not during a ride.**\n\n## Remove\n\nSwipe left."

    chunks = _chunks(text)

    assert chunks[1].content == "## Update\n\nOpen the app.\n\n**Note: not during a ride.**"
    assert chunks[2].content == "## Remove\n\nSwipe left."


def test_a_heading_whose_only_text_is_a_bold_line_keeps_it():
    text = f"{TITLE}\n\nIntro.\n\n## Safety\n\n**Always wear a helmet.**\n\n## Payment\n\nCards only."

    chunks = _chunks(text)

    assert chunks[1].content == "## Safety\n\n**Always wear a helmet.**"
    assert chunks[1].metadata["section"] == "Safety"
    assert chunks[2].metadata["section"] == "Payment"


@pytest.mark.parametrize(
    "bold_line, section",
    [
        ("**Safe****access**", "Safeaccess"),
        ("_**Tip: lock the bike**_", "Tip: lock the bike"),
    ],
)
def test_bold_lines_written_in_two_spans_or_in_italics_start_a_section(bold_line, section):
    chunks = _chunks(f"{TITLE}\n\nIntro.\n\n{bold_line}\n\nSome text.")

    assert chunks[1].metadata["section"] == section


@pytest.mark.parametrize(
    "heading, section",
    [
        ("## [Lost bike](https://help.example.com/lost)", "Lost bike"),
        ("## Lost bike ##", "Lost bike"),
        ("## Lost\u200b bike", "Lost bike"),
    ],
)
def test_links_closing_marks_and_invisible_characters_are_left_out_of_the_label(heading, section):
    chunks = _chunks(f"{TITLE}\n\nIntro.\n\n{heading}\n\nCall us at once.")

    assert chunks[1].metadata["section"] == section
    assert chunks[1].content.startswith(heading)


def test_a_bold_line_followed_by_text_starts_a_section():
    text = f"{TITLE}\n\nIntro.\n\n**Lost bike**\n\nCall us at once.\n\n**Flat tyre**\n\nDock the bike."

    chunks = _chunks(text)

    assert [chunk.content for chunk in chunks[1:]] == ["**Lost bike**\n\nCall us at once.", "**Flat tyre**\n\nDock the bike."]
    assert chunks[1].metadata["section"] == "Lost bike"


def test_bold_lines_in_a_row_start_one_section():
    text = f"{TITLE}\n\nIntro.\n\n**Acme Depot**\n**12 Mill Lane**\n\nOpen 9 to 5.\n\n## Returns\n\nBring the bike back."

    chunks = _chunks(text)

    assert chunks[1].content == "**Acme Depot**\n**12 Mill Lane**\n\nOpen 9 to 5."
    assert chunks[1].metadata["section"] == "Acme Depot"
    assert chunks[2].metadata["section"] == "Returns"


@pytest.mark.parametrize("bold_line", ["**Lost bike \xa0**", "**Lost bike**\xa0", "**Lost bike**\r"])
def test_a_bold_line_with_unusual_spacing_still_starts_a_section(bold_line):
    chunks = _chunks(f"{TITLE}\n\nIntro.\n\n{bold_line}\n\nCall us at once.")

    assert chunks[1].metadata["section"] == "Lost bike"


def test_settings_left_over_from_another_strategy_do_not_change_the_cut():
    pricing = "## Pricing\n\n" + (LONG_SENTENCE * 6 + "\n\n") * 4
    text = f"{TITLE}\n\nIntro.\n\n{pricing}"
    left_over = ChunkConfig(
        type="sections", chunk_size=600, chunk_overlap=0, separators=". ,! ,? , ", keep_separator=False
    )
    clean = ChunkConfig(type="sections", chunk_size=600, chunk_overlap=0)

    with_left_overs = [chunk.content for chunk in left_over.get().chunk_text(text, {})]

    assert with_left_overs == [chunk.content for chunk in clean.get().chunk_text(text, {})]


def test_a_long_section_is_cut_by_size_inside_that_section():
    pricing = "## Pricing\n\n" + LONG_SENTENCE * 40
    text = f"{TITLE}\n\nIntro.\n\n{pricing}\n\n## Returns\n\nBring the bike back."

    chunks = _chunks(text, chunk_size=1000, chunk_overlap=200)
    pricing_chunks = [chunk for chunk in chunks if chunk.metadata.get("section") == "Pricing"]

    assert len(pricing_chunks) > 1
    assert all(len(chunk.content) <= 1000 for chunk in pricing_chunks)
    assert all("Bring the bike back" not in chunk.content for chunk in pricing_chunks)
    assert all(chunk.embedding_text.startswith(f"{TITLE} > Pricing\n\n") for chunk in pricing_chunks)
    assert chunks[-1].content == "## Returns\n\nBring the bike back."


def test_text_without_headings_is_cut_like_the_recursive_strategy():
    text = LONG_SENTENCE * 60
    config = ChunkConfig(type="sections", chunk_size=1000, chunk_overlap=200)

    by_sections = config.get().chunk_text(text, {"name": "notes.txt"})
    by_size = RecursiveChunker(config).chunk_text(text, {"name": "notes.txt"})

    assert len(by_sections) > 1
    assert [chunk.model_dump() for chunk in by_sections] == [chunk.model_dump() for chunk in by_size]
    assert all(chunk.embedding_text is None for chunk in by_sections)


def test_heading_marks_inside_a_code_block_do_not_start_a_section():
    text = f"{TITLE}\n\nIntro.\n\n## Install\n\n```\n# install the tool\n**not a heading**\n```\n\nThen sign in."

    chunks = _chunks(text)

    assert len(chunks) == 2
    assert chunks[1].content.endswith("Then sign in.")
    assert "# install the tool" in chunks[1].content


def test_inline_code_in_triple_backticks_does_not_open_a_code_block():
    text = f"{TITLE}\n\n```pip install acme``` is the command.\n\n## Install\n\nRun it.\n\n## Use\n\nRide."

    assert [chunk.metadata.get("section") for chunk in _chunks(text)] == [None, "Install", "Use"]


def test_a_code_block_is_closed_only_by_the_mark_that_opened_it():
    text = f"{TITLE}\n\nIntro.\n\n## Install\n\n```\n~~~\n## not a heading\n```\n\n## Use\n\nRide."

    assert [chunk.metadata.get("section") for chunk in _chunks(text)] == [None, "Install", "Use"]


def test_a_very_long_line_is_not_a_heading():
    text = f"{TITLE}\n\nIntro.\n\n## {'word ' * 100}\n\nMore text.\n\n## Use\n\nRide."

    assert [chunk.metadata.get("section") for chunk in _chunks(text)] == [None, "Use"]


@pytest.mark.parametrize(
    "empty_heading",
    [
        "##",
        "## \xa0",
        "## \u200b",
        "## [](https://help.example.com/lost)",
        "## ![](https://help.example.com/map.png)",
    ],
)
def test_a_heading_line_with_only_spacing_is_dropped(empty_heading):
    chunks = _chunks(f"{TITLE}\n\nIntro.\n\n{empty_heading}\n\n## Payments\n\nWe take cards.")

    assert [chunk.content for chunk in chunks] == [f"{TITLE}\n\nIntro.", "## Payments\n\nWe take cards."]


def test_an_empty_heading_line_is_dropped():
    text = f"{TITLE}\n\nIntro.\n\n##\n\n## **Payments**\n\nWe take cards."

    chunks = _chunks(text)

    assert [chunk.content for chunk in chunks] == [f"{TITLE}\n\nIntro.", "## **Payments**\n\nWe take cards."]
    assert chunks[1].metadata["section"] == "Payments"


def test_chunks_are_numbered_in_order_and_point_at_their_text():
    pricing = "## Pricing\n\n" + LONG_SENTENCE * 40
    text = f"{TITLE}\n\nIntro.\n\n{pricing}\n\n## Returns\n\nBring the bike back."

    chunks = _chunks(text)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(text[chunk.start_char:chunk.end_char] == chunk.content for chunk in chunks)


@pytest.mark.parametrize("text", ["", "   \n\n  "])
def test_blank_text_gives_no_chunks(text):
    assert _chunks(text) == []


class _RecordingEmbedder:
    def __init__(self):
        self.embedded = []

    async def embed_texts(self, texts):
        self.embedded = list(texts)
        return [[0.1, 0.2] for _ in texts]


class _RecordingStore:
    def __init__(self):
        self.contents = []

    async def delete_vectors_by_metadata(self, filter_dict):
        return True

    async def add_vectors(self, ids, vectors, metadatas, contents):
        self.contents = list(contents)
        return True


def _provider(chunker, embedder, store):
    provider = VectorProvider(SimpleNamespace(), "kb-1")
    provider.chunker, provider.embedder, provider.vector_db = chunker, embedder, store
    provider._initialized = True
    return provider


@pytest.mark.asyncio
async def test_the_label_is_embedded_but_not_stored():
    embedder, store = _RecordingEmbedder(), _RecordingStore()

    added = await _provider(_chunker(), embedder, store).add_document("KB:1#article_7", GUIDE, {DOCUMENT_TITLE_KEY: TITLE})

    assert added is True
    assert store.contents[1] == "## Unlocking\n\nTap a bike and then Unlock."
    assert embedder.embedded[1] == f"{TITLE} > Unlocking\n\n## Unlocking\n\nTap a bike and then Unlock."


@pytest.mark.asyncio
async def test_other_strategies_embed_exactly_what_they_store():
    embedder, store = _RecordingEmbedder(), _RecordingStore()
    recursive = ChunkConfig(type="recursive", chunk_size=1000, chunk_overlap=200).get()

    await _provider(recursive, embedder, store).add_document("KB:1#content", GUIDE, {"name": TITLE})

    assert embedder.embedded == store.contents
