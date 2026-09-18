"""Execution-level scope request terms for R-C2-03."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml


DEFAULT_SCOPE_REQUEST_CONFIG_PATH = (
    Path(__file__).resolve().parent / "config" / "scope_request_terms.yaml"
)


def _normalize_terms(values: object) -> tuple[str, ...]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError("out_of_scope_products must be a list of strings")
    terms = tuple(value.strip() for value in values if value.strip())
    if "청소기" in terms:
        raise ValueError("bare 청소기 is forbidden; use compound product names")
    forbidden = {"스마트코티지", "모듈러하우스", "세컨하우스"}
    overlap = forbidden.intersection(terms)
    if overlap:
        raise ValueError(f"in-scope smart-cottage terms cannot be excluded: {sorted(overlap)}")
    return terms


@lru_cache(maxsize=4)
def load_out_of_scope_products(path: str | Path | None = None) -> tuple[str, ...]:
    """Load defaults, with an optional per-run environment override."""

    env_terms = os.getenv("VOC_OUT_OF_SCOPE_PRODUCTS", "").strip()
    if path is None and env_terms:
        return _normalize_terms([value for value in env_terms.split(",")])
    config_path = Path(path) if path is not None else DEFAULT_SCOPE_REQUEST_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"scope request config must be a mapping: {config_path}")
    return _normalize_terms(payload.get("out_of_scope_products", []))
