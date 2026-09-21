# -*- coding: utf-8 -*-
"""같은 문서가 여러 곳에 있는 것을 **한 판으로 맞춘다.**

★ 왜 (2026-08-24)
  같은 문서가 세 곳에 있다.

      _판독패키지\\0_붙여넣을_프롬프트_감독.md    ← 실제로 고치는 자리
      0_붙여넣을_프롬프트_감독.md                ← 뿌리 사본
      _정본\\최신\\0_붙여넣을_프롬프트_감독.md     ← 정본 사본

  손으로 맞추다 **오늘 또 갈렸다.** 어제도 갈렸고 push 훅이 잡았다.
  ★ 갈린 것을 매번 손으로 맞추면 매번 빠진다. 도구로 맞춘다.

  ★★ 어느 쪽이 최신인지는 **날짜로 정하지 않는다** —
    파일을 만지기만 해도 날짜가 바뀐다.
    **`_판독패키지` 가 원본**이다. 거기 있는 것을 나머지에 퍼뜨린다.
    `_판독패키지` 에 없는 문서는 뿌리가 원본이다.

★★ 2026-09-18 — **이름이 다른 쌍둥이를 못 봤다.**
  `_판독패키지/1a_기준문서_정본_1부.md` 의 짝이 뿌리에는 `21a_…` 라는 이름으로 있다.
  파일 이름으로만 짝을 찾았으니 「짝 없음」 으로 보고 **조용히 넘어갔다.**
  그래서 「구독」 정의가 5벌 중 1벌에만 들어갔고, 「정본」 폴더는 옛판으로 남았다.
  같은 쌍둥이가 셋 있었다 — 1a↔21a · 1b↔21b · 6↔25.
  → 앞 번호(`21a_`·`6_`)를 뗀 이름으로도 짝을 찾는다. 짝이 둘 이상이면 고르지 않고 멈춘다.
  → 판 사본(`_N판/`, `_N판/_판독패키지/`)도 맞춘다 — 거기도 사본이 있었다.
  → `--보기만` 에서 갈린 것이 있으면 **종료코드 1** 이다. 전에는 늘 0 이라
    마무리 검사가 「통과」 로 찍었다.

쓰기
    python 정본_맞추기.py            맞춘다
    python 정본_맞추기.py --보기만    무엇이 갈렸는지 보기만 한다 (갈렸으면 종료코드 1)
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

원본자리 = ROOT / "_판독패키지"
_판들 = sorted(p for p in ROOT.glob("_*판") if p.is_dir() and p.name[1:-1].isdigit())
사본자리 = [ROOT, ROOT / "_정본" / "최신"] + [x for 판 in _판들
                                          for x in (판, 판 / "_판독패키지")]
_앞번호 = re.compile(r"^\d+[a-z]?_")


def _알맹이(이름: str) -> str:
    """`21a_기준문서_정본_1부.md` → `기준문서_정본_1부.md`"""
    return _앞번호.sub("", 이름)


def _짝(자리: Path, 원이름: str) -> tuple[Path | None, str]:
    """이 자리에서 원본의 짝을 찾는다. 같은 이름이 먼저, 없으면 앞 번호만 다른 이름.

    돌려주는 것 — (짝, 사연). 짝이 둘 이상이면 (None, "여럿") — 고르지 않는다.
    """
    같은이름 = 자리 / 원이름
    if 같은이름.exists():
        return 같은이름, ""
    if not 자리.is_dir():
        return None, ""
    후보 = [p for p in 자리.iterdir()
            if p.is_file() and p.suffix == Path(원이름).suffix
            and _알맹이(p.name) == _알맹이(원이름)]
    if len(후보) == 1:
        return 후보[0], "이름 다른 쌍둥이"
    if len(후보) > 1:
        return None, "여럿"
    return None, ""


def _지문(p: Path) -> str:
    """줄바꿈은 하나로 맞춰 센다 — CRLF/LF 때문에 헛것이 나온 적이 있다."""
    b = p.read_bytes()
    try:
        b = b.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode()
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(b).hexdigest()[:16]


def main() -> int:
    보기만 = "--보기만" in sys.argv
    print("=" * 70)
    print("  정본 맞추기 — 같은 문서를 한 판으로")
    print("=" * 70)
    print("  원본 자리 : %s" % 원본자리.name)
    print("  사본 자리 : %s" % " · ".join(
        str(p.relative_to(ROOT)) if p != ROOT else "뿌리" for p in 사본자리))
    print()

    맞춘것, 갈린것, 못가림 = 0, [], []

    def 맞추기(원: Path, 사본: Path, 사연: str) -> None:
        nonlocal 맞춘것
        if _지문(사본) == _지문(원):
            return
        표 = str(사본.relative_to(ROOT))
        if 사연:
            표 += "  (%s)" % 사연
        갈린것.append((원.name, 표))
        if not 보기만:
            shutil.copy2(원, 사본)
            맞춘것 += 1

    for 원 in sorted(원본자리.glob("*.md")) + sorted(원본자리.glob("*.csv")):
        for 자리 in 사본자리:
            사본, 사연 = _짝(자리, 원.name)
            if 사연 == "여럿":
                못가림.append((원.name, str(자리.relative_to(ROOT)) or "뿌리"))
                continue
            if 사본 is None:
                continue                      # 없는 곳에 새로 만들지 않는다
            맞추기(원, 사본, 사연)

    # 뿌리가 원본인 것 (_판독패키지 에 쌍둥이가 없는 문서)
    for 원 in sorted(ROOT.glob("*.md")):
        짝, _ = _짝(원본자리, 원.name)
        if 짝 is not None:
            continue                          # 위에서 다뤘다
        for 자리 in [ROOT / "_정본" / "최신"] + _판들:
            사본 = 자리 / 원.name
            if 사본.exists():
                맞추기(원, 사본, "")

    if 못가림:
        print("  ★ 짝이 둘 이상이라 고르지 않은 것 %d곳" % len(못가림))
        for 이름, 자리 in 못가림:
            print("     %-44s @ %s" % (이름, 자리))
        print()

    if not 갈린것:
        print("  갈린 것이 없습니다.")
    else:
        print("  갈린 것 %d곳" % len(갈린것))
        for 이름, 자리 in 갈린것:
            print("     %-36s → %s" % (이름, 자리))
        print()
        if 보기만:
            print("  ★ 보기만 했습니다. 맞추려면 `--보기만` 없이 돌리십시오.")
        else:
            print("  %d곳을 맞췄습니다." % 맞춘것)

    print("=" * 70)
    # ★ 보기만 할 때 갈린 것이 있으면 실패로 끝낸다 — 늘 0 이면 검사가 아니다
    if 보기만 and (갈린것 or 못가림):
        return 1
    return 1 if 못가림 else 0


if __name__ == "__main__":
    sys.exit(main())
