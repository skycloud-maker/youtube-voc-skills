# -*- coding: utf-8 -*-
"""기준 정답 맞대기 시험 (섹션 2 · 결정 0002).

기준 정답 = 옛 2판 도구 **사본**을 저장소 밖 기준 자리에서 한 번 돌려 얼린 결과
(`<BASELINE>/실행/3차준비_1` · `3차마무리_1`). 파일 목록과 해시는 git 안의
`tests/baseline/얼린기준_목록.json` 에 있다.

★ 기준 자리를 못 찾으면 **실패**한다 — 건너뛰지 않는다. 「못 찾음」 은 통과가 아니다.
★ 재현 시험은 몇 분 걸린다 (사본을 새로 차려 두 도구를 돌린다). 그래도 기본으로 돈다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent
sys.path.insert(0, str(_여기.parent / "plugin" / "shared"))
sys.path.insert(0, str(_여기 / "baseline"))
from paths import BASELINE  # noqa: E402
import 기준_만들기  # noqa: E402
import 맞대기 as 맞대기_mod  # noqa: E402
from 맞대기 import 맞대기  # noqa: E402

목록 = json.loads((_여기 / "baseline" / "얼린기준_목록.json").read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for 조각 in iter(lambda: f.read(1 << 20), b""):
            h.update(조각)
    return h.hexdigest()


def test_기준_자리가_있다():
    assert BASELINE.is_dir(), "기준 자리를 못 찾았다 — %s (VOC_BASELINE 으로 가리킬 것)" % BASELINE
    for 이름 in 목록:
        assert (BASELINE / "실행" / 이름).is_dir(), "얼린 기준이 없다 — %s" % 이름


@pytest.mark.parametrize("이름", sorted(목록))
def test_얼린_기준이_그대로다(이름):
    뿌리 = BASELINE / "실행" / 이름
    assert 뿌리.is_dir(), "얼린 기준이 없다 — %s" % 뿌리
    적힌것 = 목록[이름]["파일"]
    assert len(적힌것) == 목록[이름]["파일수"] > 0
    있는것 = {p.relative_to(뿌리).as_posix() for p in 뿌리.rglob("*") if p.is_file()}
    assert 있는것 == set(적힌것), "파일 목록이 달라졌다 — 더 생김 %s · 없어짐 %s" % (
        sorted(있는것 - set(적힌것))[:5], sorted(set(적힌것) - 있는것)[:5])
    바뀜 = [r for r, h in 적힌것.items() if _sha(뿌리 / r) != h]
    assert not 바뀜, "얼린 기준 파일이 바뀌었다 — %s" % 바뀜[:5]
    기록 = (뿌리 / "실행기록.txt").read_text(encoding="utf-8")
    assert "종료코드: 0" in 기록


def test_맞대기가_다름을_잡는다(tmp_path):
    # 검사기를 먼저 시험한다 — 헛통과를 막으려고
    import openpyxl
    가, 나 = tmp_path / "가", tmp_path / "나"
    for d in (가, 나):
        d.mkdir()
        (d / "a.csv").write_text("x,1\n자리,%s\\s13_judge\n잰_날짜,2026-09-18 18:3%d\n"
                                 % (d, 3 if d is 가 else 4), encoding="utf-8")
        wb = openpyxl.Workbook()
        wb.active.append(["id", "값"])
        wb.active.append(["r1", "같음"])
        wb.save(d / "b.xlsx")
    assert 맞대기(가, 나) == [], "경로와 시각만 다른 것은 같음이어야 한다"

    (나 / "c.md").write_text("더 생김", encoding="utf-8")
    assert any("한쪽에만" in x for x in 맞대기(가, 나))
    (나 / "c.md").unlink()

    (나 / "a.csv").write_text("x,2\n", encoding="utf-8")
    assert any("내용 다름" in x for x in 맞대기(가, 나))

    wb = openpyxl.Workbook()
    wb.active.append(["id", "값"])
    wb.active.append(["r1", "다름"])
    wb.save(나 / "b.xlsx")
    assert any("칸 값 다름" in x for x in 맞대기(가, 나))

    # 섹션 4 에 더한 시각 규칙 — 시각만 다르면 같음, 같은 줄의 다른 글자가 다르면 다름
    for d, t in ((가, "20:28"), (나, "20:34")):
        (d / "c.md").write_text("만든 날 2026-09-18 %s · 원본 `x.xlsx`\n" % t, encoding="utf-8")
        (d / "s.json").write_text('{\n "생성": "2026-09-18T%s:10",\n "행": 1\n}\n' % t, encoding="utf-8")
    assert not any(("c.md" in x or "s.json" in x) for x in 맞대기(가, 나))
    (나 / "c.md").write_text("만든 날 2026-09-18 20:34 · 원본 `y.xlsx`\n", encoding="utf-8")
    assert any("c.md" in x for x in 맞대기(가, 나)), "시각 말고 다른 글자가 다르면 다름이어야 한다"

    # 2026-09-21 교차점검에 더한 날짜 규칙 — handoff.py 가 적는 「도는 날」
    for d, 날 in ((가, "2026-09-18"), (나, "2026-09-21")):
        (d / "인계서.md").write_text("작성 %s · 자동 생성 (`handoff.py`)\n| **접수** | %s |\n" % (날, 날),
                                   encoding="utf-8")
        (d / "보정요청.csv").write_text("번호,접수일,갈래,처리상태\n1,%s,기준서공백,대기\n" % 날, encoding="utf-8")
    assert not any(("인계서" in x or "보정요청" in x) for x in 맞대기(가, 나)), "날짜만 다르면 같음이어야 한다"
    (나 / "보정요청.csv").write_text("번호,접수일,갈래,처리상태\n1,2026-09-21,기준서공백,반영\n", encoding="utf-8")
    assert any("보정요청.csv" in x for x in 맞대기(가, 나)), "다른 칸(처리상태)이 다르면 다름이어야 한다"
    (나 / "보정요청.csv").write_text("번호,접수일,갈래,처리상태\n1,2026-09-21,기준서공백,대기\n", encoding="utf-8")

    assert 맞대기(tmp_path / "없음", 가), "없는 폴더는 같음이 아니다"
    (tmp_path / "빈1").mkdir(), (tmp_path / "빈2").mkdir()
    assert 맞대기(tmp_path / "빈1", tmp_path / "빈2"), "빈 폴더끼리는 같음이 아니다"


@pytest.mark.parametrize("이름", sorted(기준_만들기.실행들))
def test_기준이_재현된다(이름):
    """사본을 새 자리에 다시 차려 돌리면 얼린 기준과 같아야 한다.

    ★ 지금은 후보가 옛 도구 사본 자신이다 — 시험 틀과 기준이 맞는지 보는 것.
      새 도구가 생기면(섹션 4~6) 같은 틀로 새 도구를 돌려 맞댄다.
    """
    그릇 = BASELINE / "시험실행" / 이름
    if 그릇.exists():
        shutil.rmtree(그릇)
    그릇.mkdir(parents=True)
    assert 기준_만들기.차려서_돌리기(이름, 그릇) == 0, (그릇 / "실행기록.txt").read_text(encoding="utf-8")[-2000:]
    얼린 = BASELINE / "실행" / ("%s_1" % 이름)
    다름 = 맞대기(얼린 / "2판", 그릇 / "2판")
    assert not 다름, "얼린 기준과 다르다:\n" + "\n".join(다름[:20])


import 기준_만들기_2차  # noqa: E402

# ★ 2차 기준(8월 · 옛 판독 꾸러미 엔진)과 지금 엔진(09-07 동결본) 사이에 **일부러 다른** 파생 칸 (sky 2026-10-07 「1번」)
#   엔진 09-07 판이 `brand_display` 를 「그 댓글이 자사 얘기(entity_role=product_brand)일 때만」 채운다
#   (대시보드 LG 필터가 전체의 93% 를 끌어오던 것을 sky 가 고치게 했다 — engine/src/dashboard60/data_contract.py `_brand_display`).
#   영상 요약의 브랜드 칸은 그 칸으로 계산한다. 그 밖의 칸이 하나라도 다르면 시험은 실패한다.
허용칸_2차 = {"raw_voc": {"brand_display"}, "inquiry_rows": {"brand_display"},
            "video_summary": {"main_brand", "main_brand_note", "main_brand_breakdown"}}
# 지금 실제로 다른 칸 수 — 또 달라지면 드러나게 못박는다 (2026-09-22 들여온 엔진으로 센 것)
허용칸_2차_칸수 = {
    "2차번들A": {("raw_voc", "brand_display"): 3500, ("inquiry_rows", "brand_display"): 146,
               ("video_summary", "main_brand"): 2, ("video_summary", "main_brand_note"): 33,
               ("video_summary", "main_brand_breakdown"): 33},
    "2차번들B": {("raw_voc", "brand_display"): 3483, ("inquiry_rows", "brand_display"): 389,
               ("video_summary", "main_brand"): 3, ("video_summary", "main_brand_note"): 37,
               ("video_summary", "main_brand_breakdown"): 37},
}


@pytest.mark.parametrize("이름", 기준_만들기_2차.실행들)
def test_판독스킬이_2차_기준과_같다(이름):
    """★ 새 도구 시험 (섹션 4) — 판독 스킬의 판독폴더_차리기.py 로 차린 폴더에서 같은 일을 하면
    얼린 2차 기준(옛 꾸러미로 돌린 것)과 결과가 같아야 한다.

    맞대는 자리는 도구가 만든 결과뿐이다 (`볼자리`). 차린 폴더의 지문 · 옛 판이었던 문서는 달라도 된다.
    """
    그릇 = BASELINE / "시험실행" / ("스킬_%s" % 이름)
    if 그릇.exists():
        shutil.rmtree(그릇)
    그릇.mkdir(parents=True)
    코드 = 기준_만들기_2차.차려서_돌리기(이름, 그릇, 기준_만들기_2차.스킬로_차리기)
    assert 코드 == 0, (그릇 / "실행기록.txt").read_text(encoding="utf-8")[-2000:]
    얼린 = BASELINE / "실행" / ("%s_1" % 이름) / "판독"
    센것: dict = {}
    for 자리 in 기준_만들기_2차.볼자리[이름]:
        다름 = 맞대기(얼린 / 자리, 그릇 / "판독" / 자리, 허용칸=허용칸_2차, 허용센것=센것)
        assert not 다름, "%s 가 얼린 기준과 다르다:\n%s" % (자리, "\n".join(다름[:20]))
    # 허용한 칸은 **몇 칸이 다른지까지** 못박는다 (sky 2026-10-07 「1번」) — 엔진이 또 바뀌면 여기서 드러난다
    본것 = {(t, c): n for (_, t, c), n in 센것.items()}
    기대 = 허용칸_2차_칸수.get(이름)
    if 기대 is not None:
        assert 본것 == 기대, "허용한 칸의 다른 칸 수가 바뀌었다 — 엔진이 또 바뀌었나:\n  지금 %s\n  적어 둔 것 %s" % (본것, 기대)


import 총괄후보  # noqa: E402


@pytest.mark.parametrize("이름", ("3차준비", "3차마무리"))
def test_총괄스킬로_차린_자리가_3차_기준과_같다(이름):
    """★ 새 도구 시험 (섹션 5) — 총괄 스킬의 총괄자리_차리기 로 차린 자리에 같은 입력을 얹어 돌리면
    얼린 3차 기준(옛 2판 사본 전체에서 돌린 것)과 결과가 같아야 한다 → 차린 자리에 모자람이 없다.

    ★ 엔진 — 섹션 7 ① (2026-09-22) 부터 플러그인 엔진이 얼린 기준을 만든 동결본(live_merge a94e731) 그 자체다.
      그래서 따로 넣지 않고 **차린 자리의 엔진(= 플러그인 엔진)** 으로 돌린다. 전에는 판독 꾸러미 엔진이라 엑셀 번들 시트가 달랐다.
    """
    그릇 = BASELINE / "시험실행" / ("총괄_%s" % 이름)
    if 그릇.exists():
        shutil.rmtree(그릇)
    그릇.mkdir(parents=True)
    코드 = 총괄후보.차려서_돌리기(이름, 그릇)
    assert 코드 == 0, (그릇 / "실행기록.txt").read_text(encoding="utf-8")[-2000:]
    얼린 = BASELINE / "실행" / ("%s_1" % 이름) / "2판"
    판 = 그릇 / "총괄" / "2판"
    for 자리 in 총괄후보.볼자리[이름]:
        다름 = 맞대기(얼린 / 자리, 판 / 자리, 얼린, 판)
        assert not 다름, "%s 가 얼린 기준과 다르다:\n%s" % (자리, "\n".join(다름[:20]))
    if 이름 == "3차준비":
        # 총괄이 차린 감독 폴더 = 감독 스킬 모양 74개(새 판 · 섹션 7 ① 엔진 · 섹션 7a ③ 안내서 그림 6 포함)
        #   + 감독 입력 + 시작 안내 · 편향검사·정답지 없음
        입력수 = len(list((판 / "s13_judge").glob("judge_*")))
        for 감독 in ("3차 감독1", "3차 감독2"):
            d = 판 / "_감독폴더" / 감독
            assert len([p for p in d.rglob("*") if p.is_file()]) == 74 + 입력수 + 1, 감독
            assert not (d / "스크립트" / "편향검사.py").exists()
            assert not list(d.rglob("ab_mapping*"))
            assert (d / "0_여기서_시작하십시오.md").is_file()


def test_가3_뒤처리가_N_A행을_다시_빼지_않는다():
    """★ 섹션 5b (sky 2026-09-22 「§17 대로 남긴다」) — 새 동작으로 3차 마무리를 돌리면
    얼린 기준에서 「+미판정→제외」 로 빠졌던 N/A 행만 normal 로 남고, 나머지 행은 그대로여야 한다.
    (얼린 기준 재현 시험은 옛 동작 스위치로 돈다 — 둘이 같이 있어야 바꾼 것이 정확히 그것뿐임을 안다)"""
    import csv, io
    그릇 = BASELINE / "시험실행" / "총괄_3차마무리_새동작"
    if 그릇.exists():
        shutil.rmtree(그릇)
    그릇.mkdir(parents=True)
    assert 총괄후보.차려서_돌리기("3차마무리", 그릇, 옛판=False) == 0,         (그릇 / "실행기록.txt").read_text(encoding="utf-8")[-2000:]

    def 읽기(p):
        return {r["atomic_id"]: r for r in csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig")))}
    얼린 = 읽기(BASELINE / "실행" / "3차마무리_1" / "2판" / "s15_master" / "raw_voc.csv")
    새것 = 읽기(그릇 / "총괄" / "2판" / "s15_master" / "raw_voc.csv")
    뺐던 = {k for k, r in 얼린.items() if "+미판정→제외" in (r.get("decided_by") or "")}
    assert 뺐던, "얼린 기준에 옛 규칙으로 뺀 행이 없다 — 시험 대상을 못 찾았다 (통과가 아니다)"
    assert set(얼린) == set(새것), "행이 늘거나 줄었다"
    for k in 뺐던:
        # 옛 규칙은 topic 도 N/A 로 덮었다 — 원래 값(N/A 또는 미분류)이 남아야 한다
        assert 새것[k]["status"] == "normal" and 새것[k]["topic"] in ("N/A", "미분류"), (k, 새것[k]["status"], 새것[k]["topic"])
        assert "+미판정→제외" not in (새것[k].get("decided_by") or "")
    바뀐 = [k for k in 얼린 if k not in 뺐던 and
           any(얼린[k].get(c) != 새것[k].get(c) for c in ("status", "topic", "scope_exclusion_reason", "decided_by"))]
    assert not 바뀐, "옛 규칙과 상관없는 행이 바뀌었다: %s" % 바뀐[:5]


def test_허용한_칸만_빼고_나머지는_잡는다():
    """★ 일부러 틀리게 — 허용칸은 다름에서 빼고 센다. 허용하지 않은 칸은 잡는다 (sky 2026-10-07 「1번」)."""
    머리 = ("atomic_id", "topic", "brand_display")
    가 = [머리, ("a-01", "흡입력", "LG"), ("a-02", "소음/진동", "LG")]
    나 = [머리, ("a-01", "흡입력", None), ("a-02", "소음/진동", None)]
    센것: dict = {}
    assert 맞대기_mod._칸다름("x.xlsx", "raw_voc", 가, 나, {"brand_display"}, 센것) == []
    assert 센것 == {("x.xlsx", "raw_voc", "brand_display"): 2}, 센것

    다른칸 = [머리, ("a-01", "청소/관리", None), ("a-02", "소음/진동", None)]
    센것 = {}
    걸림 = 맞대기_mod._칸다름("x.xlsx", "raw_voc", 가, 다른칸, {"brand_display"}, 센것)
    assert len(걸림) == 1 and "topic" in 걸림[0], 걸림
    assert 센것 == {("x.xlsx", "raw_voc", "brand_display"): 2}, 센것

    # 머리줄이 다르면 그것부터 다름이다
    assert 맞대기_mod._칸다름("x.xlsx", "raw_voc", 가, [("atomic_id", "topic", "brand")] + 나[1:],
                          {"brand_display"}, {})
    # 행 수가 다르면 다름이다
    assert 맞대기_mod._칸다름("x.xlsx", "raw_voc", 가, 나[:2], {"brand_display"}, {})


# ─────────────────────────────────────────────────────────────────────────────
# 사람 결정이 든 4차 — **옛 최종 결과 그 자체**와 댄다 (2026-10-23 · 결정 0005 의 빈 칸)
#
# sky 2026-10-23 — 「이 패키지로 나온 최종 아웃풋이 첨부한 『★ 2판_최최종_아웃풋번들』 이
#   나오도록 돌아가는 skill 이 맞는지」
#
# ★ 다른 얼린 기준과 **다른 방식**이다. 다른 것들은 「옛 도구 사본을 돌려 만든 정답」 과 대지만,
#   이것은 **옛 저장소가 실제로 낸 최종 번들**과 댄다. 더 센 대조다 — 사람 결정 683칸이 든 판이다.
#   그 번들은 `원본사본/2판/_판독패키지/_결과/master_final/` 에 이미 복사돼 있다 (2026-09 복사).
#   `★ 2판_최최종_아웃풋번들.xlsx` 와 **같은 파일**임을 지문으로 확인했다 (결정 0005).
#
# ★ 옛 저장소는 **읽지도 않는다** — 기준 자리의 사본만 쓴다 (결정 0001 · 변화 0).
#   (옛 자리의 경로는 `paths.py` 한 곳에만 둔다 — 2026-10-23 검사가 이 줄을 잡았다)
# ★ 값으로 댄다 (`data_only=True`). 색·너비 같은 꾸밈은 `번들꾸미기` 얼린 기준이 따로 지킨다.
# ─────────────────────────────────────────────────────────────────────────────
_옛번들지문 = "6e07c2281953a8c29a0d38ec7c1f499bd9a61d77b5a549c77734854cb7be0c3f"
# 4차_반영 이 읽는 입력 — 어느 자리에서 읽는지는 도구 안에 적혀 있다
_4차입력 = [
    "_판독패키지/_결과/master_final/raw_voc.csv",
    "_판독패키지/_결과/master_final/분리제안.csv",
    "_판독패키지/_결과/master_final/수정로그_오류확정.csv",
    "_판독패키지/_결과/master_final/수정로그_재검토필요.csv",
    "_판독패키지/_결과/master_final/편향검사.csv",
    "_판독패키지/_결과/master_final/구조적결함.csv",
    "_판독패키지/_결과/master_final/기준서개정후보.csv",
    "_판독패키지/_결과/master_final/판정불일치.csv",
    "s15_master/raw_voc.csv",
    "s15_master/사람이볼목록.csv",
    "_인계/보정요청.csv",
]
_옛번들 = "_판독패키지/_결과/master_final/voc_dashboard_export_bundle_2차시험본.xlsx"


def _시트값(길: Path, 이름: str) -> list:
    """시트 한 장을 값만 읽는다 — 꼬리 빈 줄은 뺀다."""
    import openpyxl                                            # noqa: PLC0415

    책 = openpyxl.load_workbook(길, read_only=True, data_only=True)
    try:
        줄들 = [tuple("" if c is None else str(c) for c in 행)
              for 행 in 책[이름].iter_rows(values_only=True)]
    finally:
        책.close()
    while 줄들 and not any(줄들[-1]):
        줄들.pop()
    return 줄들


def test_사람결정이_든_4차가_옛_최종번들을_그대로_낸다():
    """★ 결정 0005 의 빈 칸 하나를 메운다.

    우리 총괄 스킬이 차린 자리에 **옛 4차 입력**(사람 결정이 든 것)을 얹어
    우리 `4차_반영.py` 를 돌리면, 옛 저장소가 낸 최종 번들과 **시트 17장이 값까지 같아야** 한다.
    """
    원본 = BASELINE / "원본사본" / "2판"
    assert 원본.is_dir(), "기준 자리의 옛 2판 사본이 없다 — %s" % 원본
    옛번들길 = 원본 / _옛번들
    assert 옛번들길.is_file(), "옛 최종 번들이 없다 — %s" % 옛번들길
    assert _sha(옛번들길) == _옛번들지문, (
        "옛 최종 번들이 바뀌었다 — 이것은 대조의 **기준**이다. 결정 0005 를 다시 본다.")
    for r in _4차입력:
        assert (원본 / r).is_file(), "옛 4차 입력이 없다 — %s" % r

    그릇 = BASELINE / "시험실행" / "4차_사람결정"
    if 그릇.exists():
        shutil.rmtree(그릇)
    그릇.mkdir(parents=True)

    # ① 우리 스킬로 자리를 차린다 (옛 폴더 모양은 스킬이 만든다)
    차리개 = _뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts" / "총괄자리_차리기.py"
    r = subprocess.run([sys.executable, "-X", "utf8", str(차리개), str(그릇), "2판"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    판 = 그릇 / "2판"
    assert (판 / "4차_반영.py").is_file(), "차린 자리에 4차_반영.py 가 없다"

    # ② 옛 4차 입력을 얹는다 (**복사만** — 기준 자리의 사본에서 읽는다)
    for rel in _4차입력:
        q = 판 / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(원본 / rel, q)

    # ③ 우리 4차_반영 을 돌린다
    env = dict(os.environ, VOC_ENGINE=str(판 / "engine"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-B", str(판 / "4차_반영.py")], cwd=str(판),
                       env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    (그릇 / "실행기록.txt").write_text(
        "종료코드: %d\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
        % (r.returncode, r.stdout, r.stderr), encoding="utf-8")
    assert r.returncode == 0, (r.stdout + r.stderr)[-3000:]

    # ④ 옛 최종 번들과 **시트 17장을 값까지** 댄다
    import openpyxl                                            # noqa: PLC0415

    낸것 = 판 / _옛번들
    assert 낸것.is_file(), "번들을 못 냈다 — %s" % 낸것
    책옛 = openpyxl.load_workbook(옛번들길, read_only=True, data_only=True)
    책새 = openpyxl.load_workbook(낸것, read_only=True, data_only=True)
    try:
        옛시트, 새시트 = list(책옛.sheetnames), list(책새.sheetnames)
    finally:
        책옛.close()
        책새.close()
    assert 새시트 == 옛시트, ("시트 이름·순서가 다르다\n  옛 %s\n  새 %s" % (옛시트, 새시트))
    assert len(옛시트) == 17, "옛 번들 시트가 %d장으로 바뀌었다" % len(옛시트)
    다름 = []
    for s in 옛시트:
        a, b = _시트값(옛번들길, s), _시트값(낸것, s)
        if a == b:
            continue
        첫 = None
        for i in range(min(len(a), len(b))):
            for j in range(max(len(a[i]), len(b[i]))):
                x = a[i][j] if j < len(a[i]) else ""
                y = b[i][j] if j < len(b[i]) else ""
                if x != y:
                    첫 = "%d행 %d칸 — 옛 %r / 새 %r" % (i + 1, j + 1, x[:60], y[:60])
                    break
            if 첫:
                break
        다름.append("[%s] 행 옛 %d / 새 %d · %s" % (s, len(a), len(b), 첫 or "행 수만 다르다"))
    assert not 다름, "옛 최종 번들과 다른 시트 %d장:\n%s" % (len(다름), "\n".join(다름))

    # ⑤ 데이터는 건드리지 않았는지 — 4차_반영 은 raw_voc 를 고치지 않아야 한다
    #   (분리 승인이 없고 묶음이 이미 맞으므로. 여기서 바뀌면 둘 중 하나가 깨진 것이다)
    assert _sha(판 / "_판독패키지/_결과/master_final/raw_voc.csv") == _sha(
        원본 / "_판독패키지/_결과/master_final/raw_voc.csv"), (
        "4차_반영 이 raw_voc 를 고쳤다 — 옛 판에서는 고칠 것이 없었다")


# ─────────────────────────────────────────────────────────────────────────────
# 보고서 — **앞으로 안 변하는가** (회귀 방지 · 2026-10-26)
#
# ★ 다른 기준들과 묻는 것이 다르다. 보고서는 옛 저장소에 **댈 상대가 0개**다 (2026-10-23 실측 ·
#   결정 0005). 섹션 8 에서 새로 지은 것이라 「기존과 같은가」 가 성립하지 않는다.
#   그래서 우리 출력을 얼려 **누가 조용히 바꾸는 것**을 잡는다.
#
# ★ 「만든 날」 한 줄만 자리표로 바꾸고 나머지는 전량 댄다. 그 줄이 사라지거나 늘어나면
#   **그것도 실패**로 본다 — 자리표로 바꾸는 범위를 넓히면 진짜 변화를 덮는다.
# ─────────────────────────────────────────────────────────────────────────────
_만든날 = re.compile(r"만든 날</b> \d{4}-\d{2}-\d{2} \d{2}:\d{2}")


def _보고서_맞출꼴(글: str, 어디: str) -> str:
    """때만 자리표로. ★ 그 줄이 **정확히 하나**가 아니면 실패한다."""
    셈 = len(_만든날.findall(글))
    assert 셈 == 1, "%s 의 「만든 날」 줄이 %d개다 (하나여야 한다)" % (어디, 셈)
    return _만든날.sub("만든 날</b> [때]", 글)


def test_보고서가_얼린_기준과_같다():
    """우리 보고서 스킬을 **고정된 입력**으로 다시 돌려 얼린 것과 전량 댄다."""
    import 보고서기준_만들기 as 보고서후보                       # noqa: PLC0415

    얼린 = BASELINE / "실행" / "보고서_1" / 보고서후보.낼이름
    assert 얼린.is_file(), (
        "얼린 보고서 기준이 없다 — %s\n"
        "  만들려면: python tests/baseline/보고서기준_만들기.py" % 얼린)
    그릇 = BASELINE / "시험실행" / "보고서"
    if 그릇.exists():
        shutil.rmtree(그릇)
    코드 = 보고서후보.돌리기(그릇)
    assert 코드 == 0, (그릇 / "실행기록.txt").read_text(encoding="utf-8")[-2000:]
    낸것 = 그릇 / 보고서후보.낼이름
    assert 낸것.is_file(), "보고서를 못 냈다 — %s" % 낸것
    a = _보고서_맞출꼴(얼린.read_text(encoding="utf-8"), "얼린 기준")
    b = _보고서_맞출꼴(낸것.read_text(encoding="utf-8"), "다시 돌린 것")
    if a != b:
        줄a, 줄b = a.split("\n"), b.split("\n")
        다름 = ["%d줄: 얼린 %r / 새 %r" % (i + 1, 줄a[i][:90], 줄b[i][:90])
              for i in range(min(len(줄a), len(줄b))) if 줄a[i] != 줄b[i]]
        raise AssertionError(
            "보고서가 얼린 기준과 다르다 (줄 %d → %d)\n%s"
            % (len(줄a), len(줄b), "\n".join(다름[:15]) or "줄 수만 다르다"))


def test_보고서는_두_번_돌려도_같다():
    """★ 얼린 기준을 믿을 수 있나 — 두 번째 실행(`보고서_2`)과 대본다.

    다른 자리가 「만든 날」 뿐이어야 한다. 더 있으면 그 자리는 기준에서 빼야 한다.
    """
    하나 = BASELINE / "실행" / "보고서_1" / "VoC_분석보고서.html"
    둘 = BASELINE / "실행" / "보고서_2" / "VoC_분석보고서.html"
    for p in (하나, 둘):
        assert p.is_file(), "두 번 돌린 기준이 없다 — %s" % p
    a = _보고서_맞출꼴(하나.read_text(encoding="utf-8"), "보고서_1")
    b = _보고서_맞출꼴(둘.read_text(encoding="utf-8"), "보고서_2")
    assert a == b, "같은 입력으로 두 번 돌렸는데 「만든 날」 말고도 다른 자리가 있다"


def test_보고서_기준의_입력지문이_한_곳에서만_정해진다():
    """★ 같은 지문이 두 벌이 되면 한쪽만 고쳐도 모른다 (공통 규칙 6).

    4차 시험과 보고서 기준이 **같은 입력 파일**을 쓴다. 지문을 두 곳에 적었으니 같아야 한다.
    """
    import 보고서기준_만들기 as 보고서후보                       # noqa: PLC0415

    assert 보고서후보.입력지문 == _옛번들지문, (
        "보고서 기준과 4차 시험이 적은 입력 지문이 다르다 — 둘은 같은 파일이다")
