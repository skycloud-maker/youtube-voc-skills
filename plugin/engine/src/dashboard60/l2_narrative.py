"""Optional L2 narrative layer for improvement-task clusters.

This module is intentionally separate from deterministic L1 scoring.  L2 may
call an LLM to explain already-scored clusters, but it never changes L1 scores,
ordering, or dashboard eligibility.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_MODEL = "gpt-4o-mini"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "outputs" / ".l2_cache"
PROMPT_VERSION = "ko-only-v2"


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _number(value: Any) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cluster_payload(cluster_row: Any, top_vocs: list[dict[str, Any]], *, k: int) -> dict[str, Any]:
    if hasattr(cluster_row, "to_dict"):
        row = cluster_row.to_dict()
    else:
        row = dict(cluster_row)
    cluster = {
        "product_category": _text(row.get("product_category")),
        "topic": _text(row.get("topic")),
        "n": int(_number(row.get("n"))),
        "neg_count": int(_number(row.get("neg_count"))),
        "neg_ratio": _number(row.get("neg_ratio")),
        "mean_neg": _number(row.get("mean_neg")),
        "rc_coverage": _number(row.get("rc_coverage")),
        "priority_score": _number(row.get("priority_score")),
    }
    evidence = []
    for voc in list(top_vocs or [])[:k]:
        evidence.append(
            {
                "original_voc": _text(voc.get("original_voc")),
                "rootcause_problem": _text(voc.get("rootcause_problem")),
                "rootcause_summary": _text(voc.get("rootcause_summary")),
                "negative_intensity": _number(voc.get("negative_intensity")),
            }
        )
    return {"cluster": cluster, "top_vocs": evidence}


def _cache_key(payload: dict[str, Any], *, model: str) -> str:
    raw = json.dumps(
        {"model": model, "prompt_version": PROMPT_VERSION, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_json_loads(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _resolve_api_key() -> str:
    """Resolve OpenAI API key for Streamlit Cloud first, then local/CI env."""

    try:
        import streamlit as st  # type: ignore

        try:
            value = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            value = ""
        if value and str(value).strip():
            return str(value).strip()
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY", "").strip()


def api_key_available() -> bool:
    """Return whether L2 can attempt an OpenAI call in the current runtime."""

    return bool(_resolve_api_key())


def _call_openai_json(
    system_prompt: str,
    user_payload: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    """Call OpenAI Chat Completions and return a JSON object.

    Kept small and isolated so tests can monkeypatch this function without any
    external API access.
    """

    api_key = _resolve_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        raise RuntimeError(f"OpenAI SDK is not available: {exc}") from exc

    client = OpenAI(api_key=api_key, timeout=60, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
            },
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    return _safe_json_loads(content)


def _normalize_success_result(
    payload: dict[str, Any],
    *,
    summary_result: dict[str, Any],
    suggestions_result: dict[str, Any],
    model: str,
    cached: bool = False,
) -> dict[str, Any]:
    summary = _text(summary_result.get("summary"))
    raw_suggestions = suggestions_result.get("suggestions", [])
    if isinstance(raw_suggestions, str):
        suggestions = [raw_suggestions]
    elif isinstance(raw_suggestions, list):
        suggestions = [_text(item) for item in raw_suggestions if _text(item)]
    else:
        suggestions = []
    return {
        "summary": summary or None,
        "suggestions": suggestions,
        "grounded_vocs": payload["top_vocs"],
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": cached,
        "error": None,
    }


def summarize_task(
    cluster_row: Any,
    top_vocs: list[dict[str, Any]],
    *,
    k: int = 3,
    cache_dir: str | Path | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Generate an optional L2 narrative for one L1 improvement-task cluster.

    Returns a safe object on any failure.  Callers should treat L1 scores as the
    source of truth regardless of this output.
    """

    selected_model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
    payload = _cluster_payload(cluster_row, top_vocs, k=k)
    cache_root = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
    key = _cache_key(payload, model=selected_model)
    cache_path = cache_root / f"{key}.json"

    if cache_path.exists():
        try:
            cached_value = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached_value, dict):
                cached_value["cached"] = True
                return cached_value
        except Exception:
            pass

    summary_prompt = (
        "너는 한국어 VoC 개선과제 대시보드의 사실 요약 작성자다. "
        "반드시 한국어로만 작성한다. 영어 단어/문장은 제품명·브랜드명처럼 입력 근거에 있는 고유명사일 때만 허용한다. "
        "제공된 cluster metrics, representative VoCs, rootcause fields만 근거로 사용한다. "
        "새로운 사실, 숫자, 제품, 원인, 비즈니스 주장을 지어내지 않는다. "
        "대표 VoC나 rootcause에 리뷰어·유튜버의 테스트 방식, 시연, 영상 설명에 대한 비판이 섞여 있으면 "
        "이를 제품 자체의 결함·내구성 문제로 단정하지 말고, 참고용 리뷰/검증 방식 의견으로만 표현한다. "
        "2~3문장의 한국어 사실 요약만 작성한다. "
        "Return JSON only: {\"summary\": \"근거 기반 한국어 요약\"}."
    )
    suggestions_prompt = (
        "너는 같은 VoC 군집에 대한 선택형 실험 제안을 작성한다. "
        "반드시 한국어로만 작성한다. 영어 단어/문장은 제품명·브랜드명처럼 입력 근거에 있는 고유명사일 때만 허용한다. "
        "사실 요약과 섞지 말고, 제공된 VoC의 구체 pain point를 겨냥한 개선 아이디어 2~3개만 작성한다. "
        "리뷰/검증 방식 비판은 제품 결함 개선안이 아니라 콘텐츠/검증 커뮤니케이션 개선 가설로 분리한다. "
        "확실하지 않은 내용은 반드시 '가설:'로 표시한다. "
        "Return JSON only: {\"suggestions\": [\"한국어 제안\", \"한국어 제안\"]}."
    )

    try:
        summary_result = _call_openai_json(summary_prompt, payload, model=selected_model)
        suggestions_result = _call_openai_json(suggestions_prompt, payload, model=selected_model)
        result = _normalize_success_result(
            payload,
            summary_result=summary_result,
            suggestions_result=suggestions_result,
            model=selected_model,
        )
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception as exc:
        return {
            "summary": None,
            "suggestions": [],
            "grounded_vocs": payload["top_vocs"],
            "model": selected_model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
            "error": str(exc),
        }
