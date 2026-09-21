# -*- coding: utf-8 -*-
"""아무도 안 채우는 칸을 찾는다.

★ 왜 만들었나 — 2026-08-26 에 **분리 조각 570행이 13칸 넘게 통째로 비어**
  있는 것을 sky 가 물어서 찾았다. 검사가 잡은 게 아니다.
  그때 검사 12종이 전부 통과하고 있었다.

  값이 각각 유효하면 기존 검사는 지나간다. 빈 칸도 「유효한 빈 칸」 이다.
  놓친 것은 **칸과 칸의 관계**가 아니라 **행을 만든 주체별 차이**였다.

      reader_agree (2차 판독)      4,566행   0.7% 빔
      judge_agree  (3차 감독)      1,196행   1.6~3.5% 빔
      감독_분리제안 (3차가 나눈 조각)    37행  13.2% 빔
      sky+분리회차 (4차 apply_split)   570행 **100% 빔**   ← 여기만 통째로 빈다

  「전체의 8%가 비었다」 는 눈에 안 띈다. **「한 묶음만 100% 비었다」 는 띈다.**
  그것이 이 검사의 전부다.

무엇을 보나
-----------
검사 ①  데이터   행을 「누가 만들었나」 로 묶고, 칸마다 묶음별 빈칸률을 잰다.
                 한 묶음만 유독 비어 있으면 그 묶음을 만든 도구가 안 채운 것이다.
검사 ②  코드     조각을 만드는 도구 둘(`build_bundle.py` 2·3차용 ·
                 `apply_split.py` 4차용)이 각각 어느 칸에 값을 넣는지
                 소스에서 뽑아 맞댄다. 한쪽만 채우는 칸을 미리 잡는다.

②가 예방이고 ①이 사후 확인이다. 도구를 새로 만들 때는 ②가 먼저 운다.

★ ② 는 혼자서는 시끄럽다. 두 도구 다 「조각(seg)이 준 값은 그대로 받는다」 는
  갈래가 있어서, 어느 칸을 누가 명시로 넣는지는 취향 차이일 때가 많다.
  그래서 ② 가 문 칸을 **① 의 데이터로 되짚어**, 실제로 빈칸률이 갈리는 것만
  ★ 로 올린다. 코드가 「샐 수 있다」 하고 데이터가 「샜다」 해야 경보다.

쓰는 법
-------
    python 아무도_안채우는칸_검사.py            # 본다
    python 아무도_안채우는칸_검사.py --자세히     # 칸별 표를 다 편다

새는 자리가 있으면 종료코드 1 이다 (`마무리_이력정리.py` 가 이걸 본다).
"""

from __future__ import annotations

import ast
import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 8)
뿌리 = Path(__file__).resolve().parent
자세히 = "--자세히" in sys.argv

