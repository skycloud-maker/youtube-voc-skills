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
import shutil
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
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
