# -*- coding: utf-8 -*-
"""정확도 채점 — 채점지를 만들고, 사람이 매긴 것을 **그대로** 세는가 (2026-11-06).

★ 왜 이 시험이 있나 — sky 2026-11-06 「정확도 채점과 큰 규모 실행은 실무에서 직접 하게
  될 단계이지만, 여기서 그게 돌아가서 그런 결과는 나오는 skill 을 만들어놔야」.
  전에는 채점지를 **만드는** 도구만 있었고 **세는** 도구가 없었다.

★ 알맹이는 「심은 답이 그대로 나오나」 다 — 정답을 알고 X 를 심어 두고, 도구가 낸 숫자가
  심은 숫자와 **칸마다** 같은지 본다. 그리고 「못 찾음 · 0칸 · 덜 채움 · 이상한 값 ·
  데이터가 바뀜」 을 **통과로 돌려주지 않는지** 본다.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "plugin" / "shared" / "tools"))

칸머리 = ["atomic_id", "atomic_voc", "decided_by", "status", "scope_exclusion_reason",
        "product_category", "topic", "cej", "sentiment_dir", "brand", "inquiry_type"]


@pytest.fixture()
def 채():
    return importlib.reload(importlib.import_module("정확도_채점"))


def _최종(p: Path, 합의=40, 감독=12, 사람=5, 제외비=4) -> Path:
    """가짜 최종 엑셀 — 합의 40 · 감독 12 · 사람이 정한 5. 넷에 하나는 제외."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "raw_voc"
    ws.append(칸머리)
    i = 0
    for 구, n, 누가 in (("합의", 합의, "reader_agree"), ("감독", 감독, "judge_agree(A)"),
                       ("사람", 사람, "sky_결정")):
        for _ in range(n):
            i += 1
            제외 = i % 제외비 == 0
            ws.append(["S%03d-01" % i, "댓글 %d" % i, 누가,
                       "scope_excluded" if 제외 else "normal",
                       "no_analytic_value" if 제외 else None, "로봇청소기",
                       "N/A" if 제외 else "흡입력", "해당없음" if 제외 else "사용",
                       "중립" if 제외 else "부정", "N/A" if 제외 else "LG", "none"])
    wb.save(p)
    return p


def _매기기(채점지: Path, 규칙) -> dict:
    """규칙(구간, 칸, 순번) → 'O'/'X'/'?'/''/그 밖. 심은 것을 (구간, 칸) 마다 센 것을 돌려준다."""
    wb = openpyxl.load_workbook(채점지)
    ws = wb["채점"]
    h = [c.value for c in ws[2]]
    심은 = {}
    for r in range(3, ws.max_row + 1):
        구 = ws.cell(r, 2).value
        for _, 보임 in __import__("정확도_채점").칸들:
            c = ws.cell(r, h.index(보임 + " O/X") + 1)
            if c.value == "—":
                continue
            k = (구, 보임)
            n = 심은.setdefault(k, {"O": 0, "X": 0, "?": 0, "": 0})
            v = 규칙(구, 보임, sum(n.values()))
            c.value = v or None
            n[v if v in n else ""] += 1
    wb.save(채점지)
    return 심은


def test_구간마다_정한_수만큼_뽑고_사람이_정한_행은_뺀다(채, tmp_path):
    채점지 = 채.만들기(_최종(tmp_path / "f.xlsx"), tmp_path / "o", 30)
    ws = openpyxl.load_workbook(채점지)["채점"]
    구간들 = [ws.cell(r, 2).value for r in range(3, ws.max_row + 1)]
    assert 구간들.count("합의") == 30          # 40 중 30
    assert 구간들.count("감독") == 12          # 12 뿐이라 전량
    assert "사람" not in 구간들
    assert (tmp_path / "o" / 채.안내이름).is_file()


def test_다시_만들어도_같은_행이다(채, tmp_path):
    f = _최종(tmp_path / "f.xlsx")
    a = openpyxl.load_workbook(채.만들기(f, tmp_path / "a"))["채점"]
    b = openpyxl.load_workbook(채.만들기(f, tmp_path / "b"))["채점"]
    열 = len(list(a.iter_rows(max_row=2))[1])
    ids = lambda ws: [ws.cell(r, 열).value for r in range(3, ws.max_row + 1)]
    assert ids(a) == ids(b)


def test_제외된_행은_제외_여부만_묻는다(채, tmp_path):
    ws = openpyxl.load_workbook(채.만들기(_최종(tmp_path / "f.xlsx"), tmp_path / "o"))["채점"]
    h = [c.value for c in ws[2]]
    for r in range(3, ws.max_row + 1):
        제외 = str(ws.cell(r, h.index("제외 여부 확정") + 1).value).startswith("제외")
        topic = ws.cell(r, h.index("topic O/X") + 1).value
        assert (topic == "—") == 제외


