"""Analyst topic lists ("Topic" or "Topic > Subtopic" entries) and the guard that keeps LLM verdicts on them"""

from dataclasses import dataclass
from typing import Any, Iterable

from app.core.utils.enums.conversation_topic_enum import ConversationTopic

TOPIC_SEPARATOR = ">"


@dataclass(frozen=True)
class TopicSpec:
    name: str
    subtopics: tuple[str, ...] = ()


DEFAULT_TOPIC_SPECS = tuple(TopicSpec(topic.value) for topic in ConversationTopic)


def _key(value: str) -> str:
    return value.strip().casefold()


def _collect(pairs: Iterable[tuple[str, str]]) -> list[TopicSpec]:
    topics: dict[str, tuple[str, dict[str, str]]] = {}
    for name, subtopic in pairs:
        _, subtopics = topics.setdefault(_key(name), (name, {}))
        if subtopic:
            subtopics.setdefault(_key(subtopic), subtopic)
    return [TopicSpec(name, tuple(subtopics.values())) for name, subtopics in topics.values()]


def configured_topic_specs(settings: Any) -> list[TopicSpec]:
    """Splits each entry on the first separator; empty when nothing usable is set"""
    topics = settings.get("topics") if isinstance(settings, dict) else None
    pairs = []
    for entry in topics if isinstance(topics, list) else []:
        if not isinstance(entry, str):
            continue
        name, _, subtopic = entry.partition(TOPIC_SEPARATOR)
        if name.strip():
            pairs.append((name.strip(), subtopic.strip()))
    return _collect(pairs)


def parse_topic_settings(settings: Any) -> list[TopicSpec]:
    return configured_topic_specs(settings) or list(DEFAULT_TOPIC_SPECS)


def topics_csv(specs: Iterable[TopicSpec], *, include_subtopics: bool = False) -> str:
    if not include_subtopics:
        return ", ".join(spec.name for spec in specs)
    return ", ".join(
        f"{spec.name} (sub-topics: {', '.join(spec.subtopics)})" if spec.subtopics else spec.name for spec in specs
    )


def merge_topic_specs(spec_lists: Iterable[list[TopicSpec]]) -> list[TopicSpec]:
    return _collect(
        (spec.name, subtopic) for specs in spec_lists for spec in specs for subtopic in ("", *spec.subtopics)
    )


def _match(value: str, options: Iterable[str]) -> str:
    key = _key(value)
    return next((option for option in options if _key(option) == key), "")


def normalize_topic_verdict(title: str, subtopic: str, specs: list[TopicSpec]) -> tuple[str, str]:
    """Unknown titles stay verbatim, unknown sub-topics become "", and "Topic > Sub" titles are split"""
    specs_by_key = {_key(spec.name): spec for spec in specs}
    spec = specs_by_key.get(_key(title))
    if spec is None and TOPIC_SEPARATOR in title:
        head, _, tail = title.partition(TOPIC_SEPARATOR)
        spec = specs_by_key.get(_key(head))
        if spec is not None and not _match(subtopic, spec.subtopics):
            subtopic = tail
    if spec is None:
        return title, ""
    return spec.name, _match(subtopic, spec.subtopics)
