# -*- coding: utf-8 -*-
"""정확도 채점 — 최종 데이터에서 표본을 뽑아 **사람이 O/X 를 매기게** 하고, 매긴 것을 세어
**구간별 · 칸별 정확도**를 낸다 (2026-11-06).

    python 정확도_채점.py 만들기 <최종엑셀> <내놓을폴더> [--개수 30]
    python 정확도_채점.py 세기   <채점지.xlsx> [<최종엑셀>]

★ 왜 있나 — sky 2026-11-06 「'정확도 채점과 큰 규모 실행'은 … 실무에서 직접하게 될
  단계이지만, 일단 여기서 그게 돌아가서 그런 결과는 나오는 skill 을 만들어놔야」.
  전에는 채점지를 **만드는** 도구(`make_grading_sheet.py` · topic 하나)만 있었고
  **세는** 도구가 없었다. 어느 스킬 안내에도 나오지 않아 실무자는 있는 줄도 몰랐다.

★ sky 가 정한 것 (2026-11-06 · 네 물음 다 권고안)
  · 칸 여섯 — 제외 여부 · topic · cej · 감성 방향(sentiment_dir) · brand · inquiry_type
  · **AI 가 확정한 답을 보여 주고 O/X** 를 받는다 — 빠르다. 다만 보이는 답에 끌려
    **실제보다 높게** 나오기 쉽다. 그래서 결과에 「답을 보고 매김」 을 늘 적는다.
  · 선 — **90% 이상 믿고 간다 · 80~90% 참고 · 80% 아래 사람이 본다.**
    **결과를 보고 이 선을 바꾸지 않는다** (채점지를 만들 때 미리 적는다).
  · 표본 — **구간마다 30행.** 모자라면 그 구간은 전량.

★ 구간 — 정확도는 하나의 숫자로 말할 수 없다. 행마다 누가 정했는지가 다르다
  (옛 실측: 판독자 둘이 합의한 구간 93% · 감독까지 거치고도 갈린 구간 73%).
    합의   decided_by 가 `reader_agree` 로 시작 — 판독자 둘이 같은 답
    감독   decided_by 가 `judge` 로 시작 — 판독자가 갈려 감독이 정함
  그 밖(사람이 4차에서 정한 행 · 분리 등)은 **채점 밖**이다 — 사람이 이미 정했다.

★ 「못 찾음」 은 「없음」 이 아니다 — 채점지를 못 찾거나 한 칸도 안 채웠으면 **점수를 내지
  않고 멈춘다** (종료 2). 덜 채웠으면 센 것만큼 내되 **「미완」** 이라 크게 적고 종료 3.
"""
from __future__ import annotations

import collections
import csv
import datetime as _dt
import hashlib
import io
import random
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

칸들 = [  # (열 이름 · 사람에게 보이는 이름)
    ("제외", "제외 여부"),
    ("topic", "topic"),
    ("cej", "cej"),
    ("sentiment_dir", "감성 방향"),
    ("brand", "brand"),
    ("inquiry_type", "inquiry_type"),
]
선_믿음, 선_참고 = 0.90, 0.80
기본개수 = 30
씨앗 = 20261106
안물음 = "—"
채점지이름 = "채점지.xlsx"
안내이름 = "0_채점하는_법.md"


# ── 공통 ────────────────────────────────────────────────────────────────

