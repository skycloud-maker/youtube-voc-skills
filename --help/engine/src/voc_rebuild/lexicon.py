"""Topic evidence lexicon loader for the VoC rebuild engine.

Phase 0.5 only externalizes taxonomy evidence terms. It does not implement the
E1 evidence guard itself; Phase 1 will reuse this loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Iterable

import yaml


DEFAULT_LEXICON_PATH = Path(__file__).resolve().parent / "config" / "topic_evidence_lexicon.yaml"
COMMON_SCOPE = "common"


@dataclass(frozen=True)
class TopicEvidenceEntry:
    label: str
    scope: str
    evidence_terms: tuple[str, ...]
    fallback_only: bool = False
    note: str = ""
    guard_terms: tuple[str, ...] = ()
    exclude_terms: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def exclusions_for(self, term: str) -> tuple[str, ...]:
        for evidence_term, exclusions in self.exclude_terms:
            if evidence_term == term:
                return exclusions
        return ()


@dataclass(frozen=True)
class TopicEvidenceLexicon:
    version: str
    entries: tuple[TopicEvidenceEntry, ...]

    def labels_for_scope(self, scope: str) -> tuple[TopicEvidenceEntry, ...]:
        """Return common labels plus labels dedicated to ``scope``."""

        requested = _normalize_scope(scope)
        return tuple(entry for entry in self.entries if entry.scope in {COMMON_SCOPE, requested})

    def entries_for_label(self, label: str, *, scope: str | None = None) -> tuple[TopicEvidenceEntry, ...]:
        requested = _normalize_scope(scope) if scope else None
        return tuple(
            entry
            for entry in self.entries
            if entry.label == label and (requested is None or entry.scope in {COMMON_SCOPE, requested})
        )

    def entry_for_label(self, label: str, *, scope: str | None = None) -> TopicEvidenceEntry:
        matches = self.entries_for_label(label, scope=scope)
        if not matches:
            scope_hint = f" for scope={scope}" if scope else ""
            raise KeyError(f"Topic evidence label not found: {label}{scope_hint}")
        if scope:
            requested = _normalize_scope(scope)
            exact = [entry for entry in matches if entry.scope == requested]
            if exact:
                return exact[0]
        return matches[0]


def _normalize_scope(scope: str | None) -> str:
    value = (scope or COMMON_SCOPE).strip()
    return value or COMMON_SCOPE


def _string_tuple(values: Iterable[Any], *, field_name: str, label: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} for {label!r} must contain only strings")
        result.append(value)
    return tuple(result)


def _validate_evidence_term(term: str, *, label: str) -> None:
    """Reject taxonomy notes/enumerations that cannot occur verbatim in a VoC."""

    value = term.strip()
    invalid = (
        not value
        or bool(re.search(r"[()]", value))
        or bool(re.search(r"(?:^|\s)등(?:\s|$)", value))
        or ("/" in value and value.upper() != "A/S")
        or (
            any(marker in value for marker in (" 표기", " 제약", " 대비 ", " 예시"))
            and " " in value
        )
    )
    if invalid:
        raise ValueError(f"invalid evidence term for {label!r}: {term!r}")


def _entry_from_payload(payload: dict[str, Any]) -> TopicEvidenceEntry:
    label = payload.get("label")
    scope = payload.get("scope")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Each topic evidence entry must have a non-empty label")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError(f"Topic evidence entry {label!r} must have a non-empty scope")
    evidence_terms = payload.get("evidence_terms", [])
    guard_terms = payload.get("guard_terms", [])
    exclude_terms = payload.get("exclude_terms", {})
    if not isinstance(evidence_terms, list):
        raise ValueError(f"evidence_terms for {label!r} must be a list")
    if not isinstance(guard_terms, list):
        raise ValueError(f"guard_terms for {label!r} must be a list")
    if not isinstance(exclude_terms, dict):
        raise ValueError(f"exclude_terms for {label!r} must be a mapping")
    normalized_evidence_terms = _string_tuple(
        evidence_terms, field_name="evidence_terms", label=label
    )
    for term in normalized_evidence_terms:
        _validate_evidence_term(term, label=label)
    normalized_exclude_terms: list[tuple[str, tuple[str, ...]]] = []
    for term, exclusions in exclude_terms.items():
        if term not in normalized_evidence_terms:
            raise ValueError(f"exclude_terms key for {label!r} is not an evidence term: {term!r}")
        if not isinstance(exclusions, list):
            raise ValueError(f"exclude_terms[{term!r}] for {label!r} must be a list")
        normalized_exclude_terms.append(
            (
                term,
                _string_tuple(exclusions, field_name=f"exclude_terms[{term!r}]", label=label),
            )
        )
    return TopicEvidenceEntry(
        label=label.strip(),
        scope=scope.strip(),
        evidence_terms=normalized_evidence_terms,
        fallback_only=bool(payload.get("fallback_only", False)),
        note=str(payload.get("note", "") or ""),
        guard_terms=_string_tuple(guard_terms, field_name="guard_terms", label=label),
        exclude_terms=tuple(normalized_exclude_terms),
    )


@lru_cache(maxsize=4)
def load_topic_evidence_lexicon(path: str | Path | None = None) -> TopicEvidenceLexicon:
    """Load the topic evidence lexicon YAML.

    The return shape is intentionally simple so Phase 1 can add matching logic
    without changing the YAML contract.
    """

    lexicon_path = Path(path) if path is not None else DEFAULT_LEXICON_PATH
    with lexicon_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Topic evidence lexicon must be a mapping: {lexicon_path}")
    entries_payload = payload.get("labels")
    if not isinstance(entries_payload, list):
        raise ValueError(f"Topic evidence lexicon must contain a labels list: {lexicon_path}")
    entries = tuple(_entry_from_payload(item) for item in entries_payload if isinstance(item, dict))
    if len(entries) != len(entries_payload):
        raise ValueError("Every item in topic evidence labels must be a mapping")
    return TopicEvidenceLexicon(version=str(payload.get("version", "") or ""), entries=entries)


def get_labels_for_scope(scope: str, path: str | Path | None = None) -> tuple[TopicEvidenceEntry, ...]:
    return load_topic_evidence_lexicon(path).labels_for_scope(scope)


def get_topic_evidence_terms(label: str, *, scope: str | None = None, path: str | Path | None = None) -> tuple[str, ...]:
    return load_topic_evidence_lexicon(path).entry_for_label(label, scope=scope).evidence_terms


def get_price_value_guard_terms(path: str | Path | None = None) -> tuple[str, ...]:
    entry = load_topic_evidence_lexicon(path).entry_for_label("가격/가성비", scope=COMMON_SCOPE)
    return entry.guard_terms or entry.evidence_terms


def get_evidence_excludes(term: str, path: str | Path | None = None) -> tuple[str, ...]:
    """Return all declared compound exclusions for one evidence term."""

    exclusions: list[str] = []
    for entry in load_topic_evidence_lexicon(path).entries:
        for exclusion in entry.exclusions_for(term):
            if exclusion not in exclusions:
                exclusions.append(exclusion)
    return tuple(exclusions)

