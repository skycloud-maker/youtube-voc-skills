"""Observation-only AnalysisRun manifest sidecar for successful legacy analysis."""

from __future__ import annotations

import logging
from pathlib import Path

from src.application.shadow.contracts import ShadowSidecarFailureLog
from src.application.shadow.legacy_collection_mapper import FilesystemLegacyCollectionMapper
from src.domain.digests import canonical_json_digest, sha256_digest
from src.domain.runs import AnalysisKind, AnalysisRun, RunStatus, utc_now
from src.infrastructure.storage.filesystem import FilesystemAnalysisRunRepository

UNKNOWN_CODE_COMMIT = "unknown"


def legacy_analysis_dataset_fingerprint(run_dir: str | Path) -> str:
    """Fingerprint exact legacy analysis input bytes without changing legacy files."""

    root = Path(run_dir)
    descriptors: list[dict[str, object]] = []
    for stem in ("videos_raw", "comments_raw"):
        path = _existing_input_path(root, stem)
        if path is None:
            continue
        payload = path.read_bytes()
        descriptors.append(
            {
                "input_name": stem,
                "filename": path.name,
                "byte_length": len(payload),
                "content_digest": sha256_digest(payload),
            }
        )
    return canonical_json_digest(descriptors)


def _existing_input_path(run_dir: Path, stem: str) -> Path | None:
    for suffix in (".parquet", ".csv"):
        candidate = run_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


class AnalysisRunSidecar:
    """Append one canonical AnalysisRun beside a successful legacy execution."""

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        self._repository = FilesystemAnalysisRunRepository(canonical_shadow_root)
        self._mapper = FilesystemLegacyCollectionMapper(canonical_shadow_root)

    def observe_legacy_analysis(
        self,
        *,
        legacy_run_id: str,
        run_dir: str | Path,
        analysis_kind: AnalysisKind,
    ) -> AnalysisRun:
        """Resolve existing collection lineage and append one fresh AnalysisRun."""

        mapping = self._mapper.resolve_existing(legacy_run_id)
        run = AnalysisRun(
            collection_run_id=mapping.collection_run_id,
            analysis_kind=analysis_kind,
            pipeline_version="legacy-analytics-pipeline-v1",
            schema_bundle_version="legacy-processed-inputs-v1",
            code_commit=UNKNOWN_CODE_COMMIT,
            dataset_fingerprint=legacy_analysis_dataset_fingerprint(run_dir),
            status=RunStatus.SUCCEEDED,
            finished_at=utc_now(),
            legacy_ids=(legacy_run_id,),
        )
        return self._repository.create_analysis_run(run)


def observe_legacy_analysis_safely(
    *,
    sidecar: AnalysisRunSidecar,
    logger: logging.Logger,
    legacy_run_id: str,
    run_dir: str | Path,
    analysis_kind: AnalysisKind,
) -> AnalysisRun | None:
    """Observe analysis without changing the authoritative legacy result."""

    try:
        run = sidecar.observe_legacy_analysis(
            legacy_run_id=legacy_run_id,
            run_dir=run_dir,
            analysis_kind=analysis_kind,
        )
    except Exception as exc:
        failure = ShadowSidecarFailureLog.from_exception(
            operation="analysis_run_observation",
            error=exc,
            legacy_run_id=legacy_run_id,
            details={"run_dir": str(Path(run_dir)), "analysis_kind": analysis_kind.value},
        )
        logger.warning(
            "AnalysisRun sidecar observation failed",
            extra={"shadow_failure": failure.model_dump(mode="json")},
        )
        return None

    logger.info(
        "AnalysisRun sidecar observation completed",
        extra={
            "legacy_run_id": legacy_run_id,
            "analysis_run_id": run.analysis_run_id,
            "collection_run_id": run.collection_run_id,
        },
    )
    return run
