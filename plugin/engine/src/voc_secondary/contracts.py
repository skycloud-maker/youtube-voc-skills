"""Read-only validation of the frozen Phase-1 66-column output."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable
import re

from src.voc_rebuild.schema import ENUM_COLUMNS, TARGET_COLUMNS


SOURCE_LEVEL_COLUMNS = (
    "source_id", "raw_row_index", "parent_voc_id", "comment_relation",
    "original_voc", "voc_cleaned", "voc_residual", "reference_brand",
    "market", "language", "source_context_summary", "status",
    "scope_exclusion_reason", "proposal_flag", "video_id", "video_title",
    "video_url", "product_category", "product_category_source",
)


def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _atomic_sort_key(row: dict[str, str]) -> tuple[int, str]:
    raw = str(row.get("atomic_index") or "")
    match = re.search(r"\d+", raw)
    return (int(match.group()) if match else 10**9, str(row.get("atomic_id") or ""))


def _group_preservation_errors(group: list[dict[str, str]]) -> list[str]:
    cleaned = str(group[0].get("voc_cleaned") or "")
    used = [False] * len(cleaned)
    cursor = 0
    errors: list[str] = []
    for row in sorted(group, key=_atomic_sort_key):
        atomic = str(row.get("atomic_voc") or "")
        start = cleaned.find(atomic, cursor)
        if start < 0:
            starts = [m.start() for m in re.finditer(re.escape(atomic), cleaned)] if atomic else []
            starts = [candidate for candidate in starts if not any(used[candidate:candidate + len(atomic)])]
            if len(starts) != 1:
                errors.append(f"atomic_span_unresolved:{row.get('atomic_id','')}")
                continue
            start = starts[0]
        end = start + len(atomic)
        if any(used[start:end]):
            errors.append(f"atomic_span_overlap:{row.get('atomic_id','')}")
            continue
        for index in range(start, end):
            used[index] = True
        cursor = end
    leftover = "".join(char for index, char in enumerate(cleaned) if not used[index])
    residual = str(group[0].get("voc_residual") or "")
    if _compact_whitespace(leftover) != _compact_whitespace(residual):
        errors.append("atomic_plus_residual_not_preserved")
    return errors


def validate_contract(rows: list[dict[str, str]], fieldnames: Iterable[str]) -> dict[str, object]:
    ids = [str(row.get("atomic_id") or "").strip() for row in rows]
    counts = Counter(ids)
    v01 = [
        {"atomic_id": atomic_id, "reason": "missing" if not atomic_id else "duplicate"}
        for atomic_id, count in counts.items()
        if not atomic_id or count > 1
    ]

    actual_columns = list(fieldnames)
    column_errors: list[dict[str, object]] = []
    if actual_columns != TARGET_COLUMNS:
        column_errors.append({
            "reason": "column_set_or_order_mismatch",
            "missing": [column for column in TARGET_COLUMNS if column not in actual_columns],
            "extra": [column for column in actual_columns if column not in TARGET_COLUMNS],
            "actual_count": len(actual_columns),
        })
    enum_counts: Counter[str] = Counter()
    enum_examples: list[dict[str, str]] = []
    for row in rows:
        for column, allowed in ENUM_COLUMNS.items():
            value = str(row.get(column) or "").strip()
            if column == "scope_exclusion_reason" and not value and row.get("status") != "scope_excluded":
                continue
            if value not in allowed:
                enum_counts[column] += 1
                if len(enum_examples) < 50:
                    enum_examples.append({"atomic_id": row.get("atomic_id", ""), "column": column, "value": value})
    if enum_counts:
        column_errors.append({"reason": "enum_violation", "counts": dict(enum_counts), "examples": enum_examples})

    v03 = [
        {"atomic_id": row.get("atomic_id", ""), "reason": "atomic_not_substring"}
        for row in rows
        if str(row.get("status") or "") != "scope_excluded"
        if str(row.get("atomic_voc") or "") not in str(row.get("voc_cleaned") or "")
    ]

    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_source[str(row.get("source_id") or "")].append(row)
    v04: list[dict[str, object]] = []
    v05: list[dict[str, object]] = []
    for source_id, group in by_source.items():
        preservation = (
            [] if all(str(row.get("status") or "") == "scope_excluded" for row in group)
            else _group_preservation_errors(group)
        )
        if preservation:
            v04.append({"source_id": source_id, "errors": preservation})
        baseline = group[0]
        differing = [
            column for column in SOURCE_LEVEL_COLUMNS
            if len({str(row.get(column) or "") for row in group}) > 1
        ]
        if differing:
            v05.append({"source_id": source_id, "columns": differing})

    checks = {
        "V-0-1": {"violations": len(v01), "details": v01},
        "V-0-2": {"violations": len(column_errors), "details": column_errors},
        "V-0-3": {"violations": len(v03), "details": v03},
        "V-0-4": {"violations": len(v04), "details": v04},
        "V-0-5": {"violations": len(v05), "details": v05},
    }
    return {
        "rows": len(rows),
        "sources": len(by_source),
        "checks": checks,
        "fatal": bool(v01 or column_errors),
    }
