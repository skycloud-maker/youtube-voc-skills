# -*- coding: utf-8 -*-
"""1차 분석 결과 엑셀 하나를 이 꾸러미의 「판독할 데이터」로 앉힌다.

★ 왜 있는가 (sky 2026-08-21)
  「이게 매번 판독할 데이터가 바뀌면 또 새로 해야되는건가요?
    분석할 데이터가 담긴 엑셀은 안줘도 되나요?」

  전에는 데이터가 바뀔 때마다 총괄이 꾸러미를 새로 묶어 줘야 했다.
  이제 **꾸러미는 한 번만 만들고, 다음부터는 엑셀만 주면 된다.**

  실무자는 이것도 직접 칠 필요가 없다 — 판독자 LLM 이 알아서 돌린다.
  프롬프트에 「데이터가 없으면 엑셀을 달라고 하고 이것을 돌려라」 가 적혀 있다.

무엇을 하나
  ① 엑셀(또는 CSV)에서 판독할 표를 뽑아 `판독대상/<이름>/` 에 놓는다
     2차가 채울 칸 5개는 빈 칸으로 미리 붙인다 (pilot 과 같은 모양)
  ② 회차 배치를 나눠 `회차배치/` 에 놓는다 (기본 120행씩)

쓰기
    python 스크립트/데이터_넣기.py 분석결과.xlsx
    python 스크립트/데이터_넣기.py 분석결과.xlsx --이름 로니 --회차크기 150

★ 이미 데이터가 앉아 있으면 먼저 물어본다. `--덮어쓰기` 를 주면 묻지 않는다.
"""

from __future__ import annotations

import csv
import io
import shutil
import sys
from datetime import datetime
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 2차 판독이 채우는 칸 — 1차 결과에는 없는 것이 정상이다. 빈 칸으로 붙인다
SEC_COLS = ["na_class", "qc_status_summary", "qc_rule_ids",
            "split_origin_atomic_id", "secondary_topic_source"]

# 판독에 쓰지 않는 칸 — 대시보드가 보여 주려고 만든 파생 칸이다
_HERE = Path(__file__).resolve().parent
뿌리 = _HERE.parent if _HERE.name in ("스크립트", "scripts") else _HERE


def 표읽기(길: Path) -> tuple[list[str], list[dict]]:
    """1차 결과를 읽는다. xlsx 면 raw_voc 시트를, csv 면 그대로."""

    if 길.suffix.lower() in (".xlsx", ".xls"):
        try:
            import pandas as pd
        except ImportError:
            raise SystemExit(
                "★ 엑셀을 읽으려면 pandas 가 필요합니다.\n"
                "  설치가 어려우면 엑셀을 CSV 로 저장해서 주십시오 — CSV 는 그냥 됩니다."
            )
        묶음 = pd.ExcelFile(길)
        시트 = "raw_voc" if "raw_voc" in 묶음.sheet_names else 묶음.sheet_names[0]
        if 시트 != "raw_voc":
            print("  ! raw_voc 시트가 없어 첫 시트(%s)를 씁니다" % 시트)
        # ★ 정본 §0-2 — 문자열 "N/A" 를 결측으로 읽지 않는다
        틀 = 묶음.parse(시트, keep_default_na=False, na_values=[], dtype=str)
        return [str(c) for c in 틀.columns], 틀.to_dict("records")

    with 길.open("r", encoding="utf-8-sig", newline="") as f:
        읽개 = csv.DictReader(f)
        return list(읽개.fieldnames or []), list(읽개)


def 기준칸(밑바탕: Path) -> list[str]:
    """판독 표의 칸 차례 — 도구들이 아는 모양을 그대로 쓴다.

    이미 앉아 있는 데이터가 있으면 그 머리를 쓰고,
    없으면 pilot 데이터셋에서 딴다. 둘 다 없으면 읽은 것을 쓴다.
    """

    후보 = sorted(밑바탕.glob("판독대상/*/voc_secondary_dataset.csv"))
    후보 += [p for p in sorted(밑바탕.glob("p1_overlabel_suggest_*/voc_secondary_dataset.csv"))
             if "smoke" not in str(p) and "recovery" not in str(p)]
    for p in 후보:
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            return next(csv.reader(f))
    return []


def 준비(원본: Path, 이름: str, 회차크기: int, 밑바탕: Path) -> dict:
    """엑셀 → 판독대상 표 + 회차배치. 만든 것을 알려 준다."""

    머리, 행들 = 표읽기(원본)
    if "atomic_id" not in 머리:
        raise SystemExit("★ atomic_id 칸이 없습니다. 1차 분석 결과가 맞는지 확인하십시오.")

    칸차례 = 기준칸(밑바탕) or ([c for c in 머리 if c not in SEC_COLS] + SEC_COLS)
    없는칸 = [c for c in 칸차례 if c not in 머리 and c not in SEC_COLS]
    버리는칸 = [c for c in 머리 if c not in 칸차례]

    담을곳 = io.StringIO()
    쓰개 = csv.DictWriter(담을곳, fieldnames=칸차례, extrasaction="ignore")
    쓰개.writeheader()
    아이디 = []
    for 행 in 행들:
        쓰개.writerow({c: ("" if 행.get(c) is None else str(행.get(c, ""))) for c in 칸차례})
        값 = str(행.get("atomic_id", "")).strip()
        if 값:
            아이디.append(값)

    회차 = [아이디[i:i + 회차크기] for i in range(0, len(아이디), 회차크기)]
    return {
        "표": 담을곳.getvalue(),
        "행수": len(행들),
        "회차": 회차,
        "없는칸": 없는칸,
        "버리는칸": 버리는칸,
        "겹친아이디": len(아이디) - len(set(아이디)),
        "칸차례": 칸차례,
    }


