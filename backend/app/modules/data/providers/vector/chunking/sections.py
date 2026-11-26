"""
Section-based text chunker: one chunk per section of a Markdown document
"""

import re
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from ...models import DOCUMENT_TITLE_KEY
from .base import BaseChunker, Chunk, ChunkConfig
from .recursive import RecursiveChunker

HEADING_LINE = re.compile(r"(#{1,6})(?:\s+(.*))?$")
FENCE_OPENING = re.compile(r" {0,3}(`{3,}|~{3,})(.*)$")
EMPHASIS_UNDERSCORES = re.compile(r"(?<!\w)_+([^_]+?)_+(?!\w)")
LINK_MARKUP = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
ZERO_WIDTH_CHARACTERS = re.compile("[\u200b\u200c\u200d\ufeff]")
CLOSING_HASHES = re.compile(r"\s+#+$")
BOLD_MARK = "**"
ADJACENT_BOLD_SPANS = "****"
BOLD_LINE_LEVEL = 7
MAX_MARKER_LINE_LENGTH = 300
PATH_SEPARATOR = " > "


@dataclass(frozen=True)
class LineMark:
    level: int
    heading: str


@dataclass(frozen=True)
class SectionStart:
    position: int
    level: int
    heading: str


@dataclass(frozen=True)
class Section:
    start: int
    end: int
    level: int
    heading: str
    path: Tuple[str, ...]


def _clean_heading(raw_heading: str) -> str:
    """The heading text without Markdown marks, link targets or invisible characters."""
    visible = ZERO_WIDTH_CHARACTERS.sub("", raw_heading)
    without_links = LINK_MARKUP.sub(r"\1", visible)
    without_asterisks = re.sub(r"[\\*]", "", without_links)
    without_emphasis = EMPHASIS_UNDERSCORES.sub(r"\1", without_asterisks).strip()
    return CLOSING_HASHES.sub("", without_emphasis)


def _bold_only_text(line: str) -> Optional[str]:
    """The text of a line that is bold from its first to its last character."""
    stripped = line.rstrip().strip("_")
    is_wrapped_in_marks = (
        stripped.startswith(BOLD_MARK) and stripped.endswith(BOLD_MARK) and len(stripped) > 2 * len(BOLD_MARK)
    )
    if not is_wrapped_in_marks:
        return None
    inner = stripped.strip("*").replace(ADJACENT_BOLD_SPANS, "").strip()
    is_bold_throughout = bool(inner) and BOLD_MARK not in inner
    return _clean_heading(inner) if is_bold_throughout else None


def _line_mark(line: str) -> Optional[LineMark]:
    """What a line marks: a heading, a bold-only line, or nothing. Very long lines mark nothing."""
    if len(line) > MAX_MARKER_LINE_LENGTH:
        return None
    heading = HEADING_LINE.match(line.rstrip())
    if heading is not None:
        return LineMark(len(heading.group(1)), _clean_heading(heading.group(2) or ""))
    bold_text = _bold_only_text(line)
    return LineMark(BOLD_LINE_LEVEL, bold_text) if bold_text is not None else None


def _opened_fence(line: str) -> Optional[str]:
    """The marks a line opens a code block with; inline code that closes on the same line opens none."""
    opening = FENCE_OPENING.match(line.rstrip())
    if opening is None:
        return None
    marks, rest_of_line = opening.group(1), opening.group(2)
    is_inline_code = marks.startswith("`") and "`" in rest_of_line
    return None if is_inline_code else marks


def _closes_fence(line: str, open_fence: str) -> bool:
    """True for a line of only the opening mark, at least as many as opened the block."""
    stripped = line.strip()
    return len(stripped) >= len(open_fence) and set(stripped) == {open_fence[0]}


def _section_starts(text: str) -> List[SectionStart]:
    """Heading lines and the first line of each run of bold-only lines, outside code blocks."""
    starts: List[SectionStart] = []
    open_fence: Optional[str] = None
    follows_bold_line = False
    position = 0
    for line in text.splitlines(keepends=True):
        line_start, position = position, position + len(line)
        if open_fence is not None:
            open_fence = None if _closes_fence(line, open_fence) else open_fence
            continue
        if not line.strip():
            continue
        open_fence = _opened_fence(line)
        mark = None if open_fence else _line_mark(line)
        is_bold_line = mark is not None and mark.level == BOLD_LINE_LEVEL
        continues_bold_run = is_bold_line and follows_bold_line
        if mark is not None and not continues_bold_run:
            starts.append(SectionStart(line_start, mark.level, mark.heading))
        follows_bold_line = is_bold_line
    return starts


def _is_bold_line(line: str) -> bool:
    mark = _line_mark(line)
    return mark is not None and mark.level == BOLD_LINE_LEVEL


def _has_text_of_its_own(section_text: str, level: int) -> bool:
    """True when a section holds more than its heading line, or more than its opening run of bold lines."""
    filled_lines = [line for line in section_text.splitlines() if line.strip()]
    if level == BOLD_LINE_LEVEL:
        return any(not _is_bold_line(line) for line in filled_lines)
    heading_lines = 1 if level else 0
    return len(filled_lines) > heading_lines


