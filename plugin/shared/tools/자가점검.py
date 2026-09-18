# -*- coding: utf-8 -*-
"""이 꾸러미가 「이 컴퓨터에서」 돌아가는지 먼저 본다.

★ 왜 있는가 (sky 2026-08-21)
  「실무자들에게 이미 zip 파일 다 줬는데 어떻게 하면 되죠?」

  배포한 꾸러미가 실무자 컴퓨터에서 첫 명령부터 멈췄다. 원인은 경로가
  코드에 박혀 있던 것인데, **그걸 미리 알아챌 방법이 없었다.**
  꾸러미 검사기는 「꾸러미가 최신 판인가」만 봤고,
  「남의 컴퓨터에서 도는가」는 아무도 안 봤다. 이 파일이 그 자리를 메운다.

★ 고정 목록으로 재지 않는다
  처음엔 「2차에 있어야 할 파일」 목록을 박아 두었더니, 3차·4차 꾸러미에서
  없는 것이 정상인 파일을 두고 ✗ 를 쏟아냈다. 헛경보도 사고다.
  그래서 **꾸러미가 스스로 필요로 하는 것**만 본다 —
  들어 있는 도구를 실제로 불러 보고, 있는 것만 재고, 없는 것은 넘어간다.

★ 실무자는 이것을 직접 칠 필요가 없다.
  붙여넣는 프롬프트의 첫 단계가 「자가점검부터 돌려라」 이므로
  판독자 LLM 이 알아서 돌리고 결과를 사람 말로 알려 준다.

쓰기
    python 스크립트/자가점검.py

돌릴 수 있으면 종료코드 0, 막힌 것이 있으면 1.
"""

from __future__ import annotations

import ast
import contextlib
import io
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name in ("스크립트", "scripts") else HERE
sys.path.insert(0, str(HERE))

문제: list[str] = []
알림: list[str] = []
해결법: list[str] = []      # ★ 스스로 할 수 있는 일 (사람이 보는 말)
스스로: set[str] = set()    # ★ 그 일이 고치는 「문제」 문구 — 짝을 정확히 맞춘다


def 줄(mark: str, 말: str) -> None:
    print("  %-3s %s" % (mark, 말))


def 차수() -> str:
    """이 꾸러미가 몇 차인지 — 꾸러미가 스스로 적어 둔 것을 읽는다."""

    안내 = ROOT / "0_먼저_읽으십시오.md"
    if 안내.exists():
        첫줄 = 안내.read_text(encoding="utf-8", errors="replace").splitlines()
        if 첫줄:
            return 첫줄[0].lstrip("# ").strip()
    return "이름 없는 꾸러미"


print("=" * 66)
print("  준비 점검 — 이 컴퓨터에서 돌아가는가")
print("=" * 66)
print("  꾸러미      : %s" % 차수())
print("  풀린 자리   : %s" % ROOT)
print()

# ── ⓪ 이 컴퓨터가 갖췄는가 ─────────────────────────────────────────
#
# ★ 왜 맨 앞인가 (sky 2026-08-22)
#   「어느 컴퓨터에 어느 사람이나 써도 잘 돌아갈 수 있게 할 수 있는거죠?」
#
#   컴퓨터마다 파이썬도 꾸러미도 다르다. 그것을 **판독을 시작하기 전에**
#   잡아야 한다. 판독 중에 터지면 판독자가 제 나름대로 우회하게 되고,
#   그 순간 다른 판독자와 조건이 달라진다 — 대조가 무의미해진다.
#
#   실제로 겪었다 — 한 판독자의 파이썬에서 pandas·yaml 이 깨져 있었는데
#   자가점검이 그것을 안 봐서, 판독 도중에야 드러났다.
print("⓪ 이 컴퓨터가 갖췄는가")
줄("·", "python %d.%d.%d — %s"
   % (sys.version_info[0], sys.version_info[1], sys.version_info[2],
      sys.executable))
