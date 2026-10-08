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
    # 140 + scripts 2개(1차 실행 경로) + nlp_analyzer 10개 — 둘 다 2026-10-07
    assert len(출처["파일"]) == 152, len(출처["파일"])
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


def test_글자경로로_부르는_파일이_다_있다():
    """★ 2026-10-07 — import 가 아니라 **글자 경로로 subprocess** 로 부르는 파일은 import 추적에 안 잡힌다.

    그래서 1차 실행 경로(`scripts/run_dashboard60_youtube_collect_and_analyze.py`)가 빠진 채 ① 이 「통과」 였다.
    엔진 전체에서 `ROOT / "<폴더>" / "<파일>.py"` 꼴을 찾아 그 파일이 실제로 있는지 본다.
    """
    import re
    찾음, 없음 = 0, []
    무늬 = re.compile(r'ROOT\s*/\s*"([A-Za-z_0-9]+)"\s*/\s*"([A-Za-z_0-9.\-]+\.py)"')
    for p in 엔진.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        for 폴더, 이름 in 무늬.findall(p.read_text(encoding="utf-8", errors="ignore")):
            찾음 += 1
            if not (엔진 / 폴더 / 이름).is_file():
                없음.append("%s → %s/%s" % (p.relative_to(엔진).as_posix(), 폴더, 이름))
    assert 찾음 >= 2, "글자 경로로 부르는 자리를 못 찾았다 — 무늬가 안 맞는다 (못 찾음 ≠ 없음)"
    assert not 없음, "엔진이 글자 경로로 부르는데 파일이 없다 — 가져올것 에 더한다: %s" % 없음


def test_도구가_부르는_엔진_입구가_목록과_맞다():
    import re
    부름 = set()
    for p in (REPO / "plugin" / "shared" / "tools").glob("*.py"):
        부름 |= set(re.findall(r"(?:from|import) (src\.[\w.]+)", p.read_text(encoding="utf-8")))
    assert 부름 <= set(꾸러미.엔진입구), "도구가 새 엔진 입구를 부른다 — 꾸러미.엔진입구 에 더한다: %s" % (부름 - set(꾸러미.엔진입구))


def test_nlp_analyzer_는_엔진_안_사본이_잡힌다():
    """★ 2026-10-07 sky 결정 — 1차가 쓰는 `nlp_analyzer` 를 엔진 안에 들여왔다 (다른 저장소에 있던 것).

    두 가지를 본다 — ① 엔진 자리에서 `import nlp_analyzer` 가 **엔진 안 사본**으로 잡히나
    (이 컴퓨터에는 같은 이름이 site-packages 에도 깔려 있다. 다른 PC 에는 없다) ·
    ② 1차가 쓰는 입구 네 개가 실제로 불러지나 (`src/analytics/sentiment.py:18~21`).
    없으면 1차는 조용히 enrichment 칸을 비운 채 돈다 — 그래서 「못 찾음」 을 통과로 두지 않는다.
    """
    코드 = ("import nlp_analyzer, pathlib;"
          " from nlp_analyzer import analyze_comment, analyze_batch, AnalysisResult, is_valid;"
          " from nlp_analyzer.router import LLMRouter;"
          " from nlp_analyzer.providers.claude import ClaudeProvider;"
          " from nlp_analyzer.providers.openai import OpenAIProvider;"
          " print(pathlib.Path(nlp_analyzer.__file__).resolve())")
    r = subprocess.run([sys.executable, "-B", "-c", 코드], cwd=엔진, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0, r.stdout + r.stderr[-2000:]
    잡힌자리 = Path(r.stdout.strip().splitlines()[-1])
    assert 잡힌자리 == (엔진 / "nlp_analyzer" / "__init__.py").resolve(), 잡힌자리


def test_저장소_안에_엔진_사본이_하나뿐이다():
    """★ 2026-10-08 에 실제로 겪었다 — 띄우개에 `--help` 를 줬더니 그것을 **자리 이름으로 보고**
    저장소 안에 `--help/` 폴더를 만들어 엔진 157개를 복사했고, `git add -A` 로 같이 커밋됐다.

    1차 · 대시보드 자리는 **저장소 밖**이어야 한다. 저장소 안에 엔진 사본이 또 생기면 여기서 드러난다.
    """
    표시 = ["streamlit_app.py", "출처_엔진.json"]
    딴것 = []
    for 이름 in 표시:
        for p in REPO.rglob(이름):
            if "__pycache__" in p.parts or ".git" in p.parts:
                continue
            if p.parent != 엔진:
                딴것.append(p.relative_to(REPO).as_posix())
    assert not 딴것, "저장소 안에 엔진 사본이 또 있다 (작업 자리는 저장소 밖이어야 한다) — %s" % 딴것[:5]


def test_1차가_쓰는_자리와_대시보드가_찾는_자리가_같다():
    """★ 2026-10-08 섹션 7 ④ 에서 어긋나 있던 자리 — 글로만 맞춰 두면 또 어긋난다.

    대시보드는 `latest_dataset(root=outputs/voc_dashboard_60)` 으로 **스스로 찾아** 띄운다.
    1차 돌리개가 다른 자리에 쓰면 1차를 돌려도 「Dataset not found」 가 뜨고 사람이 손으로 옮겨야 한다.
    그래서 두 자리를 코드에서 읽어 맞댄다 (어느 한쪽을 고치면 여기서 드러난다).
    """
    import importlib.util
    import inspect
    사양 = importlib.util.spec_from_file_location(
        "돌리개", REPO / "plugin" / "skills" / "running-voc-engine" / "scripts" / "1차_돌리기.py")
    m = importlib.util.module_from_spec(사양)
    사양.loader.exec_module(m)
    돌리개자리 = m.결과뿌리.relative_to(m.엔진).as_posix()

    sys.path.insert(0, str(엔진))
    from src.dashboard60.data_contract import latest_dataset      # noqa: PLC0415
    대시보드자리 = Path(inspect.signature(latest_dataset).parameters["root"].default).as_posix()
    assert 돌리개자리 == 대시보드자리, (
        "1차가 결과를 쓰는 자리와 대시보드가 찾는 자리가 다르다 — %s vs %s" % (돌리개자리, 대시보드자리))


def test_1차_입구와_대시보드_입구를_불러진다():
    r = subprocess.run([sys.executable, "-B", "-c", "import src.cli, src.dashboard60.app_operating; print('ok')"],
                       cwd=엔진, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr[-2000:]