def test_심은_답이_칸마다_그대로_나온다(채, tmp_path):
    """★ 알맹이 — topic 은 셋에 하나 X, 감독 cej 는 전부 X, 합의 brand 는 하나 ?."""
    f = _최종(tmp_path / "f.xlsx")
    채점지 = 채.만들기(f, tmp_path / "o")

    def 규칙(구, 보임, i):
        if 보임 == "topic" and i % 3 == 0:
            return "X"
        if 보임 == "cej" and 구 == "감독":
            return "X"
        if 보임 == "brand" and 구 == "합의" and i == 0:
            return "?"
        return "O"
    심은 = _매기기(채점지, 규칙)
    코드, 글 = 채.세기(채점지, f)
    assert 코드 == 0, 글
    import csv
    표 = {(r["구간"], r["칸"]): r for r in csv.DictReader(
        open(tmp_path / "o" / "채점결과.csv", encoding="utf-8-sig"))}
    for (구, 보임), n in 심은.items():
        r = 표[(구, 보임)]
        assert (int(r["맞음"]), int(r["틀림"]), int(r["모름"])) == (n["O"], n["X"], n["?"]), (구, 보임)
        기대 = n["O"] / (n["O"] + n["X"])
        assert abs(float(r["정확도"]) - 기대) < 1e-4
        assert r["판단"] == 채.판단(기대)
    assert 표[("감독", "cej")]["판단"] == "사람이 본다"


def test_선은_90과_80이다(채):
    assert 채.판단(0.90) == "믿고 간다"
    assert 채.판단(0.8999) == "참고"
    assert 채.판단(0.80) == "참고"
    assert 채.판단(0.7999) == "사람이 본다"
    assert 채.판단(None) == "잴 수 없음"


def test_한_칸도_안_매겼으면_점수를_내지_않는다(채, tmp_path):
    f = _최종(tmp_path / "f.xlsx")
    코드, 글 = 채.세기(채.만들기(f, tmp_path / "o"), f)
    assert 코드 == 2 and "하나도 없습니다" in 글
    assert not (tmp_path / "o" / "채점결과.md").exists()


def test_채점지를_못_찾으면_통과가_아니다(채, tmp_path):
    코드, 글 = 채.세기(tmp_path / "없음.xlsx")
    assert 코드 == 2 and "못 찾음" in 글


def test_덜_채웠으면_미완이라_적는다(채, tmp_path):
    f = _최종(tmp_path / "f.xlsx")
    채점지 = 채.만들기(f, tmp_path / "o")
    _매기기(채점지, lambda 구, 보임, i: "" if (구 == "합의" and i == 0) else "O")
    코드, 글 = 채.세기(채점지, f)
    assert 코드 == 3 and "미완" in 글


def test_읽을_수_없는_값은_빼고_알린다(채, tmp_path):
    f = _최종(tmp_path / "f.xlsx")
    채점지 = 채.만들기(f, tmp_path / "o")
    _매기기(채점지, lambda 구, 보임, i: "글쎄" if (보임 == "topic" and i == 0) else "O")
    코드, 글 = 채.세기(채점지, f)
    assert 코드 == 1 and "글쎄" in 글


def test_채점지를_만든_뒤_데이터가_바뀌면_그_칸은_빼고_알린다(채, tmp_path):
    f = _최종(tmp_path / "f.xlsx")
    채점지 = 채.만들기(f, tmp_path / "o")
    _매기기(채점지, lambda 구, 보임, i: "O")
    wb = openpyxl.load_workbook(f)
    ws = wb["raw_voc"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 7).value == "흡입력":
            ws.cell(r, 7).value = "소음"      # 첫 넣음 행의 topic 을 바꾼다
            break
    wb.save(f)
    코드, 글 = 채.세기(채점지, f)
    assert 코드 == 1 and "데이터가 바뀐 칸" in 글


def test_사람이_매긴_채점지는_덮어쓰지_않는다(채, tmp_path):
    f = _최종(tmp_path / "f.xlsx")
    채점지 = 채.만들기(f, tmp_path / "o")
    _매기기(채점지, lambda 구, 보임, i: "X")
    전 = 채점지.read_bytes()
    채.만들기(f, tmp_path / "o")
    assert 채점지.read_bytes() == 전


# ── 돌리개 `--채점` ─────────────────────────────────────────────────────

@pytest.fixture()
def 돌리개():
    sys.path.insert(0, str(REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))
    return importlib.reload(importlib.import_module("한줄_돌리기"))


def test_돌리개_최종이_없으면_멈춘다(돌리개, tmp_path, capsys):
    assert 돌리개.채점하기(tmp_path) == 2
    assert "못 찾았습니다" in capsys.readouterr().out


def test_돌리개_처음엔_채점지를_만들고_매기면_센다(돌리개, tmp_path, capsys):
    """실제 길 — 아웃풋 2 의 최종 엑셀로 채점지를 만들고(종료 2 · 아직 안 매김),
    사람이 매긴 뒤 같은 명령이 점수를 낸다(종료 0)."""
    판 = tmp_path / "판"
    (판 / "아웃풋2_최종").mkdir(parents=True)
    _최종(판 / "아웃풋2_최종" / "voc_dashboard_export_bundle_x.xlsx")
    assert 돌리개.채점하기(판) == 2
    채점지 = 판 / "아웃풋2_최종" / "채점" / "채점지.xlsx"
    assert 채점지.is_file()
    assert 돌리개.채점하기(판) == 2                       # 안 매겼으면 점수 없음
    assert not (채점지.parent / "채점결과.md").exists()
    _매기기(채점지, lambda 구, 보임, i: "O")
    assert 돌리개.채점하기(판) == 0
    assert "100.0%" in (채점지.parent / "채점결과.md").read_text(encoding="utf-8")


def test_4차반영이_채점지를_같이_낸다(돌리개):
    """4차 반영 끝에 채점지를 만드는 줄이 있는가 — 실제 4차는 AI 를 띄워야 해서 여기서는 글로 본다."""
    import inspect
    글 = inspect.getsource(돌리개.사차반영)
    assert '채점도구(), "만들기"' in 글
    assert 돌리개.채점도구().is_file()
