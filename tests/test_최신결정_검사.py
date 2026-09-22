# -*- coding: utf-8 -*-
"""최신결정_검사.py 가 정말 잡는가 — 일부러 틀린 자료를 만들어 규칙마다 한 번씩 본다 (섹션 5b · 2026-09-22).

★ 검사기는 크게 실패해야 한다 — 볼 것을 못 찾으면 0 이 아니라 2 로 끝나야 한다.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

도구 = Path(__file__).resolve().parents[1] / "plugin" / "shared" / "tools" / "최신결정_검사.py"
칸 = ["source_id", "atomic_id", "atomic_voc", "original_voc", "video_id", "video_title", "product_category",
     "status", "scope_exclusion_reason", "topic", "topic_evidence", "brand", "competitor_brand_tags"] + \
    ["tee_%s_%s" % (a, b) for a in ("time", "effort", "emotion", "success") for b in ("score", "evidence")]


def _행(**k):
    r = {c: "" for c in 칸}
    r.update(source_id="s1", atomic_id="s1-01", atomic_voc="흡입력이 좋아요", original_voc="흡입력이 좋아요",
             video_id="v1", video_title="LG 로봇청소기 리뷰", product_category="로봇청소기",
             status="normal", topic="흡입력", topic_evidence="흡입력이 좋아요", brand="LG")
    for a in ("time", "effort", "emotion", "success"):
        r["tee_%s_score" % a], r["tee_%s_evidence" % a] = "3", "흡입력이 좋아요"
    r.update(k)
    return r


def _폴더(tmp: Path, 번들행: list[dict], 일차행: list[dict] | None = None) -> Path:
    for 자리, rows in (("_판독패키지/_결과/claudecode_bundle/raw_voc.csv", 번들행),
                     ("판독대상/시험/voc_secondary_dataset.csv", 일차행 if 일차행 is not None else 번들행)):
        p = tmp / 자리
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8-sig", newline="") as h:
            w = csv.DictWriter(h, fieldnames=칸)
            w.writeheader()
            w.writerows(rows)
    return tmp


def _돌리기(d: Path, *인자: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", str(도구), *인자], cwd=d, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def test_깨끗하면_통과한다(tmp_path):
    코드, 말 = _돌리기(_폴더(tmp_path, [_행()]), "번들")
    assert 코드 == 0, 말


@pytest.mark.parametrize("규칙, 행", [
    ("라2", dict(competitor_brand_tags="삼성|LG")),
    ("라4", dict(brand="creator_channel")),
    ("라5", dict(tee_time_score="0", tee_time_evidence="")),
    ("라6", dict(status="scope_excluded", scope_exclusion_reason="no_analytic_value", topic="미분류")),
    ("라7", dict(topic="구매의사/이탈")),
    ("라7", dict(topic="기타(로봇청소기)")),
])
def test_규칙마다_잡는다(tmp_path, 규칙, 행):
    코드, 말 = _돌리기(_폴더(tmp_path, [_행(**행)]), "번들")
    assert 코드 == 1 and ("✗ %s" % 규칙) in 말, 말


def test_라3_목차_댓글을_나누면_잡는다(tmp_path):
    rows = [_행(atomic_id="s1-01", atomic_voc="00:00 인트로"), _행(atomic_id="s1-02", atomic_voc="03:12 흡입력")]
    코드, 말 = _돌리기(_폴더(tmp_path, rows), "번들")
    assert 코드 == 1 and "✗ 라3" in 말, 말


def test_라8_라벨만_바꾸고_근거는_그대로면_잡는다(tmp_path):
    일차 = [_행(topic="소음/진동", topic_evidence="흡입력이 좋아요")]
    코드, 말 = _돌리기(_폴더(tmp_path, [_행(topic="흡입력", topic_evidence="흡입력이 좋아요")], 일차), "번들")
    assert 코드 == 1 and "✗ 라8" in 말, 말
    # 1차가 미분류였으면 1차 근거가 새 라벨을 뒷받침할 수 있다 — 잡지 않는다 (실제 데이터의 거짓 경보)
    일차 = [_행(topic="미분류", topic_evidence="흡입력이 좋아요")]
    코드, 말 = _돌리기(_폴더(tmp_path, [_행()], 일차), "번들")
    assert 코드 == 0, 말


def test_1차를_못_찾으면_통과가_아니다(tmp_path):
    d = _폴더(tmp_path, [_행()])
    (d / "판독대상" / "시험" / "voc_secondary_dataset.csv").unlink()
    코드, 말 = _돌리기(d, "번들")
    assert 코드 == 2 and "라8 을 못 봤습니다" in 말, 말


def test_번들을_못_찾으면_통과가_아니다(tmp_path):
    코드, 말 = _돌리기(tmp_path, "번들")
    assert 코드 == 2, 말


def test_라1_제목도_댓글도_다른_영상을_알린다(tmp_path):
    rows = [_행(atomic_id="s%d-01" % i, video_id="v9", video_title="안샀으면 후회할 뻔한 가전 3가지",
                original_voc="계란찜기 최고") for i in range(6)]
    rows += [_행(atomic_id="t%d-01" % i) for i in range(6)]          # 정상 영상은 알리지 않는다
    코드, 말 = _돌리기(_폴더(tmp_path, rows), "영상")
    assert 코드 == 0 and "! v9" in 말 and "! v1" not in 말, 말


def test_라1_1차를_못_찾으면_통과가_아니다(tmp_path):
    코드, 말 = _돌리기(tmp_path, "영상")
    assert 코드 == 2, 말


def test_쓰지_않는_라벨_목록_세_벌이_서로_맞다():
    """★ 같은 것이 세 벌 (2026-09-22 재점검에서 찾음) — 도구가 나뉘어 실려 한 파일로 합칠 수 없어 여기서 대조한다.
      check_selfcheck.DEAD_TOPIC (판독 · 감독 폴더) = 폐기라벨_정리.바꿀것 의 옛 이름 (총괄) ⊆ 최신결정_검사.폐기라벨 (판독 폴더)
      그리고 새 판 §8 표에 폐기라벨이 모두 적혀 있다."""
    import importlib
    import os
    tools = 도구.parent
    sys.path.insert(0, str(tools))
    옛 = os.environ.pop("VOC_얼린기준_재현", None)
    try:
        cs = importlib.import_module("check_selfcheck")
        pj = importlib.import_module("폐기라벨_정리")
        검 = importlib.import_module("최신결정_검사")
    finally:
        if 옛 is not None:
            os.environ["VOC_얼린기준_재현"] = 옛
    assert set(cs.DEAD_TOPIC) == set(pj.바꿀것), (cs.DEAD_TOPIC, pj.바꿀것)
    assert set(pj.바꿀것) <= 검.폐기라벨, set(pj.바꿀것) - 검.폐기라벨
    판 = (도구.parents[1] / "standards" / "0_최신결정_먼저.md").read_text(encoding="utf-8")
    표줄 = [l for l in 판.splitlines() if l.startswith("| 라7 |")]
    assert 표줄 and all(x in 표줄[0] for x in 검.폐기라벨), (표줄, 검.폐기라벨)
    assert not cs.DEAD_REASON, "out_of_scope_product 는 [가1] 로 살아 있는 사유다 (옛 동작은 VOC_얼린기준_재현=1 때만)"