def 지문(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def 행읽기(최종: Path) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(최종, read_only=True)
    if "raw_voc" not in wb.sheetnames:
        raise SystemExit("못 찾음: %s 에 raw_voc 시트가 없다 (통과가 아니다)" % 최종)
    줄 = list(wb["raw_voc"].iter_rows(values_only=True))
    wb.close()
    머리 = [str(x) for x in 줄[0]]
    없는 = [c for c in ("atomic_id", "atomic_voc", "decided_by", "status") +
            tuple(c for c, _ in 칸들 if c != "제외") if c not in 머리]
    if 없는:
        raise SystemExit("못 찾음: raw_voc 에 칸이 없다 — %s" % 없는)
    return [{k: ("" if v is None else str(v).strip()) for k, v in zip(머리, r)} for r in 줄[1:]]


def 구간(r: dict) -> str | None:
    d = r.get("decided_by", "")
    if d.startswith("reader_agree"):
        return "합의"
    if d.startswith("judge"):
        return "감독"
    return None


def 제외인가(r: dict) -> bool:
    return r.get("status") == "scope_excluded"


def 확정값(r: dict, 칸: str) -> str:
    """그 칸에서 사람에게 보일 확정 답. 묻지 않을 칸은 「—」."""
    if 칸 == "제외":
        return ("제외 (%s)" % (r.get("scope_exclusion_reason") or "까닭 없음")
                if 제외인가(r) else "분석에 넣음")
    if 제외인가(r):
        return 안물음     # 제외된 행은 「제외가 맞나」 만 묻는다
    return r.get(칸, "")


def 표본(행들: list[dict], n: int) -> dict[str, list[dict]]:
    """구간마다 n행 — 제외/라벨 비율대로. 씨앗이 고정이라 다시 만들어도 같은 행이다."""
    out = {}
    for 이름 in ("합의", "감독"):
        모 = [r for r in 행들 if 구간(r) == 이름]
        if len(모) <= n:
            out[이름] = list(모)
            continue
        묶 = collections.defaultdict(list)
        for r in 모:
            묶["제외" if 제외인가(r) else "넣음"].append(r)
        rnd = random.Random("%d-%s" % (씨앗, 이름))
        뽑 = []
        for k in sorted(묶):
            v = sorted(묶[k], key=lambda r: r["atomic_id"])
            rnd.shuffle(v)
            뽑 += v[:max(1, round(n * len(v) / len(모)))]
        뽑 = sorted(뽑, key=lambda r: r["atomic_id"])
        rnd.shuffle(뽑)
        out[이름] = 뽑[:n]
    return out


# ── 만들기 ──────────────────────────────────────────────────────────────

def 판정읽기(v) -> str:
    """사람이 적은 것을 O · X · ? · 빈칸 · 묻지않음 · 모름(그 밖) 으로."""
    s = "" if v is None else str(v).strip()
    if s == 안물음:
        return "묻지않음"
    if s == "":
        return "빈칸"
    u = s.upper()
    if u in ("O", "○", "◯", "맞음", "맞다"):
        return "O"
    if u in ("X", "×", "✕", "틀림", "틀리다"):
        return "X"
    if u in ("?", "？", "모름", "모르겠다"):
        return "?"
    return "모름:" + s


def 채운것이_있나(채점지: Path) -> bool:
    import openpyxl
    wb = openpyxl.load_workbook(채점지, read_only=True)
    ws = wb["채점"]
    줄 = list(ws.iter_rows(values_only=True))
    wb.close()
    머리 = [str(x) for x in 줄[1]]
    판칸 = [i for i, h in enumerate(머리) if h.endswith(" O/X")]
    return any(판정읽기(r[i]) not in ("빈칸", "묻지않음") for r in 줄[2:] for i in 판칸)


def 만들기(최종: Path, 폴더: Path, n: int = 기본개수) -> Path:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    최종, 폴더 = Path(최종), Path(폴더)
    if not 최종.is_file():
        raise SystemExit("못 찾음: 최종 엑셀 %s (통과가 아니다)" % 최종)
    폴더.mkdir(parents=True, exist_ok=True)
    나갈곳 = 폴더 / 채점지이름
    # ★ 사람이 매긴 채점지를 덮어쓰면 그 손이 사라진다 — 하나라도 채웠으면 건드리지 않는다.
    if 나갈곳.is_file() and 채운것이_있나(나갈곳):
        print("  · 채점지가 이미 있고 사람이 매긴 칸이 있습니다 — 덮어쓰지 않습니다: %s" % 나갈곳)
        return 나갈곳

    행들 = 행읽기(최종)
    뽑 = 표본(행들, n)
    모집단 = collections.Counter(구간(r) or "채점 밖" for r in 행들)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "채점"
    ws.append(["원문을 읽고 칸마다 확정된 답이 맞으면 O, 틀리면 X(옆에 맞는 답), 모르겠으면 ? 를 적으십시오. "
               "「—」 칸은 묻지 않습니다. 자세한 것은 %s" % 안내이름])
    머리 = ["번호", "구간", "제품군", "원문"]
    for _, 보임 in 칸들:
        머리 += ["%s 확정" % 보임, "%s O/X" % 보임, "%s 아니면" % 보임]
    머리 += ["메모", "atomic_id"]
    ws.append(머리)
    회색 = PatternFill("solid", fgColor="DDDDDD")
    노랑 = PatternFill("solid", fgColor="FFF2CC")
    dv = DataValidation(type="list", formula1='"O,X,?"', allow_blank=True)
    ws.add_data_validation(dv)
    번호 = 0
    for 이름 in ("합의", "감독"):
        for r in 뽑[이름]:
            번호 += 1
            줄 = [번호, 이름, r.get("product_category", ""), r.get("atomic_voc", "")]
            for 칸, _ in 칸들:
                v = 확정값(r, 칸)
                줄 += [v, 안물음 if v == 안물음 else "", 안물음 if v == 안물음 else ""]
            줄 += ["", r["atomic_id"]]
            ws.append(줄)
            행 = ws.max_row
            for j, (칸, _) in enumerate(칸들):
                판열 = 5 + j * 3 + 1        # 1부터: 번호1 구간2 제품군3 원문4 → 확정5 O/X6 아니면7
                셀 = ws.cell(행, 판열)
                if 셀.value == 안물음:
                    for c in range(판열 - 1, 판열 + 2):
                        ws.cell(행, c).fill = 회색
                else:
                    셀.fill = 노랑
                    dv.add(셀)
    for c in range(1, len(머리) + 1):
        ws.cell(2, c).font = Font(bold=True)
    ws.column_dimensions["D"].width = 60
    for 행 in ws.iter_rows(min_row=3, min_col=4, max_col=4):
        for 셀 in 행:
            셀.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "E3"

    정 = wb.create_sheet("정보")
    for k, v in [
        ("만든 때", _dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("최종 엑셀", str(최종)),
        ("최종 엑셀 지문", 지문(최종)),
        ("표본 씨앗", 씨앗),
        ("구간마다 표본", n),
        ("선 — 믿고 간다", "%d%% 이상" % round(선_믿음 * 100)),
        ("선 — 참고", "%d%% 이상 %d%% 미만" % (round(선_참고 * 100), round(선_믿음 * 100))),
        ("선 — 사람이 본다", "%d%% 미만" % round(선_참고 * 100)),
        ("선을 바꾸지 않는다", "결과를 보고 선을 바꾸지 않습니다 (채점지를 만들 때 정함)"),
        ("답을 보여 줌", "예 — 보이는 답에 끌려 실제보다 높게 나올 수 있습니다"),
        ("모집단 합의", 모집단.get("합의", 0)),
        ("모집단 감독", 모집단.get("감독", 0)),
        ("채점 밖 (사람이 정한 행 등)", 모집단.get("채점 밖", 0)),
        ("표본 합의", len(뽑["합의"])),
        ("표본 감독", len(뽑["감독"])),
    ]:
        정.append([k, v])
    wb.save(나갈곳)

    (폴더 / 안내이름).write_text(안내글(len(뽑["합의"]), len(뽑["감독"]), 모집단),
                               encoding="utf-8", newline="\n")
    print("  · 채점지 — 합의 %d행 · 감독 %d행 (모집단 합의 %d · 감독 %d · 채점 밖 %d) → %s"
          % (len(뽑["합의"]), len(뽑["감독"]), 모집단.get("합의", 0), 모집단.get("감독", 0),
             모집단.get("채점 밖", 0), 나갈곳))
    return 나갈곳


def 안내글(합, 감, 모집단) -> str:
    return """# 채점하는 법 — 이 판의 AI 판정이 얼마나 맞나

이 폴더의 `{지}` 에 **합의 {합}행 · 감독 {감}행**을 뽑아 두었습니다.
(이 판 전체: 판독자 둘이 합의한 행 {모합} · 감독이 정한 행 {모감} · 사람이 정한 행 등 {밖} — 마지막은 채점하지 않습니다)

## 매기는 법

`채점` 시트에서 행마다 **원문**을 읽고, 칸마다 노란 칸에 적습니다.

| 적는 것 | 뜻 |
|---|---|
| `O` | 확정된 답이 맞다 |
| `X` | 틀리다 — 옆 「아니면」 칸에 맞는 답을 적습니다 |
| `?` | 모르겠다 — 점수에서 뺍니다 (몇 개였는지는 따로 적습니다) |

- 여러 답이 맞아 보이고 **확정된 답이 그중 하나면 `O`** 입니다.
- **회색 「—」 칸은 묻지 않습니다.** 제외된 행은 「제외가 맞나」 만 봅니다.
- 「제외」 는 제품 얘기가 아니라는 뜻입니다 (채널 칭찬 · 인사 · 잡담 · 광고 · 영상 대본).
- ★ **답을 보여 드리고 매기는 방식**이라, 보이는 답에 끌려 **실제보다 높게** 나오기 쉽습니다.
  애매하면 `X` 나 `?` 쪽으로 적어 주십시오.

## 선 — 결과를 보기 **전에** 정했습니다

| 구간 정확도 | 뜻 |
|---|---|
| **90% 이상** | 이 구간은 믿고 갑니다 |
| **80% 이상 90% 미만** | 쓰되 「참고」 로 표시합니다 |
| **80% 미만** | 이 구간은 사람이 봐야 합니다 |

★ **결과를 보고 이 선을 바꾸지 않습니다.**

## 다 매긴 뒤

```
python <꾸러미>/plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py <판자리> --채점
```

같은 폴더에 `채점결과.md` · `채점결과.csv` 가 생깁니다. 덜 채웠으면 센 것만큼 내되 **「미완」** 이라 적습니다.
""".format(지=채점지이름, 합=합, 감=감, 모합=모집단.get("합의", 0), 모감=모집단.get("감독", 0),
           밖=모집단.get("채점 밖", 0))


# ── 세기 ────────────────────────────────────────────────────────────────

def 판단(정확도: float | None) -> str:
    if 정확도 is None:
        return "잴 수 없음"
    if 정확도 >= 선_믿음:
        return "믿고 간다"
    if 정확도 >= 선_참고:
        return "참고"
    return "사람이 본다"


def 세기(채점지: Path, 최종: Path | None = None) -> tuple[int, str]:
    """(종료코드, 결과 글). 0 다 채움 · 1 알 수 없는 값/데이터 어긋남 · 2 못 찾음/0칸 · 3 미완."""
    import openpyxl
    채점지 = Path(채점지)
    if not 채점지.is_file():
        return 2, "못 찾음: 채점지 %s — 점수를 내지 않습니다 (통과가 아닙니다)" % 채점지
    wb = openpyxl.load_workbook(채점지, read_only=True)
    if "채점" not in wb.sheetnames:
        return 2, "못 찾음: %s 에 「채점」 시트가 없습니다" % 채점지
    줄 = list(wb["채점"].iter_rows(values_only=True))
    정보 = {str(r[0]): r[1] for r in wb["정보"].iter_rows(values_only=True)} if "정보" in wb.sheetnames else {}
    wb.close()
    머리 = [str(x) for x in 줄[1]]
    본문 = [dict(zip(머리, r)) for r in 줄[2:] if r and r[0] is not None]

    지금 = {}
    if 최종 is not None:
        지금 = {r["atomic_id"]: r for r in 행읽기(Path(최종))}

    셈 = collections.defaultdict(collections.Counter)     # (구간, 칸) → Counter
    모름값, 어긋남 = [], []
    for r in 본문:
        구 = str(r.get("구간") or "")
        aid = str(r.get("atomic_id") or "")
        for 칸, 보임 in 칸들:
            p = 판정읽기(r.get("%s O/X" % 보임))
            if p.startswith("모름:"):
                모름값.append("%s번 %s「%s」" % (r.get("번호"), 보임, p[3:]))
                continue
            if 지금 and p in ("O", "X"):
                now = 지금.get(aid)
                확 = "" if r.get("%s 확정" % 보임) is None else str(r.get("%s 확정" % 보임)).strip()
                if now is None or 확정값(now, 칸) != 확:
                    어긋남.append("%s번 %s" % (r.get("번호"), 보임))
                    continue
            셈[(구, 칸)][p] += 1

    매긴 = sum(c["O"] + c["X"] + c["?"] for c in 셈.values())
    빈 = sum(c["빈칸"] for c in 셈.values())
    if 매긴 == 0:
        return 2, ("채점지에 매긴 칸이 **하나도 없습니다** (빈칸 %d) — 점수를 내지 않습니다. "
                   "`%s` 를 보고 매긴 뒤 다시 돌리십시오." % (빈, 안내이름))

    L = ["# 채점 결과 — %s" % _dt.datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    if 빈:
        L += ["> ★★ **미완 — 아직 안 매긴 칸이 %d개 있습니다.** 아래 숫자는 매긴 칸만으로 셌습니다." % 빈, ""]
    L += ["> ★ **답을 보고 매긴 채점입니다** — 보이는 답에 끌려 실제보다 높게 나올 수 있습니다.",
          "> 선(결과를 보기 전에 정함) — 90% 이상 믿고 간다 · 80~90% 참고 · 80% 미만 사람이 본다.",
          "> 채점지 `%s` · 최종 엑셀 지문 %s" % (채점지.name, 정보.get("최종 엑셀 지문", "모름")), ""]
    if 모름값:
        L += ["> ✗ **읽을 수 없는 값 %d개** (O · X · ? 가 아님) — 점수에서 뺐습니다: %s"
              % (len(모름값), " · ".join(모름값[:10])), ""]
    if 어긋남:
        L += ["> ✗ **채점지를 만든 뒤 데이터가 바뀐 칸 %d개** — 점수에서 뺐습니다: %s"
              % (len(어긋남), " · ".join(어긋남[:10])), ""]

    표 = []
    L += ["## 구간별 · 칸별", "",
          "| 구간 | 칸 | 맞음 | 틀림 | 모름(?) | 빈칸 | 정확도 | 판단 |",
          "|---|---|---|---|---|---|---|---|"]
    for 구 in ("합의", "감독"):
        for 칸, 보임 in 칸들:
            c = 셈.get((구, 칸), collections.Counter())
            분모 = c["O"] + c["X"]
            정 = c["O"] / 분모 if 분모 else None
            작음 = " (표본 %d — 흔들림 큼)" % 분모 if 0 < 분모 < 20 else ""
            L.append("| %s | %s | %d | %d | %d | %d | %s | %s%s |"
                     % (구, 보임, c["O"], c["X"], c["?"], c["빈칸"],
                        "%.1f%%" % (정 * 100) if 정 is not None else "—", 판단(정), 작음))
            표.append({"구간": 구, "칸": 보임, "맞음": c["O"], "틀림": c["X"], "모름": c["?"],
                      "빈칸": c["빈칸"], "정확도": "" if 정 is None else round(정, 4), "판단": 판단(정)})

    # 판 전체 어림 — 구간 정확도를 그 구간의 모집단 크기로 무게를 매긴다
    모 = {"합의": int(정보.get("모집단 합의") or 0), "감독": int(정보.get("모집단 감독") or 0)}
    L += ["", "## 판 전체 어림 (합의 · 감독 구간을 모집단 크기로 무게 매김 · 사람이 정한 행 %s 은 빼고)"
          % 정보.get("채점 밖 (사람이 정한 행 등)", "?"), "",
          "| 칸 | 어림 정확도 | 판단 |", "|---|---|---|"]
    for 칸, 보임 in 칸들:
        합무게, 합값 = 0, 0.0
        for 구 in ("합의", "감독"):
            c = 셈.get((구, 칸), collections.Counter())
            if c["O"] + c["X"] and 모[구]:
                합무게 += 모[구]
                합값 += 모[구] * c["O"] / (c["O"] + c["X"])
        정 = 합값 / 합무게 if 합무게 else None
        L.append("| %s | %s | %s |" % (보임, "%.1f%%" % (정 * 100) if 정 is not None else "—", 판단(정)))

    틀린 = []
    for r in 본문:
        for 칸, 보임 in 칸들:
            if 판정읽기(r.get("%s O/X" % 보임)) == "X":
                틀린.append("| %s | %s | %s | %s | %s |" % (
                    r.get("번호"), r.get("구간"), 보임, r.get("%s 확정" % 보임) or "",
                    r.get("%s 아니면" % 보임) or "(안 적음)"))
    if 틀린:
        L += ["", "## 틀렸다고 매긴 칸 — 다음 판 기준 고칠 거리", "",
              "| 번호 | 구간 | 칸 | 확정된 답 | 사람이 적은 답 |", "|---|---|---|---|---|"] + 틀린

    글 = "\n".join(L) + "\n"
    (채점지.parent / "채점결과.md").write_text(글, encoding="utf-8", newline="\n")
    with io.open(채점지.parent / "채점결과.csv", "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(표[0]))
        w.writeheader()
        w.writerows(표)
    코드 = 1 if (모름값 or 어긋남) else (3 if 빈 else 0)
    return 코드, 글


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("만들기", "세기"):
        print(__doc__)
        return 2
    if argv[0] == "만들기":
        if len(argv) < 3:
            print(__doc__)
            return 2
        n = int(argv[argv.index("--개수") + 1]) if "--개수" in argv else 기본개수
        만들기(Path(argv[1]), Path(argv[2]), n)
        return 0
    코드, 글 = 세기(Path(argv[1]), Path(argv[2]) if len(argv) > 2 else None)
    print(글)
    return 코드


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
