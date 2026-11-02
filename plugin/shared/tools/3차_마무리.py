# -*- coding: utf-8 -*-
"""감독자 둘의 판정을 합쳐 **최종 아웃풋까지 한 번에** 낸다.

★ 왜 (sky 2026-08-23)
  「2차와 3차 결과에 대한 통합도 실무자가 따로 말하지 않아도
    최종 아웃풋 자체를 …」

  지금까지는 총괄(나)가 build_master → check_selfcheck → handoff 를
  손으로 이어 돌렸다. 그 사람이 실무자 자리에는 없다.

무엇을 하나
  ① 감독자 둘의 결과를 **스스로 찾아 모은다** (폴더가 나뉘어 있어도)
  ② 2차 판독 번들 둘을 찾는다
  ③ 두 감독자가 전 회차를 마쳤는지 세어 본다 — 모자라면 말하고 멈춘다
  ④ 통합 → 스스로 검사 → 보정요청 뽑기
  ⑤ 실무자가 받을 것만 `_최종결과/` 에 모아 놓는다

★ 앞 차수 보정요청을 **이어받는다.** 08-23 에 2차 3건이 통째로 사라졌다.

쓰기
    python 스크립트/3차_마무리.py                스스로 찾는다
    python 스크립트/3차_마무리.py <감독자1> <감독자2>  자리를 짚어 줄 때
"""
from __future__ import annotations

import glob
import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기
R = ROOT / "_판독패키지" / "_결과"


# ★ 자기가 만든 산출물 — 2차 결과로 세면 안 된다 (2026-08-23).
#   한 번 돌린 뒤 다시 돌리니 s15_master 가 2차 번들로 잡혔다.
#   raw_voc.csv 가 있어 겉으로는 같아 보인다.
_내것 = ("master_final", "s15_master", "_최종결과", "_총괄만",
        "s9_group", "s12_full", "s13_judge")


def _이차번들() -> list[Path]:
    """2차 판독자의 최종 번들을 뒤진다 — 3차_준비 와 같은 눈으로.

    ★ build_master 는 `_판독패키지/_결과/` 안만 본다.
      실무자는 2차 결과를 `2차결과/판독자1` 처럼 옆에 놓는다 —
      있는데 못 찾아 멈추면 실무자는 무엇을 해야 할지 모른다.
    """
    본자리: list[Path] = []
    for 밑 in (ROOT, ROOT.parent):
        if not 밑.is_dir():
            continue
        for 깊이 in ("*", "*/*", "*/*/*",
                   # ★ 2차 폴더를 통째로 옆에 둔 경우 (sky 화면 · 2026-08-23)
                   #   VoC 판독 A/_판독패키지/_결과/claudecode_bundle
                   #   깊이를 늘리는 대신 **자리를 안다** — 아무 데나 안 훑는다
                   "*/_판독패키지/_결과/*",
                   "_판독패키지/_결과/*"):
            for p in sorted(밑.glob(깊이)):
                if not p.is_dir() or not (p / "raw_voc.csv").exists():
                    continue
                if p.name.startswith("bundle_") or "옛판" in p.name:
                    continue
                if p.name in _내것:
                    continue
                if p not in 본자리:
                    본자리.append(p)
        if 본자리:
            break
    return 본자리


