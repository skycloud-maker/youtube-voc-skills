# -*- coding: utf-8 -*-
"""`tools/일치율이_정확도인가_재기.py` 가 **쏠림을 집어내는지** 본다.

★ 왜 이 시험이 있나 (2026-11-03) — sky 물음

  > 「저렇게 급격히 높아진 퍼센트가 그런 오류가 섞인건 아닌가 … 분석정확도
  >  (저 퍼센트가 이 의미맞죠?)」

  내가 「`brand` 50.05 → 90.97%」 를 **좋아진 증거**로 보고했는데, 옛 2판의 brand 는
  92.58% 가 「LG」 다. 즉 **「LG」 만 적는 멍청한 규칙이 92.58% 를 받는다** —
  내가 자랑한 90.97% 는 그보다 **낮다.** 일치율을 정확도라 부른 것이 틀렸다.

  그 틀림을 다시 하지 않으려면 **집어내는 장치**가 있어야 한다. 네 가지를 지킨다 —
    ① 멍청규칙을 못 넘긴 칸을 **✗ 로 집어낸다** (조용히 표에만 두지 않는다)
    ② 원문 칸이 없으면 **멈춘다** — 근거율을 0% 로 돌려주면 「안 쟀음」 을 숨긴다
    ③ 근거율을 정확히 센다 (별명 「엘지」 · 「트롬」 도 LG 근거로 알아본다)
    ④ 옛 기준에 있는 **[다5] 위반**을 센다 — 거기서는 어긋나는 것이 맞는 것이다
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
도구쪽 = REPO / "tools" / "일치율이_정확도인가_재기.py"


def _칸들() -> list[str]:
    """도구와 **같은 자리**에서 긁는다 — 시험이 칸 이름을 따로 적으면 두 벌이 된다."""
    글 = (REPO / "plugin" / "shared" / "tools" / "build_master.py").read_text(encoding="utf-8")
    i = 글.find("CC_FIELDS = [")
    칸 = [x.strip().strip("'\"") for x in
          글[i + len("CC_FIELDS = ["):글.find("]", i)].replace("\n", " ").split(",")]
    return [x for x in 칸 if x]


def _쓰기(쪽: Path, 행들: list[dict], 더: tuple[str, ...] = ("atomic_voc", "original_voc")) -> Path:
    칸 = ["atomic_id"] + list(더) + _칸들()
    쪽.parent.mkdir(parents=True, exist_ok=True)
    with 쪽.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=칸)
        w.writeheader()
        for r in 행들:
            w.writerow({c: r.get(c, "같은값") for c in 칸})
    return 쪽


def _돌리기(*인자: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", "-B", str(도구쪽), *인자],
                       cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _근거줄(말: str, 이름: str) -> tuple[int, int, int]:
    """근거율 표의 한 줄에서 (구체브랜드 · 원문에있음 · 원문에없음) 을 **숫자로** 뽑는다.

    ★ 왜 글자 찾기로 안 하나 — 처음에 `"100.0%" in 줄` 로 보았더니, 별명표를 **꺼서
      일부러 고장냈는데도 시험이 통과했다.** 「100.0%」 가 「원문에없음」 칸에도 찍히기
      때문이다. 느슨한 assert 는 고장을 못 잡는다 (2026-11-03 에 실제로 겪었다)."""
    줄 = [l for l in 말.splitlines() if l.strip().startswith(이름)]
    assert 줄, "근거율 표에 %s 줄이 없다:\n%s" % (이름, 말[-1500:])
    수 = re.findall(r"(\d+)\(\s*[\d.]+%\)", 줄[0])
    머리 = re.match(r"\s*\S+\s+(\d+)\s", 줄[0])
    assert 머리 and len(수) == 2, "근거율 줄을 못 읽었다: %r" % 줄[0]
    return int(머리.group(1)), int(수[0]), int(수[1])


def test_두_결과를_안_주면_멈춘다():
    코드, 말 = _돌리기()
    assert 코드 != 0 and "두 결과를 주십시오" in 말, 말[-800:]


def test_없는_파일을_주면_멈춘다(tmp_path):
    코드, 말 = _돌리기(str(tmp_path / "a.csv"), str(tmp_path / "b.csv"),
                   "--옛", str(tmp_path / "o.csv"))
    assert 코드 != 0 and "못 찾음" in 말, 말[-800:]


def test_원문_칸이_없으면_멈춘다(tmp_path):
    """★ 원문을 못 보면 근거율을 **잴 수 없다.** 0% 로 돌려주면 「안 쟀음」 을 숨긴다."""
    행 = [{"atomic_id": "a1", "brand": "LG"}]
    for 이름 in ("옛.csv", "코.csv", "클.csv"):
        _쓰기(tmp_path / 이름, 행, 더=())        # ★ atomic_voc · original_voc 를 뺀다
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 1, "원문 칸이 없는데 통과했다 — 안 잰 것을 숨긴다\n%s" % 말[-900:]
    assert "원문 칸이 없다" in 말, 말[-900:]


def test_멍청규칙을_못_넘긴_칸을_집어낸다(tmp_path):
    """★ 알맹이 — 내가 2026-11-03 에 틀린 그대로다.

    ★ 차이를 **-1% 로 아주 작게** 둔다. 처음엔 -10% 로 두었는데, 도구의 문턱을
      `<= 0` 에서 `<= -5` 로 **일부러 고장냈을 때 시험이 그냥 통과했다** — 차이가 커서
      문턱 안에 들어왔기 때문이다. 실제 `brand` 의 차이는 **-1.61%** 다. 작은 차이를
      놓치는 것이 바로 위험한 고장이므로, 시험도 그 자리에서 재야 한다 (2026-11-03).

    옛 2판 100행 가운데 95행이 「LG」 → 멍청규칙 95%. claude 가 94행만 맞히면 94% 이고,
    그것은 **잘한 것이 아니다.** 표에만 두지 않고 ✗ 로 집어내야 한다."""
    옛 = [{"atomic_id": "a%03d" % i, "brand": ("LG" if i < 95 else "삼성"),
           "atomic_voc": "글", "original_voc": "글"} for i in range(100)]
    코 = [dict(r, brand="N/A") for r in 옛]
    # claude 는 **「LG」 만 적는다** — 그 자체로 95% 다. 거기서 한 행을 더 틀려 94% → -1.00%
    클 = [dict(r, brand="LG") for r in 옛]
    클[0]["brand"] = "로보락"
    _쓰기(tmp_path / "옛.csv", 옛)
    _쓰기(tmp_path / "코.csv", 코)
    _쓰기(tmp_path / "클.csv", 클)
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 0, 말[-900:]
    assert "멍청규칙을 못 넘긴 칸" in 말, ("못 넘긴 칸을 집어내지 않는다\n%s" % 말[-1500:])
    brand줄 = [l for l in 말.splitlines() if l.strip().startswith("· brand")]
    assert brand줄, ("brand 를 못 넘긴 칸으로 집어내지 않았다\n%s" % 말[-1500:])
    assert "최빈값=「LG」" in brand줄[0], brand줄[0]


def test_멍청규칙을_넘으면_집어내지_않는다(tmp_path):
    """★ 「없음」 과 「안 셌음」 을 가른다 — 넘은 칸을 ✗ 로 찍으면 거짓 경보다."""
    옛 = [{"atomic_id": "a%d" % i, "brand": ("LG" if i < 5 else "삼성"),
           "atomic_voc": "LG 삼성", "original_voc": "LG 삼성"} for i in range(10)]
    코 = [dict(r, brand="N/A") for r in 옛]
    클 = [dict(r) for r in 옛]                 # 전부 맞힌다 → 100% > 멍청규칙 50%
    _쓰기(tmp_path / "옛.csv", 옛)
    _쓰기(tmp_path / "코.csv", 코)
    _쓰기(tmp_path / "클.csv", 클)
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 0, 말[-900:]
    brand줄 = [l for l in 말.splitlines() if l.strip().startswith("· brand")]
    assert not brand줄, ("넘은 칸을 못 넘겼다고 찍었다 — 거짓 경보\n%s" % 말[-1200:])


def test_근거율을_정확히_센다(tmp_path):
    """원문에 브랜드가 있는 행 1 · 없는 행 2 — 33.3% / 66.7% 여야 한다.

    ★ 왜 「1 대 1」 로 안 두나 — 도구는 **없음이 있음보다 많을 때** 경고한다.
      정확히 50% 는 「많다」 가 아니므로 경고가 안 나오는 것이 맞다. 경계에 걸쳐 두면
      시험이 무엇을 지키는지 흐려지므로, **진짜 과반**인 자리에서 잰다."""
    옛 = [{"atomic_id": "a1", "brand": "LG", "atomic_voc": "LG 세탁기 좋아요", "original_voc": ""},
          {"atomic_id": "a2", "brand": "LG", "atomic_voc": "배수캡 있으면 되나요", "original_voc": ""},
          {"atomic_id": "a3", "brand": "LG", "atomic_voc": "설치 문의드려요", "original_voc": ""}]
    _쓰기(tmp_path / "옛.csv", 옛)
    _쓰기(tmp_path / "코.csv", [dict(r, brand="N/A") for r in 옛])
    _쓰기(tmp_path / "클.csv", [dict(r) for r in 옛])
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 0, 말[-900:]
    assert _근거줄(말, "옛2판") == (3, 1, 2), ("근거율을 틀리게 센다 — %s" % (_근거줄(말, "옛2판"),))
    assert "33.3%" in 말 and "66.7%" in 말, 말[-1200:]
    assert "원문에 없다" in 말, ("절반 넘게 근거가 없는데 말하지 않는다\n%s" % 말[-1200:])


def test_별명을_알아본다(tmp_path):
    """★ 「엘지」 · 「트롬」 도 LG 근거다 — 글자만 보면 근거를 **없다고 깎아내린다.**"""
    옛 = [{"atomic_id": "a1", "brand": "LG", "atomic_voc": "엘지 건조기", "original_voc": ""},
          {"atomic_id": "a2", "brand": "LG", "atomic_voc": "트롬 쓰는데", "original_voc": ""}]
    _쓰기(tmp_path / "옛.csv", 옛)
    _쓰기(tmp_path / "코.csv", [dict(r, brand="N/A") for r in 옛])
    _쓰기(tmp_path / "클.csv", [dict(r) for r in 옛])
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 0, 말[-900:]
    # ★ 숫자로 본다 — 「100.0%」 글자 찾기는 「원문에없음」 칸에도 걸려 고장을 못 잡았다
    assert _근거줄(말, "옛2판") == (2, 2, 0), \
        ("엘지·트롬을 LG 근거로 알아보지 않는다 — %s" % (_근거줄(말, "옛2판"),))


def test_다5_위반을_센다(tmp_path):
    """★ 옛 기준이 **틀린 자리**를 센다 — 거기서는 어긋나는 것이 맞는 것이다."""
    옛 = [{"atomic_id": "a1", "brand": "unknown", "atomic_voc": "글", "original_voc": ""},
          {"atomic_id": "a2", "brand": "creator_channel", "atomic_voc": "글", "original_voc": ""},
          {"atomic_id": "a3", "brand": "LG", "atomic_voc": "LG", "original_voc": ""}]
    _쓰기(tmp_path / "옛.csv", 옛)
    _쓰기(tmp_path / "코.csv", [dict(r, brand="N/A") for r in 옛])
    _쓰기(tmp_path / "클.csv", [dict(r, brand="LG") for r in 옛])
    코드, 말 = _돌리기(str(tmp_path / "코.csv"), str(tmp_path / "클.csv"),
                   "--옛", str(tmp_path / "옛.csv"))
    assert 코드 == 0, 말[-900:]
    옛줄 = [l for l in 말.splitlines() if "unknown" in l and l.strip().startswith("옛2판")]
    assert 옛줄 and "위반 2행" in 옛줄[0], ("다5 위반 2행을 못 센다\n%s" % 말[-1500:])
    assert "어긋나는 것이 맞는 것" in 말, 말[-1200:]


def test_판정24칸을_build_master_에서_긁는다():
    """손으로 적으면 두 벌이 된다 (공통 규칙 6)."""
    글 = 도구쪽.read_text(encoding="utf-8")
    assert "CC_FIELDS = [" in 글, "build_master 에서 긁지 않는다 — 손으로 적은 목록이 있다"
    assert len(_칸들()) == 24, "CC_FIELDS 가 24칸이 아니다 — %d칸" % len(_칸들())
