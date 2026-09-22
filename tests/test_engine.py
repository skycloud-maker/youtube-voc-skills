# -*- coding: utf-8 -*-
"""1차 분석 엔진 한 벌 (섹션 7 ①) — `plugin/engine/` 은 옛 live_merge 동결본(a94e731)에서 한 번 들여왔다.

★ 출처는 `plugin/engine/출처_엔진.json` 한 벌 — 파일마다 원본 자리 · 원본 해시 · 지금 해시 · 고친 이력.
★ 1차 입구(src.cli)와 대시보드 입구(src.dashboard60.app_operating)를 **실제로 불러 본다** — 빠진 파일이 있으면 여기서 드러난다.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
엔진 = REPO / "plugin" / "engine"
출처 = json.loads((엔진 / "출처_엔진.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(REPO / "plugin" / "shared" / "lib"))
import 꾸러미  # noqa: E402


def _파일들() -> set[str]:
    return {p.relative_to(엔진).as_posix() for p in 엔진.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.name != "출처_엔진.json"}


def test_출처_기록과_파일이_하나씩_맞다():
    assert len(출처["파일"]) == 140, len(출처["파일"])
    assert _파일들() == set(출처["파일"]), (sorted(_파일들() - set(출처["파일"]))[:5], sorted(set(출처["파일"]) - _파일들())[:5])
    어긋남 = [n for n, v in 출처["파일"].items() if hashlib.sha256((엔진 / n).read_bytes()).hexdigest() != v["지금_sha256"]]
    assert not 어긋남, "출처 기록과 다른 엔진 파일 — 고쳤다면 고친_이력과 지금_sha256 을 — %s" % 어긋남[:5]


def test_원본과_다른_것은_이유가_있다():
    for n, v in 출처["파일"].items():
        if v["원본_sha256"] and v["원본_sha256"] != v["지금_sha256"] and not v["고친_이력"]:
            assert b"\r\n" not in (엔진 / n).read_bytes(), "%s — 고친_이력 없이 줄바꿈 말고도 달라졌다" % n


def test_뺀_것은_없다():
    for 자리 in 출처["뺀_것"]:
        assert not (엔진 / 자리.rstrip("/")).exists(), 자리


# 옛 경로 · 절대경로는 tests/test_no_old_paths.py 가 plugin/ 전체(엔진 포함)에서 본다 — 여기서 두 번 보지 않는다


def test_판독_감독_폴더의_엔진은_도구가_부르는_것을_다_싣는다():
    목록 = 꾸러미.꾸러미엔진(엔진)
    없음 = [n for n in 목록 if not (엔진 / n).is_file()]
    assert not 없음, 없음
    for m in 꾸러미.엔진입구:                     # 입구 모듈 자신이 들어 있다
        p = 꾸러미._모듈자리(엔진, m)
        assert p is not None and p.relative_to(엔진).as_posix() in 목록, m
    # ★ 2026-09-22 에 빠져서 2차 번들 xlsx 가 안 만들어졌던 자리
    assert "src/v5/pipeline.py" in 목록
    assert "0_이 폴더는 무엇입니까.md" in 목록 and "src/voc_rebuild/config/topic_evidence_lexicon.yaml" in 목록


def test_도구가_부르는_엔진_입구가_목록과_맞다():
    import re
    부름 = set()
    for p in (REPO / "plugin" / "shared" / "tools").glob("*.py"):
        부름 |= set(re.findall(r"(?:from|import) (src\.[\w.]+)", p.read_text(encoding="utf-8")))
    assert 부름 <= set(꾸러미.엔진입구), "도구가 새 엔진 입구를 부른다 — 꾸러미.엔진입구 에 더한다: %s" % (부름 - set(꾸러미.엔진입구))


def test_1차_입구와_대시보드_입구를_불러진다():
    r = subprocess.run([sys.executable, "-B", "-c", "import src.cli, src.dashboard60.app_operating; print('ok')"],
                       cwd=엔진, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr[-2000:]