if sys.version_info < (3, 9):
    줄("✗", "python 3.9 이상이 필요합니다")
    줄("", "  ↳ 이렇게 고칩니다 (판정과 무관하니 하셔도 됩니다)")
    줄("", "     python.org 에서 최신 판을 받아 깔고 다시 여십시오")
    줄("", "     이미 깔려 있다면 그 파이썬의 전체 경로로 부르십시오")
    해결법.append("python 새로 깔기")
    스스로.add("python 이 너무 낮습니다 (3.9 이상)")
    문제.append("python 이 너무 낮습니다 (3.9 이상)")

for _꾸러미, _쓰임, _막나 in (("pandas", "엑셀을 읽고 번들을 만든다", True),
                            ("openpyxl", "xlsx 를 쓴다", True),
                            ("yaml", "설정을 읽는다", False)):
    try:
        _m = __import__(_꾸러미)
        _판 = getattr(_m, "__version__", "?")
        # ★ 이름만 같고 알맹이가 다른 것이 끼어들 수 있다 (실제로 겪었다)
        _성함 = True
        if _꾸러미 == "pandas":
            _성함 = hasattr(_m, "ExcelFile") and hasattr(_m, "read_csv")
        elif _꾸러미 == "yaml":
            _성함 = hasattr(_m, "safe_load")
        if not _성함:
            raise ImportError("알맹이가 다릅니다 — %s" % getattr(_m, "__file__", "?"))
        줄("·", "%-10s %s" % (_꾸러미, _판))
    except Exception as exc:                                  # noqa: BLE001
        if _막나:
            줄("✗", "%-10s 없거나 깨졌습니다 — %s" % (_꾸러미, str(exc)[:44]))
            줄("", "  쓰임: %s" % _쓰임)
            # ★ 고치는 법을 같이 준다 (sky 2026-08-22).
            #   「총괄에게 보내십시오」 만으로는 실무자가 기다리기만 한다.
            #   이건 판정과 무관한 자리라 스스로 고쳐도 된다
            줄("", "  ↳ 이렇게 고칩니다 (판정과 무관하니 하셔도 됩니다)")
            줄("", '     "%s" -m pip install %s' % (sys.executable, _꾸러미))
            해결법.append("%s 설치" % _꾸러미)
            스스로.add("%s 를 못 씁니다 (%s)" % (_꾸러미, _쓰임))
            문제.append("%s 를 못 씁니다 (%s)" % (_꾸러미, _쓰임))
        else:
            줄("!", "%-10s 없거나 깨졌습니다 — 판독은 됩니다" % _꾸러미)
            알림.append("%s 를 못 씁니다 — 판독과는 무관합니다" % _꾸러미)

# 결과를 쓸 수 있는가
_시험 = ROOT / "_판독패키지" / "_결과"
try:
    _시험.mkdir(parents=True, exist_ok=True)
    _쪽지 = _시험 / "_쓰기시험.tmp"
    _쪽지.write_text("ok", encoding="utf-8")
    _쪽지.unlink()
    줄("·", "결과 폴더에 쓸 수 있습니다")
except Exception as exc:                                      # noqa: BLE001
    줄("✗", "결과 폴더에 못 씁니다 — %s" % str(exc)[:50])
    줄("", "  ↳ 이렇게 고칩니다 (판정과 무관하니 하셔도 됩니다)")
    줄("", "     zip 을 다른 자리에 다시 푸십시오 — 바탕화면이나 문서 폴더")
    줄("", "     (Program Files · C 드라이브 뿌리는 권한이 막혀 있습니다)")
    해결법.append("다른 폴더에 다시 풀기")
    스스로.add("결과 폴더에 쓸 수 없습니다")
    문제.append("결과 폴더에 쓸 수 없습니다")
print()

