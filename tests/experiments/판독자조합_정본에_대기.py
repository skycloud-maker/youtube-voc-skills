# -*- coding: utf-8 -*-
"""판독자 조합 실험 ③ — 2판 정본(최종 산출물)을 답으로 놓고 댄다 (sky 2026-09-21 「최종 결과물이 정답지라고 가정하고」).

★ 정본 = `원본사본/2판/s15_master/raw_voc.csv`. 행마다 3차 결과(4차 규칙 전 스냅샷)부터 최종까지 라벨을 따라가,
  판독자가 정본과 다른 까닭을 나눈다 — 3차 뒤 규칙이 바꾼 행은 판독자 탓이 아니다.
★ 걸림 — 정본의 대부분(reader_agree)은 8월 Claude · Codex 가 같은 답을 내 사람이 안 본 행이다.
  그래서 8월 쌍의 「같이 틀림」 은 언제나 0 이고, 정본은 8월 Codex 쪽 제외 사유를 물려받았다.

쓰기
    python tests/experiments/판독자조합_정본에_대기.py                          A · B · C (섹션 5b 전)
    python tests/experiments/판독자조합_정본에_대기.py claudeA codexC claudeD codexE   이름을 주면 그들끼리

★ 섹션 5b 뒤 (sky 2026-09-22 [가1] 가전이면 살린다) — 정본은 「대상 제품군 밖 가전」 을 뺐으므로
  제품군이 어긋난 영상(최신결정_검사 라1)의 행은 정본이 더는 답이 아니다. 그 행은 따로 센다.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

정본자리 = BASELINE / "원본사본" / "2판" / "s15_master"
결과자리 = BASELINE / "실험" / "판독자조합"
지금 = ["claudeA", "claudeB", "codexC"]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugin" / "shared" / "tools"))
import 최신결정_검사 as 검사  # noqa: E402


def _어긋난영상(정: dict) -> set[str]:
    """라1 과 같은 기준 — 정본 전체에서 제품군이 어긋나 보이는 영상"""
    import re as _re
    from collections import defaultdict as _dd
    묶음 = _dd(list)
    for r in 정.values():
        묶음[(r.get("video_id", ""), r.get("video_title", ""), r.get("product_category", ""))].append(r)
    out = set()
    for (vid, 제목, 군), xs in 묶음.items():
        pat = 검사.어휘.get(군)
        if not pat or len(xs) < 검사.최소행 or _re.search(pat, 제목, _re.I):
            continue
        if sum(bool(_re.search(pat, x.get("original_voc", ""), _re.I)) for x in xs) / len(xs) < 검사.댓글비율:
            out.add(vid)
    return out


def _읽기(p: Path) -> dict:
    return {r["atomic_id"]: r for r in csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig")))}


def _라벨(r: dict | None) -> str:
    if r is None:
        return "(행없음)"
    if (r.get("status") or "") == "scope_excluded":
        return "제외:" + (r.get("scope_exclusion_reason") or "?")
    return r.get("topic") or "(빈칸)"


def _넣고빼기(x: str) -> str:
    return "제외" if x.startswith("제외:") else x


def _종류(x: str, v: dict) -> str:
    g = v["정본"]
    if x == g:
        return "0 같음"
    if v["바뀜"] and x == v["3차"]:
        return "1 3차 뒤 규칙이 바꾼 행 (판독자 탓 아님)"
    xe, ge = x.startswith("제외:"), g.startswith("제외:")
    if xe and ge:
        return "2 둘 다 제외 · 사유만 다름"
    if g == "제외:out_of_scope_product":
        return "3 정본은 「대상 제품 아님」 으로 뺐는데 판독자는 라벨"
    if xe != ge:
        return "4 넣고 빼기가 다름 (그 밖)"
    return "5 라벨이 다름"


def main(이름들: list[str] | None = None) -> None:
    지금 = 이름들 or globals()["지금"]
    정 = _읽기(정본자리 / "raw_voc.csv")
    스냅 = sorted(정본자리.glob("raw_voc_*.csv"), key=lambda p: re.search(r"(\d{8}_\d{4})", p.name).group(1))
    if not 스냅:
        raise SystemExit("정본 스냅샷을 못 찾았다 — %s" % 정본자리)
    단계 = [(re.sub(r"raw_voc_|_\d{8}_\d{4}\.csv", "", p.name), _읽기(p)) for p in 스냅]
    옛 = {"8월claude": _읽기(BASELINE / "원본사본/판독A/_판독패키지/_결과/claudecode_bundle/raw_voc.csv"),
         "8월codex": _읽기(BASELINE / "원본사본/판독B/_판독패키지/_결과/Codex_bundle/raw_voc.csv")}
    R = {}
    for n in 지금:
        후보 = sorted((BASELINE / "스킬시험" / ("실험_" + n) / "작업" / "_판독패키지" / "_결과").glob("*_bundle/raw_voc.csv"))
        if len(후보) != 1:
            raise SystemExit("%s 의 최종 번들을 하나로 못 찾았다 — %s" % (n, 후보))
        R[n] = _읽기(후보[0])
    ks = sorted(set.intersection(*(set(d) for d in R.values())) & set(정))
    if not ks:
        raise SystemExit("정본과 겹치는 행이 없다 — 못 찾음은 통과가 아니다")

    표 = {}
    for k in ks:
        seq = [(s, _라벨(d.get(k))) for s, d in 단계] + [("최종", _라벨(정[k]))]
        바뀜 = ["%s: %s→%s" % (a[0], a[1], b[1]) for a, b in zip(seq, seq[1:]) if a[1] != b[1]]
        표[k] = {"정본": _라벨(정[k]), "3차": _라벨(단계[0][1].get(k)), "바뀜": 바뀜, "decided_by": 정[k].get("decided_by", ""),
                 **{n: _라벨(d.get(k)) for n, d in 옛.items()}, **{n: _라벨(d[k]) for n, d in R.items()},
                 "영상": 정[k].get("video_title", ""), "원문": 정[k].get("original_voc", ""), "조각": 정[k].get("atomic_voc", "")}
    print("행 %d (세 판독 · 정본에 다 있는 행) · 3차 뒤 라벨이 바뀐 행 %d" % (len(ks), sum(bool(v["바뀜"]) for v in 표.values())))
    print("정본을 정한 쪽:", dict(Counter(v["decided_by"] for v in 표.values()).most_common()))
    print("\n① 정본과 다른 까닭")
    for n in list(옛) + 지금:
        print("  %-9s %s" % (n, dict(sorted(Counter(_종류(v[n], v) for v in 표.values()).items()))))
    안바뀐 = [k for k in ks if not 표[k]["바뀜"]]
    print("\n② 쌍마다 — 3차 뒤 안 바뀐 %d행 · 제외 사유는 무시(넣고 빼기 + 라벨)" % len(안바뀐))
    import itertools
    어긋 = _어긋난영상(정)
    print("  (제품군이 어긋난 영상 %d개 — %s)" % (len(어긋), sorted(어긋)))
    for 이름, 볼행 in (("전체", 안바뀐), ("어긋난 영상 뺌", [k for k in 안바뀐 if 정[k].get("video_id") not in 어긋])):
      print("  ── %s %d행" % (이름, len(볼행)))
      for n in 지금 + list(옛):
          print("     %-9s 정본과 같음 %d" % (n, sum(_넣고빼기(표[k][n]) == _넣고빼기(표[k]["정본"]) for k in 볼행)))
      for x, y in list(itertools.combinations(지금, 2)) + [("8월claude", "8월codex")]:
        합 = [k for k in 볼행 if _넣고빼기(표[k][x]) == _넣고빼기(표[k][y])]
        틀 = [k for k in 합 if _넣고빼기(표[k][x]) != _넣고빼기(표[k]["정본"])]
        print("     %s·%s  같은 답 %d · 같이 틀림 %d · 감독에게 갈 행 %d" % (x, y, len(합), len(틀), len(볼행) - len(합)))
    for x, y in []:
        합 = [k for k in 안바뀐 if _넣고빼기(표[k][x]) == _넣고빼기(표[k][y])]
        틀 = [k for k in 합 if _넣고빼기(표[k][x]) != _넣고빼기(표[k]["정본"])]
        oos = sum(표[k]["정본"] == "제외:out_of_scope_product" for k in 틀)
        print("  %s·%s  같은 답 %d · 같이 틀림 %d (그중 대상 제품 아님 못 거름 %d) · 감독에게 갈 행 %d"
              % (x, y, len(합), len(틀), oos, len(안바뀐) - len(합)))
    (결과자리 / "정본추적.json").write_text(json.dumps(표, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n행마다 →", 결과자리 / "정본추적.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:] or None)
