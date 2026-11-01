# -*- coding: utf-8 -*-
"""4차의 **분리가 번들에 닿는가** (2026-11-01).

★ 왜 이 시험이 있나 — 2판을 통째로 다시 돌려 보고 찾았다.

  `apply_split.py` 는 `s15_master/raw_voc.csv` 를 읽고 **거기에 쓴다.**
  그런데 번들은 `_판독패키지/_결과/master_final/raw_voc.csv` 로 만든다.
  그래서 **사람이 승인한 분리 74건이 번들에 닿지 않았다.** 실측 —

      s15_master    6,530행 · 쪼개진 조각 316
      master_final  6,393행 · 쪼개진 조각 105   ← 번들이 이것을 담았다

  행 137개 · 조각 211개가 **오류 하나 없이** 버려졌다 (종료 0 · 「끝났습니다」).
  그래서 재는 것은 둘이다 — **옮기는가** · **못 옮겼으면 크게 실패하는가.**
"""
from __future__ import annotations

import csv
import importlib.util
import io
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
도구쪽 = REPO / "plugin" / "shared" / "tools" / "4차_반영.py"

칸들 = ["atomic_id", "topic", "split_origin_atomic_id"]


def _불러오기(뿌리: Path):
    """`4차_반영.py` 를 **그 판 자리**에서 불러온다 (ROOT 가 파일 자리로 정해지므로 복사한다)."""
    사본 = 뿌리 / "4차_반영.py"
    사본.write_bytes(도구쪽.read_bytes())
    spec = importlib.util.spec_from_file_location("사차반영_시험", 사본)
    m = importlib.util.module_from_spec(spec)
    sys.modules["사차반영_시험"] = m
    spec.loader.exec_module(m)
    return m


def _쓰기(쪽: Path, 줄들):
    쪽.parent.mkdir(parents=True, exist_ok=True)
    with io.open(쪽, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=칸들)
        w.writeheader()
        for r in 줄들:
            w.writerow(r)


def _읽기(쪽: Path):
    with io.open(쪽, encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


def _판(tmp_path: Path, s15줄, 번들줄):
    뿌리 = tmp_path / "판"
    _쓰기(뿌리 / "s15_master" / "raw_voc.csv", s15줄)
    _쓰기(뿌리 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv", 번들줄)
    return 뿌리


def _행(aid, topic="가", 부모=""):
    return {"atomic_id": aid, "topic": topic, "split_origin_atomic_id": 부모}


def test_분리가_번들_자리로_옮겨진다(tmp_path):
    """★ 알맹이. 안 옮기면 사람이 승인한 분리가 최종에서 사라진다."""
    뿌리 = _판(tmp_path,
             [_행("A-01"), _행("A-02", 부모="A-01"), _행("A-03", 부모="A-01")],
             [_행("A-01")])
    m = _불러오기(뿌리)
    코드, 말 = m._분리_옮기기()
    assert 코드 == 0, 말
    뒤 = _읽기(뿌리 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv")
    assert len(뒤) == 3, ("번들 자리가 %d행이다 — 3행이어야 한다. "
                         "분리가 닿지 않으면 최종에서 조용히 사라진다" % len(뒤))
    조각 = sum(1 for r in 뒤 if r["split_origin_atomic_id"])
    assert 조각 == 2, "쪼개진 조각이 %d개다 — 2개여야 한다" % 조각
    assert "닿았습니다" in 말, 말


def test_옮길_것이_없으면_그대로_넘어간다(tmp_path):
    """분리가 하나도 없는 판도 있다. 그때 실패하면 안 된다 (「없음」 과 「못 찾음」 을 가른다)."""
    줄들 = [_행("A-01"), _행("B-01")]
    뿌리 = _판(tmp_path, 줄들, 줄들)
    m = _불러오기(뿌리)
    코드, 말 = m._분리_옮기기()
    assert 코드 == 0, 말
    assert "옮길 것이 없습니다" in 말, 말


def test_s15가_더_적으면_멈춘다(tmp_path):
    """덮으면 행을 잃는다. 조용히 덮지 않는다."""
    뿌리 = _판(tmp_path, [_행("A-01")], [_행("A-01"), _행("A-02", 부모="A-01")])
    m = _불러오기(뿌리)
    코드, 말 = m._분리_옮기기()
    assert 코드 == 1, "행을 잃는데 통과했다 —\n%s" % 말
    assert "더 적습니다" in 말, 말
    뒤 = _읽기(뿌리 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv")
    assert len(뒤) == 2, "멈췄는데 번들 자리를 건드렸다"


def test_칸이_다르면_멈춘다(tmp_path):
    """칸이 다른 파일로 덮으면 번들이 깨진다."""
    뿌리 = _판(tmp_path, [_행("A-01")], [_행("A-01")])
    쪽 = 뿌리 / "s15_master" / "raw_voc.csv"
    with io.open(쪽, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=["atomic_id", "topic"])
        w.writeheader()
        w.writerow({"atomic_id": "A-01", "topic": "가"})
        w.writerow({"atomic_id": "A-02", "topic": "나"})
    m = _불러오기(뿌리)
    코드, 말 = m._분리_옮기기()
    assert 코드 == 1, "칸이 다른데 통과했다 —\n%s" % 말
    assert "칸이 다릅니다" in 말, 말


def test_s15가_없으면_크게_실패한다(tmp_path):
    """★ 「못 찾음」 은 통과가 아니다."""
    뿌리 = tmp_path / "판"
    _쓰기(뿌리 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv", [_행("A-01")])
    m = _불러오기(뿌리)
    코드, 말 = m._분리_옮기기()
    assert 코드 == 1, 말
    assert "못 찾음은 통과가 아닙니다" in 말, 말


def test_차례에_그_단계가_들어_있다(tmp_path):
    """★ 함수만 있고 차례에 없으면 **아무도 안 부른다** (가드는 돌리는 자리에)."""
    뿌리 = tmp_path / "판"
    뿌리.mkdir()
    m = _불러오기(뿌리)
    이름들 = [이름 for 이름, _, _ in m.차례]
    맞는것 = [x for x in 이름들 if x.startswith("⓪-1")]
    assert 맞는것, "차례에 ⓪-1 단계가 없다 — 함수가 있어도 안 돌아간다\n%s" % 이름들
    자리 = 이름들.index(맞는것[0])
    분리 = [i for i, (_, 도구, _) in enumerate(m.차례) if 도구 == "apply_split.py"]
    xlsx = [i for i, (이름, 도구, _) in enumerate(m.차례)
            if 도구 is None and 이름.startswith("①")]
    assert 분리 and 자리 > 분리[0], "분리 반영 **뒤**에 와야 한다"
    assert xlsx and 자리 < xlsx[0], "xlsx 만들기 **앞**에 와야 한다 (안 그러면 못 담는다)"