# ── ① 판독할 데이터 (있는 꾸러미만) ────────────────────────────────
행수: dict[str, int] = {}
데이터폴더 = ROOT / "판독대상"
if 데이터폴더.is_dir():
    print("① 판독할 데이터")
    try:
        from build_bundle import SRC, PRODUCTS, read_csv
    except Exception as exc:                                # noqa: BLE001
        줄("✗", "도구를 못 불러왔습니다 — %s" % exc)
        문제.append("build_bundle 을 불러오지 못했습니다")
        SRC, PRODUCTS = {}, ()

    for 이름 in PRODUCTS:
        길 = SRC[이름]
        if not os.path.exists(길):
            줄("✗", "%s — 파일이 없습니다" % 이름)
            문제.append("%s 데이터가 없습니다" % 이름)
            continue
        try:
            rows, _ = read_csv(길)
        except Exception as exc:                            # noqa: BLE001
            줄("✗", "%s — 못 읽었습니다: %s" % (이름, exc))
            문제.append("%s 를 못 읽습니다" % 이름)
            continue
        행수[이름] = len(rows)
        줄("·", "%-20s %6d행" % (이름, len(rows)))

    # ★ 3차(감독자) 꾸러미는 입력이 다르다 — 판독대상 엑셀이 아니라
    #   s13_judge/judge_input.csv 다. 2차 기준으로 막으면 감독자가 시작도 못 한다.
    #   ②-2 가 그 입력을 따로 본다 (2026-08-23 · 헛경보도 사고다).
    _감독자꾸러미 = (ROOT / "s13_judge" / "judge_input.csv").exists()
    if not PRODUCTS and _감독자꾸러미:
        줄("·", "이 꾸러미는 감독자용입니다 — 판독대상 엑셀은 필요 없습니다")
    elif not PRODUCTS:
        줄("✗", "판독할 데이터를 못 찾았습니다")
        줄("", "이 꾸러미는 데이터 없이 나갑니다.")
        줄("", "  ↳ 이렇게 하시면 됩니다 (판독자가 스스로 할 수 있는 일입니다)")
        줄("", "     ① 이 폴더와 그 아래에서 1차 분석 결과 파일을 찾습니다")
        줄("", "        (.xlsx 또는 .csv — 사람이 이미 넣어 두었을 때가 많습니다)")
        줄("", "     ② python 스크립트/데이터_넣기.py \"<찾은파일>\" --이름 <제품이름>")
        줄("", "     ③ 아무것도 없을 때만 사람에게 엑셀을 달라고 합니다")
        해결법.append("폴더에서 엑셀을 찾아 앉히기")
        스스로.add("판독할 데이터를 못 찾았습니다 (엑셀을 찾아 앉히면 됩니다)")
        문제.append("판독할 데이터를 못 찾았습니다 (엑셀을 찾아 앉히면 됩니다)")
    elif 행수:
        줄("→", "모두 %d행" % sum(행수.values()))
    print()

# ── ①-2 판독자 폴더가 섞였는가 ────────────────────────────────────
#
# ★ 실제로 겪었다 (2026-08-23) — B 폴더에 A 번들이 들어가 있었고
#   보정요청 3건이 A 것으로 채워졌다. 판독자 폴더는 한 사람 것만 있어야 한다.
_결과 = ROOT / "_판독패키지" / "_결과"
if _결과.is_dir():
    print("①-2 판독자 폴더가 섞였는가")
    import collections as _c
    import re as _re
    _이름 = _c.Counter()
    for _p in _결과.glob("판독결과_full_*.md"):
        _m = _re.match(r"판독결과_full_[^_]+_(.+)$", _p.stem)
        if _m:
            _이름[_m.group(1)] += 1
    _나 = _이름.most_common(1)[0][0] if _이름 else ""
    _남 = []
    for _d in sorted(_결과.iterdir()):
        if not _d.is_dir() or _d.name.startswith("bundle_full_"):
            continue
        if not (_d / "raw_voc.csv").exists():
            continue
        if _나 and _나.lower() not in _d.name.lower():
            _남.append(_d.name)
    if _남:
        줄("✗", "이 폴더의 판독자는 「%s」 인데 남의 번들이 있습니다" % _나)
        for _x in _남:
            줄("", "  · _판독패키지/_결과/%s" % _x)
        줄("", "↳ 이렇게 고칩니다 — 그 폴더를 지우거나 밖으로 옮기십시오")
        해결법.append("남의 번들을 치우기")
        스스로.add("판독자 폴더가 섞였습니다 (남의 번들이 있습니다)")
        문제.append("판독자 폴더가 섞였습니다 (남의 번들이 있습니다)")
    elif _나:
        줄("·", "판독자 「%s」 것만 있습니다" % _나)
    print()