def _달리기(도구: str, *인자: str) -> tuple[int, str]:
    p = _여기 / 도구
    if not p.exists():
        return 1, "  %s 를 못 찾았습니다" % 도구
    r = subprocess.run([sys.executable, str(p), *인자], cwd=str(ROOT),
                       text=True, encoding="utf-8", capture_output=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")[-600:]


def _감독폴더찾기() -> list[Path]:
    """감독자 결과가 든 폴더를 뒤진다 — 이 폴더와 옆 폴더까지."""
    본것 = []
    for 밑 in (ROOT, ROOT.parent):
        if not 밑.is_dir():
            continue
        for 깊이 in ("", "*", "*/*"):
            무늬 = os.path.join(str(밑), 깊이, "_판독패키지", "_결과",
                              "감독결과_*.md") if 깊이 else \
                os.path.join(str(밑), "_판독패키지", "_결과", "감독결과_*.md")
            for p in glob.glob(무늬):
                d = Path(p).parent
                if d not in 본것:
                    본것.append(d)
        # ★ 자기 것을 찾아도 멈추지 않는다 (2026-08-23).
        #   멈췄더니 옆 폴더의 다른 감독자를 못 봐서 사람이 손으로 모아야 했다.
        #   감독자는 폴더가 나뉘어 있는 것이 정상이다 — 둘 다 본다.
    return 본것


def _이름(p: Path) -> str:
    m = re.match(r"감독결과_[^_]+_(.+)$", p.stem)
    return m.group(1) if m else ""


def _자물쇠(뿌리: Path):
    """감독자 둘이 동시에 통합을 시작하는 것을 막는다.

    ★ 왜 (sky 2026-08-24) — 「3차 마무리를 하는 AI가 2개인데 누가 통합을?」
      늦게 끝난 쪽이 하는 것이 맞지만, **동시에** 끝나면 둘 다 시작한다.
      같은 파일에 함께 쓰면 번들이 깨진다.

    ★ 오래된 자물쇠는 무시한다 — 앞 판이 중간에 죽었을 수 있다.
    """
    import os
    import time

    p = 뿌리 / "_판독패키지" / "_결과" / ".통합중.tmp"
    if p.exists():
        나이 = time.time() - p.stat().st_mtime
        if 나이 < 1800:                      # 30분 안이면 남이 도는 중
            print()
            print("  ★ 다른 감독자가 지금 통합하고 있습니다 (%d분 전에 시작)."
                  % int(나이 / 60))
            print("    잠시 뒤 다시 돌리거나, 그쪽이 끝나기를 기다리십시오.")
            print("    한 번에 하나만 해야 번들이 안 깨집니다.")
            return None
        print("  ★ 오래된 자물쇠를 치웁니다 (%d분 전 것)" % int(나이 / 60))
        try:
            os.remove(p)
        except OSError:
            pass
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("%d" % os.getpid(), encoding="utf-8")
    return p


def _알림남기기(뿌리: Path, 낼곳: Path) -> None:
    """**두 폴더 모두에** 결과가 어디 있는지 남긴다.

    ★ 통합은 늦게 끝난 쪽 폴더에 생긴다 (sky 2026-08-24).
      먼저 끝난 쪽에는 아무것도 없어 실무자가 어디를 볼지 모른다.
    """
    말 = ("# 최종 결과는 어디 있나\n\n"
          "★ 감독자 둘 중 **늦게 끝난 쪽**이 통합합니다. 이번에는 여기입니다.\n\n"
          "```\n%s\n```\n\n"
          "그 폴더 안에 받으실 것이 다 있습니다 —\n"
          "3차_최종데이터.xlsx · 사람이볼목록.csv · 보정요청_논의본.md ·\n"
          "보정요청.csv · 참조용_개별결과\\\n\n"
          "★ 다른 감독 폴더에는 `_최종결과` 가 없습니다. 그것이 맞습니다.\n"
          % 낼곳)
    자리 = [뿌리]
    for d in _감독폴더찾기():
        위 = Path(d).parent.parent          # …/_판독패키지/_결과 → 그 폴더
        if 위 not in 자리:
            자리.append(위)
    for x in 자리:
        try:
            (x / "0_결과는_어디_있나.md").write_text(말, encoding="utf-8")
        except OSError:
            pass


def 옛이름_고치기(자리) -> int:
    """옛 이름(심판결과_judge_*)이 들어오면 새 이름으로 바꾼다.

    ★ 왜 (2026-08-25)
      「심판」 을 「감독」 으로 바꿨는데, 밖에서 옛 이름 파일이 들어올 수 있다.
      실제로 겪었다 — 남의 폴더 번들이 섞여 들어온 적이 있다.

      ★ 읽는 자리마다 무늬를 둘씩 두면 일곱 군데를 손으로 맞춰야 한다.
        그러면 반드시 한 곳이 빠진다. 들어오는 길목 하나에서 바꾼다.
    """
    바뀜 = 0
    for p in Path(자리).rglob("심판결과_judge_*.md"):
        새 = p.parent / p.name.replace("심판결과_judge", "감독결과")
        if not 새.exists():
            p.rename(새)
            바뀜 += 1
    if 바뀜:
        print("   ※ 옛 이름 %d개를 감독결과_* 로 바꿨습니다" % 바뀜)
    return 바뀜


def _확인만이면_보여주고_멈춘다() -> bool:
    """★ --확인만 — 무엇을 할지 보여만 준다 (2026-08-26).

    이 도구는 통합부터 번들까지 데이터를 통째로 바꾼다.
    「도는지 보려고」 돌렸다가 데이터가 바뀐 일이 오늘만 여러 번 있었다.
    """
    if "--확인만" not in sys.argv:
        return False
    print("=" * 70)
    print("  3차 마무리 — 확인만 (아무것도 안 바꿉니다)")
    print("=" * 70)
    for x in ("① build_master        두 감독 결과를 통합한다",
              "② check_selfcheck     스스로 검사한다",
              "③ handoff             보정요청을 뽑는다",
              "④ ★총괄검수            갈래를 나누고 판정 자리를 차린다",
              "⑤ rank_two_axis       개선 우선순위",
              "⑥ 편향검사             감독이 자기 편을 들었나",
              "⑦ PL이슈_뽑기          안전·위생 전량",
              "⑧ 시트_붙이기          사람이 볼 것을 xlsx 로",
              "⑨ ★차례_만들기         0_차례 + 시트 순서",
              "⑩ 보정요청_논의본",
              "⑪ _최종결과 에 모은다"):
        print("     %s" % x)
    print()
    print("  바뀌는 것 — s15_master/ · _판독패키지/_결과/master_final/ · _최종결과/")
    print("  실제로 하려면 --확인만 을 빼고 다시 돌리십시오.")
    print("=" * 70)
    return True


def _바탕인자() -> list[str]:
    """`--바탕 <이름조각>` 을 뽑아 `build_master.py` 로 **넘긴다** (2026-11-02).

    ★ 왜 — `build_master.py` 에는 `--바탕` 이 있는데 **이 도구가 안 넘겨 주고 있었다.**
      스킬을 쓰는 사람은 `3차_마무리.py` 를 돌리므로, 그 인자는 **닿을 길이 없었다.**
      더 나쁜 것은 **조용히 틀리게 돌았다는 것이다** —
        · `--바탕` 은 아래 `startswith("--")` 에 걸려 **버려지고**
        · 값 `claudecode` 는 `--` 가 없으니 **감독폴더 경로로 오해**된다
      그러면 감독결과를 그 엉뚱한 자리에서 찾아 **0개**를 세고, 사람은 바탕을 바꿨다고
      믿는다. 「못 찾음」 을 「없음」 으로 돌려주는 것과 같은 꼴이다.
    """
    if "--바탕" not in sys.argv:
        return []
    i = sys.argv.index("--바탕") + 1
    if i >= len(sys.argv) or sys.argv[i].startswith("--"):
        print("  ✗ `--바탕` 뒤에 번들 이름(조각)을 주십시오 — 예: `--바탕 claudecode`")
        raise SystemExit(2)
    return ["--바탕", sys.argv[i]]


def main() -> int:
    if _확인만이면_보여주고_멈춘다():
        return 0
    print("=" * 70)
    print("  3차 마무리 — 감독자 둘을 합쳐 최종 아웃풋을 냅니다")
    print("=" * 70)

    R.mkdir(parents=True, exist_ok=True)

    바탕 = _바탕인자()
    if 바탕:
        print("  · `--바탕 %s` 를 build_master 로 넘깁니다 (판정 24칸의 바탕 번들)" % 바탕[1])

    # ── ① 감독자 결과를 모은다 ──────────────────────────────────────
    #   ★ `--바탕` 의 **값**도 빼야 한다 — 안 빼면 감독폴더 경로로 오해한다
    _값 = set(바탕[1:])
    준것 = [Path(a) for a in sys.argv[1:] if not a.startswith("--") and a not in _값]
    자리 = 준것 or _감독폴더찾기()
    # ★ 파일 **이름**으로 센다 (2026-08-24).
    #   한 번 통합하면 다른 감독자 결과가 이 폴더로 복사된다. 다시 돌리면
    #   같은 파일을 두 곳에서 찾아 **두 번 세었다** — 「claudecode 24회차」.
    #   판정은 안 겹치지만(같은 이름이라 덮어씀) 셈이 거짓이 된다.
    #   ★ 6회차만 했는데 앞서 복사된 6개와 합쳐 12가 되면
    #     「다 마쳤다」 로 보고 덜 끝난 채 통합한다. 에러도 안 난다.
    본이름: dict[str, set] = {}
    for d in 자리:
        for p in sorted(Path(d).glob("감독결과_*.md")):
            이 = _이름(p)
            if not 이:
                continue
            낼곳 = R / p.name
            새것 = (not 낼곳.exists()
                   or 낼곳.stat().st_mtime < p.stat().st_mtime)
            if 새것 and p.resolve() != 낼곳.resolve():
                shutil.copy2(p, 낼곳)
            본이름.setdefault(이, set()).add(p.name)
    모은것 = {이: len(x) for 이, x in 본이름.items()}

    print("  감독자 — %s" % (" · ".join("%s %d회차" % x for x in 모은것.items())
                        or "못 찾았습니다"))

    if len(모은것) < 2:
        print()
        print("  ★ 감독자가 **둘**이어야 합니다.")
        print("    한쪽만으로 합치면 감독자가 통째로 무시된 채 최종 파일이 나옵니다")
        print("    (08-23 에 실제로 그랬습니다 — 그럴듯해 보여서 더 나쁩니다).")
        print()
        print("  ↳ 다른 감독자가 쓴 `감독결과_*.md` 를")
        print("     `_판독패키지/_결과/` 에 놓고 다시 돌리십시오.")
        return 1

    # ── ② 전 회차를 마쳤는가 ──────────────────────────────────────
    회차 = len(list((ROOT / "s13_judge").glob("judge_*_ids.txt")))
    모자람 = {이: 회차 - n for 이, n in 모은것.items() if n < 회차}
    if 회차 and 모자람:
        print()
        print("  ★ 아직 마치지 않은 감독자가 있습니다 (전체 %d회차)" % 회차)
        for 이, k in 모자람.items():
            print("     · %s — %d회차 모자람" % (이, k))
        return 1

    # ★ 동시에 끝났을 때를 막는다 (sky 2026-08-24)
    자물쇠 = _자물쇠(ROOT)
    if 자물쇠 is None:
        return 1

    # ── ③ 통합 ────────────────────────────────────────────────────
    print()
    번들 = _이차번들()
    print("  2차 번들 — %s"
          % (" · ".join(p.name for p in 번들) or "못 찾았습니다"))
    if len(번들) < 2:
        print()
        print("  ★ 2차 판독자 **둘**의 결과가 있어야 합칩니다.")
        print("    본 자리 : %s 와 그 아래" % ROOT)
        print()
        print("  ↳ 2차에서 나온 결과 폴더 둘을 이 폴더 안에 놓고 다시 돌리십시오.")
        return 1
    if len(번들) > 2:
        print()
        print("  ★ 2차 결과 폴더가 %d개입니다 — 둘이어야 합니다." % len(번들))
        for p in 번들:
            print("     · %s" % p)
        return 1

    코드, 말 = _달리기("build_master.py", str(번들[0]), str(번들[1]), *바탕)
    # ★ 2026-11-02 — 아래 「마지막 14줄」 은 build_master 의 **머리에 찍히는**
    #   「바탕 번들 = …」 줄을 잘라 버린다. 그 줄은 결정 0012 ㉢ 이 「바탕이 **몰래**
    #   정해지지 않게」 넣은 것인데, 사람이 보는 것은 이 도구의 화면이므로
    #   **스킬 경로에서는 ㉢ 이 깨져 있었다.** 그래서 그 줄만 따로 끌어올린다.
    for _줄 in 말.splitlines():
        if "바탕 번들 =" in _줄:
            print("  " + _줄.strip())
    print("\n".join("  " + x for x in 말.rstrip().splitlines()[-14:]))
    if 코드:
        try:
            자물쇠.unlink()      # ★ 멈출 때도 풀어야 다음이 돈다
        except OSError:
            pass
        return 코드

    # ── ④ 스스로 검사 ─────────────────────────────────────────────
    print()
    코드, 말 = _달리기("check_selfcheck.py", "_판독패키지/_결과/master_final")
    # ★ 원문을 화면에 찍지 않는다 (2026-08-23) — 검사기가 예시로 발화를 찍는다.
    #   프롬프트가 판독자에게 금지한 것을 도구가 하면 안 된다. 맺음 줄만 뽑는다.
    끝줄 = [x for x in 말.rstrip().splitlines()
          if "✗" in x and "건 ·" in x][-1:]
    print("\n".join("  " + x.strip() for x in 끝줄))

    # ── ⑤ 보정요청 ────────────────────────────────────────────────
    print()
    코드, 말 = _달리기("handoff.py")
    print("\n".join("  " + x for x in 말.rstrip().splitlines()[:3]))

    # ── ⑤-2 ★ 총괄 검수 — 실무자가 볼 것을 줄인다 (축1 ③) ─────────
    #   ★ 2판에서 새로 생긴 단계 (sky 2026-08-26).
    #     감독 둘이 어긋난 것을 갈래로 나누고, 되풀이되는 규칙 후보를 뽑고,
    #     판정 자리를 차려 놓는다. **판정 자체는 사람이 한다.**
    #   ★ 막지 않는다 — 검수를 못 해도 뒤 단계는 돌아야 한다.
    코드, 말 = _달리기("총괄검수.py", str(번들[0]), str(번들[1]))
    if not 코드:
        print("\n".join("  " + x for x in 말.rstrip().splitlines()
                        if x.strip() and ("★" in x or "가르면" in x or "판정 자리" in x)))
    else:
        print("  ! 총괄검수를 못 돌렸습니다 (막지는 않습니다)")

    # ★ 검수 판정이 데이터에 반영됐는지 본다 (2026-08-26).
    #   실측 — 2차 원본에는 「위생/살균」·「위생/냄새(곰팡이)」 옛 이름이 있다.
    #   총괄이 §9 를 적용해야 「위생/냄새」 가 된다.
    #   검수 전에 PL 을 뽑으면 **위생 0행** 이 나온다. 실제로 그랬다.
    _판정자리 = ROOT / "s15_master" / "총괄검수_판정자리.csv"
    _아직 = False
    if _판정자리.exists():
        try:
            import csv as _csv
            with io.open(_판정자리, encoding="utf-8-sig", newline="") as _h:
                _몸 = list(_csv.DictReader(_h))
            _빈 = sum(1 for _x in _몸 if not (_x.get("총괄_판정") or "").strip())
            if _빈:
                _아직 = True
                print()
                print("  ★ 검수를 아직 안 하셨습니다 — %d/%d행이 비어 있습니다"
                      % (_빈, len(_몸)))
                print("     아래 PL·개선우선순위는 **검수 전 라벨**로 셉니다.")
                print("     판정을 끝낸 뒤 이 도구를 다시 돌리십시오.")
        except Exception:
            pass

    # ── ⑥ 개선 우선순위(두 축)를 낸다 ─────────────────────────────
    #   ★ 이 단계가 빠져 4차 꾸러미가 「없는 파일」 로 걸렸다 (2026-08-23).
    #     62·63 문서가 가리키는 파일이라 없으면 실무자가 못 찾는다.
    코드, 말 = _달리기("rank_two_axis.py")
    if 코드:
        print("  ! 개선우선순위를 못 냈습니다 (막지는 않습니다)")

    # ── ⑦ 감독자가 자기 편을 들었는지 잰다 ──────────────────────────
    #   ★ 익명화는 완전한 방어가 아니다 (sky 2026-08-23).
    #     막을 수 없으면 잰다. 매핑을 아는 이 자리에서만 잴 수 있다.
    코드, 말 = _달리기("편향검사.py")
    if not 코드:
        print("\n".join("  " + x for x in 말.rstrip().splitlines()
                        if "자기" in x or "치우침" in x or "눈여겨" in x))

    # ── ⑧ ★PL Issue 를 뽑는다 (안전·위생을 건수와 무관하게 전량) ──
    #   ★ 시트_붙이기가 PL이슈.csv 를 찾는다. 여기서 안 만들면
    #     「못 찾았습니다」 하고 조용히 건너뛴다 — 시트가 하나 없는 채로 끝난다.
    코드, 말 = _달리기("PL이슈_뽑기.py")
    print(말.rstrip() or "  (PL이슈_뽑기 없음)")
    # ★ 2026-10-28 독립 점검 F07 — 실패 코드를 **보고도 안 멈추고** 있었다.
    #   시트_붙이기는 PL이슈.csv 가 없으면 「못 찾았습니다」 하고 조용히 건너뛴다.
    #   그래서 PL 뽑기가 실패하면 **시트 하나가 빠진 채로 끝까지 갔다.**
    #   PL 이슈는 제품 안전 건이다 — 여기서 멈추고 사람에게 알린다.
    if 코드:
        print("  ! PL이슈_뽑기 가 종료코드 %d 로 끝났습니다 — 여기서 멈춥니다" % 코드)
        print("    (★PL Issue 시트가 빠진 번들을 「다 됐다」 로 내보내지 않습니다)")
        return 코드

    # ── ⑨ 사람이 볼 것을 xlsx 안으로 넣는다 ───────────────────────
    #   ★ 파일이 흩어지면 사람은 하나만 본다 (sky 2026-08-23).
    #     69행이 「수정로그_재검토필요」 라는 이름 아래 묻혀 있었고,
    #     보정요청은 xlsx 안에 아예 없었다.
    코드, 말 = _달리기("시트_붙이기.py")
    if not 코드:
        # ★ 시트를 다 붙인 **뒤에** 차례를 만든다 (2026-08-26).
        #   먼저 만들면 나중에 붙는 시트가 차례에 빠진다.
        _코드2, _말2 = _달리기("차례_만들기.py")
        if not _코드2:
            print("\n".join("  " + x for x in _말2.rstrip().splitlines()[:2]))
    if not 코드:
        print("\n".join("  " + x for x in 말.rstrip().splitlines()[-3:]))

    # ★ 번들 색칠은 여기서 하지 않는다 (sky 2026-08-24).
    #   「2차 판독 3차 감독에서가 아닌 최종 단계에서 메인 AI 가 반영」
    #   꾸밈은 판독자가 할 일이 아니다 — 총괄이 마지막에 한다.
    #   도구는 outputs/voc_secondary/번들_색칠하기.py 에 있다.

    # ── ⑩ 논의 보조용으로 다듬는다 ────────────────────────────────
    코드, 말 = _달리기("보정요청_논의본.py")
    if not 코드:
        print("\n".join("  " + x for x in 말.rstrip().splitlines()[-2:]))

    # ── ⑪ 받을 것만 모아 놓는다 ───────────────────────────────────
    낼곳 = ROOT / "_최종결과"
    if 낼곳.exists():
        shutil.rmtree(낼곳)
    낼곳.mkdir()
    받을것 = [
        (next(iter(sorted((R / "master_final").glob("*.xlsx"))), None),
         "3차_최종데이터.xlsx"),
        (ROOT / "s15_master" / "사람이볼목록.csv", "사람이볼목록.csv"),
        (ROOT / "_인계" / "보정요청.csv", "보정요청.csv"),
        (ROOT / "_인계" / "보정요청_논의본.md", "보정요청_논의본.md"),
    ]
    담긴것 = []
    for 원, 새 in 받을것:
        if 원 and Path(원).exists():
            shutil.copy2(원, 낼곳 / 새)
            담긴것.append(새)

    # 참조용 — 개별 결과도 함께 준다 (sky 2026-08-23)
    참조 = 낼곳 / "참조용_개별결과"
    참조.mkdir()
    # ★ 2차 번들은 옆 폴더에 있을 수 있다 — 아까 찾아 둔 것을 그대로 쓴다.
    #   `_결과/` 아래만 보다가 참조용에서 2차 A·B 가 통째로 빠졌다 (2026-08-23).
    for d in 번들:
        _엑 = list(d.glob("*.xlsx"))
        for x in _엑:
            shutil.copy2(x, 참조 / ("2차_%s.xlsx" % d.name))
        if not _엑 and (d / "raw_voc.csv").exists():
            shutil.copy2(d / "raw_voc.csv", 참조 / ("2차_%s.csv" % d.name))
    for p in sorted(R.glob("감독결과_*.md")):
        shutil.copy2(p, 참조 / ("3차_" + p.name))

    # ★ 자물쇠를 풀고, 두 폴더 모두에 「결과는 저기」 를 남긴다
    try:
        자물쇠.unlink()
    except OSError:
        pass
    _알림남기기(ROOT, 낼곳)

    print()
    print("=" * 70)
    print("  끝났습니다 — `_최종결과/` 를 총괄께 드리십시오")
    for x in 담긴것:
        print("     · %s" % x)
    print("     · 참조용_개별결과/  (2차 A·B · 3차 감독 둘의 원본)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
