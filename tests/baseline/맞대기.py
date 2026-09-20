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

★ 「못 찾음」 은 같음이 아니다 — 폴더가 없거나 비었으면 다름으로 돌려준다.

쓰기
    python tests/baseline/맞대기.py <폴더1> <폴더2> [<뿌리1> <뿌리2>]
    뿌리를 주지 않으면 폴더 자신을 뿌리로 본다.
"""
from __future__ import annotations

import sys
from pathlib import Path

글 = {".csv", ".md", ".json", ".txt", ".py", ".js"}

# 도는 시각을 적는 칸 — 첫 칸 이름. 늘릴 때는 두 번 돌려 그 칸만 다른 것을 확인한 뒤에.
시각칸 = ("잰_날짜",)
# json 에서 도는 시각을 적는 열쇠
시각열쇠 = ("생성",)
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


def _글읽기(p: Path, 뿌리: Path) -> str:
    t = p.read_bytes().decode("utf-8-sig", errors="replace")
    for 꼴 in _경로꼴(뿌리):
        t = t.replace(꼴, "<뿌리>")
    줄 = t.splitlines()
    for i, x in enumerate(줄):
        for k in 시각칸:
            if x.startswith(k + ","):
                줄[i] = _시각꼴.sub("<시각>", x)
        for k in 시각머리:
            if x.startswith(k):
                줄[i] = _시각꼴.sub("<시각>", x, count=1)
        for k in 시각열쇠:
            if x.strip().startswith('"%s": "' % k):
                줄[i] = _시각꼴.sub("<시각>", x)
        for k in 날짜머리:
            if x.startswith(k):
                줄[i] = _날짜꼴.sub("<날짜>", 줄[i], count=1)
    t = "\n".join(줄)
    if p.suffix.lower() == ".csv":
        t = _표에서_날짜칸_가리기(t)
    return t


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
                if r and r[0] in 시각칸:
                    r = [r[0]] + [("<시각>" if isinstance(v, str) and _시각꼴.search(v) else v)
                                  for v in r[1:]]
                rows.append(tuple(r))
            while rows and not rows[-1]:
                rows.pop()
            out.append((ws.title, rows))
        return out
    finally:
        wb.close()


def _첫다름(a: list, b: list) -> str:
    for i, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return "%d번째에서 처음 다름" % i
    return "길이가 다름 %d / %d" % (len(a), len(b))


def 맞대기(가: Path, 나: Path, 뿌리가: Path | None = None, 뿌리나: Path | None = None,
           뺄것: tuple[str, ...] = ()) -> list[str]:
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
                else:
                    for (t, a), (_, b) in zip(x, y):
                        if a != b:
                            다름.append("칸 값 다름: %s [%s]  (%s)" % (r, t, _첫다름(a, b)))
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
