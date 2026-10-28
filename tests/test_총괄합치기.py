# -*- coding: utf-8 -*-
"""판독자 둘의 발견을 총괄이 **다 잇는가** (2026-10-29 · 작게 한 번 돌려 보고 만들었다).

★ 왜 만들었나 — 2026-10-28 에 영상 1개(84행)로 한 줄 흐름을 처음 끝까지 돌려 봤다.
  `master_final` 의 발견 시트 네 개가 **Codex 번들의 바이트 그대로**였고(네 파일 지문이 같았다),
  판독A(claude)가 낸 구조적결함 8 · 기준서개정후보 7 · 분리제안 8 · 수정로그_오류확정 393행이
  **최종에 없었다.** 그 안에는 「장문 후기의 소모품 VoC 한 건이 통째로 사라졌다」 도 있었다.
  `build_master.py` 주석은 「CC 회차 것을 그대로 잇는다」 였는데 코드는 **판독자 2** 를 집었고,
  한 줄 흐름에서 판독자 2 는 폴더를 훑은 **순서**로 정해진다 — 어느 판독자가 살아남을지가
  폴더 이름 순서에 달려 있었다. 판독자를 둘 쓰는 뜻이 거기서 깨진다.

보는 것
  ① 합치면 **둘 다** 들어오고, 어느 판독자가 낸 것인지 `낸_판독자` 칸에 남는다.
  ② 똑같은 줄은 한 줄로 줄이고, **다른** 제안은 둘 다 남긴다 (사람이 고를 수 있어야 한다).
  ③ 빈 파일에도 머리글이 같다 (CP-29 — 비었을 때와 열이 다르면 승인 도구가 못 읽는다).
  ④ 한 칸에 승인이 둘이면 4차 반영이 **아무것도 반영하지 않고 멈춘다.**
     (합치면 생기는 새 위험이다. 나중에 읽은 줄이 조용히 이기면 사람은 자기가 고른 값이
      들어갔다고 믿는다.)
  ⑤ 판독자가 낸 보정요청이 총괄 자리로 **이어진다** — 10건이 각자 폴더에만 남아 있었다.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import PLUGIN, SHARED  # noqa: E402

sys.path.insert(0, str(SHARED / "tools"))


def _모듈(길: Path, 이름: str):
    규격 = importlib.util.spec_from_file_location(이름, 길)
    m = importlib.util.module_from_spec(규격)
    sys.modules[이름] = m
    규격.loader.exec_module(m)
    return m


def _쓰기(길: Path, 머리: list, 줄들: list) -> None:
    길.parent.mkdir(parents=True, exist_ok=True)
    with io.open(길, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=머리)
        w.writeheader()
        for r in 줄들:
            w.writerow(r)


def _읽기(길: Path) -> list:
    return list(csv.DictReader(길.read_text(encoding="utf-8-sig").splitlines()))


@pytest.fixture(scope="module")
def 합치개():
    import build_master
    return build_master.로그합치기


def test_판독자_둘의_발견을_다_잇는다(합치개, tmp_path):
    머리 = ["atomic_id", "원인"]
    _쓰기(tmp_path / "A_bundle" / "구조적결함.csv", 머리,
         [{"atomic_id": "a1", "원인": "A 가 본 것"},
          {"atomic_id": "a2", "원인": "둘 다 본 것"}])
    _쓰기(tmp_path / "B_bundle" / "구조적결함.csv", 머리,
         [{"atomic_id": "b1", "원인": "B 가 본 것"},
          {"atomic_id": "a2", "원인": "둘 다 본 것"}])
    받을곳 = tmp_path / "master_final"
    받을곳.mkdir()
    모두, 남은 = 합치개(받을곳, [("A_bundle", str(tmp_path / "A_bundle")),
                           ("B_bundle", str(tmp_path / "B_bundle"))], "구조적결함.csv")
    assert (모두, 남은) == (4, 3), (모두, 남은)      # 똑같은 줄 하나는 줄인다
    줄들 = _읽기(받을곳 / "구조적결함.csv")
    assert [r["atomic_id"] for r in 줄들] == ["a1", "a2", "b1"]
    낸이 = {r["atomic_id"]: r["낸_판독자"] for r in 줄들}
    assert 낸이 == {"a1": "A_bundle", "a2": "A_bundle", "b1": "B_bundle"}, 낸이
    # ★ 한 쪽만 담기면(옛 동작) 여기서 걸린다
    assert "b1" in 낸이, "판독자 한 쪽의 발견이 사라졌다"


def test_둘이_다른_제안을_내면_둘_다_남긴다(합치개, tmp_path):
    머리 = ["atomic_id", "field", "제안값", "승인상태"]
    _쓰기(tmp_path / "A_bundle" / "수정로그_오류확정.csv", 머리,
         [{"atomic_id": "x", "field": "topic", "제안값": "구매의사", "승인상태": ""}])
    _쓰기(tmp_path / "B_bundle" / "수정로그_오류확정.csv", 머리,
         [{"atomic_id": "x", "field": "topic", "제안값": "제조사 신뢰/품질", "승인상태": ""}])
    받을곳 = tmp_path / "master_final"
    받을곳.mkdir()
    모두, 남은 = 합치개(받을곳, [("A_bundle", str(tmp_path / "A_bundle")),
                           ("B_bundle", str(tmp_path / "B_bundle"))], "수정로그_오류확정.csv")
    assert (모두, 남은) == (2, 2)
    줄들 = _읽기(받을곳 / "수정로그_오류확정.csv")
    assert {r["제안값"] for r in 줄들} == {"구매의사", "제조사 신뢰/품질"}


def test_얼린기준_재현일_때는_옛_동작으로_담는다(합치개, tmp_path):
    """★ 얼린 3차 기준은 **옛 동작**(판독자 2 것만)으로 만들어졌다. 동결된 정답을 고치지 않고
    재현할 수 있어야 하므로 `VOC_얼린기준_재현=1` 이면 그 동작으로 돈다.

    섹션 5b 에서 §17(미판정→제외)과 handoff 의 88자 자르기를 같은 스위치로 가른 것과 같은 꼴이다.
    둘이 같이 있어야 **바꾼 것이 정확히 그것뿐임**을 안다.
    """
    머리 = ["atomic_id", "원인"]
    _쓰기(tmp_path / "A_bundle" / "구조적결함.csv", 머리, [{"atomic_id": "a1", "원인": "A 것"}])
    _쓰기(tmp_path / "B_bundle" / "구조적결함.csv", 머리, [{"atomic_id": "b1", "원인": "B 것"}])
    자리들 = [("A_bundle", str(tmp_path / "A_bundle")), ("B_bundle", str(tmp_path / "B_bundle"))]
    받을곳 = tmp_path / "master_final"
    받을곳.mkdir()
    assert 합치개(받을곳, 자리들, "구조적결함.csv", 얼린기준재현=True) == (1, 1)
    글 = (받을곳 / "구조적결함.csv").read_text(encoding="utf-8-sig")
    assert 글.splitlines()[0].split(",") == 머리, "옛 동작인데 칸이 늘었다 — %s" % 글.splitlines()[0]
    assert "b1" in 글 and "a1" not in 글, "옛 동작은 판독자 2 것만 담는다 — %s" % 글
    # 바이트 그대로인가 (옛 동작은 베끼기였다)
    assert (받을곳 / "구조적결함.csv").read_bytes() ==         (tmp_path / "B_bundle" / "구조적결함.csv").read_bytes()
    # 기본 동작(스위치 없음)은 둘을 합친다 — 같은 입력으로 바로 대 본다
    받을곳2 = tmp_path / "master_final2"
    받을곳2.mkdir()
    assert 합치개(받을곳2, 자리들, "구조적결함.csv", 얼린기준재현=False) == (2, 2)
    글2 = (받을곳2 / "구조적결함.csv").read_text(encoding="utf-8-sig")
    assert "a1" in 글2 and "b1" in 글2 and "낸_판독자" in 글2


def test_빈_파일에도_머리글이_같다(합치개, tmp_path):
    """★ CP-29 — 비었을 때와 있을 때 열이 다르면 승인 도구·대시보드가 시트를 못 읽는다."""
    머리 = ["atomic_id", "원인"]
    _쓰기(tmp_path / "A_bundle" / "구조적결함.csv", 머리, [])
    _쓰기(tmp_path / "B_bundle" / "구조적결함.csv", 머리, [])
    받을곳 = tmp_path / "master_final"
    받을곳.mkdir()
    assert 합치개(받을곳, [("A_bundle", str(tmp_path / "A_bundle")),
                      ("B_bundle", str(tmp_path / "B_bundle"))], "구조적결함.csv") == (0, 0)
    글 = (받을곳 / "구조적결함.csv").read_text(encoding="utf-8-sig").splitlines()
    assert 글[0].split(",") == ["atomic_id", "원인", "낸_판독자"], 글[0]


def test_한_칸에_승인이_둘이면_4차가_멈춘다():
    """★ 합치면 생기는 새 위험 — `apply_approved` 의 반영 고리는 **나중 줄이 이긴다.**"""
    import apply_approved
    승인 = [("수정로그_오류확정.csv",
           {"atomic_id": "x", "field": "topic", "제안값": "구매의사",
            "낸_판독자": "claudecode_bundle", "승인상태": "승인"}),
          ("수정로그_오류확정.csv",
           {"atomic_id": "x", "field": "topic", "제안값": "제조사 신뢰/품질",
            "낸_판독자": "Codex_bundle", "승인상태": "승인"})]
    둘, 누가 = apply_approved.부딪히는_승인(승인)
    assert list(둘) == [("x", "topic")], 둘
    assert 누가[("x", "topic")] == {"claudecode_bundle", "Codex_bundle"}
    # 값이 같으면 부딪힘이 아니다 — 어느 줄이 들어가도 결과가 같다
    같음 = [(f, dict(r, 제안값="구매의사")) for f, r in 승인]
    assert apply_approved.부딪히는_승인(같음)[0] == {}


_돌리개길 = PLUGIN / "skills" / "coordinating-voc-pipeline" / "scripts" / "한줄_돌리기.py"


def test_판독자_보정요청이_총괄로_이어진다(tmp_path):
    """★ 2026-10-28 실측 — 판독A 8건 · 판독B 2건이 각자 폴더에만 남고 아웃풋 1 에 없었다."""
    돌리개 = _모듈(_돌리개길, "한줄_돌리기_시험본")
    머리 = ["번호", "접수일", "나온_회차", "갈래", "무엇이_문제인가", "처리상태"]
    판 = tmp_path / "판자리"
    낸것 = {
        "판독A": [{"번호": "1", "접수일": "2026-10-29", "나온_회차": "2차·3차 통합",
                 "갈래": "엔진결함", "무엇이_문제인가": "엔진결함 / E1 어휘가드", "처리상태": "대기"},
                {"번호": "2", "접수일": "2026-10-29", "나온_회차": "2차·3차 통합",
                 "갈래": "기준서공백", "무엇이_문제인가": "기준서공백 / 담을 라벨이 없다",
                 "처리상태": "대기"}],
        "판독B": [{"번호": "1", "접수일": "2026-10-29", "나온_회차": "2차·3차 통합",
                 "갈래": "엔진결함", "무엇이_문제인가": "엔진결함 / E1 어휘가드", "처리상태": "대기"},
                {"번호": "2", "접수일": "2026-10-29", "나온_회차": "2차·3차 통합",
                 "갈래": "데이터", "무엇이_문제인가": "데이터 / 수집이 모자란다", "처리상태": "대기"}],
    }
    for 이름, 것 in 낸것.items():
        _쓰기(판 / 이름 / "_인계" / "보정요청.csv", 머리, 것)
    판자리 = 판 / "총괄" / "판1"
    판자리.mkdir(parents=True)
    남은말 = 돌리개._판독자_보정요청_이어주기(판, 판자리)
    assert 남은말 == [], 남은말
    줄들 = _읽기(판자리 / "_인계" / "보정요청.csv")
    assert len(줄들) == 3, 줄들            # 같은 지적 하나는 겹치지 않는다
    assert [r["번호"] for r in 줄들] == ["1", "2", "3"], "번호가 겹친다"
    낸곳 = {r["무엇이_문제인가"]: r["나온_회차"] for r in 줄들}
    assert 낸곳["엔진결함 / E1 어휘가드"] == "2차 판독 (판독A)"
    assert 낸곳["데이터 / 수집이 모자란다"] == "2차 판독 (판독B)"
    # ★ 두 번 돌려도 늘어나지 않는다 (되감아 다시 돌릴 때)
    돌리개._판독자_보정요청_이어주기(판, 판자리)
    assert len(_읽기(판자리 / "_인계" / "보정요청.csv")) == 3


def test_판독자_보정요청_파일이_없으면_0건이라고_하지_않는다(tmp_path):
    """★ 「못 찾음」 은 「0건」 이 아니다 — 안 냈는지 못 냈는지 모르면 그렇게 말해야 한다."""
    돌리개 = _모듈(_돌리개길, "한줄_돌리기_시험본")
    판 = tmp_path / "판자리"
    판자리 = 판 / "총괄" / "판1"
    판자리.mkdir(parents=True)
    남은말 = 돌리개._판독자_보정요청_이어주기(판, 판자리)
    assert len(남은말) == 2, 남은말        # 판독자 둘 다 못 찾았다고 말한다
    assert all("없습니다" in x for x in 남은말)