# ── ② 회차 배치 (있는 꾸러미만) ────────────────────────────────────
배치들 = sorted(ROOT.glob("회차배치/full_*_ids.txt"))
if 배치들:
    print("② 회차 배치 — 한 번에 볼 행 목록")
    담긴행: set[str] = set()
    for 배치 in 배치들:
        담긴행 |= {x.strip() for x in 배치.read_text(encoding="utf-8").splitlines() if x.strip()}
    줄("·", "%d회차 · 담긴 행 %d개" % (len(배치들), len(담긴행)))
    전체 = sum(행수.values())
    if 전체 and len(담긴행) != 전체:
        줄("✗", "데이터는 %d행인데 배치에는 %d행 — 어긋납니다" % (전체, len(담긴행)))
        문제.append("배치와 데이터의 행 수가 다릅니다 (%d vs %d)" % (len(담긴행), 전체))
    print()
elif 행수:
    # ★ 데이터가 아예 없을 때는 위에서 이미 말했다. 여기서 또 하면
    #   실무자가 두 가지 문제로 읽는다 — 하나인데
    print("② 회차 배치")
    줄("✗", "판독할 데이터는 있는데 회차 배치가 없습니다")
    문제.append("회차 배치가 없습니다")
    print()

# ── ②-2 감독할 것 (3차 꾸러미만) ───────────────────────────────────
감독자입력 = ROOT / "s13_judge" / "judge_input.csv"
감독자회차 = sorted((ROOT / "s13_judge").glob("judge_*_ids.txt"))
감독자프롬프트 = list(ROOT.glob("프롬프트/0_붙여넣을_프롬프트_감독.md"))
if 감독자프롬프트:
    print("②-2 감독할 것 (2차에서 갈린 행)")
    if not 감독자입력.exists():
        줄("!", "아직 없습니다 — 총괄이 넣어 주어야 합니다")
        줄("", "  ★ 스스로 만들지 마십시오. 만들려면 2차 결과를 봐야 하고,")
        줄("", "     그것을 보면 A 와 B 가 누구인지 알게 됩니다")
        알림.append("감독할 것이 없습니다 — 총괄에게 요청하십시오")
    else:
        # ★ else 가 빠져 있었다 (2026-08-26에 고침).
        #   「아직 없습니다」 라고 말한 **바로 다음 줄**에서 그 파일을 열어
        #   빈 꾸러미에서 자가점검이 죽었다. 실무자가 맨 처음 돌리는 도구다.
        갈린행 = sum(1 for _ in 감독자입력.open("r", encoding="utf-8-sig")) - 1
        줄("·", "judge_input.csv %d행 · 회차 %d개" % (갈린행, len(감독자회차)))

    # ★ 이 파일이 감독자 손에 들어가면 이 단계가 통째로 무의미해진다
    매핑 = ROOT / "s13_judge" / "ab_mapping.json"
    if 매핑.exists():
        줄("✗", "★ ab_mapping.json 이 있습니다 — 열지 말고 총괄에게 알리십시오")
        줄("", "  총괄은 이것을 넣지 않습니다. 있다면 사고입니다")
        알림.append("ab_mapping.json 이 꾸러미 안에 있습니다 (감독자에게 주면 안 됩니다)")
    print()

# ── ③ 붙여넣을 프롬프트와 기준 문서 ────────────────────────────────
print("③ 판독자에게 줄 것")
프롬프트 = sorted(ROOT.glob("프롬프트/0_붙여넣을_*.md"))
if 프롬프트:
    줄("·", "붙여넣을 프롬프트 %d개" % len(프롬프트))
    for p in 프롬프트[:4]:
        줄(" ", "  " + p.name)
else:
    줄("·", "붙여넣을 프롬프트 없음 (이 꾸러미는 사람이 보는 것입니다)")

기준 = sorted((ROOT / "판독패키지").glob("*.md")) if (ROOT / "판독패키지").is_dir() else []
if 기준:
    줄("·", "기준 문서 %d개" % len(기준))
print()

