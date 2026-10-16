"""Unit tests for analyst topic-list parsing and the topic verdict guard"""

import pytest

from app.core.utils.topic_settings import (
    DEFAULT_TOPIC_SPECS,
    TopicSpec,
    merge_topic_specs,
    normalize_topic_verdict,
    parse_topic_settings,
    topics_csv,
)

SPECS = [
    TopicSpec("Payment issue", ("Declined payment", "Unexpected charges")),
    TopicSpec("Refund", ("Wrong plate",)),
    TopicSpec("Other"),
]


@pytest.mark.parametrize("settings", [None, {}, {"topics": []}, {"topics": "A, B"}, {"topics": [">", " ", 3]}, "x"])
def test_missing_or_unusable_lists_fall_back_to_the_defaults(settings):
    assert parse_topic_settings(settings) == list(DEFAULT_TOPIC_SPECS)


def test_entries_are_grouped_trimmed_and_deduplicated_in_order():
    topics = [
        "Refund > Wrong plate",
        " Payment issue ",
        "payment issue > Declined payment",
        "Refund",
        "REFUND >  wrong PLATE",
        "A >",
        "B > B1 > x",
    ]
    assert parse_topic_settings({"topics": topics}) == [
        TopicSpec("Refund", ("Wrong plate",)),
        TopicSpec("Payment issue", ("Declined payment",)),
        TopicSpec("A"),
        TopicSpec("B", ("B1 > x",)),
    ]


def test_topics_csv_lists_sub_topics_only_when_asked():
    assert topics_csv(SPECS) == "Payment issue, Refund, Other"
    assert topics_csv(SPECS, include_subtopics=True) == (
        "Payment issue (sub-topics: Declined payment, Unexpected charges), Refund (sub-topics: Wrong plate), Other"
    )


def test_merge_keeps_the_first_spelling_and_unions_sub_topics():
    merged = merge_topic_specs(
        [
            [TopicSpec("Refund", ("Wrong plate",))],
            [TopicSpec("refund", ("Duplicate", "wrong plate")), TopicSpec("Other")],
        ]
    )
    assert merged == [TopicSpec("Refund", ("Wrong plate", "Duplicate")), TopicSpec("Other")]


@pytest.mark.parametrize(
    "title, subtopic, expected",
    [
        ("payment issue", "declined PAYMENT", ("Payment issue", "Declined payment")),
        ("Payment issue", "Wrong plate", ("Payment issue", "")),
        ("Billing", "Declined payment", ("Billing", "")),
        ("", "", ("", "")),
        ("Payment issue > Declined payment", "", ("Payment issue", "Declined payment")),
        ("payment issue > nope", "", ("Payment issue", "")),
        ("Payment issue > Declined payment", "Unexpected charges", ("Payment issue", "Unexpected charges")),
        ("Unknown > x", "", ("Unknown > x", "")),
    ],
)
def test_verdict_is_mapped_onto_the_configured_list(title, subtopic, expected):
    assert normalize_topic_verdict(title, subtopic, SPECS) == expected
