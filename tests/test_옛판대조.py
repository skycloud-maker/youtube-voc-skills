# -*- coding: utf-8 -*-
"""옛 2판과 대는 장치가 **맞게 세는가** — 돈 쓰기 전에 본다 (2026-10-29).

★ 왜 이 시험이 있나 — sky 2026-10-29

  > 「②로 해주세요, 장치 먼저 만들고 돈 쓰기 전에 확인」

  `tools/옛판_결과대조.py` 가 우리 결과를 옛 2판 최종과 행·칸마다 대어
  **「몇 % 같은가」** 를 낸다. 그 수로 「완성인가」 에 답할 참이다.
  **장치가 틀리면 그 수가 거짓이 되고, 전량을 돌리는 돈($460 어림)을 버린다.**
  그래서 돌리기 전에 **일부러 틀리게 만들어** 정말 잡는지 본다 (공통 규칙 4-3).

보는 것
-------
  · 같은 것을 **같다**고 하는가 (옛 ↔ 옛 = 100%)
  · 다른 것을 **다르다**고 하는가 — N 행을 바꾸면 **정확히 N 행**을 잡는가
  · 행을 지우거나 더하면 **한쪽만 있는 것**으로 세는가 (분리·병합이 여기 드러난다)
  · 열쇠가 없거나 비면 **크게 실패**하는가 (「못 찾음」 은 통과가 아니다)
  · 칸 묶음이 **겹치거나 합이 안 맞으면** 드러나는가
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
sys.path.insert(0, str(REPO / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

도구쪽 = REPO / "tools" / "옛판_결과대조.py"
옛최종 = BASELINE / "원본사본" / "2판" / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"

# 묶음마다 한 칸씩 — 기준 글이 어느 묶음에 넣었는지는 도구가 긁는다
A칸, B칸, C칸, D칸, 밖칸 = "original_voc", "atomic_index", "voc_cleaned", "topic", "sentiment_dir"
_머리 = ["atomic_id", A칸, B칸, C칸, D칸, 밖칸]


@pytest.fixture(scope="module")
def 도구():
    assert 도구쪽.is_file(), "못 찾음: %s" % 도구쪽
    spec = importlib.util.spec_from_file_location("옛판_결과대조", 도구쪽)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _쓰기(쪽: Path, 줄들: list) -> Path:
    쪽.parent.mkdir(parents=True, exist_ok=True)
    with 쪽.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_머리)
        w.writeheader()
        w.writerows(줄들)
    return 쪽


def _본보기(n: int = 20) -> list:
    return [{"atomic_id": "a%03d" % i, A칸: "원문 %d" % i, B칸: str(i),
             C칸: "정제 %d" % i, D칸: "소음/진동", 밖칸: "부정"} for i in range(n)]


# ── 같은 것을 같다고 하는가 ────────────────────────────────────────

def test_옛것을_자기자신과_대면_다_같다(도구):
    """★ 장치의 바닥. 여기서 100%가 안 나오면 그 뒤 숫자는 다 거짓이다."""
    if not 옛최종.is_file():
        pytest.skip("기준 자리의 옛 2판 최종이 없다 — %s" % 옛최종)
    r = 도구.대조(옛최종, 옛최종)
    n = r["양쪽"]
    assert n == 6846, "양쪽 행이 %d다 (6846 이어야 한다)" % n
    assert not r["옛에만"] and not r["새에만"], "자기 자신인데 한쪽만 있는 행이 있다"
    assert not r["옛칸만"] and not r["새칸만"], "자기 자신인데 한쪽만 있는 칸이 있다"
    다른칸 = [c for c, 같다 in r["칸결과"].items() if 같다 != n]
    assert not 다른칸, "자기 자신인데 다른 칸이 있다 — %s" % 다른칸
    for 갈래 in ("A", "B", "C", "D"):
        assert r["묶음결과"][갈래] == n, "%s 묶음이 100%%가 아니다" % 갈래


def test_사람결정을_넣은_우리_최종이_옛_최종과_행칸까지_같다(도구):
    """★ sky 가 물은 그 수다 — 「최종2판 결과물과 거의 동일한? 혹은 백프로?」

    `tests/test_baseline.py` 의 `test_사람결정이_든_4차가_옛_최종번들을_그대로_낸다` 가
    우리 `4차_반영.py` 에 **옛 4차 입력(사람 결정)** 을 얹어 돌려 낸 결과를 남긴다.
    그 시험은 **최종 번들 엑셀의 시트 17장**을 본다. 여기서는 같은 결과를
    **행 6,846 · 칸 89 단위로** 댄다 — 2026-10-29 에 **100.00%** 였다.

    ★ 이 수가 뜻하는 것과 뜻하지 않는 것을 갈라 둔다.
      뜻하는 것    — **도구가 옛 도구와 같은 일을 한다** (4차 반영 · 사람 결정 포함)
      뜻하지 않는 것 — 2차·3차의 **AI 판정**이 옛 판정과 같다는 것. 여기서는 AI 판정을
                     **옛것으로 고정**하고 도구만 댄다. 그것은 2판을 통째로 돌려야 나온다.

    ★ 그 자리는 `test_baseline.py` 가 만든다 (한 번에 44분). 없으면 건너뛴다 —
      건너뜀은 **통과가 아니다.** 돌린 뒤 여기서 본다.
    """
    자리 = (BASELINE / "시험실행" / "4차_사람결정" / "2판"
          / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv")
    if not 자리.is_file():
        pytest.skip("4차_사람결정 결과가 없다 — `pytest tests/test_baseline.py` 를 먼저 돌린다")
    if not 옛최종.is_file():
        pytest.skip("기준 자리의 옛 2판 최종이 없다")
    r = 도구.대조(옛최종, 자리)
    n = r["양쪽"]
    assert n == 6846 and not r["옛에만"] and not r["새에만"], (
        "행이 안 맞는다 — 양쪽 %d · 옛에만 %d · 새에만 %d"
        % (n, len(r["옛에만"]), len(r["새에만"])))
    assert not r["옛칸만"] and not r["새칸만"], "칸이 안 맞는다"
    다른칸 = {c: n - 같다 for c, 같다 in r["칸결과"].items() if 같다 != n}
    assert not 다른칸, ("우리 최종이 옛 최종과 다르다 — 칸 %d개: %s"
                       % (len(다른칸), 다른칸))


def test_묶음_합이_칸_수와_맞는다(도구):
    """★ 묶음 어디에도 안 들어간 칸이 조용히 사라지면 % 가 거짓이 된다."""
    if not 옛최종.is_file():
        pytest.skip("기준 자리의 옛 2판 최종이 없다")
    r = 도구.대조(옛최종, 옛최종)
    합 = sum(len(r["묶은칸"][g]) for g in "ABCD") + len(r["안덮인"])
    assert 합 == len(r["같은칸"]), (
        "묶음 합 %d 인데 칸은 %d 다 — 어디에도 안 들어간 칸이 있거나 두 번 센 칸이 있다"
        % (합, len(r["같은칸"])))
    assert len(r["같은칸"]) == 89, "옛 최종의 칸이 %d개로 바뀌었다" % len(r["같은칸"])


def test_한_칸이_두_묶음에_들면_크게_실패한다(도구, tmp_path, monkeypatch):
    """★ 실제로 겪은 것 — 긁기가 설명 칸까지 읽어 `confidence_rating` 이 B·D 에 둘 다 들어갔다."""
    가짜 = tmp_path / "분류.md"
    가짜.write_text(
        "# A. 보지 않는다 — 원천 (1칸)\n\n| 컬럼 | 근거 |\n|---|---|\n| `topic` | 겹치게 적었다 |\n\n"
        "# D. ★ 판정 대상 — LLM (1칸)\n\n| 축 | 컬럼 | 핵심 규칙 |\n|---|---|---|\n"
        "| topic | `topic` | 같은 칸을 두 묶음에 |\n",
        encoding="utf-8")
    monkeypatch.setattr(도구, "분류글", 가짜)
    with pytest.raises(SystemExit) as e:
        도구.칸묶음()
    assert "두 묶음" in str(e.value), str(e.value)


def test_설명_칸의_이름을_칸으로_읽지_않는다(도구, tmp_path, monkeypatch):
    """★ 「컬럼」 칸만 읽는다 — 핵심 규칙 칸의 이름은 설명이지 칸이 아니다."""
    가짜 = tmp_path / "분류.md"
    가짜.write_text(
        "# D. ★ 판정 대상 — LLM (1칸)\n\n| 축 | 컬럼 | 핵심 규칙 |\n|---|---|---|\n"
        "| topic | `topic` | `confidence_rating` 만 엔진 계산이다 |\n",
        encoding="utf-8")
    monkeypatch.setattr(도구, "분류글", 가짜)
    묶음, _ = 도구.칸묶음()
    assert 묶음["D"] == ["topic"], "설명 칸의 이름까지 읽었다 — %s" % 묶음["D"]


def test_줄임말_evidence_를_펴_준다(도구, tmp_path, monkeypatch):
    """`+ 각 \\`_evidence\\`` 는 칸 이름이 아니다 — 같은 줄의 `*_score` 에서 펴 준다."""
    가짜 = tmp_path / "분류.md"
    가짜.write_text(
        "# D. ★ 판정 대상 — LLM (3칸)\n\n| 축 | 컬럼 | 핵심 규칙 |\n|---|---|---|\n"
        "| TEE | `tee_time_score` · `tee_effort_score` + 각 `_evidence` | 근거가 인용인가 |\n",
        encoding="utf-8")
    monkeypatch.setattr(도구, "분류글", 가짜)
    묶음, _ = 도구.칸묶음()
    assert "tee_time_evidence" in 묶음["D"] and "tee_effort_evidence" in 묶음["D"], 묶음["D"]
    assert "_evidence" not in 묶음["D"], "줄임말을 칸으로 남겼다"


# ── 다른 것을 다르다고 하는가 ──────────────────────────────────────

@pytest.mark.parametrize("바꿀칸,묶음", [(D칸, "D"), (A칸, "A"), (B칸, "B"), (C칸, "C")])
def test_N행을_바꾸면_정확히_N행을_잡는다(도구, tmp_path, 바꿀칸, 묶음):
    """★ 하나만 틀려도 안 되고, 셋을 틀렸는데 둘만 잡아도 안 된다."""
    옛 = _쓰기(tmp_path / "옛.csv", _본보기())
    줄들 = _본보기()
    바꾼수 = 7
    for x in 줄들[:바꾼수]:
        x[바꿀칸] = "달라진 값"
    새 = _쓰기(tmp_path / "새.csv", 줄들)
    r = 도구.대조(옛, 새)
    n = r["양쪽"]
    assert n == 20, n
    assert r["칸결과"][바꿀칸] == n - 바꾼수, (
        "%s 칸에서 %d행을 바꿨는데 같은 행이 %d다 (%d 이어야 한다)"
        % (바꿀칸, 바꾼수, r["칸결과"][바꿀칸], n - 바꾼수))
    assert r["묶음결과"][묶음] == n - 바꾼수, "%s 묶음이 %d다" % (묶음, r["묶음결과"][묶음])
    # 안 건드린 칸은 그대로여야 한다
    for c in (set(_머리) - {"atomic_id", 바꿀칸}):
        assert r["칸결과"][c] == n, "안 건드린 칸 %s 가 달라졌다" % c


def test_분류_밖_칸도_센다(도구, tmp_path):
    """★ 분류 글이 안 다루는 칸을 **빼 버리면** 다름이 숨는다."""
    옛 = _쓰기(tmp_path / "옛.csv", _본보기())
    줄들 = _본보기()
    for x in 줄들[:3]:
        x[밖칸] = "긍정"
    새 = _쓰기(tmp_path / "새.csv", 줄들)
    r = 도구.대조(옛, 새)
    assert 밖칸 in r["안덮인"], "%s 를 분류 밖으로 세지 않았다 — %s" % (밖칸, r["안덮인"])
    assert r["칸결과"][밖칸] == 17, r["칸결과"][밖칸]
    assert r["안덮인_같다"] == 17, r["안덮인_같다"]


def test_행을_지우면_옛에만_으로_센다(도구, tmp_path):
    옛 = _쓰기(tmp_path / "옛.csv", _본보기())
    새 = _쓰기(tmp_path / "새.csv", _본보기()[:15])
    r = 도구.대조(옛, 새)
    assert r["양쪽"] == 15 and len(r["옛에만"]) == 5 and not r["새에만"], (
        r["양쪽"], r["옛에만"], r["새에만"])


def test_행을_더하면_새에만_으로_센다(도구, tmp_path):
    옛 = _쓰기(tmp_path / "옛.csv", _본보기())
    줄들 = _본보기()
    줄들.append({"atomic_id": "a999", A칸: "새 조각", B칸: "99",
                C칸: "", D칸: "소음/진동", 밖칸: "부정"})
    새 = _쓰기(tmp_path / "새.csv", 줄들)
    r = 도구.대조(옛, 새)
    assert r["양쪽"] == 20 and not r["옛에만"] and r["새에만"] == ["a999"], (
        r["양쪽"], r["옛에만"], r["새에만"])


def test_칸을_지우면_한쪽만_있는_칸으로_센다(도구, tmp_path):
    옛 = _쓰기(tmp_path / "옛.csv", _본보기())
    쪽 = tmp_path / "새.csv"
    with 쪽.open("w", encoding="utf-8", newline="") as f:
        머리 = [c for c in _머리 if c != D칸]
        w = csv.DictWriter(f, fieldnames=머리)
        w.writeheader()
        for x in _본보기():
            w.writerow({k: x[k] for k in 머리})
    r = 도구.대조(옛, 쪽)
    assert r["옛칸만"] == [D칸], r["옛칸만"]
    assert D칸 not in r["칸결과"], "없는 칸을 센 것처럼 적었다"


# ── 못 찾으면 크게 실패하는가 ──────────────────────────────────────

def test_열쇠_칸이_없으면_크게_실패한다(도구, tmp_path):
    쪽 = tmp_path / "열쇠없음.csv"
    with 쪽.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[A칸, D칸])
        w.writeheader()
        w.writerow({A칸: "원문", D칸: "소음/진동"})
    with pytest.raises(SystemExit) as e:
        도구.읽기(쪽)
    assert "atomic_id" in str(e.value), str(e.value)


def test_열쇠가_비면_크게_실패한다(도구, tmp_path):
    줄들 = _본보기(3)
    줄들[1]["atomic_id"] = ""
    쪽 = _쓰기(tmp_path / "빈열쇠.csv", 줄들)
    with pytest.raises(SystemExit) as e:
        도구.읽기(쪽)
    assert "빈 행" in str(e.value), str(e.value)


def test_파일이_없으면_크게_실패한다(도구, tmp_path):
    with pytest.raises(SystemExit) as e:
        도구.읽기(tmp_path / "없는것.csv")
    assert "못 찾음" in str(e.value), str(e.value)


def test_분류_글이_없으면_크게_실패한다(도구, tmp_path, monkeypatch):
    monkeypatch.setattr(도구, "분류글", tmp_path / "없는글.md")
    with pytest.raises(SystemExit) as e:
        도구.칸묶음()
    assert "못 찾음" in str(e.value), str(e.value)


def test_같아야_가_다름을_잡는다(도구, tmp_path):
    """`--같아야` 는 장치를 확인할 때 쓴다 — 다르면 종료코드 1 이어야 한다."""
    옛 = _쓰기(tmp_path / "옛.csv", _본보기())
    줄들 = _본보기()
    줄들[0][D칸] = "가격/가성비"
    새 = _쓰기(tmp_path / "새.csv", 줄들)
    assert 도구.main([str(새), "--옛", str(옛), "--같아야"]) == 1, "다른데 0 으로 끝났다"
    assert 도구.main([str(옛), "--옛", str(옛), "--같아야"]) == 0, "같은데 1 로 끝났다"
