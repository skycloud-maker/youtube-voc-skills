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
import json
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


def _지문뜨는법():
    """지문을 뜨는 방식은 `지문검사.py` **한 곳**에서 정한다 — 여기서 베끼지 않는다.

    꾸러미 안에서는 둘이 같은 `스크립트/` 폴더에 있고, 저장소에서는 둘이 같은
    `plugin/shared/tools/` 에 있다. 그래서 이 파일 옆을 보면 된다.
    못 불러오면 **조용히 넘어가지 않고** None 을 돌려준다 — 부르는 쪽이 말한다.
    """
    여기 = str(Path(__file__).resolve().parent)
    if 여기 not in sys.path:
        sys.path.insert(0, 여기)
    try:
        import 지문검사                                        # noqa: PLC0415
    except Exception:                                         # noqa: BLE001
        return None
    return getattr(지문검사, "한칸_지문", None)


def 지문_한칸_다시뜨기(밑바탕: Path, 자리이름: str) -> str:
    """대장의 지문에서 **그 한 칸만** 다시 뜨고, 다시 뜬 사실을 이력에 남긴다.

    ★ 왜 (2026-10-28 · sky 가 ㉯ 로 정했다)
      꾸러미는 `판독패키지/7_영상메타.csv` 자리에 **견본**(옛 판 영상 21개)을 담고
      그 견본의 지문을 떠 둔다 (`꾸러미.py` 의 볼곳에 `판독패키지/` 가 있다).
      그런데 바로 아래 `영상메타_갈아끼우기()` 가 **설계대로** 그것을 이 판의
      것으로 갈아 끼운다. → 지문이 반드시 어긋나고,
      **실제 1차를 돌린 판은 모두 판독이 헛반려된다.**
      깨끗한 판 1 에서 판독A·판독B 가 둘 다 그렇게 반려됐다 (2026-10-27).
      `지문검사.py` 주석이 적어 둔 대로 — 「헛경보도 사고다」.

      ★ 왜 「지문에서 빼기」(㉮)가 아닌가 — 영상메타는 제목·태그·설명·채널을 주는
        **판정에 쓰이는 자리**다. 지키기를 포기하면 판독자가 고쳐도 안 드러난다.
        그래서 지키되, 갈아 끼운 그 칸만 다시 뜨고 **다시 뜬 사실을 이력에 남긴다.**
        `지문검사.py` 는 통과 화면에서도 「몇 번 다시 떴다」 를 먼저 말한다.

      ★ 시험은 **갈아 끼운 판**에서 물어야 한다. 옛 시험 그릇은 견본을 그대로
        쓰므로 갈리지 않고, 그래서 이 결함을 한 번도 못 잡았다.
    """
    대장 = 밑바탕 / "대장" / "지문.json"
    자리 = 밑바탕 / 자리이름
    if not 대장.is_file():
        return ("  · 대장에 지문이 아직 없어 다시 뜨지 않았습니다 "
                "(지문검사도 이 꾸러미는 건너뜁니다)")
    뜨기 = _지문뜨는법()
    if 뜨기 is None:
        return ("  ! 지문검사.py 를 못 불러 **대장의 지문을 다시 뜨지 못했습니다** — "
                "판독자가 지문검사를 돌리면 이 파일이 「바뀜」 으로 나옵니다 (헛반려)")
    try:
        적힌것 = json.loads(대장.read_text(encoding="utf-8"))
    except (OSError, ValueError) as 왜:
        return "  ! 대장/지문.json 을 읽지 못해 지문을 다시 뜨지 못했습니다 — %s" % 왜
    지문 = 적힌것.get("지문")
    if not isinstance(지문, dict) or 자리이름 not in 지문:
        return ("  ! 대장의 지문에 `%s` 칸이 없어 다시 뜨지 못했습니다 — "
                "꾸러미를 어떻게 묶었는지 보십시오" % 자리이름)
    새것 = 뜨기(자리)
    if 지문[자리이름] == 새것:
        return ""                      # 견본과 같은 파일이었다 — 다시 뜰 것이 없다

    이제 = datetime.now().strftime("%Y-%m-%d %H:%M")
    이력자리 = 대장.parent / "지문_이력.json"
    이력 = []
    if 이력자리.is_file():
        try:
            이력 = json.loads(이력자리.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            이력 = []
    if not isinstance(이력, list):
        이력 = []
    이력.append({"언제": 이제, "옛것을_뜬날": 적힌것.get("뜬날"),
                "바뀐파일수": 1, "바뀐것": [자리이름],
                "누가": "데이터_넣기.py — 1차 결과의 영상메타로 갈아 끼웠습니다"})
    지문[자리이름] = 새것
    적힌것["지문"] = 지문
    적힌것["다시뜬횟수"] = len(이력)
    # ★ `뜬날` 은 **꾸러미가 뜬 날 그대로** 둔다. 그날이 기준이고,
    #   다시 뜬 것은 이력이 말한다. 여기서 오늘로 바꾸면 「처음부터 이랬다」 로 보인다.
    이력자리.write_text(json.dumps(이력, ensure_ascii=False, indent=1), encoding="utf-8")
    대장.write_text(json.dumps(적힌것, ensure_ascii=False, indent=1), encoding="utf-8")
    return "  · 대장의 지문도 그 한 칸만 다시 떴습니다 (`%s` · 이력에 남습니다)" % 자리이름


def 영상메타_갈아끼우기(원본: Path, 밑바탕: Path) -> str:
    """1차 결과 **옆에** `7_영상메타.csv` 가 있으면 꾸러미의 것을 그것으로 갈아 끼운다.

    ★ 왜 (2026-09-22 알게 됨 · 2026-10-08 고침)
      꾸러미에 들어 있는 `7_영상메타.csv` 는 **옛 판의 영상 21개**짜리다. 판독자는 `video_id` 로 조인해
      제목 · 태그 · 설명 · 채널을 보는데, 이 판의 영상이 거기에 없으면 **제목만 보고 판독**하게 된다
      (2판 240행의 영상 18개 중 16개가 없었다). 1차 스킬이 판마다 만들어 번들 옆에 둔다.
      없으면 그대로 두고 **말은 한다** — 조용히 옛 것을 쓰게 두지 않는다.
    """
    옆 = 원본.parent / "7_영상메타.csv"
    자리 = 밑바탕 / "판독패키지" / "7_영상메타.csv"
    if not 옆.is_file():
        return ("  ! 1차 결과 옆에 7_영상메타.csv 가 없습니다 — 꾸러미에 든 옛 판 것을 그대로 씁니다.\n"
                "    그 안에 이 판의 영상이 없으면 판독자는 제목만 보게 됩니다 (1차 스킬이 만들어 줍니다).")
    if not 자리.parent.is_dir():
        return "  ! 판독패키지 폴더가 없어 7_영상메타.csv 를 갈아 끼우지 못했습니다."
    shutil.copyfile(옆, 자리)
    수 = max(0, sum(1 for _ in io.open(자리, encoding="utf-8-sig")) - 1)
    말 = "  · 7_영상메타.csv 를 이 판의 것으로 갈아 끼웠습니다 (영상 %d개)" % 수
    # ★ 갈아 끼웠으면 대장의 그 칸도 다시 뜬다 — 안 뜨면 판독이 헛반려된다 (2026-10-28)
    더 = 지문_한칸_다시뜨기(밑바탕, "판독패키지/7_영상메타.csv")
    return 말 + (("\n" + 더) if 더 else "")


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
    print(영상메타_갈아끼우기(원본, 뿌리))

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