# ── 일부러 비워 두는 칸 ────────────────────────────────────
#    비어 있는 게 맞는 칸이다. 이유를 같이 적어 둔다 —
#    이유 없이 목록에만 올리면 다음 사람이 진짜 결함을 여기 숨긴다.
봐준다: dict[str, str] = {
    "qc_status_summary": "엔진 QC 로그. 조각은 엔진을 안 거치므로 빈 게 맞다",
    "qc_rule_ids": "위와 같음",
    "qc_verdict": "위와 같음",
    "qc_finding_count": "위와 같음",
    "qc_entity": "위와 같음",
    "qc_confidence": "위와 같음",
    "qc_criteria_uncovered": "위와 같음",
    "qc_structural_defect": "위와 같음",
    "na_class": "N/A 로 판정된 행에만 붙는다. 묶음마다 N/A 비율이 다르다",
    "scope_exclusion_reason": "제외된 행에만 붙는다",
    "voc_residual": "부모 행에만 남는다. 조각에는 없는 게 맞다",
    "split_origin_atomic_id": "분리로 생긴 행에만 붙는다 — 이 칸이 곧 묶음 이름이다",
    "decided_note": "판정을 바꾼 행에만 이유가 붙는다",
    "topic_provisional": "1차가 확정 못 한 행에만 남는다",
    "proposal_flag": "제안이 달린 행에만 붙는다",
    "inquiry_type_raw": "문의로 잡힌 행에만 붙는다",
    "need_signal_type_raw": "니즈 신호가 잡힌 행에만 붙는다",
    "competitor_product_additional_info": "경쟁 제품이 언급된 행에만 붙는다",
    "product_additional_info": "제품 상세가 언급된 행에만 붙는다",
    # ★ 2026-09-07 — 이 둘은 「원래 드문 칸」 이라 묶음끼리 늘 갈린다.
    #   경쟁사를 실제로 말한 행에만 붙기 때문이다.
    #   분리 조각은 「여러 주제가 섞인 긴 댓글」 에서 나오므로 경쟁사를 말할
    #   확률이 높아 99% 가 차 있고, 보통 댓글은 경쟁사를 안 말하는 게 정상이라
    #   85~92% 가 빈다. 도구가 안 채운 것이 아니라 말할 것이 없던 것이다.
    #   ★ 그래도 4차 조각 570행이 0% 였던 것은 진짜 결함이었고 7차에서 채웠다 —
    #     그때는 「부모에는 값이 있는데 조각에만 없었다」 가 증거였다.
    #     이 칸을 다시 의심할 때는 그 증거(부모와 견주기)로 판단하십시오.
    "competitor_brand_tags": "경쟁사를 말한 행에만 붙는 칸. 묶음마다 언급률이 다르다",
    "competitor_product_tags": "위와 같음",
    "secondary_topic_source": "2차가 주제를 바꾼 행에만 붙는다",
    "review_reason": "검토가 필요한 행에만 붙는다",
}

# 빈칸률 차이가 이만큼 벌어지면 「새는 자리」 로 본다
비었다고본다 = 0.80        # 그 묶음의 80% 이상이 비고
차이가난다 = 0.50          # 잘 채운 묶음과 50%p 이상 벌어지면
묶음최소 = 20              # 20행 미만인 묶음은 통계로 안 본다

# ★ 잣대가 되는 묶음은 이만큼은 돼야 한다 (2026-09-07).
#   22행짜리 묶음을 잣대로 삼았더니 competitor_brand_tags 처럼
#   **원래 드문 칸**이 걸렸다 — 경쟁사를 실제로 말한 행에만 붙는 칸이라
#   일반 행은 17% 만 값이 있는데, 22행 묶음이 우연히 100% 였다.
#   「비었다」 쪽은 작은 묶음도 본다. 통째로 빈 작은 묶음이야말로 찾을 것이니까.
#   「잘 채웠다」 쪽만 큰 묶음으로 제한한다.
잣대최소 = 100


# ══════════════════════════════════════════════════════════
#  검사 ①  데이터 — 한 묶음만 유독 비어 있나
# ══════════════════════════════════════════════════════════

