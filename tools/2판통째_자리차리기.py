# -*- coding: utf-8 -*-
"""**2판을 통째로 다시 돌릴** 자리를 차린다 — 1차는 다시 돌리지 않는다 (2026-10-30).

★ 왜 이 도구가 있나 — sky 2026-10-30 「3번 돌려주세요, 2판 통째로」

  재려는 것은 하나다 — **2차·3차 AI 판정이 옛 2판의 판정과 같은가.**
  `tools/옛판_결과대조.py` 로 잰 100.00% 는 **도구**가 같은 일을 한다는 것만 말한다.
  단계별 대조는 AI 판정을 **옛것으로 고정**하고 도구만 댔기 때문이다.
  AI 가 같은 판정을 하는지는 **처음부터 끝까지 다시 돌려야** 나온다.

★ 1차는 **다시 돌리지 않는다.** 옛 댓글을 다시 모을 수 없다 —
  유튜브에서 지워진 댓글이 있고, 새로 달린 댓글도 있다. 같은 검색어로 다시 모으면
  **다른 모수**가 나와서 「AI 판정이 같은가」 를 재는 것이 아니게 된다.
  그래서 **2판의 1차 결과를 그대로 2차 입구에 앉히고** 거기서부터 돌린다.

★ 이것은 돌리개를 고치는 것이 **아니다.** 돌리개에는 이미 이어가는 길이 있다 —
  `상태.json` 의 `끝난단계` 에 「1차」 가 있으면 1차를 건너뛰고, 갖춤새도
  키·엔진을 안 본다 (`갖춤새_점검` 의 ③④). 이 도구는 그 길에 **옛 1차 결과를
  앉혀 주는** 것뿐이다. 그래서 `plugin/` 을 건드리지 않고 판도 다시 묶지 않는다.

쓰기 —
    python tools/2판통째_자리차리기.py <판자리>
    python plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py <판자리> --확인만

  ★ 판자리는 **저장소 밖**에 둔다. 실제로 쓰는 자리는 `docs/진행_2판통째.md` 에 적혀 있다
    (절대경로는 `paths.py` 에만 둔다 — `tests/test_no_old_paths.py` 가 지킨다).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "shared"))
import paths  # noqa: E402

# ── 옛 2판의 1차 결과가 있는 자리 (우리 사본 — 옛 저장소를 건드리지 않는다) ──────────
_기본번들 = paths.BASELINE / "실행" / "2차데이터넣기_1" / "판독" / "voc_dashboard_export_bundle (14).xlsx"
_기본메타 = paths.BASELINE / "원본사본" / "판독A" / "판독패키지" / "7_영상메타.csv"
_옛최종 = paths.BASELINE / "원본사본" / "2판" / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"

이름 = "2판통째"

# ★ 조건은 **머리글과 어림에만** 쓰인다 (1차를 안 돌리므로 수집에는 안 쓰인다).
#   검색어 「로니」 는 2판 판독대상 폴더 이름에서 확인했다 (`판독대상/로니/`).
#   영상 65 · 댓글 100 은 1차 번들을 세어 적었다 (6,336행 / 영상 65개 ≈ 97).
조건글 = "검색어=로니; 영상=65; 댓글=100; 이름=%s" % 이름


def 번들_세기(번들: Path) -> dict:
    """★ 앉히기 **전에** 무엇을 앉히는지 센다. 「못 찾음」 을 「없음」 으로 넘기지 않는다."""
    import openpyxl
    wb = openpyxl.load_workbook(번들, read_only=True)
    if "raw_voc" not in wb.sheetnames:
        raise SystemExit("1차 번들에 raw_voc 시트가 없습니다 — %s" % 번들)
    ws = wb["raw_voc"]
    줄 = ws.iter_rows(values_only=True)
    머리 = list(next(줄))
    for 꼭 in ("atomic_id", "video_id"):
        if 꼭 not in 머리:
            raise SystemExit("1차 번들 raw_voc 에 `%s` 칸이 없습니다 — 2차로 넘길 수 없습니다" % 꼭)
    i_a, i_v = 머리.index("atomic_id"), 머리.index("video_id")
    행, 아이디, 영상 = 0, set(), set()
    for r in 줄:
        if r is None or all(x is None for x in r):
            continue
        행 += 1
        if r[i_a]:
            아이디.add(r[i_a])
        if r[i_v]:
            영상.add(r[i_v])
    wb.close()
    if len(아이디) != 행:
        raise SystemExit("atomic_id 가 유일하지 않습니다 (행 %d · 유일 %d) — 열쇠로 쓸 수 없습니다"
                         % (행, len(아이디)))
    return {"행": 행, "칸": len(머리), "영상": len(영상), "시트": len(wb.sheetnames)}


def 옛최종_세기(쪽: Path) -> dict:
    """대조할 **옛 최종**도 지금 센다 — 나중에 「몇 % 인가」 의 분모다."""
    if not 쪽.is_file():
        raise SystemExit("옛 2판 최종을 못 찾았습니다 (%s) — 못 찾음은 「없음」 이 아닙니다" % 쪽)
    with io.open(쪽, encoding="utf-8-sig", newline="") as f:
        줄 = csv.reader(f)
        머리 = next(줄)
        행 = sum(1 for r in 줄 if r and any(x.strip() for x in r))
    return {"행": 행, "칸": len(머리)}


def 차리기(판: Path, 번들: Path, 메타: Path, 덮어쓰기: bool) -> dict:
    if not 번들.is_file():
        raise SystemExit("1차 번들을 못 찾았습니다 — %s" % 번들)
    상태쪽 = 판 / "상태.json"
    if 상태쪽.is_file() and not 덮어쓰기:
        있던 = json.loads(상태쪽.read_text(encoding="utf-8"))
        raise SystemExit(
            "이 자리에는 이미 돌던 판이 있습니다 — %s\n"
            "  끝난단계: %s\n"
            "  ★ 덮어쓰면 **돈을 쓴 진행이 사라집니다.** 이어 돌리려면 이 도구를 쓰지 말고\n"
            "    한줄_돌리기.py 에 같은 자리를 그대로 넣으십시오 (끝난 단계는 건너뜁니다).\n"
            "    정말 처음부터면 --덮어쓰기 를 붙이십시오."
            % (판, " · ".join(있던.get("끝난단계", [])) or "(없음)"))

    쟨것 = 번들_세기(번들)
    옛것 = 옛최종_세기(_옛최종)

    자리 = 판 / "1차" / "engine" / "outputs" / "voc_dashboard_60" / 이름
    자리.mkdir(parents=True, exist_ok=True)
    shutil.copy2(번들, 자리 / 번들.name)
    # ★ 영상메타는 1차 결과 **옆에** 있어야 갈아 끼워진다 (`데이터_넣기.영상메타_갈아끼우기`).
    #   안 놓으면 판독자는 꾸러미에 든 견본을 보고 판단한다 — 2판 재현이 아니게 된다.
    메타말 = "놓지 않았습니다 (꾸러미 견본을 씁니다)"
    if 메타.is_file():
        shutil.copy2(메타, 자리 / "7_영상메타.csv")
        with io.open(메타, encoding="utf-8-sig", newline="") as f:
            수 = sum(1 for r in csv.reader(f)) - 1
        메타말 = "놓았습니다 (영상 %d개)" % 수

    상태 = {
        "만든날": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "끝난단계": ["1차"],
        "소견": [],
        "기록": {"1차": "옛 2판의 1차 결과를 그대로 앉혔습니다 — 다시 모으지 않았습니다.\n"
                     "  번들: %s\n  행 %d · 칸 %d · 영상 %d · 시트 %d\n  영상메타 — %s"
                     % (번들.name, 쟨것["행"], 쟨것["칸"], 쟨것["영상"], 쟨것["시트"], 메타말)},
        "조건글": 조건글,
        "조건": dict(x.split("=", 1) for x in
                   (c.strip() for c in 조건글.split(";")) if "=" in x),
        "왜": "2026-10-30 — 2판을 통째로 다시 돌려 **AI 판정이 옛 판정과 같은가**를 잰다. "
             "1차는 다시 돌리지 않는다 (옛 댓글을 다시 모을 수 없다).",
    }
    판.mkdir(parents=True, exist_ok=True)
    상태쪽.write_text(json.dumps(상태, ensure_ascii=False, indent=1),
                    encoding="utf-8", newline="\n")
    return {"판": 판, "번들자리": 자리 / 번들.name, "쟨것": 쟨것, "옛것": 옛것, "메타말": 메타말}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("판자리")
    p.add_argument("--번들", default=str(_기본번들))
    p.add_argument("--영상메타", default=str(_기본메타))
    p.add_argument("--덮어쓰기", action="store_true")
    a = p.parse_args()
    r = 차리기(Path(a.판자리).resolve(), Path(a.번들), Path(a.영상메타), a.덮어쓰기)

    print("=" * 66)
    print("  2판 통째 재현 — 자리를 차렸습니다")
    print("=" * 66)
    print("  판자리     %s" % r["판"])
    print("  1차 결과   %s" % r["번들자리"])
    print("             행 %d · 칸 %d · 영상 %d · 시트 %d"
          % (r["쟨것"]["행"], r["쟨것"]["칸"], r["쟨것"]["영상"], r["쟨것"]["시트"]))
    print("  영상메타   %s" % r["메타말"])
    print("  옛 최종    행 %d · 칸 %d  ← 끝나면 이것과 댑니다" % (r["옛것"]["행"], r["옛것"]["칸"]))
    더 = r["옛것"]["행"] - r["쟨것"]["행"]
    print()
    print("  ★ 1차 %d행 → 옛 최종 %d행 — **%d행이 뒤에서 늘어납니다.**"
          % (r["쟨것"]["행"], r["옛것"]["행"], 더))
    print("    3차 D 판정(「둘 다 맞다 — 나눠야 한다」)과 4차 반영이 행을 쪼개기 때문입니다.")
    print("    그래서 행까지 100% 같으려면 **쪼개는 판단까지 같아야** 합니다.")
    print()
    print("  다음 —")
    print("    ① 돈 안 드는 확인:  python plugin/skills/coordinating-voc-pipeline/scripts/"
          "한줄_돌리기.py %s --확인만" % r["판"])
    print("    ② 실제로 돌리기:    같은 명령에 --승인 --깨끗 (돈이 듭니다)")
    print("    ③ 끝나면 대조:      python tools/옛판_결과대조.py <새 최종 raw_voc.csv>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
