"""Unit tests for the compact transcript sent to the conversation analyst"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.utils.transcript_utils import (
    count_scorable_customer_messages,
    is_scorable_customer_message,
    transcript_messages_to_lines,
)

START = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)


def _msg(speaker, text, create_time=None, type="message"):
    return SimpleNamespace(speaker=speaker, text=text, create_time=create_time, type=type)


@pytest.mark.parametrize(
    "speaker, text, type, expected",
    [
        ("customer", "hi", "message", True),
        ("User", "hi", "message", True),
        ("caller", "hi", "message", True),
        (None, "hi", "message", True),
        ("customer", "transcribed words", "audio", True),
        ("agent", "hi", "message", False),
        ("Assistant", "hi", "message", False),
        ("bot", "hi", "message", False),
        ("customer", "   ", "message", False),
        ("customer", "[Voice message]", "audio", False),
        ("customer", "[Voice message]", "message", False),
        ("user", '{"url": "https://x/f.pdf"}', "file", False),
        ("agent", '{"fields": []}', "form_request", False),
        ("", "", "takeover", False),
    ],
)
def test_only_non_agent_conversational_text_is_scorable(speaker, text, type, expected):
    assert is_scorable_customer_message(_msg(speaker, text, type=type)) is expected


def test_scorable_customer_messages_are_counted_per_update():
    messages = [
        _msg("customer", "hi"),
        _msg("agent", "hello"),
        _msg("user", '{"url": "https://x/f.pdf"}', type="file"),
        _msg("customer", "[Voice message]", type="audio"),
        _msg("caller", "still here"),
    ]
    assert count_scorable_customer_messages(messages) == 2
    assert count_scorable_customer_messages([]) == 0


def test_lines_normalise_speakers_collapse_whitespace_and_skip_empty_rows():
    messages = [
        _msg("User", "  hi\n there ", START),
        _msg("bot", "hello"),
        _msg("agent", "   "),
        _msg("caller", "still here"),
        _msg(None, "who?"),
    ]
    assert transcript_messages_to_lines(messages) == (
        "customer: hi there\nagent: hello\ncaller: still here\nunknown: who?"
    )


def test_offsets_count_from_the_first_timestamped_message():
    messages = [
        _msg("agent", "welcome"),
        _msg("customer", "hi", START),
        _msg("agent", "how can I help?", START + timedelta(minutes=12, seconds=34)),
        _msg("customer", "typed on a slow clock", START - timedelta(seconds=90)),
        _msg("customer", "back next day", START + timedelta(hours=26, seconds=5)),
    ]
    assert transcript_messages_to_lines(messages, include_offset=True).splitlines() == [
        "agent: welcome",
        "[+0:00:00] customer: hi",
        "[+0:12:34] agent: how can I help?",
        "[+0:00:00] customer: typed on a slow clock",
        "[+26:00:05] customer: back next day",
    ]