# ── ④ 도구가 실제로 불러지는가 (이 꾸러미에 든 것만) ───────────────
#
# ★ 판독을 「막을」 도구와 「곁들이」 를 가른다 (sky 2026-08-22)
#   실제로 겪었다 — Codex 쪽 파이썬에서 run_status.py 가 yaml 문제로 못 떴는데,
#   그 하나 때문에 53회차 판독이 통째로 막혔다.
#   run_status 는 「어디까지 했나」 를 보여 주는 것뿐이다. 판정과 무관하다.
#   막을 것은 **프롬프트가 판독자에게 돌리라고 시키는 것**뿐이다.
꼭필요 = {
    "build_bundle",      # 번들 생성
    "check_submission",  # 제출 검사
    "check_lineage",     # 계보 검사
    "topic_registry",    # 대장 검사
    "check_selfcheck",   # 마무리 검사
    "handoff",           # 보정요청서
    "데이터_넣기",        # 데이터 앉히기
    # ★ build_master · make_judge_input 은 여기 없다 (2026-08-24).
    #   총괄 자리에서만 돈다. 꾸러미에 없는 것을 「꼭 필요」 로 두면
    #   멀쩡한 판독이 막힌다 (sky 규칙: 오탐도 사고다).
}

def _혼자_돌아버리나(길):
    """★ 불러 보기 전에 — 이 파일이 **import 만 해도 일을 하나** (2026-08-26).

    왜 생겼나. `sample_reader.py` 에는 `if __name__ == "__main__"` 이 없고
    맨 윗줄부터 표본을 뽑아 `_판독패키지` 를 새로 씁니다. 그런데 ④ 는
    폴더의 모든 .py 를 `__import__` 합니다.
    ★★ **점검하려고 돌린 도구가 정본 폴더를 갈아엎었습니다.**
      2026-08-26 18:14 · 18:15 두 번, `_판독패키지` 파일 18개가 지워졌습니다.
      되돌리기는 됐지만(인덱스에 있었습니다), 검사 도구가 데이터를
      건드리는 것 자체가 있어서는 안 되는 일입니다.

    그래서 가드가 없는 파일은 **불러 보지 않고** 글자로만 봅니다.
    ④ 가 잡으려는 것은 「없는 모듈을 부르나」 인데, 그건 안 돌려도 압니다.
    """
    try:
        나무 = ast.parse(길.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return False, None            # 문법이 깨졌으면 아래에서 드러난다
    for 마디 in 나무.body:
        # ★ `__name__ == "__main__"` 만 가드로 친다.
        #   `__name__ != "__main__"` 은 **거꾸로** 다 — import 를 막으려고
        #   일부러 세워 둔 빗장이다. 그것을 가드로 세면 도로 불러 버린다.
        if isinstance(마디, ast.If) and isinstance(마디.test, ast.Compare) \
                and isinstance(마디.test.ops[0], ast.Eq) \
                and "__name__" in ast.dump(마디.test):
            return False, 나무        # 가드가 있다 — 불러도 안전하다
    return True, 나무


def _글자로만_보기(길, 나무, _있는이름=None):
    """돌리지 않고 — 문법이 되나 · 부르는 모듈이 이 컴퓨터에 있나.

    ★ 「폴더에 있는 이름만 견준다」 로 하면 **없는 것을 못 잡습니다** —
      빠진 모듈은 애초에 폴더에 없으니 견줄 목록에도 없습니다.
      그래서 `find_spec` 으로 **정말 찾아지는지**를 봅니다.
      찾기만 하고 돌리지는 않습니다.
    """
    import importlib.util

    try:
        compile(길.read_text(encoding="utf-8"), str(길), "exec")
    except SyntaxError as e:
        return ["문법오류 %s 줄 %s" % (e.msg, e.lineno)]

    탈 = []
    for 마디 in ast.walk(나무):
        딸린것 = []
        if isinstance(마디, ast.Import):
            딸린것 = [a.name.split(".")[0] for a in 마디.names]
        elif isinstance(마디, ast.ImportFrom) and 마디.module and not 마디.level:
            딸린것 = [마디.module.split(".")[0]]
        for m in 딸린것:
            if m in 탈 or m == "__future__":
                continue
            try:
                if importlib.util.find_spec(m) is None:
                    탈.append("%s 를 못 찾습니다" % m)
            except (ImportError, ValueError, ModuleNotFoundError):
                탈.append("%s 를 못 찾습니다" % m)
    return 탈


도구 = sorted(p for p in HERE.glob("*.py") if p.name != Path(__file__).name)
if 도구:
    print("④ 도구 %d개 — 불러 봅니다"
          " (부르면 스스로 도는 것은 글자로만 봅니다)" % len(도구))
    _있는이름 = {p.stem for p in 도구}
    for 길 in 도구:
        이름 = 길.stem
        _혼자, _나무 = _혼자_돌아버리나(길)
        if _혼자:
            # ★ 불러선 안 되는 것 — 돌리면 파일을 쓴다. 글자로만 본다
            탈 = _글자로만_보기(길, _나무, _있는이름)
            if 탈:
                줄("!", "%s — %s" % (길.name, " · ".join(탈)[:56]))
                알림.append("%s — %s" % (길.name, " · ".join(탈)))
            else:
                줄("·", "%s (안 불러 봤습니다 — 부르면 스스로 돌아가는 "
                        "파일입니다)" % 길.name)
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                __import__(이름)
            줄("·", 길.name)
        except SystemExit:
            줄("·", 길.name)      # 인자 없이 부르면 스스로 끝내는 것 — 정상
        except Exception as exc:  # noqa: BLE001
            # ★ 데이터가 아직 없으면 도구가 못 도는 것이 당연하다 (2026-08-22).
            #   그것까지 「막힌 것」 으로 세면 원인이 하나인데 둘로 보인다.
            if 데이터폴더.is_dir() and not 행수:
                줄("·", "%s (데이터가 앉으면 됩니다)" % 길.name)
                continue
            if 이름 not in 꼭필요:
                # ★ 곁들이 도구다. 알려는 주되 판독을 막지는 않는다
                줄("!", "%s — %s" % (길.name, str(exc)[:56]))
                줄("", "  판독에 쓰는 도구가 아닙니다. 그대로 진행하셔도 됩니다")
                알림.append("%s 를 못 씁니다 — 판독과는 무관합니다" % 길.name)
                continue
            줄("✗", "%s — %s" % (길.name, str(exc)[:64]))
            문제.append("%s 를 못 씁니다 (%s)" % (길.name, type(exc).__name__))
    print()

# ── ④-2 어느 1차 엔진을 보고 있는가 ────────────────────────────────
#
# ★ 실제로 겪었다 (sky 2026-08-22) — 판독자가 `C:\codex` 안에 폴더를 만들어
#   돌았더니 그 아래 옛 엔진(`C:\codex\src`, 1,934줄)을 잡았다.
#   그래서 「ENUM_COLUMNS 가 없다」 같은 가짜 결함을 보고하고 판독을 세웠다.
#   도구가 import 되는지만 봐서는 못 잡는다. **무엇을 보는지**를 봐야 한다.
if (HERE / "check_selfcheck.py").exists() or (HERE / "build_bundle.py").exists():
    print("④-2 어느 1차 엔진을 보고 있는가")
    try:
        # ★ 엔진 자리를 sys.path 맨 앞에 먼저 놓는다 (2026-08-22).
        #   다른 도구가 제 사정으로 넣어 둔 경로가 앞에 있으면 엉뚱한 판본을
        #   읽는다. 실제로 worktree 쪽 schema 를 읽고 있었다.
        _엔진 = None
        # ★ 꾸러미가 지고 온 엔진을 **먼저** 본다 (2026-08-23).
        #   남의 PC 에는 C:/codex_live_merge 가 없다. engine/ 이 그 자리다.
        for _c in (os.environ.get("VOC_ENGINE"), str(ROOT / "engine")):
            if _c and os.path.isdir(_c):
                _엔진 = _c
                break
        if _엔진:
            while _엔진 in sys.path:
                sys.path.remove(_엔진)
            sys.path.insert(0, _엔진)
        for _m in [k for k in list(sys.modules) if k.startswith("src.")or k == "src"]:
            del sys.modules[_m]
        from src.voc_rebuild import schema as _sc
        _자리 = getattr(_sc, "__file__", "?")
        if _엔진 and os.path.normcase(_엔진.replace("/", os.sep)) not in \
                os.path.normcase(_자리):
            줄("!", "정본 엔진이 아닌 곳을 읽었습니다")
            줄("", "  바란 곳: %s" % _엔진)
            알림.append("정본이 아닌 엔진을 읽었습니다 — %s" % _자리)
        줄("·", "schema : %s" % _자리)
        빠진 = [n for n in ("ENUM_COLUMNS", "CANONICAL_TOPICS") if not hasattr(_sc, n)]
        if 빠진:
            줄("✗", "옛 엔진을 보고 있습니다 — %s 가 없습니다" % " · ".join(빠진))
            줄("", "이 꾸러미를 C:\\codex 밖에 풀어 주십시오")
            줄("", "(그 안에 있으면 옆의 옛 엔진을 먼저 잡습니다)")
            문제.append("옛 엔진을 보고 있습니다 (꾸러미를 C:\\codex 밖에 푸십시오)")
        else:
            줄("·", "ENUM_COLUMNS · CANONICAL_TOPICS 둘 다 있습니다")
    except Exception as exc:                                  # noqa: BLE001
        줄("!", "1차 엔진을 못 찾았습니다 — %s" % str(exc)[:56])
        줄("", "  xlsx 번들과 계약 검증만 못 합니다. 판독은 됩니다")
        알림.append("1차 엔진을 못 찾았습니다 (판독은 됩니다)")
    print()

# ── ⑤ 이 컴퓨터에만 있는 자리를 아직 붙잡고 있는가 ─────────────────
print("⑤ 남의 컴퓨터 경로가 남아 있는가")
샌것: list[str] = []
for 길 in 도구:
    본문 = 길.read_text(encoding="utf-8", errors="replace")
    줄들 = 본문.splitlines()
    for 번호, 줄내용 in enumerate(줄들, 1):
        if 줄내용.strip().startswith("#"):
            continue
        # ★ 「있으면 쓰고 없으면 건너뛴다」 로 고쳐 둔 자리는 봐준다.
        #   그 판단은 한 줄 안에 안 들어가므로 앞뒤를 같이 본다.
        둘레 = "\n".join(줄들[max(0, 번호 - 4):번호 + 2])
        if "isdir" in 둘레 or "os.environ" in 둘레:
            continue
        if any(x in 줄내용 for x in ("C:/codex", "C:\\codex", "C:\\Users", "C:/Users")):
            샌것.append("%s:%d" % (길.name, 번호))
if 샌것:
    for x in 샌것[:6]:
        줄("✗", x)
    문제.append("이 컴퓨터에만 있는 경로가 %d줄 남아 있습니다" % len(샌것))
else:
    줄("·", "없습니다")

# ── 맺음 ───────────────────────────────────────────────────────────
print()
print("=" * 66)
if 문제:
    print("  ★ 아직 시작하면 안 됩니다 — 막힌 것 %d건" % len(문제))
    for x in 문제:
        print("     ·", x)
    print()
    # ★ 갈라 준다 (sky 2026-08-22) —
    #   「실무자들은 하다 에러나면 그냥 암것도 못하는거네요」
    #   스스로 할 수 있는 것까지 총괄을 기다리게 하면 안 된다
    if 해결법:
        print("  ✅ 이 중 %d건은 **직접 하실 수 있습니다**" % len(해결법))
        for x in 해결법:
            print("     ·", x)
        print()
        print("     위에 「↳ 이렇게 고칩니다」 라고 적힌 줄을 그대로 하시면 됩니다.")
        print("     판정과 무관한 자리라 결과에 영향을 주지 않습니다.")
        print("     하신 뒤 이 점검을 다시 돌리십시오.")
        print()
    남은것 = [x for x in 문제 if x not in 스스로]
    if 남은것:
        print("  이건 총괄 몫입니다 — 이 화면을 그대로 보내십시오.")
        for x in 남은것:
            print("     ·", x)
    print("=" * 66)
    sys.exit(1)

print("  준비됐습니다. 시작하셔도 됩니다.")
if 알림:
    print()
    print("  참고 (막는 것은 아닙니다)")
    for x in 알림:
        print("     ·", x)
print("=" * 66)
sys.exit(0)
