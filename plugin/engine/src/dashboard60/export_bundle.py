"""Build a 6-sheet Excel export bundle for dashboard60 outputs.

The bundle captures already-materialized tab results.  It intentionally does
not call OpenAI; L2 narrative fields are read from cache only when present.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.dashboard60.data_contract import ensure_dashboard_columns, inquiry_rows, materialize_dashboard_columns, video_summary
from src.dashboard60.inquiry_labels import display_inquiry_label, display_need_signal_label
from src.dashboard60.l2_narrative import DEFAULT_CACHE_DIR, DEFAULT_MODEL, _cache_key, _cluster_payload
from src.dashboard60.scoring import score_improvement_tasks, top_negative_vocs


BUNDLE_FILENAME = "voc_dashboard_export_bundle.xlsx"
SHEET_RAW_VOC = "raw_voc"
SHEET_VIDEO_SUMMARY = "video_summary"
SHEET_INQUIRY_ROWS = "inquiry_rows"
SHEET_IMPROVEMENT_PRIORITY = "improvement_priority"
SHEET_IMPROVEMENT_PRIORITY_COMP = "improvement_priority_comp"
SHEET_IMPROVEMENT_EVIDENCE = "improvement_evidence_and_ai"


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _cache_for_task(
    cluster_row: pd.Series,
    top_vocs: list[dict[str, Any]],
    *,
    cache_dir: str | Path | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    selected_model = model or DEFAULT_MODEL
    payload = _cluster_payload(cluster_row, top_vocs, k=3)
    cache_root = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
    cache_path = cache_root / f"{_cache_key(payload, model=selected_model)}.json"
    return _safe_json(cache_path)


def build_inquiry_export(frame: pd.DataFrame) -> pd.DataFrame:
    inquiry = inquiry_rows(ensure_dashboard_columns(frame)).copy()
    if inquiry.empty:
        for column in ("inquiry_type_display", "need_signal_type_display"):
            inquiry[column] = pd.Series(dtype="object")
        return inquiry
    inquiry["inquiry_type_display"] = inquiry["inquiry_type"].map(display_inquiry_label)
    inquiry["need_signal_type_display"] = inquiry["need_signal_type"].map(display_need_signal_label)
    return inquiry


def build_improvement_evidence_export(
    frame: pd.DataFrame,
    *,
    cache_dir: str | Path | None = None,
    model: str | None = None,
) -> pd.DataFrame:
    safe_frame = materialize_dashboard_columns(frame)
    scored = score_improvement_tasks(safe_frame)
    rows: list[dict[str, Any]] = []
    if scored.empty:
        return pd.DataFrame(
            columns=[
                "product_category",
                "topic",
                "priority_rank",
                "priority_score",
                "evidence_rank",
                "original_voc",
                "rootcause_problem",
                "rootcause_summary",
                "negative_intensity",
                "ai_summary",
                "ai_suggestions",
                "ai_status",
                "ai_cached",
                "ai_model",
            ]
        )

    for priority_rank, (_, cluster) in enumerate(scored.iterrows(), start=1):
        product_category = _safe_text(cluster.get("product_category"))
        topic = _safe_text(cluster.get("topic"))
        examples = top_negative_vocs(safe_frame, product_category, topic, k=3)
        cached = _cache_for_task(cluster, examples, cache_dir=cache_dir, model=model)
        summary = _safe_text(cached.get("summary")) if cached else ""
        suggestions = cached.get("suggestions", []) if cached else []
        if isinstance(suggestions, list):
            suggestions_text = "\n".join(_safe_text(item) for item in suggestions if _safe_text(item))
        else:
            suggestions_text = _safe_text(suggestions)
        ai_status = "AI 서술 생성됨" if summary or suggestions_text else "AI 서술 미생성"
        if not examples:
            examples = [{"original_voc": "", "rootcause_problem": "", "rootcause_summary": "", "negative_intensity": 0}]
        for evidence_rank, evidence in enumerate(examples, start=1):
            rows.append(
                {
                    "product_category": product_category,
                    "topic": topic,
                    "priority_rank": priority_rank,
                    "priority_score": cluster.get("priority_score", 0),
                    "evidence_rank": evidence_rank,
                    "original_voc": _safe_text(evidence.get("original_voc")),
                    "rootcause_problem": _safe_text(evidence.get("rootcause_problem")),
                    "rootcause_summary": _safe_text(evidence.get("rootcause_summary")),
                    "negative_intensity": evidence.get("negative_intensity", 0),
                    "ai_summary": summary,
                    "ai_suggestions": suggestions_text,
                    "ai_status": ai_status,
                    "ai_cached": bool(cached),
                    "ai_model": _safe_text(cached.get("model")) if cached else _safe_text(model or DEFAULT_MODEL),
                }
            )
    return pd.DataFrame(rows)


def build_export_sheets(
    frame: pd.DataFrame,
    *,
    cache_dir: str | Path | None = None,
    model: str | None = None,
) -> dict[str, pd.DataFrame]:
    safe_frame = materialize_dashboard_columns(frame)
    return {
        SHEET_RAW_VOC: safe_frame,
        SHEET_VIDEO_SUMMARY: video_summary(safe_frame),
        SHEET_INQUIRY_ROWS: build_inquiry_export(safe_frame),
        SHEET_IMPROVEMENT_PRIORITY: score_improvement_tasks(safe_frame),
        SHEET_IMPROVEMENT_PRIORITY_COMP: score_improvement_tasks(safe_frame, include_competitors=True),
        SHEET_IMPROVEMENT_EVIDENCE: build_improvement_evidence_export(
            safe_frame,
            cache_dir=cache_dir,
            model=model,
        ),
    }


def write_export_bundle(
    frame: pd.DataFrame,
    output_path: str | Path,
    *,
    cache_dir: str | Path | None = None,
    model: str | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheets = build_export_sheets(frame, cache_dir=cache_dir, model=model)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, sheet_frame in sheets.items():
            clean_sheet = sheet_frame.copy()
            clean_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            worksheet = writer.sheets[sheet_name[:31]]
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                header = str(column_cells[0].value or "")
                width = min(max(len(header) + 2, 12), 48)
                worksheet.column_dimensions[column_cells[0].column_letter].width = width
    return output


def write_bundle_metadata_marker(run_dir: Path, bundle_path: Path) -> None:
    metadata_path = run_dir / "metadata.json"
    metadata = _safe_json(metadata_path)
    metadata["export_bundle"] = {
        "path": str(bundle_path),
        "filename": bundle_path.name,
        "sheets": [
            SHEET_RAW_VOC,
            SHEET_VIDEO_SUMMARY,
            SHEET_INQUIRY_ROWS,
            SHEET_IMPROVEMENT_PRIORITY,
            SHEET_IMPROVEMENT_PRIORITY_COMP,
            SHEET_IMPROVEMENT_EVIDENCE,
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

