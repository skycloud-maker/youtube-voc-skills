"""Optional LLM adapter for Golden120 semantic card interpretation.

The default dashboard/CLI path must remain safe without network access or
provider credentials.  This module therefore exposes a disabled/payload-only
mode by default and only attempts an OpenAI call when explicitly configured.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Golden120SemanticInterpreterConfig:
    provider: str = "payload"
    model: str = "gpt-4o-mini"
    max_cards: int = 0
    temperature: float = 0.0


def build_semantic_interpreter_config(scope: Mapping[str, Any] | None = None) -> Golden120SemanticInterpreterConfig:
    payload = scope or {}
    provider = str(payload.get("semantic_interpreter_provider") or "payload").strip().lower()
    model = str(payload.get("semantic_interpreter_model") or "gpt-4o-mini").strip()
    try:
        max_cards = int(payload.get("semantic_interpreter_max_cards") or 0)
    except (TypeError, ValueError):
        max_cards = 0
    return Golden120SemanticInterpreterConfig(
        provider=provider if provider in {"disabled", "payload", "openai"} else "payload",
        model=model or "gpt-4o-mini",
        max_cards=max(0, max_cards),
    )


def interpret_golden120_semantic_payloads(
    prompt_payloads: list[dict[str, Any]],
    *,
    config: Golden120SemanticInterpreterConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Interpret prompt payloads when an explicit provider is configured.

    Returns `(outputs, diagnostics)`.  In payload-only mode, outputs are empty
    and diagnostics explain that no external model call was attempted.
    """

    if config.provider == "disabled":
        return [], _diagnostics(
            status="disabled",
            provider=config.provider,
            model=config.model,
            attempted=0,
            succeeded=0,
            failed=0,
            message="Semantic interpreter is disabled; only projection/rule heuristic cards are used.",
        )
    if config.provider == "payload":
        return [], _diagnostics(
            status="payload_only",
            provider=config.provider,
            model=config.model,
            attempted=0,
            succeeded=0,
            failed=0,
            message="Prompt payloads were written for later LLM interpretation; no external API call was attempted.",
        )
    if config.provider != "openai":
        return [], _diagnostics(
            status="unsupported_provider",
            provider=config.provider,
            model=config.model,
            attempted=0,
            succeeded=0,
            failed=0,
            message=f"Unsupported semantic interpreter provider: {config.provider}",
        )

    api_key = _openai_api_key()
    if not api_key:
        return [], _diagnostics(
            status="missing_api_key",
            provider=config.provider,
            model=config.model,
            attempted=0,
            succeeded=0,
            failed=0,
            message="OPENAI_API_KEY is not set; semantic LLM interpretation was skipped.",
        )

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional local package
        return [], _diagnostics(
            status="missing_sdk",
            provider=config.provider,
            model=config.model,
            attempted=0,
            succeeded=0,
            failed=0,
            message=f"OpenAI SDK is not available: {exc}",
        )

    client = OpenAI(api_key=api_key)
    selected_payloads = prompt_payloads[: config.max_cards] if config.max_cards else prompt_payloads
    outputs: list[dict[str, Any]] = []
    failures = 0
    for payload in selected_payloads:
        try:  # pragma: no cover - network/provider call is opt-in
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                messages=[
                    {"role": "system", "content": str(payload.get("system_prompt", ""))},
                    {"role": "user", "content": str(payload.get("user_prompt", ""))},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            parsed = _parse_json_object(content)
            outputs.append(
                {
                    "atomic_unit_id": payload.get("atomic_unit_id", ""),
                    "provider": config.provider,
                    "model": config.model,
                    "status": "succeeded",
                    "result": parsed,
                }
            )
        except Exception as exc:  # pragma: no cover - network/provider call is opt-in
            failures += 1
            outputs.append(
                {
                    "atomic_unit_id": payload.get("atomic_unit_id", ""),
                    "provider": config.provider,
                    "model": config.model,
                    "status": "failed",
                    "error": str(exc),
                }
            )
    return outputs, _diagnostics(
        status="completed" if failures == 0 else "completed_with_failures",
        provider=config.provider,
        model=config.model,
        attempted=len(selected_payloads),
        succeeded=len(selected_payloads) - failures,
        failed=failures,
        message="OpenAI semantic interpreter call completed.",
    )


def _openai_api_key() -> str:
    env_value = os.getenv("OPENAI_API_KEY", "").strip()
    if env_value:
        return env_value
    if os.getenv("GOLDEN120_LOAD_DOTENV", "1").strip().lower() in {"0", "false", "no"}:
        return ""
    try:
        from dotenv import dotenv_values  # type: ignore
    except Exception:
        return ""

    candidate_paths: list[Path] = []
    cwd_env = Path.cwd() / ".env"
    repo_env = Path(__file__).resolve().parents[3] / ".env"
    for path in (cwd_env, repo_env):
        if path not in candidate_paths:
            candidate_paths.append(path)
    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            value = dotenv_values(path).get("OPENAI_API_KEY", "")
        except Exception:
            continue
        key = str(value or "").strip()
        if key:
            return key
    return ""


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {"raw_content": content, "parse_error": "invalid_json"}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _diagnostics(
    *,
    status: str,
    provider: str,
    model: str,
    attempted: int,
    succeeded: int,
    failed: int,
    message: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "model": model,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "message": message,
    }
