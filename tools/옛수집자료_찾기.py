# -*- coding: utf-8 -*-
"""옛 저장소에 **2판의 수집 자료(분석 전 원문 댓글)가 남아 있나** — 세어 답한다.

★ 왜 있나 (2026-11-02) — sky 기준 표의 마지막 빈 칸이 「② 1차 분석 재현」 이었다.
  권고가 「㉮ 옛 저장소에서 2판의 수집 결과를 찾아 복사해 와서 엔진을 다시 돌린다」 였다.
  **찾아야 했고, 이름으로 짐작하지 않고 댓글 번호로 맞췄다.**

  답 — **없다.** 수집 꼴 파일 879개를 다 합쳐도 우리 1차 댓글의 **14.1%** 만 덮인다.
  그래서 ㉮ 는 「시간이 없어서」 가 아니라 **「자료가 없어서」** 못 한다.
  잰 값 전문 → docs/측정/옛수집자료_찾기_20261102.txt

★ 옛 저장소는 **읽기만** 한다 (결정 0001 · 변화 0). 옛 코드는 돌리지 않는다.
  경로는 박지 않는다 — paths.옛저장소 에서 뿌리를 끌어내고, 그 옆 작업 폴더들을
  이름 무늬로 찾는다 (경로를 한 자리에만 두는 공통 규칙 6).

돌리기 (판 자리는 사람이 준다 — 경로를 박지 않는다)
    python tools/옛수집자료_찾기.py <판자리>/판독A/판독대상/.../voc_secondary_dataset.csv
"""
from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import 옛저장소  # noqa: E402

# 우리 1차 입력 — 2판을 통째로 돌릴 때 2차 입구에 앉힌 그 파일.
# ★ 경로를 **박지 않는다** (공통 규칙 6 · tests/test_no_old_paths.py 가 지킨다).
#   판 자리는 저장소 밖이고 판마다 다르므로 **사람이 준다.**
_받은것 = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-")
         else os.environ.get("VOC_1차입력", ""))

건너뛸폴더 = {".git", "__pycache__", "node_modules", ".venv", "venv",
            ".mypy_cache", ".pytest_cache"}
최대크기 = 400 * 1024 * 1024


def 옛뿌리들() -> list[Path]:
    """옛 저장소 본체와 그 옆 작업 폴더들 — paths.옛저장소 에서 끌어낸다."""
    본체 = 옛저장소
    while 본체.parent != 본체 and 본체.parent.name:
        if (본체 / ".git").exists() or (본체 / "src").is_dir():
            break
        본체 = 본체.parent
    뿌리 = [본체]
    부모 = 본체.parent
    if 부모.is_dir():
        뿌리 += sorted(p for p in 부모.iterdir()
                      if p.is_dir() and p != 본체 and p.name.startswith(본체.name + "_"))
    return [p for p in 뿌리 if p.is_dir()]


def 우리댓글번호() -> tuple[set, set]:
    if not _받은것:
        raise SystemExit(
            "1차 입력을 주십시오 — **댈 것이 없으면 검사가 아닙니다.**\n"
            "  python tools/옛수집자료_찾기.py <판자리>/판독A/판독대상/.../voc_secondary_dataset.csv\n"
            "  (또는 환경변수 VOC_1차입력 에 그 파일 경로를 넣으십시오)")
    우리1차 = Path(_받은것)
    if not 우리1차.is_file():
        raise SystemExit("못 찾음: %s — 댈 것이 없다 (통과가 아니다)" % 우리1차)
    글 = 우리1차.read_bytes().decode("utf-8-sig", errors="replace")
    행 = list(csv.DictReader(io.StringIO(글)))
    if not 행 or "source_id" not in 행[0]:
        raise SystemExit("%s 에 source_id 칸이 없다 — 댈 열쇠가 없다" % 우리1차)
    return ({r["source_id"] for r in 행 if r.get("source_id")},
            {r.get("video_id") for r in 행 if r.get("video_id")})


def 수집꼴인가(칸: list) -> bool:
    """수집 자리 = comment_id 가 있고 원문 칸이 있고 **판정 칸(topic)이 없는** 것."""
    s = set(칸)
    return ("comment_id" in s and bool({"text_original", "text_display"} & s)
            and "topic" not in s)


def main() -> int:
    import pyarrow.parquet as pq

    댓글, 영상 = 우리댓글번호()
    print("=" * 76)
    print("  옛 저장소에 2판의 **수집 자료**가 남아 있나 — 댓글 번호로 맞춘다")
    print("=" * 76)
    print()
    print("  우리 1차 입력 — 댓글 %d개 · 영상 %d개" % (len(댓글), len(영상)))
    뿌리 = 옛뿌리들()
    print("  옛 저장소 자리 %d개를 훑는다 (읽기만 한다)" % len(뿌리))
    for p in 뿌리:
        print("     · %s" % p)
    print()

    본파일, 수집꼴, 덮음 = 0, [], set()
    for 뿌 in 뿌리:
        for dp, dn, fn in os.walk(뿌):
            dn[:] = [d for d in dn if d not in 건너뛸폴더]
            for f in fn:
                if not f.endswith((".parquet", ".csv")):
                    continue
                p = Path(dp) / f
                try:
                    크기 = p.stat().st_size
                except OSError:
                    continue
                if 크기 < 200 or 크기 > 최대크기:
                    continue
                본파일 += 1
                try:
                    if f.endswith(".parquet"):
                        칸 = list(pq.read_schema(p).names)
                    else:
                        with io.open(p, "r", encoding="utf-8-sig", errors="replace") as h:
                            칸 = next(csv.reader(h), [])
                except Exception:
                    continue
                if not 수집꼴인가(칸):
                    continue
                try:
                    if f.endswith(".parquet"):
                        찍 = {x for x in pq.read_table(p, columns=["comment_id"])
                              .column(0).to_pylist() if x}
                    else:
                        with io.open(p, "r", encoding="utf-8-sig", errors="replace") as h:
                            찍 = {r.get("comment_id") for r in csv.DictReader(h)
                                 if r.get("comment_id")}
                except Exception:
                    continue
                겹 = len(댓글 & 찍)
                수집꼴.append((겹, len(찍), str(p)))
                덮음 |= (댓글 & 찍)

    if not 수집꼴:
        print("  ★ 수집 꼴 파일을 **한 개도 못 찾았습니다** — 검사를 못 했습니다.")
        print("     (훑은 파일 %d개. 옛 저장소 자리가 맞는지 보십시오)" % 본파일)
        return 1

    수집꼴.sort(reverse=True)
    print("  훑은 파일 %d개 · 그 가운데 **수집 꼴 %d개**를 전부 댔다" % (본파일, len(수집꼴)))
    print()
    for 겹, n, p in 수집꼴[:12]:
        print("  %6d / %d 겹침  (%6d개 든 수집)  %s" % (겹, len(댓글), n, p))
    print()
    비율 = 100.0 * len(덮음) / len(댓글)
    print("  ★ 수집 자리를 **다 합쳐도** 우리 1차 댓글 %d / %d (%.1f%%) 만 덮인다"
          % (len(덮음), len(댓글), 비율))
    if 비율 < 90.0:
        print("     → **2판의 수집 자료는 남아 있지 않다.** 1차를 원본 수집부터 재현할 수 없다")
        print("       (남은 길은 보존된 원문을 분석기에 되돌리는 것 하나 —")
        print("        그것은 **1차 전체의 재현이 아니라 분석 LLM 의 재현**이다)")
    else:
        print("     → 자료가 있다. 복사해 와서 1차를 다시 돌릴 수 있다 (옛 코드는 안 돌린다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
