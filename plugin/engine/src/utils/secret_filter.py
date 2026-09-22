# -*- coding: utf-8 -*-
"""로그에 API 키가 찍히지 않게 막는다.

★ 왜 (sky 2026-08-21)
  로니 실분석 로그(`_runner_stderr.log`)에 YouTube API 키가 평문으로 남았다.

      403 Client Error: Forbidden for url:
      https://www.googleapis.com/youtube/v3/commentThreads?...&key=AIzaSy...

  requests 가 만드는 HTTPError 메시지에 요청 URL 이 통째로 들어가고,
  retry.py 가 `logger.error(..., exc_info=exc)` 로 traceback 을 찍으면서
  그 URL 이 그대로 파일에 남았다.

  ★ 이 로그는 화면의 「진단 파일 4종 zip」 으로 누구나 받는다.
    실무자가 문제 생겨 그 zip 을 보내면 키가 함께 나간다.

★ 왜 여기서 막나
  키가 새는 자리를 하나씩 찾아 고치면 다음에 또 새는 곳이 생긴다.
  로그가 파일로 나가는 길목은 한 곳이므로, 그 자리에서 전부 가린다.
  메시지든 traceback 이든 상관없이 걸린다.

쓰기
    from src.utils.secret_filter import install_secret_filter
    install_secret_filter()      # 프로그램 시작 때 한 번
"""

from __future__ import annotations

import logging
import re

# 무엇을 가리나 — 값의 앞뒤 몇 글자만 남겨 어느 키인지는 알아볼 수 있게 한다.
#   ① URL 쿼리의 key= / api_key= / access_token=
#   ② 헤더나 본문에 그대로 찍힌 OpenAI 키 (sk-...)
#   ③ Google API 키 모양 (AIza...)
PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # ★ 값에 점(.)이 섞인 토큰도 있다 — ya29.a0AfH6SM... 같은 구글 access token.
    #   점을 빼놓았더니 앞부분만 가려지고 뒤가 남았다 (시험이 잡았다)
    (re.compile(r"(?i)\b(key|api_key|apikey|access_token|token)=([A-Za-z0-9_\-\.]{12,})"),
     r"\1=***가림***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "sk-***가림***"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"), "AIza***가림***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{16,}"), r"\1***가림***"),
)


def scrub(text: str) -> str:
    """글 안의 비밀값을 가린다. 원문 구조는 그대로 둔다."""

    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SecretFilter(logging.Filter):
    """로그 한 줄이 파일로 나가기 전에 비밀값을 가린다.

    ★ 메시지만 보지 않는다. traceback(exc_info)에도 URL 이 들어 있다.
      그래서 예외 정보를 미리 글로 만들어 가린 뒤, 원본 exc_info 는 떼어낸다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: (scrub(v) if isinstance(v, str) else v)
                               for k, v in record.args.items()}
            else:
                record.args = tuple(scrub(a) if isinstance(a, str) else a
                                    for a in record.args)

        # ★ traceback 이 진짜 새는 자리다. 글로 바꿔 가린 뒤 원본을 뗀다.
        if record.exc_info:
            formatted = logging.Formatter().formatException(record.exc_info)
            record.exc_text = scrub(formatted)
            record.exc_info = None

        # 이미 만들어진 exc_text 가 있으면 그것도 가린다
        elif getattr(record, "exc_text", None):
            record.exc_text = scrub(record.exc_text)

        return True


def install_secret_filter() -> None:
    """모든 로거에 가림막을 건다. 여러 번 불러도 한 번만 붙는다."""

    root = logging.getLogger()
    if any(isinstance(f, SecretFilter) for f in root.filters):
        return

    secret_filter = SecretFilter()
    root.addFilter(secret_filter)
    # ★ 핸들러에도 붙인다. 로거를 거치지 않고 핸들러로 바로 가는 기록이 있다
    for handler in root.handlers:
        if not any(isinstance(f, SecretFilter) for f in handler.filters):
            handler.addFilter(secret_filter)
