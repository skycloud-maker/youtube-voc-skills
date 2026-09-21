# -*- coding: utf-8 -*-
"""★ 총괄 전용 — 2차를 점검하고 3차 감독 폴더를 차려 준다.

★ 이 도구는 **감독자 꾸러미에 없다** (sky 2026-08-24).
  「중간자가 직접 점검하고 익명화하여 3차에게 전달할 파일을 만들어주는걸로」
  감독자가 만들면 **매핑을 만드는 주체가 감독자**이 된다 —
  익명화가 형식뿐이 된다. 총괄이 만들어야 진짜다.

★ 왜 (sky 2026-08-23)
  「실무자는 범용 3차 zip 과 2차에서 나온 분석 데이터를 첨부하고
    프롬프트를 그대로 붙여넣으면 …」

  지금까지는 총괄(나)가 make_judge_input 을 손으로 돌렸다.
  실무자 자리에는 그 사람이 없다. 판독자가 스스로 하게 한다.

무엇을 하나
  ① 2차 판독자 두 명의 최종 번들을 **스스로 찾는다**
     (이 폴더 · 그 아래 · 옆 폴더까지 뒤진다. 사람에게 묻지 않는다)
  ② 갈린 행을 골라 s13_judge/judge_input.csv 를 만든다
  ③ 회차로 나눈다
  ④ ★ ab_mapping.json 은 **감독자가 볼 수 없는 자리**에 둔다
     — 총괄 몫이다. 감독자가 A·B 가 누구인지 알면 편든다.

쓰기
    python 3차_준비.py                  스스로 찾는다  (총괄 자리)
    python 3차_준비.py <번들1> <번들2>   자리를 짚어 줄 때
    python 3차_준비.py --다시돌리기      ★ 편향이 의심될 때 3차를 새로
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

# 2차 번들이 갖추어야 할 것 — 이것이 있어야 판독 결과다
표 = "raw_voc.csv"


# ★ 자기가 만든 산출물 — 2차 결과로 세면 안 된다 (2026-08-23).
#   한 번 돌린 뒤 다시 돌리니 s15_master 가 2차 번들로 잡혔다.
#   raw_voc.csv 가 있어 겉으로는 같아 보인다.
_내것 = ("master_final", "s15_master", "_최종결과", "_총괄만",
        "s9_group", "s12_full", "s13_judge")


def _누가(번들: Path) -> str:
    """이 번들을 만든 판독자 이름.

    ★ 「자기」 의 정의 (sky 가 물었다 · 2026-08-24)
      폴더 이름이 아니다. 그 폴더에서 **실제로 판독을 돌린 AI 이름**이다.
      판독자가 회차마다 남기는 `판독결과_full_NN_<이름>.md` 에 적혀 있다.

    ★ 왜 이것이 필요한가 — 2026-08-23 에 겪었다.
      B 폴더에 A 번들이 1분 새것으로 들어와 있었고 「가장 새 것」 규칙이
      그것을 골라 **A 의 보정요청 3건이 B 것으로 넘어갔다.**
      기준은 새것이 아니라 **누가 만들었나** 다.

    ★ 좁은 자리부터 본다 (2026-08-24).
      위에서부터 `**/` 로 훑었더니 같은 자리의 남의 파일까지 끌어와
      아홉 개가 전부 한 사람 것으로 나왔다.
      이름이 여럿이면 뭉개지 않고 그대로 말한다 —
      「섞였다」 는 것 자체가 총괄이 알아야 할 답이다.
    """
    for 자리 in (번들, 번들.parent, 번들.parent.parent):
        if not 자리.is_dir():
            continue
        셈: dict[str, int] = {}
        for q in 자리.glob("판독결과_full_*_*.md"):
            m = re.match(r"판독결과_full_[^_]+_(.+)$", q.stem)
            if m:
                셈[m.group(1)] = 셈.get(m.group(1), 0) + 1
        if 셈:
            이름 = sorted(셈, key=lambda x: -셈[x])
            if len(이름) == 1:
                return 이름[0]
            return "★섞임 " + " · ".join("%s %d" % (x, 셈[x]) for x in 이름)
    return "?"


def _번들찾기() -> list[Path]:
    """2차 판독자의 최종 번들을 뒤진다.

    ★ 아무 데나 훑지 않는다 — 이 폴더와 그 위·아래 한 겹까지만 본다.
      깊이 훑으면 시험용 폴더까지 끌어와 대상이 늘어난다 (08-22 에 겪었다).
    """
    본자리 = []
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
                if not p.is_dir() or not (p / 표).exists():
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


def _보정요청_이어받기(번들) -> int:
    """2차 폴더의 보정요청을 이 폴더의 `_인계/` 로 가져온다.

    ★ 사람이 챙기게 두면 빠진다 (2026-08-23 에 3건이 사라졌다).
      번들이 있는 곳에서 위로 두 겹이 2차 폴더다 —
          <2차폴더>/_판독패키지/_결과/<번들>
          <2차폴더>/_인계/보정요청.csv
    """
    import csv as _csv

    낼곳 = ROOT / "_인계" / "보정요청.csv"
    if 낼곳.exists():
        return 0                      # 이미 있으면 건드리지 않는다

    본것 = []
    for b in 번들:
        for 위 in (b.parent.parent.parent, b.parent.parent, b.parent):
            p = 위 / "_인계" / "보정요청.csv"
            if p.exists() and p not in 본것:
                본것.append(p)
    if not 본것:
        return 0

    머리, 행, 본키 = None, [], set()
    for p in 본것:
        with io.open(p, encoding="utf-8-sig", newline="") as h:
            r = _csv.DictReader(h)
            머리 = 머리 or r.fieldnames
            for x in r:
                k = (x.get("무엇이_문제인가") or "").strip()
                if k and k not in 본키:
                    본키.add(k)
                    행.append(x)
    if not 행:
        return 0

    낼곳.parent.mkdir(exist_ok=True)
    with io.open(낼곳, "w", encoding="utf-8-sig", newline="") as h:
        w = _csv.DictWriter(h, fieldnames=머리)
        w.writeheader()
        for i, x in enumerate(행, 1):
            x["번호"] = i
            w.writerow(x)
    return len(행)


def 이차점검(번들: list) -> bool:
    """2차가 넘어와도 되는 상태인가 — 판독자 폴더에서 확인한다.

    ★ 지금까지 아무도 이것을 안 봤다 (sky 2026-08-24).
      2차 결과를 그대로 받아 갈린 행을 뽑기만 했다.
    """
    # ★ **그 폴더의** 검사기를 써야 한다 (2026-08-24).
    #   내 자리 것을 cwd 만 바꿔 돌렸더니 ROOT 가 내 폴더로 잡혀
    #   멀쩡한 2차를 「아직 안 끝났다」 고 했다.
    #   넘어가도_되나 는 `__file__` 로 ROOT 를 정한다 — cwd 가 아니다.

    막힌곳 = []
    for b in 번들:
        # 번들이 있는 곳에서 위로 두 겹이 2차 폴더다
        폴더 = b.parent.parent.parent
        if not (폴더 / "회차배치").is_dir():
            continue
        도구 = 폴더 / "스크립트" / "넘어가도_되나.py"
        if not 도구.exists():
            도구 = 폴더 / "넘어가도_되나.py"
        if not 도구.exists():
            print("     ! %s — 검사기가 없어 건너뜁니다" % 폴더.name)
            continue
        r = subprocess.run([sys.executable, str(도구)], cwd=str(폴더),
                           text=True, encoding="utf-8", capture_output=True)
        말 = (r.stdout or "")
        좋음 = "넘어가도 됩니다" in 말
        print("     %s %s" % ("·" if 좋음 else "✗", 폴더.name))
        if not 좋음:
            for x in 말.splitlines():
                if x.strip().startswith("·"):
                    print("         %s" % x.strip())
            막힌곳.append(폴더.name)
    if 막힌곳:
        print()
        print("  ★ 2차가 아직 끝나지 않았습니다 — %s" % " · ".join(막힌곳))
        print("    그 폴더를 먼저 마치게 하십시오.")
        return False
    return True


def 감독자폴더_차리기(회차: int) -> None:
    """감독 폴더 둘을 차려 준다 — zip 을 풀고 감독 입력을 넣는다.

    ★ 그래야 실무자가 폴더를 만들 일도, 2차 폴더를 옮길 일도 없다.
      ★★ 2차 번들과 매핑은 **넣지 않는다.** 넣으면 익명화가 깨진다.
    """
    import zipfile

    zp = ROOT / "_배포" / "VoC_3_3차감독.zip"
    if not zp.exists():
        print("  ! 3차 꾸러미를 못 찾아 폴더를 못 차립니다 — %s" % zp)
        return

    낼곳 = ROOT / "_감독폴더"
    if 낼곳.exists():
        shutil.rmtree(낼곳)
    낼곳.mkdir()

    for 이름 in ("3차 감독1", "3차 감독2"):
        d = 낼곳 / 이름
        d.mkdir()
        with zipfile.ZipFile(zp) as z:
            z.extractall(d)
        (d / "s13_judge").mkdir(exist_ok=True)
        for p in (ROOT / "s13_judge").glob("judge_*"):
            shutil.copy2(p, d / "s13_judge" / p.name)
        # ★ 매핑은 넣지 않는다 — 감독자가 A·B 를 알면 편든다
        # ★ 경로는 서식에 넣지 않는다 (2026-08-25에 고침).
        #   전에는 `"…%s…" + str(경로) + "…%d…" % (이름, 회차)` 였다.
        #   `+` 가 먼저 붙어 **경로가 서식 문자열의 일부**가 되므로,
        #   경로에 `%` 가 하나만 있어도 자리가 밀려 통째로 죽는다.
        #   ★ 이 탓에 감독 폴더가 한 번도 안 차려졌다.
        _머리 = ("# " + 이름 + " — 여기서 시작하십시오\n\n"
                "```\n"
                "작업 폴더는 여기입니다.\n"
                "\n"
                "    " + str(d.resolve()) + "\n"
                "```\n\n")
        (d / "0_여기서_시작하십시오.md").write_text(
            _머리 +
            ""
            "★ 폴더를 옮기셨으면 위 경로 대신 **지금 이 폴더의 경로**를\n"
            "  AI 에게 알려 주십시오. Codex 는 앱에서 폴더를 못 고릅니다.\n\n"
            "★ 감독 입력이 이미 들어 있습니다 (`s13_judge\\`).\n"
            "  회차 " + str(회차) + "개 · 갈린 행을 총괄이 뽑아 넣었습니다.\n\n"
            "## 하실 일\n\n"
            "```\n"
            "① 이 폴더에서 AI 를 엽니다\n"
            "② `프롬프트\\0_붙여넣을_프롬프트_감독.md` 를 그대로 붙여넣습니다\n"
            "③ 「judge_NN 까지 했습니다」 하고 멈추면 같은 것을 다시 붙여넣습니다\n"
            "```\n\n"
            "★ 다 끝나면 **이 폴더를 그대로** 총괄께 넘겨 주십시오.\n"
            "  통합은 총괄이 합니다 — 다른 감독자 결과를 가져오지 마십시오.\n",
            encoding="utf-8")
        print("     %s" % 이름)


def 다시돌리기_치우기() -> bool:
    """지금 판정을 옆으로 치운다 — **지우지 않는다.**

    ★ sky 2026-08-25 「다시 돌려야 할 때 새 폴더를 만들어 줘야 하는 것 아닌지」

    ★ 왜 지우지 않나 — 편향이 의심돼 다시 돌리는 것이지,
      앞 판이 틀렸다고 확정된 것이 아니다. 견줘 봐야 한다.
    ★ 정답지(ab_mapping)도 **함께** 옮긴다. 짝이 어긋나면 앞 판의 편향을
      다시 잴 수 없다 (오늘 그것 때문에 한참 헤맸다).
    """
    from datetime import datetime

    낼곳 = ROOT / "_되돌린것" / datetime.now().strftime("%Y%m%d_%H%M")
    옮긴것 = 0
    R = ROOT / "_판독패키지" / "_결과"
    낼곳.mkdir(parents=True, exist_ok=True)
    for p in sorted(R.glob("감독결과_*.md")):
        shutil.move(str(p), str(낼곳 / p.name))
        옮긴것 += 1
    for 이름 in ("ab_mapping.json", "judge_input.csv"):
        for 자리 in (ROOT / "_총괄만", ROOT / "s13_judge"):
            q = 자리 / 이름
            if q.exists():
                shutil.copy2(str(q), str(낼곳 / ("%s_%s" % (자리.name, 이름))))
    for q in sorted((ROOT / "s13_judge").glob("judge_*_ids.txt")):
        shutil.copy2(str(q), str(낼곳 / q.name))

    if not 옮긴것:
        print("  치울 판정이 없습니다 — 그냥 새로 만듭니다.")
        return True
    print("  ★ 앞 판을 옆으로 치웠습니다 (지우지 않았습니다)")
    print("     판정 %d개 · 정답지 · 회차 배치  →  %s"
          % (옮긴것, 낼곳.relative_to(ROOT)))
    print("     앞 판과 견주려면 이 폴더를 보십시오.")
    print()
    return True



def _모르는갈래_막기() -> None:
    """★ 모르는 갈래면 멈춘다 (2026-08-25).

    `--확인만` 을 붙여 돌렸는데 이 도구가 그것을 모르면서도 **그냥 돌았다.**
    정답지를 옮기고 폴더를 지웠다. 에러도 안 났다.
    「돌려만 보려던 것」 이 데이터를 바꾸는 사고를 오늘만 네 번 겪었다.

    ★ 조용히 무시하는 것이 가장 나쁘다 — 사람은 「했겠지」 라고 믿는다.
    """
    # ★ --확인만 은 **넣지 않는다** (2026-08-25).
    #   이 도구는 그것을 구현하지 않았다. 아는 척하면
    #   「돌려만 본다」 고 믿는 사람이 실제로 데이터를 바꾼다.
    아는것 = {"--다시돌리기"}
    모르는것 = [a for a in sys.argv[1:] if a.startswith("--") and a not in 아는것]
    if not 모르는것:
        return
    print()
    print("  ★ 모르는 갈래입니다 — %s" % " ".join(모르는것))
    print("     이 도구가 아는 것 : %s" % " · ".join(sorted(아는것)))
    print()
    print("     ★ 아무것도 하지 않고 멈췄습니다.")
    print("       모르는 갈래를 무시하고 돌면, 돌려만 보려던 것이")
    print("       실제로 데이터를 바꿉니다. 오늘 그렇게 네 번 당했습니다.")
    if "--확인만" in 모르는것:
        print()
        print("     ※ 무엇을 뽑을지만 보시려면:")
        print("        python make_judge_input.py <번들1> <번들2> --확인만")
    sys.exit(2)


def main() -> int:
    _모르는갈래_막기()
    print("=" * 70)
    print("  3차 준비 — 2차 결과에서 갈린 행을 뽑습니다")
    print("=" * 70)

    # ★ 판정이 시작됐으면 회차를 다시 만들지 않는다 (2026-08-23).
    #   멈춘 뒤 같은 프롬프트를 다시 붙여넣으면 이 도구도 다시 돈다.
    #   2차 결과가 한 줄이라도 달라지면 회차가 갈아엎히고, 이미 쓴 판정이
    #   엉뚱한 행 묶음을 가리키게 된다. 에러도 안 난다 — 가장 나쁘다.
    # ★ 일부러 다시 돌리는 자리 (sky 2026-08-25)
    if "--다시돌리기" in sys.argv:
        print("  ── 다시 돌리기 ──────────────────────────────────────")
        다시돌리기_치우기()

    이미 = ROOT / "s13_judge" / "judge_input.csv"
    쓴것 = list((ROOT / "_판독패키지" / "_결과").glob("감독결과_*.md"))
    if 이미.exists() and 쓴것:
        회차 = sorted((ROOT / "s13_judge").glob("judge_*_ids.txt"))
        print("  이어가는 중입니다 — 회차를 다시 만들지 않습니다.")
        print("     회차 %d개 · 이미 쓴 판정 %d개" % (len(회차), len(쓴것)))
        print()
        print("  ↳ `_판독패키지/_결과/` 에 **없는 회차부터** 이어서 하십시오.")
        print("=" * 70)
        return 0

    준것 = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    번들 = [p for p in 준것 if (p / 표).exists()] if 준것 else _번들찾기()

    if len(번들) < 2:
        print()
        print("  2차 판독자 **두 명**의 결과를 못 찾았습니다.")
        print("    찾은 것 : %s" % (" · ".join(p.name for p in 번들) or "없음"))
        print("    본 자리 : %s" % ROOT)
        print()
        print("  ↳ 이렇게 하시면 됩니다")
        print("     ① 2차에서 나온 판독자 둘의 결과 폴더를 이 폴더 안에 놓으십시오")
        print("        (각각 안에 raw_voc.csv 가 있는 폴더입니다)")
        print("     ② 다시 돌리십시오")
        return 1

    if len(번들) > 2:
        print()
        print("  결과 폴더가 %d개입니다 — 둘이어야 합니다." % len(번들))
        for p in 번들:
            print("     · %-40s  ← %s 가 만든 것" % (p.name, _누가(p)))
        print()
        print("  ↳ 쓸 둘만 남기거나, 자리를 짚어 주십시오")
        print("     ★ 「누가 만든 것인가」 는 그 폴더의")
        print("        판독결과_full_NN_<이름>.md 에서 읽은 것입니다.")
        print("        같은 이름이 둘이면 한쪽이 남의 폴더에 복사된 것입니다.")
        print("     python 3차_준비.py <번들1> <번들2>")
        return 1

    print("  2차 결과")
    for p in 번들:
        print("     · %s" % p.name)
    print()

    # ★ 2차가 넘어와도 되는 상태인가 — 지금까지 아무도 안 봤다
    print("  2차 점검")
    if not 이차점검(번들):
        return 1
    print()

    도구 = _여기 / "make_judge_input.py"
    if not 도구.exists():
        print("  make_judge_input.py 를 못 찾았습니다 — %s" % _여기)
        return 1

    r = subprocess.run([sys.executable, str(도구), str(번들[0]), str(번들[1])],
                       cwd=str(ROOT), text=True, encoding="utf-8",
                       capture_output=True)
    print(r.stdout.rstrip())
    if r.returncode:
        print(r.stderr.rstrip()[-800:])
        return r.returncode

    입력 = ROOT / "s13_judge" / "judge_input.csv"
    if not 입력.exists():
        print("  감독 입력이 안 만들어졌습니다.")
        return 1

    # ★ 정답지는 감독자가 볼 수 없는 자리로 옮긴다
    답 = ROOT / "s13_judge" / "ab_mapping.json"
    if 답.exists():
        숨길곳 = ROOT / "_총괄만"
        숨길곳.mkdir(exist_ok=True)
        shutil.move(str(답), str(숨길곳 / "ab_mapping.json"))
        (숨길곳 / "0_이 폴더는 무엇입니까.md").write_text(
            "# 총괄만 보는 자리\n\n"
            "★ `ab_mapping.json` — A·B 가 어느 판독자인지 적혀 있습니다.\n\n"
            "**감독자에게 주지 마십시오.** 누가 누구인지 알면 편들게 됩니다.\n"
            "통합할 때 총괄 자리에서만 씁니다.\n",
            encoding="utf-8")
        print("     ★ 정답지는 _총괄만/ 으로 옮겼습니다 (감독자에게 주지 않습니다)")

    # ★ 2차에서 나온 보정요청을 이어받는다 — 사람이 챙기면 빠진다
    _이은것 = _보정요청_이어받기(번들)
    if _이은것:
        print("     ★ 2차 보정요청 %d건을 이어받았습니다" % _이은것)

    회차 = sorted((ROOT / "s13_judge").glob("judge_*_ids.txt"))

    print()
    print("  감독 폴더를 차립니다 (2차 번들도 매핑도 넣지 않습니다)")
    감독자폴더_차리기(len(회차))

    print()
    print("=" * 70)
    print("  준비됐습니다 — %d회차" % len(회차))
    print()
    print("  `_감독폴더\\` 안의 두 폴더를 실무자에게 주십시오.")
    print("  실무자는 각 폴더에서 프롬프트만 붙여넣으면 됩니다.")
    print("  ★ 정답지는 `_총괄만\\` 에 있습니다 — 주지 마십시오.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
