# -*- coding: utf-8 -*-
"""바탕 바꾼 효과를 재는 도구 (`tools/바탕바꾼효과_재기.py`) 가 **맞게 세는지** 본다.

★ 왜 이 시험이 있나 (2026-11-02) — sky 가 「버려지는 수까지 재서 보고해주세요」 라고 했고,
  그 수는 **내가 앞서 틀리게 댄 수**다 (「codex 가 이긴 251건」 은 감독 판정이 이기므로
  바탕과 무관하다). 틀린 수를 두 번 대지 않으려면 **세는 장치부터** 확인해야 한다.

  그래서 네 가지를 지킨다 —
    ① 입력이 없거나 열쇠가 없으면 **멈춘다** (「못 찾음」 을 0% 로 돌려주지 않는다)
    ② 바탕을 바꿨는데 다른 칸이 0개면 **종료코드 1** — 「차이 없음」 이 아니라 「안 닿았다」
    ③ 얻음 · 버림 · 둘다틀림을 **만든 표로 정확히** 세는지 본다
    ④ 판정 24칸 가운데 데이터에 없는 칸이 있으면 **찍고 멈춘다**
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
도구쪽 = REPO / "tools" / "바탕바꾼효과_재기.py"


def _칸들() -> list[str]:
    """도구와 **같은 자리**에서 긁는다 — 시험이 칸 이름을 따로 적으면 두 벌이 된다."""
    글 = (REPO / "plugin" / "shared" / "tools" / "build_master.py").read_text(encoding="utf-8")
    i = 글.find("CC_FIELDS = [")
    j = 글.find("]", i)
    칸 = [x.strip().strip("'\"") for x in 글[i + len("CC_FIELDS = ["):j].replace("\n", " ").split(",")]
    return [x for x in 칸 if x]


def _쓰기(쪽: Path, 행들: list[dict], 칸: list[str]) -> Path:
    쪽.parent.mkdir(parents=True, exist_ok=True)
    with 쪽.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["atomic_id"] + 칸)
        w.writeheader()
        for r in 행들:
            w.writerow(r)
    return 쪽


def _행(aid: str, 칸: list[str], **값) -> dict:
    r = {"atomic_id": aid}
    for c in 칸:
        r[c] = 값.get(c, "같은값")
    return r


def _돌리기(*인자: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", "-B", str(도구쪽), *인자],
                       cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_두_결과를_안_주면_멈춘다():
    코드, 말 = _돌리기()
    assert 코드 != 0 and "두 결과를 주십시오" in 말, 말[-800:]


def test_없는_파일을_주면_멈춘다(tmp_path):
    코드, 말 = _돌리기(str(tmp_path / "a.csv"), str(tmp_path / "b.csv"),
                   "--옛", str(tmp_path / "o.csv"))
    assert 코드 != 0 and "못 찾음" in 말, 말[-800:]


def test_열쇠_칸이_없으면_멈춘다(tmp_path):
    for 이름 in ("옛.csv", "코.csv", "클.csv"):
        (tmp_path / 이름).write_text("a,b\n1,2\n", encoding="utf-8")
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 != 0 and "열쇠" in 말, 말[-800:]


def test_바탕이_아무것도_안_바꾸면_크게_실패한다(tmp_path):
    """★ 알맹이 — `--바탕` 이 스킬 경로에서 **버려지던 고장이 실제로 있었다** (2026-11-02).
    그때 두 결과는 똑같이 나온다. 「차이가 없다」 로 보고하면 **고장을 숨기는 것**이다."""
    칸 = _칸들()
    행들 = [_행("a1", 칸), _행("a2", 칸)]
    _쓰기(tmp_path / "옛.csv", 행들, 칸)
    _쓰기(tmp_path / "코.csv", 행들, 칸)
    _쓰기(tmp_path / "클.csv", 행들, 칸)       # ★ 코와 클이 똑같다
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 1, "다른 칸이 0개인데 통과했다 — 안 닿은 것을 차이 없음으로 보여 준다\n%s" % 말[-900:]
    assert "안 닿았다" in 말, 말[-900:]


def test_얻음과_버림을_정확히_센다(tmp_path):
    """만든 표로 **셋을 하나씩** 둔다 — 얻음 1 · 버림 1 · 둘다틀림 1."""
    칸 = _칸들()
    b, c = "brand", "cej"
    옛 = [_행("a1", 칸, **{b: "LG"}), _행("a2", 칸, **{b: "삼성"}), _행("a3", 칸, **{c: "구매"})]
    코 = [_행("a1", 칸, **{b: "코덱스값"}),      # 클이 맞다  → 얻음
          _행("a2", 칸, **{b: "삼성"}),          # 코가 맞다  → 버림
          _행("a3", 칸, **{c: "코덱스값"})]      # 둘 다 틀림
    클 = [_행("a1", 칸, **{b: "LG"}),
          _행("a2", 칸, **{b: "클로드값"}),
          _행("a3", 칸, **{c: "클로드값"})]
    _쓰기(tmp_path / "옛.csv", 옛, 칸)
    _쓰기(tmp_path / "코.csv", 코, 칸)
    _쓰기(tmp_path / "클.csv", 클, 칸)
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 0, 말[-900:]
    합줄 = [l for l in 말.splitlines() if l.strip().startswith("합")]
    assert 합줄, 말[-900:]
    수 = [int(x.lstrip("+")) for x in 합줄[0].split()[1:]]
    assert 수[:4] == [3, 1, 1, 1], ("바탕정함·얻음·버림·둘다틀림 = %s, 3·1·1·1 이어야 한다\n%s"
                                   % (수[:4], 말[-900:]))
    assert "**버림 1칸**" in 말, 말[-900:]


def test_판정칸이_데이터에_없으면_찍고_멈춘다(tmp_path):
    """★ 조용히 버리지 않는다 — 없는 칸을 빼고 세면 「24칸을 다 봤다」 는 **거짓**이 된다."""
    칸 = _칸들()[:-1]                   # 한 칸을 일부러 뺀다
    행들 = [_행("a1", 칸)]
    _쓰기(tmp_path / "옛.csv", 행들, 칸)
    _쓰기(tmp_path / "코.csv", 행들, 칸)
    _쓰기(tmp_path / "클.csv", 행들, 칸)
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 1 and "데이터에 없는 칸" in 말, 말[-900:]


def test_판정24칸을_build_master_에서_긁는다():
    """손으로 적으면 두 벌이 된다 (공통 규칙 6). 24칸이 아니면 도구가 멈춰야 한다."""
    글 = 도구쪽.read_text(encoding="utf-8")
    assert "CC_FIELDS = [" in 글, "build_master 에서 긁지 않는다 — 손으로 적은 목록이 있다"
    assert len(_칸들()) == 24, "CC_FIELDS 가 24칸이 아니다 — %d칸" % len(_칸들())


def test_일치율은_내려간_칸을_따로_다시_적는다(tmp_path):
    """★ 표 속에 섞어 두면 **좋은 쪽만 읽힌다.** 내가 「내려간 칸이 다섯」 이라고
    틀리게 센 일이 2026-11-02 에 실제로 있었다 — 임시 목록 17칸만 보았기 때문이다.
    그래서 도구가 **24칸을 다 세어** 내려간 것을 따로 다시 적게 했다."""
    칸 = _칸들()
    b, c = "brand", "cej"
    옛 = [_행("a1", 칸, **{b: "LG", c: "구매"}), _행("a2", 칸, **{b: "LG", c: "구매"})]
    코 = [_행("a1", 칸, **{b: "코", c: "구매"}), _행("a2", 칸, **{b: "코", c: "구매"})]
    클 = [_행("a1", 칸, **{b: "LG", c: "클"}), _행("a2", 칸, **{b: "LG", c: "클"})]
    _쓰기(tmp_path / "옛.csv", 옛, 칸)
    _쓰기(tmp_path / "코.csv", 코, 칸)
    _쓰기(tmp_path / "클.csv", 클, 칸)
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"), "--일치율")
    assert 코드 == 0, 말[-900:]
    assert "칸마다 — 옛 2판과 몇 % 같은가" in 말, 말[-900:]
    # brand 는 올랐고(0→100%) cej 는 내려갔다(100→0%) — 내려간 것을 따로 적어야 한다
    assert "**내려간 칸이 1개다**" in 말, ("내려간 칸을 따로 다시 적지 않는다\n%s" % 말[-1200:])
    assert "cej -100.00%" in 말, 말[-1200:]


def test_내려간_칸이_없으면_없다고_말한다(tmp_path):
    """★ 「없음」 과 「안 셌음」 을 가른다 — 조용히 넘기지 않는다."""
    칸 = _칸들()
    옛 = [_행("a1", 칸, brand="LG")]
    코 = [_행("a1", 칸, brand="코")]
    클 = [_행("a1", 칸, brand="LG")]
    _쓰기(tmp_path / "옛.csv", 옛, 칸)
    _쓰기(tmp_path / "코.csv", 코, 칸)
    _쓰기(tmp_path / "클.csv", 클, 칸)
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"), "--일치율")
    assert 코드 == 0 and "내려간 칸이 없다" in 말, 말[-900:]