def _without_bold_lines_lacking_text(text: str, starts: List[SectionStart]) -> List[SectionStart]:
    """The section starts minus bold lines with no text under them; those stay in the section they sit in."""
    kept: List[SectionStart] = []
    for number, start in enumerate(starts):
        is_last = number + 1 == len(starts)
        end = len(text) if is_last else starts[number + 1].position
        is_bold_start = start.level == BOLD_LINE_LEVEL
        if is_bold_start and not _has_text_of_its_own(text[start.position:end], BOLD_LINE_LEVEL):
            continue
        kept.append(start)
    return kept


def split_into_sections(text: str) -> List[Section]:
    """The sections of a text in reading order, each with the headings above it; empty when it has no headings."""
    starts = _without_bold_lines_lacking_text(text, _section_starts(text))
    if not starts:
        return []
    opens_with_heading = starts[0].position == 0
    bounds = starts if opens_with_heading else [SectionStart(0, 0, "")] + starts
    sections: List[Section] = []
    open_headings: Dict[int, str] = {}
    for number, start in enumerate(bounds):
        is_last = number + 1 == len(bounds)
        end = len(text) if is_last else bounds[number + 1].position
        if start.level:
            open_headings = {level: heading for level, heading in open_headings.items() if level < start.level}
        if start.heading:
            open_headings[start.level] = start.heading
        path = tuple(open_headings[level] for level in sorted(open_headings))
        sections.append(Section(start.position, end, start.level, start.heading, path))
    return sections


def _chunk_spans(text: str, sections: List[Section], title: Optional[str]) -> List[Section]:
    """Spans of text that become chunks; a heading without text of its own joins the next section with text."""
    spans: List[Section] = []
    waiting: Optional[Section] = None
    for section in sections:
        section_text = text[section.start:section.end].strip()
        has_own_text = _has_text_of_its_own(section_text, section.level) and section_text != title
        if has_own_text:
            start = waiting.start if waiting else section.start
            spans.append(replace(section, start=start))
            waiting = None
            continue
        is_wordless_heading = section.level > 0 and not section.heading
        if section_text and not is_wordless_heading:
            waiting = waiting or section
    if waiting is not None:
        spans.append(replace(waiting, end=len(text)))
    return spans


def _document_title(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    """The title the source gave for this document, if any."""
    title = str((metadata or {}).get(DOCUMENT_TITLE_KEY) or "").strip()
    return title or None


def _label(title: Optional[str], path: Tuple[str, ...]) -> str:
    """The document title and the headings above a chunk, naming the title once."""
    headings = [heading for heading in path if heading != title]
    return PATH_SEPARATOR.join([title, *headings] if title else headings)


class SectionChunker(BaseChunker):
    """Cuts at headings and bold lines; a longer section, or a text without headings, is cut by size."""

    def __init__(self, config: ChunkConfig):
        super().__init__(config)
        size_config = ChunkConfig(type="recursive", chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)
        self.size_chunker = RecursiveChunker(size_config)

    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        if not text.strip():
            return []
        sections = split_into_sections(text)
        if not sections:
            return self.size_chunker.chunk_text(text, metadata)
        title = _document_title(metadata)
        chunks: List[Chunk] = []
        for span in _chunk_spans(text, sections, title):
            chunks.extend(self._span_chunks(text, span, title, len(chunks), metadata))
        return chunks

    def _span_chunks(
        self,
        text: str,
        span: Section,
        title: Optional[str],
        first_index: int,
        metadata: Optional[Dict[str, Any]],
    ) -> List[Chunk]:
        pieces = self._pieces(text[span.start:span.end].strip())
        label = _label(title, span.path)
        chunk_metadata = dict(metadata or {})
        if span.path:
            chunk_metadata["section"] = PATH_SEPARATOR.join(span.path)
        chunks = []
        for number, (piece, start) in enumerate(zip(pieces, self._piece_starts(text, span, pieces))):
            chunk = self._create_chunk(piece, first_index + number, start, chunk_metadata)
            opens_with_label = piece.startswith(label)
            chunk.embedding_text = f"{label}\n\n{piece}" if label and not opens_with_label else None
            chunks.append(chunk)
        return chunks

    def _pieces(self, span_text: str) -> List[str]:
        """The span as one piece, or cut by size when it is longer than the chunk size."""
        if len(span_text) <= self.config.chunk_size:
            return [span_text]
        return self.size_chunker.splitter.split_text(span_text)

    @staticmethod
    def _piece_starts(text: str, span: Section, pieces: List[str]) -> List[int]:
        """Where each piece begins in the whole text."""
        starts: List[int] = []
        search_from = span.start
        for piece in pieces:
            found = text.find(piece, search_from, span.end)
            start = found if found != -1 else search_from
            starts.append(start)
            search_from = start + 1
        return starts
