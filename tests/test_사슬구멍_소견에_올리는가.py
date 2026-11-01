# -*- coding: utf-8 -*-
"""총괄이 **스스로 적어 둔** 「사슬구멍」 을 돌리개가 소견에 올리는가 (2026-11-01).

★ 왜 이 시험이 있나 — 2판 통째 재현의 4차에서 총괄(claude)이
  `master_final/4차반영_사슬구멍_status.csv` 를 **제 손으로 만들어** 적었다.
  옛 사람 결정과 데이터를 대보고 「사람이 제외로 정했는데 데이터는 normal 이다」 를
  **18행** 찾아냈다. **설계가 작동한 쪽**이다.

  그런데 **돌리개가 그 파일을 읽지 않았다.** 소견에 안 올라가면 회의 자료에도
  안 들어간다 — AI 가 찾아 놓고 **사라지는** 것이다. 사람이 폴더를 열어 봐야 알았다.
"""
from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
sys.path.insert(0, str(REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))


@pytest.fixture()
def 돌리개():
    m = importlib.import_module("한줄_돌리기")
    return importlib.reload(m)


def _구멍파일(쪽: Path, 어긋남수: int, 전체: int):
    쪽.parent.mkdir(parents=True, exist_ok=True)
    칸 = ["atomic_id", "field", "옛_사람결정_새값", "지금_데이터", "어긋남"]
    with io.open(쪽, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=칸)
        w.writeheader()
        for i in range(전체):
            w.writerow({"atomic_id": "A-%02d" % i, "field": "status",
                        "옛_사람결정_새값": "제외(operator_notice)",
                        "지금_데이터": "normal" if i < 어긋남수 else "scope_excluded",
                        "어긋남": ("★ 그렇다 — 데이터는 normal" if i < 어긋남수
                                else "아니다 — 이미 같다")})


def _판(tmp_path: Path) -> Path:
    판 = tmp_path / "판"
    판.mkdir(parents=True, exist_ok=True)
    (판 / "상태.json").write_text(json.dumps({"끝난단계": [], "소견": []}, ensure_ascii=False),
                                encoding="utf-8")
    return 판


def test_사슬구멍을_찾아_소견에_올린다(돌리개, tmp_path, capsys):
    """★ 알맹이. 안 올리면 AI 가 찾아낸 것이 회의 자료에서 사라진다."""
    판 = _판(tmp_path)
    번들 = 판 / "번들"
    _구멍파일(번들 / "4차반영_사슬구멍_status.csv", 어긋남수=18, 전체=74)
    상태: dict = {"끝난단계": [], "소견": []}
    말들 = 돌리개.사슬구멍_올리기(판, 상태, 번들)
    assert 말들, "사슬구멍 파일이 있는데 아무것도 안 올렸다"
    assert len(상태["소견"]) == 1, 상태["소견"]
    말 = 상태["소견"][0]["말"]
    assert "74행" in 말 and "18행" in 말, ("몇 행인지·몇 행이 어긋나는지 안 적었다 — %s" % 말)
    assert "사슬의 구멍" in 말, 말
    찍힌것 = capsys.readouterr().out
    assert "사슬구멍" in 찍힌것 and "소견.md 에 올렸습니다" in 찍힌것, 찍힌것


def test_이름을_박지_않고_무늬로_찾는다(돌리개, tmp_path):
    """총괄이 다음 판에서 다른 이름을 붙일 수 있다."""
    판 = _판(tmp_path)
    번들 = 판 / "번들"
    _구멍파일(번들 / "사슬구멍_topic_2026.csv", 어긋남수=3, 전체=5)
    _구멍파일(번들 / "4차_사슬구멍_entity.csv", 어긋남수=0, 전체=2)
    상태: dict = {"끝난단계": [], "소견": []}
    말들 = 돌리개.사슬구멍_올리기(판, 상태, 번들)
    assert len(말들) == 2, "이름이 다른 두 파일을 %d개만 찾았다" % len(말들)


def test_어긋남이_없으면_그_말을_안_붙인다(돌리개, tmp_path):
    판 = _판(tmp_path)
    번들 = 판 / "번들"
    _구멍파일(번들 / "4차반영_사슬구멍_status.csv", 어긋남수=0, 전체=6)
    상태: dict = {"끝난단계": [], "소견": []}
    돌리개.사슬구멍_올리기(판, 상태, 번들)
    말 = 상태["소견"][0]["말"]
    assert "아직 어긋납니다" not in 말, "어긋남이 0인데 어긋난다고 적었다 — %s" % 말
    assert "6행" in 말, 말


def test_파일이_없으면_아무_말도_안_한다(돌리개, tmp_path, capsys):
    """구멍이 없는 판이 보통이다. 그때 시끄러우면 사람이 경고를 흘려 읽는다."""
    판 = _판(tmp_path)
    번들 = 판 / "번들"
    번들.mkdir(parents=True)
    상태: dict = {"끝난단계": [], "소견": []}
    assert 돌리개.사슬구멍_올리기(판, 상태, 번들) == []
    assert 상태["소견"] == []
    assert "사슬구멍" not in capsys.readouterr().out


def test_사차반영이_그_함수를_부른다(돌리개):
    """★ 함수만 있고 아무도 안 부르면 그대로다 (가드는 돌리는 자리에)."""
    import inspect
    글 = inspect.getsource(돌리개.사차반영)
    assert "사슬구멍_올리기(" in 글, (
        "사차반영 이 사슬구멍_올리기 를 부르지 않는다 — 함수가 있어도 안 돌아간다")
