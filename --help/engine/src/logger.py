"""Structured logging configuration."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.utils.secret_filter import install_secret_filter
from typing import Any


class JsonFormatter(logging.Formatter):
    """Serialize log records as JSON for easy downstream parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("run_id", "stage", "endpoint", "video_id", "page_token"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)



def setup_logging(log_dir: Path, log_level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(log_level.upper())
    log_dir.mkdir(parents=True, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(log_dir / "pipeline.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    # ★ API 키가 로그에 남지 않게 막는다 (sky 2026-08-21).
    #   로니 실분석 로그에 YouTube 키가 평문으로 찍혀 있었다 —
    #   requests 의 HTTPError 메시지에 요청 URL 이 통째로 들어가고,
    #   retry 가 traceback 을 찍으면서 그대로 파일에 남았다.
    #   그 로그는 「진단 파일 zip」 으로 누구나 받는다.
    install_secret_filter()