def _최신판() -> Path | None:
    """데이터를 찾는다. **판 안에서 돌려도 찾게 한다.**

    ★ 2026-09-08 — 이 파일을 `_2판/` 에 사본으로 두었더니, 거기서는
      `_2판/_*판` 을 뒤지느라 데이터를 못 찾았다. 그런데도 코드 검사만 통과해
      **종료코드 0 으로 끝났다** — 검사기가 조용히 검사를 안 한 것이다.
      판 폴더를 통째로 받은 사람은 「통과」 만 보고 넘어간다.
    """
    # ① 뿌리에서 돌릴 때 — 가장 최신 판을 고른다. **이쪽이 먼저다.**
    #    ★ 뿌리에도 `_판독패키지`(1판) 가 있다. 그것을 먼저 잡으면
    #      뿌리 실행이 조용히 1판을 보게 된다 — 2026-09-08 에 한 번 그랬다.
    후보 = [d for d in 뿌리.glob("_*판")
            if d.is_dir() and d.name[1:-1].isdigit()
            and (d / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv").is_file()]
    if 후보:
        return (sorted(후보)[-1] / "_판독패키지" / "_결과"
                / "master_final" / "raw_voc.csv")
    # ② 판 폴더 안에서 돌릴 때 — 내 밑에 있다
    안 = 뿌리 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"
    return 안 if 안.is_file() else None


def _누가만들었나(r: dict) -> str:
    """행을 만든 주체로 묶는다. 도구가 다르면 채우는 칸도 다르다."""
    if (r.get("split_origin_atomic_id") or "").strip():
        d = (r.get("decided_by") or "").strip()
        if d.startswith("sky+분리"):
            return "4차 분리 (apply_split)"
        if d.startswith("감독_분리"):
            return "3차 분리 (build_bundle)"
        return "분리 (그 밖)"
    d = (r.get("decided_by") or "").strip()
    if d == "reader_agree":
        return "2차 판독 합의"
    if d.startswith("judge_agree"):
        return "3차 감독 판정"
    if d.startswith(("총괄", "sky")):
        return "총괄·사람 판정"
    return "그 밖"


def _빈칸률() -> dict[str, dict[str, float]]:
    """칸마다 「묶음별 빈칸 비율」 을 돌려준다. ① 과 ② 가 같이 쓴다."""
    길 = _최신판()
    if not 길:
        return {}
    with io.open(길, encoding="utf-8-sig", newline="") as h:
        본 = list(csv.DictReader(h))
    묶음 = defaultdict(list)
    for r in 본:
        묶음[_누가만들었나(r)].append(r)
    쓸 = {k: v for k, v in 묶음.items() if len(v) >= 묶음최소}
    return {c: {k: sum(1 for r in v if not str(r.get(c) or "").strip()) / len(v)
                for k, v in 쓸.items()}
            for c in (list(본[0]) if 본 else [])}


def 데이터로본다() -> list[str] | None:
    """돌려주는 것 — 새는 칸 목록. **데이터를 못 찾았으면 None.**

    ★ 빈 목록([])과 못 찾음(None)을 구분한다.
      전에는 못 찾아도 [] 를 돌려줘서 「새는 자리 없음」 으로 끝났다.
    """
    길 = _최신판()
    if not 길:
        print("  ★ master_final/raw_voc.csv 를 못 찾았습니다.")
        print("     **데이터 검사를 못 했습니다** — 통과가 아닙니다.")
        print("     이 파일을 판 폴더 안에 두었다면, 그 판에 데이터가 있어야 합니다.")
        return None
    with io.open(길, encoding="utf-8-sig", newline="") as h:
        본 = list(csv.DictReader(h))
    칸들 = list(본[0]) if 본 else []

    묶음 = defaultdict(list)
    for r in 본:
        묶음[_누가만들었나(r)].append(r)
    쓸묶음 = {k: v for k, v in 묶음.items() if len(v) >= 묶음최소}

    print("  ① 데이터 — %s (%s행)" % (길.parent.parent.parent.parent.name,
                                      format(len(본), ",")))
    for k in sorted(쓸묶음, key=lambda x: -len(쓸묶음[x])):
        print("       %-26s %s행" % (k, format(len(쓸묶음[k]), ",")))
    작은 = {k: len(v) for k, v in 묶음.items() if len(v) < 묶음최소}
    if 작은:
        print("       (%d행 미만이라 안 봄: %s)"
              % (묶음최소, " · ".join("%s %d" % kv for kv in 작은.items())))

    잣대 = [k for k, v in 쓸묶음.items() if len(v) >= 잣대최소]
    if not 잣대:
        잣대 = list(쓸묶음)
    샘 = []
    for c in 칸들:
        빈률 = {k: sum(1 for r in v if not str(r.get(c) or "").strip()) / len(v)
                for k, v in 쓸묶음.items()}
        if not 빈률:
            continue
        제일빈 = max(빈률, key=lambda k: 빈률[k])
        제일찬 = min(잣대, key=lambda k: 빈률[k])   # 잣대는 큰 묶음에서만
        if 빈률[제일빈] < 비었다고본다:
            continue
        if 빈률[제일빈] - 빈률[제일찬] < 차이가난다:
            continue
        샘.append((c, 제일빈, 빈률[제일빈], 제일찬, 빈률[제일찬]))

    진짜 = [x for x in 샘 if x[0] not in 봐준다]
    봐준것 = [x for x in 샘 if x[0] in 봐준다]

    print()
    if 진짜:
        print("  ★ 한 묶음만 유독 비어 있는 칸 %d개" % len(진짜))
        for c, 빈묶, 빈률, 찬묶, 찬률 in sorted(진짜, key=lambda x: -x[2]):
            print("     · %-30s %s 에서 %.0f%% 빔   ← %s 는 %.0f%%"
                  % (c, 빈묶, 빈률 * 100, 찬묶, 찬률 * 100))
    else:
        print("  · 한 묶음만 유독 비어 있는 칸은 없습니다")

    if 봐준것 and 자세히:
        print()
        print("  (일부러 비워 두는 칸 %d개 — 봐줍니다)" % len(봐준것))
        for c, 빈묶, 빈률, _, _ in sorted(봐준것, key=lambda x: -x[2]):
            print("     · %-30s %s %.0f%% — %s" % (c, 빈묶, 빈률 * 100, 봐준다[c]))
    return [c for c, *_ in 진짜]


# ══════════════════════════════════════════════════════════
#  검사 ②  코드 — 조각을 만드는 두 도구가 같은 칸을 채우나
# ══════════════════════════════════════════════════════════

def _상수모으기(나무: ast.Module) -> dict[str, list[str]]:
    """모듈 맨 위의 「글자 튜플/리스트」 상수를 모은다.

    `for c in SOURCE_LEVEL: nr[c] = ...` 같은 꼴을 풀려면 이게 있어야 한다.
    """
    표: dict[str, list[str]] = {}
    for n in 나무.body:
        if not isinstance(n, ast.Assign) or len(n.targets) != 1:
            continue
        t = n.targets[0]
        if not isinstance(t, ast.Name):
            continue
        if isinstance(n.value, (ast.Tuple, ast.List)):
            값 = [e.value for e in n.value.elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if 값:
                표[t.id] = 값
    return 표


def _채우는칸(길: Path, 행변수: set[str]) -> set[str]:
    """`nr['x'] = ...` 처럼 새 행에 값을 넣는 칸 이름을 다 모은다.

    세 가지 꼴을 푼다.
      nr['topic'] = ...                        글자 그대로
      for c in ('a','b'): nr[c] = ...          자리에서 도는 튜플
      for c in SOURCE_LEVEL: nr[c] = ...       위에서 모은 상수
    """
    나무 = ast.parse(길.read_text(encoding="utf-8"), filename=str(길))
    상수 = _상수모으기(나무)
    칸: set[str] = set()

    # 어떤 for 문의 변수가 어느 목록을 도는지 먼저 적어 둔다
    도는변수: dict[str, list[str]] = {}
    for n in ast.walk(나무):
        if not isinstance(n, ast.For) or not isinstance(n.target, ast.Name):
            continue
        it = n.iter
        값: list[str] = []
        if isinstance(it, (ast.Tuple, ast.List)):
            값 = [e.value for e in it.elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        elif isinstance(it, ast.Name):
            값 = 상수.get(it.id, [])
        if 값:
            도는변수.setdefault(n.target.id, []).extend(값)

    for n in ast.walk(나무):
        표적 = []
        if isinstance(n, ast.Assign):
            표적 = n.targets
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            표적 = [n.target]
        for t in 표적:
            if not isinstance(t, ast.Subscript):
                continue
            if not (isinstance(t.value, ast.Name) and t.value.id in 행변수):
                continue
            s = t.slice
            if isinstance(s, ast.Constant) and isinstance(s.value, str):
                칸.add(s.value)
            elif isinstance(s, ast.Name):
                칸.update(도는변수.get(s.id, []))
    return 칸


def 코드로본다(빈칸: dict[str, dict[str, float]]) -> list[str]:
    도구 = [("build_bundle.py", "2·3차 분리", {"nr"}),
            ("apply_split.py", "4차 분리", {"nr"})]
    모음: dict[str, set[str]] = {}
    print()
    print("  ② 코드 — 조각을 만드는 도구가 각각 어느 칸을 채우나")
    for 이름, 뜻, 변수 in 도구:
        길 = 뿌리 / 이름
        if not 길.is_file():
            print("     ★ %s 가 없습니다" % 이름)
            return []
        모음[이름] = _채우는칸(길, 변수)
        print("     %-20s (%s)  %d칸" % (이름, 뜻, len(모음[이름])))

    a, b = 도구[0][0], 도구[1][0]
    한쪽만 = [c for c in sorted((모음[a] - 모음[b]) | (모음[b] - 모음[a]))
              if c not in 봐준다]

    # ★ 코드만 보면 시끄럽다 — 데이터로 되짚어 실제로 갈리는 것만 올린다
    진짜, 참고 = [], []
    for c in 한쪽만:
        률 = 빈칸.get(c) or {}
        갈림 = (max(률.values()) - min(률.values())) if 률 else 0.0
        (진짜 if 갈림 >= 차이가난다 else 참고).append((c, 갈림))

    print()
    if 진짜:
        print("  ★ 한쪽만 채우고, 데이터에서도 실제로 갈리는 칸 %d개" % len(진짜))
        for c, 갈림 in 진짜:
            누가 = a if c in 모음[a] else b
            안 = b if 누가 == a else a
            print("     · %-28s %s 는 채우고 %s 는 안 채운다 (빈칸률 %.0f%%p 차이)"
                  % (c, 누가, 안, 갈림 * 100))
    else:
        print("  · 한쪽만 채우면서 데이터까지 갈리는 칸은 없습니다")

    if 참고:
        print()
        print("  (참고 — 코드는 갈리는데 데이터는 같은 칸 %d개." % len(참고))
        print("   두 도구 다 「조각이 준 값은 그대로 받는」 갈래가 있어서 결과가 같습니다)")
        if 자세히:
            for c, 갈림 in 참고:
                누가 = a if c in 모음[a] else b
                print("     · %-28s %s 만 명시로 넣는다 (빈칸률 차이 %.0f%%p)"
                      % (c, 누가, 갈림 * 100))
    return [c for c, _ in 진짜]


# ══════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 66)
    print("  아무도 안 채우는 칸 검사")
    print("=" * 66)
    print()
    빈칸 = _빈칸률()
    새는데이터 = 데이터로본다()
    새는코드 = 코드로본다(빈칸)

    print()
    print("=" * 66)
    if 새는데이터 is None:
        # ★ 검사를 못 한 것을 통과로 끝내지 않는다 (2026-09-08)
        print("  ★ 데이터 검사를 못 했습니다 — 통과가 아닙니다")
        print()
        print("  이 파일이 있는 곳: %s" % 뿌리)
        print("  여기서 아래 둘 중 하나가 보여야 합니다")
        print("    · _판독패키지/_결과/master_final/raw_voc.csv   (판 안에서 돌릴 때)")
        print("    · _N판/_판독패키지/_결과/master_final/raw_voc.csv (뿌리에서 돌릴 때)")
        return 1
    if 새는데이터 or 새는코드:
        print("  ★ 새는 자리가 있습니다 — 데이터 %d칸 · 코드 %d칸"
              % (len(새는데이터), len(새는코드)))
        print()
        print("  다음에 할 일")
        print("    · 그 칸을 그 도구가 채워야 하는 칸인지 먼저 판단하십시오")
        print("    · 채워야 하면 도구를 고치고, 이미 만들어진 행은 따로 채웁니다")
        print("    · 안 채우는 게 맞으면 이 파일 위 「봐준다」 에 **이유와 함께** 적으십시오")
        print("      (이유 없이 목록에만 올리면 다음 결함이 여기 숨습니다)")
        return 1
    print("  · 새는 자리가 없습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