def 앉히기(결과: dict, 이름: str, 밑바탕: Path, 원본이름: str) -> None:
    """만든 표와 회차를 꾸러미 안에 놓는다."""

    데이터집 = 밑바탕 / "판독대상"
    배치집 = 밑바탕 / "회차배치"
    for 옛 in sorted(데이터집.glob("*/voc_secondary_dataset.csv")):
        shutil.rmtree(옛.parent)
    for 옛 in sorted(배치집.glob("full_*_ids.txt")):
        옛.unlink()

    (데이터집 / 이름).mkdir(parents=True, exist_ok=True)
    배치집.mkdir(parents=True, exist_ok=True)
    (데이터집 / 이름 / "voc_secondary_dataset.csv").write_text(
        결과["표"], encoding="utf-8-sig")
    for 번호, 묶음 in enumerate(결과["회차"], 1):
        (배치집 / ("full_%02d_ids.txt" % 번호)).write_text("\n".join(묶음), encoding="utf-8")

    (데이터집 / "0_이_폴더는.md").write_text(
        "# 판독할 데이터\n\n"
        "```\n"
        "판독대상/%s/voc_secondary_dataset.csv   판독자 LLM 이 읽을 표 (%d행)\n"
        "회차배치/full_01_ids.txt ~              한 회차에 볼 행 목록 (%d회차)\n"
        "```\n\n"
        "★ 폴더를 옮기거나 이름을 바꾸지 마십시오. 도구가 이 자리를 보고 찾습니다.\n\n"
        "만든 날 %s · 원본 `%s`\n"
        % (이름, 결과["행수"], len(결과["회차"]),
           datetime.now().strftime("%Y-%m-%d %H:%M"), 원본이름),
        encoding="utf-8")


def 인자(이름: str, 기본=None):
    if 이름 in sys.argv:
        자리 = sys.argv.index(이름) + 1
        if 자리 < len(sys.argv):
            return sys.argv[자리]
    return 기본


def main() -> int:
    자료들 = [a for a in sys.argv[1:]
              if not a.startswith("--") and a.lower().endswith((".xlsx", ".xls", ".csv"))]
    if not 자료들:
        print(__doc__)
        return 1

    원본 = Path(자료들[0])
    if not 원본.exists():
        print("★ 그런 파일이 없습니다: %s" % 원본)
        return 1

    이름 = 인자("--이름") or 원본.stem.split("(")[0].strip().replace(" ", "_")[:24]
    회차크기 = int(인자("--회차크기", "120"))

    print("=" * 66)
    print("  판독할 데이터 앉히기")
    print("=" * 66)
    print("  꾸러미   : %s" % 뿌리)
    print("  1차 결과 : %s" % 원본.name)
    print("  이름     : %s" % 이름)
    print()

    이미 = sorted((뿌리 / "판독대상").glob("*/voc_secondary_dataset.csv"))
    if 이미 and "--덮어쓰기" not in sys.argv:
        print("  ★ 이미 판독할 데이터가 앉아 있습니다:")
        for p in 이미:
            print("     %s" % p.parent.name)
        print()
        print("  갈아 끼우려면 `--덮어쓰기` 를 붙여 다시 돌리십시오.")
        print("  ★ 판독을 이미 시작하셨다면 갈아 끼우지 마십시오 —")
        print("    회차 목록이 바뀌어 앞서 판독한 것과 대조가 안 됩니다.")
        return 1

    결과 = 준비(원본, 이름, 회차크기, 뿌리)
    print("  읽었습니다 — %d행" % 결과["행수"])
    if 결과["버리는칸"]:
        print("  · 판독에 쓰지 않는 칸 %d개는 뺍니다: %s"
              % (len(결과["버리는칸"]), ", ".join(결과["버리는칸"][:8])))
    if 결과["없는칸"]:
        print("  ! 1차 결과에 없는 칸 %d개는 빈 칸으로 둡니다: %s"
              % (len(결과["없는칸"]), ", ".join(결과["없는칸"][:6])))
    if 결과["겹친아이디"]:
        print("  ! atomic_id 가 겹치는 행이 %d개 있습니다" % 결과["겹친아이디"])

    앉히기(결과, 이름, 뿌리, 원본.name)

    시간 = len(결과["회차"]) * 35 / 60
    print("  회차     : %d개 (한 회차 %d행)" % (len(결과["회차"]), 회차크기))
    print("  ★ 판독자 한 명이 %.0f시간쯤 걸립니다 (한 회차 30~40분 기준)" % 시간)
    print()
    print("=" * 66)
    print("  앉혔습니다. 이어서 `python 스크립트/자가점검.py` 로 확인하십시오.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
