from pathlib import Path
import re
import logging
from app.modules.data.utils import FileTextExtractor
import pytest

logger = logging.getLogger(__name__)
TEXT_DIR = Path(__file__).parent / "test_files"
TARGET_SUFFIXES = {".pdf", ".doc", ".docx", ".html", ".htm", ".txt"}

# Expected sentence per type (fill with your known content)
EXPECTED_BY_SUFFIX = {
    ".txt":  "Quod equidem non reprehendo;",
    ".html": "Artificial intelligence",
    ".docx": "Lorem ipsum",
    ".doc":  "Lorem ipsum dolor sit amet",
    ".pdf":  "Lorem ipsum",
}

def _normalize(s: str) -> str:
    # resilient to whitespace, soft hyphens, and line-wrapped hyphenation
    s = s.replace("\u00AD", "")                 # soft hyphen
    s = re.sub(r"-\s*\n\s*", "", s)            # hyphenation across line breaks
    s = re.sub(r"\s+", " ", s)                 # collapse whitespace
    return s.strip().lower()

@pytest.mark.skip(reason="Skipping for now — it is failing from libraries in new server")
def test_text_extractor_on_samples_by_path():
    assert TEXT_DIR.exists(), f"Missing test_files directory: {TEXT_DIR}"

    samples = sorted(p for p in TEXT_DIR.iterdir() if p.is_file() and p.suffix.lower() in TARGET_SUFFIXES)
    assert samples, f"No target files found in {TEXT_DIR}"

    for p in samples:
        extracted = FileTextExtractor().extract(path=str(p))
        logger.debug(f"Extracted text data: {extracted}")
        assert isinstance(extracted, str), f"{p.name}: extractor did not return str"

        ext = p.suffix.lower()
        text_norm = _normalize(extracted)

        # Always non-empty for our target types
        assert text_norm, f"{p.name}: empty extraction for {ext}"

        # Assert the expected sentence appears
        expected = EXPECTED_BY_SUFFIX.get(ext) or (EXPECTED_BY_SUFFIX.get(".html") if ext == ".htm" else None)
        if expected:
            assert _normalize(expected) in text_norm, (
                f"{p.name}: missing expected text for {ext}: {expected!r}\n"
                f"Got (first 300 chars): {extracted[:300]!r}"
            )
