# -*- coding: utf-8 -*-
"""두 결과 폴더를 맞댄다 — 같으면 빈 목록, 다르면 무엇이 어디서 다른지.

★ 무엇을 「같다」 로 보나 (섹션 2, 2026-09-18)
  - 글 파일(.csv .md .json .txt) — 실행 자리의 경로를 `<뿌리>` 로 바꾼 뒤 글자가 같아야 한다.
    도구가 결과에 자기 자리 경로를 적기 때문이다 (ab_mapping.json · 안내문 · 실행기록).
  - 엑셀(.xlsx) — 시트 이름 · 차례 · 칸 값이 같아야 한다. 파일 바이트는 보지 않는다
    (xlsx 안에 저장 시각이 들어 있어 같은 내용도 바이트가 다르다).
  - 그 밖 — 바이트가 같아야 한다.
  - 한쪽에만 있는 파일도 다름이다.
  - ★ 도는 시각을 적는 **값만** 뺀다 — 아래 `시각칸`·`시각열쇠`·`시각머리` 에 적힌 자리에서,
    시각 꼴(YYYY-MM-DD HH:MM)인 값만 `<시각>` 으로 바꾼다. 같은 줄·같은 행의 다른 값은 그대로 본다
    (2026-09-21 교차점검에서 좁혔다 — 전에는 그 행·그 줄을 통째로 지워 다른 값까지 안 보였다):
      편향검사.py 의 `잰_날짜` (csv 한 줄 · xlsx [편향검사] 시트 한 행)
      build_bundle.py 의 summary.json `"생성"` (json 한 줄) — 섹션 4
      데이터_넣기.py 의 판독대상/0_이_폴더는.md `만든 날 YYYY-MM-DD HH:MM` — 섹션 4
        (★ 두 번 돌린 것이 같은 분 안에 끝나 그때는 못 봤다. 스킬 시험에서 드러났다)
  - ★ 도는 **날짜**(시각 없이)를 적는 자리도 뺀다 — handoff.py 가 쓰는 네 자리 (2026-09-21 교차점검):
      `작성 YYYY-MM-DD`(인계서 머리) · `| **접수** | YYYY-MM-DD |`(논의본 표) ·
      보정요청 표의 `접수일` 칸 (csv 와 xlsx 둘 다)
      ★ 09-18 에는 두 실행이 **같은 날**이라 드러나지 않았다. 사흘 뒤 다시 돌려서야 나왔다.
      ★ 값이 날짜 꼴일 때만 가린다. 그 칸의 다른 값(처리상태 등)은 그대로 본다.

★ 허용한 칸 (`허용칸` · 2026-10-07 sky 「1번」) — 엑셀에서 **일부러 바뀐 파생 칸**만 다름에서 뺀다.
  2차 기준은 옛 엔진으로 얼렸는데, 엔진 09-07 판이 `brand_display` 를 「자사 얘기일 때만」 채우도록 바꿨다
  (대시보드 LG 필터 과대 포섭 수정 · sky). 그 칸과 그것으로 계산되는 영상 요약 칸만 허용하고,
  **그 밖의 칸이 하나라도 다르면 다름**이다. 몇 칸이 허용에 걸렸는지는 `허용센것` 에 담아 돌려준다 —
  시험이 그 수까지 못박아, 다음에 또 달라지면 드러난다.

★ 「못 찾음」 은 같음이 아니다 — 폴더가 없거나 비었으면 다름으로 돌려준다.

쓰기
    python tests/baseline/맞대기.py <폴더1> <폴더2> [<뿌리1> <뿌리2>]
    뿌리를 주지 않으면 폴더 자신을 뿌리로 본다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

글 = {".csv", ".md", ".json", ".txt", ".py", ".js"}

# 도는 시각을 적는 칸 — 첫 칸 이름. 늘릴 때는 두 번 돌려 그 칸만 다른 것을 확인한 뒤에.
#   「편향검사」 — `번들_마무리꾸미기` 가 다시 만드는 `VoC_데이터_안내.xlsx` 의 [2_다른_시트_칸] 시트에서
#   편향검사 시트를 가리키는 행에 그 시트의 `잰_날짜` 값이 그대로 실린다 (2026-10-08 · 두 번 돌려 확인).
#   그 행에서 **시각 꼴인 값만** 가린다 — 같은 행의 다른 값은 그대로 본다.
시각칸 = ("잰_날짜", "편향검사")
# ★ 2026-10-28 독립 점검 F02 — 위 가림을 **아무 파일에나 걸지 않는다.**
#   기준 자리 전체를 뒤져 그 가림이 실제로 필요한 파일을 세었다 (2026-10-28):
#     csv  — `편향검사.csv` 하나 (`잰_날짜,<시각>` 한 줄)
#     xlsx — `VoC_데이터_안내.xlsx [2_다른_시트_칸]` 7행 · `3차_최종데이터.xlsx [편향검사]` 1행
#            · `voc_dashboard_export_bundle_2차시험본.xlsx [편향검사]` 1행
#   여기에 적힌 파일 밖에서는 시각도 그대로 댄다 — 그래야 다른 파일의 시각 차이가 드러난다.
#   늘릴 때는 두 번 돌려 그 칸만 다른 것을 확인한 뒤에 적는다.
시각가림_csv = ("편향검사.csv",)
시각가림_xlsx = ("VoC_데이터_안내.xlsx", "3차_최종데이터.xlsx",
             "voc_dashboard_export_bundle_2차시험본.xlsx")
# json 에서 도는 시각을 적는 열쇠
#   「뜬날」 — 지문검사의 `대장/지문.json` 이 **지문을 뜬 시각**을 적는다 (2026-10-08 · zip 안을 보게 되면서 드러났다)
시각열쇠 = ("생성", "뜬날")
# ★ 해시만 적힌 자리인데 그 **원본에 시각이 들어 있어** 매번 달라지는 것 (2026-10-08)
#   `대장/지문.json` 의 `공통/VoC_데이터_안내.xlsx` — 그 엑셀에 편향검사의 `잰_날짜` 가 실린다.
#   엑셀 자체는 시트·칸으로 맞대어 이미 같음을 확인하므로, 지문 쪽 해시 한 줄만 가린다.
#   ★ 가리는 것은 **그 한 열쇠의 값**뿐이다 — 다른 파일의 지문이 바뀌면 그대로 드러난다.
지문열쇠 = ("공통/VoC_데이터_안내.xlsx",)
# 글 줄 앞머리 + 시각 — 그 시각만 <시각> 으로 바꾼다
시각머리 = ("만든 날 ",)
# 글 줄 앞머리 + 날짜(시각 없이) — 그 날짜만 <날짜> 로 바꾼다
날짜머리 = ("작성 ", "| **접수** |")
# 표에서 도는 날을 적는 칸 이름 — csv 머리줄·xlsx 첫 행에서 찾아 그 칸만 가린다
날짜칸이름 = ("접수일",)
_날짜꼴 = __import__("re").compile(r"\d{4}-\d{2}-\d{2}")
_시각꼴 = __import__("re").compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?")


def _경로꼴(뿌리: Path) -> list[str]:
    s = str(뿌리.resolve())
    꼴 = {s, s.replace("\\", "/"), s.replace("\\", "\\\\"), s.replace("/", "\\")}
    return sorted(꼴, key=len, reverse=True)


class 못읽음(Exception):
    """글로 못 읽는 파일 — **같다고 돌려주지 않는다** (2026-10-28 독립 점검 F06).

    `errors="replace"` 로 읽으면 깨진 바이트가 모두 U+FFFD 한 글자로 뭉개져,
    **서로 다른 파일이 같아진다.** 실측 — `0xff` 와 `0xfe` 를 맞대니 `[]` 였다.
    못 읽는 것은 「같음」 이 아니라 **사람이 봐야 하는 일**이다.
    """


def _글읽기(p: Path, 뿌리: Path) -> str:
    바이트 = p.read_bytes()
    try:
        t = 바이트.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise 못읽음("utf-8 로 못 읽음 (%d번째 바이트) — %s" % (e.start, p.name)) from e
    for 꼴 in _경로꼴(뿌리):
        t = t.replace(꼴, "<뿌리>")
    줄 = t.splitlines()
    for i, x in enumerate(줄):
        if p.name in 시각가림_csv:
            for k in 시각칸:
                if x.startswith(k + ","):
                    줄[i] = _시각칸만_가리기(x)
        for k in 시각머리:
            if x.startswith(k):
                줄[i] = _시각꼴.sub("<시각>", x, count=1)
        for k in 시각열쇠:
            if x.strip().startswith('"%s": "' % k):
                줄[i] = _시각꼴.sub("<시각>", x)
        for k in 지문열쇠:
            if x.strip().startswith('"%s": "' % k):
                # 줄 끝 쉼표가 있어도 걸리게 — 그 열쇠가 마지막이 아닐 수도 있다
                줄[i] = re.sub(r'"[0-9a-f]{8,}"(,?)\s*$', r'"<지문>"\1', 줄[i])
        for k in 날짜머리:
            if x.startswith(k):
                줄[i] = _날짜꼴.sub("<날짜>", 줄[i], count=1)
    t = "\n".join(줄)
    if p.suffix.lower() == ".csv":
        t = _표에서_날짜칸_가리기(t)
    return t


def _시각칸만_가리기(줄: str) -> str:
    """시각칸으로 시작하는 csv 줄에서 **칸 전체가 시각인 칸만** <시각> 으로 바꾼다.

    ★ 2026-10-28 독립 점검 F02 — 전에는 `_시각꼴.sub("<시각>", 줄)` 로 **줄 전체**에
      sub 를 걸었다. 그러면 글 안에 박힌 시각까지 바뀌어, 같은 줄의 **다른 글자가
      달라져도 같아진다.** 48줄 주석은 「같은 행의 다른 값은 그대로 본다」 라고
      적고 있었으니 **주석과 코드가 어긋나 있었다.**
      이제 칸으로 쪼개어, **그 칸 전체가 시각 꼴인 칸만** 바꾼다.
    """
    import csv as _csv
    import io as _io
    try:
        칸 = next(_csv.reader(_io.StringIO(줄)))
    except (StopIteration, _csv.Error):
        return 줄
    바뀜 = False
    for i, v in enumerate(칸):
        if i and _시각꼴.fullmatch(v.strip()):
            칸[i] = "<시각>"
            바뀜 = True
    if not 바뀜:
        return 줄
    낼곳 = _io.StringIO()
    _csv.writer(낼곳, lineterminator="").writerow(칸)
    return 낼곳.getvalue()


def _표에서_날짜칸_가리기(t: str) -> str:
    """csv 머리줄에 `날짜칸이름` 이 있으면 그 칸의 날짜 값만 <날짜> 로 바꾼다."""
    import csv as _csv
    import io as _io
    머리 = t.split("\n", 1)[0]
    if not any(k in 머리 for k in 날짜칸이름):
        return t
    행 = list(_csv.reader(_io.StringIO(t)))
    if not 행:
        return t
    자리 = [i for i, c in enumerate(행[0]) if c in 날짜칸이름]
    for r in 행[1:]:
        for i in 자리:
            if i < len(r) and _날짜꼴.fullmatch(r[i].strip()):
                r[i] = "<날짜>"
    낼곳 = _io.StringIO()
    _csv.writer(낼곳, lineterminator="\n").writerows(행)
    return 낼곳.getvalue()


def _엑셀읽기(p: Path, 뿌리: Path):
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    try:
        꼴 = _경로꼴(뿌리)
        out = []
        for ws in wb.worksheets:
            rows = []
            날짜자리 = set()
            for 번, row in enumerate(ws.iter_rows(values_only=True)):
                if 번 == 0:
                    날짜자리 = {i for i, v in enumerate(row) if v in 날짜칸이름}
                    break
            for row in ws.iter_rows(values_only=True):
                r = []
                for v in row:
                    if isinstance(v, str):
                        for k in 꼴:
                            v = v.replace(k, "<뿌리>")
                    r.append(v)
                while r and r[-1] is None:
                    r.pop()
                if 날짜자리 and r:
                    r = [("<날짜>" if (i in 날짜자리 and isinstance(v, str)
                                     and _날짜꼴.fullmatch(v.strip())) else v)
                         for i, v in enumerate(r)]
                if r and r[0] in 시각칸 and p.name in 시각가림_xlsx:
                    # ★ 2026-10-28 독립 점검 F02 — 전에는 시각이 **든** 칸을 통째로
                    #   "<시각>" 으로 바꿨다. 그래서 「규칙 A 2026-01-01 09:00」 과
                    #   「규칙 B 2026-01-01 09:00」 이 **같아졌다** (실측 · `[]`).
                    #   이제 그 칸의 **시각 부분만** 바꾼다 — 나머지 글자는 그대로 댄다.
                    r = [r[0]] + [(_시각꼴.sub("<시각>", v) if isinstance(v, str) else v)
                                  for v in r[1:]]
                rows.append(tuple(r))
            while rows and not rows[-1]:
                rows.pop()
            out.append((ws.title, rows))
        return out
    finally:
        wb.close()


def _엑셀꾸밈(p: Path):
    """엑셀의 **값이 아닌 것**을 모은다 — 수식 · 열 너비 · 머리줄 꾸밈 · 숫자 꼴.

    ★ 2026-10-28 독립 점검 F05 — `_엑셀읽기` 는 `data_only=True` · `values_only=True` 로
      읽어 **값만** 댄다. 그래서 `=1+1` → `=100+100` 과 채움색 빨강 → 초록을 둘 다
      놓쳤다(실측 · `[]`). 그런데 `test_baseline.py` 는 「색·너비 같은 꾸밈은 번들꾸미기
      얼린 기준이 따로 지킨다」 고 적고 있었다 — **말과 장치가 어긋나 있었다.**
      기준 자리의 번들꾸미기 두 판을 대 보니 꾸밈이 완전히 같았다(머리칸 341개 · 다른 곳 0),
      그래서 **약한 말로 바꾸는 대신 대조를 넣는다.**
    """
    import openpyxl
    wb = openpyxl.load_workbook(p, data_only=False)      # 수식을 보려면 False
    try:
        out = []
        for ws in wb.worksheets:
            너비 = {k: (v.width, v.hidden) for k, v in sorted(ws.column_dimensions.items())}
            수식 = []
            꼴 = []
            채움 = []
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("="):
                        수식.append((c.coordinate, c.value))
                    if c.number_format not in ("General", None):
                        꼴.append((c.coordinate, c.number_format))
                    # ★ 채움색은 **머리줄만 보면 안 된다** — 꾸밈은 본문 칸에도 들어간다.
                    #   칸이 많을 수 있어 상한을 둔다. 상한에 닿으면 그 사실을 남긴다.
                    if c.fill is not None and c.fill.patternType:
                        if len(채움) < 20000:
                            채움.append((c.coordinate, c.fill.patternType,
                                       c.fill.fgColor.rgb, c.fill.bgColor.rgb))
                        elif 채움[-1][0] != "…상한":
                            채움.append(("…상한", None, None, None))
            머리 = [(c.coordinate, c.fill.fgColor.rgb, c.font.bold, c.font.size,
                   c.alignment.horizontal) for c in (ws[1] if ws.max_row else [])]
            out.append((ws.title, 너비, tuple(수식), tuple(꼴[:4000]), tuple(머리),
                        ws.freeze_panes, ws.sheet_state, tuple(채움)))
        return out
    finally:
        wb.close()


def _꾸밈다름(이름: str, a, b) -> list[str]:
    """`_엑셀꾸밈` 둘을 대고 **무엇이 다른지** 말로 돌려준다."""
    말 = []
    for (t, 너비a, 수식a, 꼴a, 머리a, 얼a, 상a, 채움a), \
            (_, 너비b, 수식b, 꼴b, 머리b, 얼b, 상b, 채움b) in zip(a, b):
        if 너비a != 너비b:
            다른열 = sorted({k for k in set(너비a) | set(너비b)
                          if 너비a.get(k) != 너비b.get(k)})
            말.append("열 너비 다름: %s [%s]  %s" % (이름, t, 다른열[:6]))
        if 수식a != 수식b:
            말.append("수식 다름: %s [%s]  (%d개 / %d개)"
                    % (이름, t, len(수식a), len(수식b)))
        if 꼴a != 꼴b:
            말.append("숫자 꼴 다름: %s [%s]" % (이름, t))
        if 머리a != 머리b:
            말.append("머리줄 꾸밈 다름: %s [%s]" % (이름, t))
        if 채움a != 채움b:
            다른칸 = [x[0] for x in set(채움a) ^ set(채움b)]
            말.append("채움색 꾸밈 다름: %s [%s]  %s" % (이름, t, sorted(다른칸)[:6]))
        if (얼a, 상a) != (얼b, 상b):
            말.append("틀고정·시트상태 다름: %s [%s]" % (이름, t))
    return 말


def _첫다름(a: list, b: list) -> str:
    for i, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return "%d번째에서 처음 다름" % i
    return "길이가 다름 %d / %d" % (len(a), len(b))


def _칸다름(파일: str, 시트: str, a: list, b: list, 허용: set, 센것: dict) -> list[str]:
    """행·칸을 하나씩 대고, 허용한 칸은 센것에 담는다. 머리줄(첫 행)이 다르면 그것부터 다름이다."""
    out = []
    if len(a) != len(b):
        out.append("칸 값 다름: %s [%s]  (행 수 %d / %d)" % (파일, 시트, len(a), len(b)))
        return out
    if not a:
        return out
    머리 = list(a[0])
    if 머리 != list(b[0]):
        out.append("칸 값 다름: %s [%s]  (머리줄이 다름)" % (파일, 시트))
        return out
    for 번, (x, y) in enumerate(zip(a, b), 1):
        if x == y:
            continue
        for j in range(max(len(x), len(y))):
            값가 = x[j] if j < len(x) else None
            값나 = y[j] if j < len(y) else None
            if 값가 == 값나:
                continue
            이름 = 머리[j] if j < len(머리) else "(%d번째 칸)" % (j + 1)
            if 이름 in 허용:
                센것[(파일, 시트, 이름)] = 센것.get((파일, 시트, 이름), 0) + 1
                continue
            out.append("칸 값 다름: %s [%s] %s  (%d번째 행)" % (파일, 시트, 이름, 번))
            if len(out) >= 20:
                return out
    return out


def 맞대기(가: Path, 나: Path, 뿌리가: Path | None = None, 뿌리나: Path | None = None,
           뺄것: tuple[str, ...] = (), 허용칸: dict | None = None, 허용센것: dict | None = None,
           꾸밈: bool = False) -> list[str]:
    가, 나 = Path(가), Path(나)
    뿌리가, 뿌리나 = Path(뿌리가 or 가), Path(뿌리나 or 나)
    다름: list[str] = []
    for d in (가, 나):
        if not d.is_dir():
            return ["폴더를 못 찾음 — %s" % d]
    def 목록(d: Path) -> set[str]:
        return {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()
                and not any(p.relative_to(d).as_posix().startswith(x) for x in 뺄것)}
    ㄱ, ㄴ = 목록(가), 목록(나)
    if not ㄱ and not ㄴ:
        return ["두 폴더 모두 비었음 — 맞댈 것이 없다"]
    for r in sorted(ㄱ - ㄴ):
        다름.append("한쪽에만: %s  (%s)" % (r, 가.name))
    for r in sorted(ㄴ - ㄱ):
        다름.append("한쪽에만: %s  (%s)" % (r, 나.name))
    for r in sorted(ㄱ & ㄴ):
        p, q = 가 / r, 나 / r
        sfx = p.suffix.lower()
        try:
            if sfx in 글:
                x, y = _글읽기(p, 뿌리가), _글읽기(q, 뿌리나)
                if x != y:
                    다름.append("내용 다름: %s  (%s)" % (r, _첫다름(x.splitlines(), y.splitlines())))
            elif sfx == ".xlsx":
                x, y = _엑셀읽기(p, 뿌리가), _엑셀읽기(q, 뿌리나)
                if [t for t, _ in x] != [t for t, _ in y]:
                    다름.append("시트 다름: %s  %s / %s" % (r, [t for t, _ in x], [t for t, _ in y]))
                elif 허용칸 is None:
                    for (t, a), (_, b) in zip(x, y):
                        if a != b:
                            다름.append("칸 값 다름: %s [%s]  (%s)" % (r, t, _첫다름(a, b)))
                else:
                    센것 = 허용센것 if 허용센것 is not None else {}
                    for (t, a), (_, b) in zip(x, y):
                        if a != b:
                            다름 += _칸다름(r, t, a, b, set(허용칸.get(t, ())), 센것)
                # ★ 2026-10-28 F05 — 값 말고 **꾸밈·수식**도 댄다 (부르는 쪽이 켤 때)
                if 꾸밈:
                    다름 += _꾸밈다름(r, _엑셀꾸밈(p), _엑셀꾸밈(q))
            elif sfx == ".zip":
                # ★ zip 은 **안을 풀어 같은 기준으로** 본다 (2026-10-08).
                #   zip 바이트에는 압축 시각이 들어가 같은 내용도 다르다. 그리고 안에 든
                #   `VoC_데이터_안내.xlsx` 에는 편향검사의 `잰_날짜` 가 실려 겉바이트 비교로는 늘 다르게 나온다.
                #   맞대기 자신을 다시 불러 규칙을 한 벌로 지킨다 (zip 안의 zip 도 그대로 처리된다).
                import tempfile
                import zipfile
                with tempfile.TemporaryDirectory() as 임시:
                    ㄱ자리, ㄴ자리 = Path(임시) / "가", Path(임시) / "나"
                    for 자리, 파일 in ((ㄱ자리, p), (ㄴ자리, q)):
                        자리.mkdir()
                        with zipfile.ZipFile(파일) as z:
                            z.extractall(자리)
                    for 말 in 맞대기(ㄱ자리, ㄴ자리, 뿌리가, 뿌리나, 뺄것, 허용칸,
                                  허용센것, 꾸밈):
                        다름.append("zip 안 다름: %s → %s" % (r, 말))
            elif p.read_bytes() != q.read_bytes():
                다름.append("바이트 다름: %s" % r)
        except Exception as e:                      # 못 읽은 것은 같음이 아니다
            다름.append("못 읽음: %s  (%s)" % (r, e))
    return 다름


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if len(a) not in (2, 4):
        print(__doc__)
        return 2
    결과 = 맞대기(*[Path(x) for x in a])
    for x in 결과:
        print("  ✗ " + x)
    print("  다름 %d개" % len(결과) if 결과 else "  같음")
    return 1 if 결과 else 0


if __name__ == "__main__":
    sys.exit(main())
