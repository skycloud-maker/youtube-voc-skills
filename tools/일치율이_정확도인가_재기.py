# -*- coding: utf-8 -*-
"""일치율은 **정확도가 아니다** — 그것을 숫자로 보여 준다 (2026-11-03).

★ 왜 이 도구가 있나 — sky 물음 2026-11-03

  > 「브랜드가 마냥 그냥 다 기본적으로 LG … 특별한 언급이 없다면 다 그냥 LG로 넣는
  >  경우도 있었는데, 이런게 백프로 맞는건 아니다보니 … 저렇게 급격히 높아진 퍼센트가
  >  그런 오류가 섞인건 아닌가 … 분석정확도(저 퍼센트가 이 의미맞죠?)」

  **아니다.** 그 퍼센트는 「**옛 2판과 몇 % 같은가**」 다. 옛 2판은 맞다고 검증된
  정답지가 아니라 **비교 기준**일 뿐이다. 그러므로 일치율이 올라가는 데에는 두 가지
  서로 다른 까닭이 있고, 일치율만 보면 **둘을 가를 수 없다** —

      ① 분석이 정말 나아졌다
      ② 옛 2판이 쏠려 있고(예: brand 92.58% 가 「LG」), 그 쏠림을 더 잘 흉내 냈다

  sky 가 물은 것은 ② 다. ② 는 **잴 수 있다.** 그래서 이 도구가 있다.

무엇을 재나 — 셋 다 전량이다 (표본이 아니다)
----------------------------------------------
  ① **멍청규칙 대비** — 「그 칸에서 옛 2판의 **최빈값만 적는** 규칙」의 점수를 같이 찍는다.
     brand 는 「LG」 만 적어도 92.58% 를 받는다. 그보다 못한 일치율은 **잘한 것이 아니다.**
     (통계에서 majority-class baseline 이라 부르는 것이다 — 분석 없이 받는 공짜 점수.)

  ② **근거율** — 적어 놓은 브랜드 이름이 **원문에 실제로 있나.**
     기준서 `3_데이터사전_Enum.md` 는 `brand` 를 「**원문 표기 브랜드**」 로 정의하고,
     `1a_기준문서_정본_1부.md` R18 은 「**본문 우선 · 메타데이터는 보조** — 본문에 브랜드
     언급이 없으면 영상 제목·맥락만으로 확정하지 않는다」 고 못박는다.
     그리고 `reference_brand` 는 **LG 고정**이다 — 영상이 LG 것이라는 정보는 이미 그 칸에
     있으므로, `brand` 에까지 LG 를 채우는 것은 새 정보가 아니다.

  ③ **다5 위반** — `0_최신결정_먼저.md` [다5] 「brand 칸에 entity_role 값을 넣지 않는다」
     (sky 08-15 · 09-07). 옛 2판에는 이 위반이 남아 있다. 그 자리에서는 **옛 2판과
     어긋나는 것이 맞는 것**이다 — 일치율이 오히려 벌을 준다.

★ 한계를 숨기지 않는다
  근거율의 별명표(`별명`)는 **손으로 적은 것**이다. 표에 없는 브랜드는 글자가 그대로
  있어야만 「있음」 으로 센다. 그래서 「없음」 쪽이 조금 많게 나올 수 있다 —
  즉 근거율은 **최솟값**이다. brand 값은 거의 전부 LG 계열이라(별명표가 덮는다)
  이 한계가 결론을 뒤집지는 않지만, 수를 댈 때 이 말을 같이 해야 한다.

쓰기
    python tools/일치율이_정확도인가_재기.py <codex바탕 raw_voc.csv> <claude바탕 raw_voc.csv>
                                           [--옛 <옛 2판 raw_voc.csv>] [--보기]

    --옛    안 주면 `paths.py` 의 BASELINE 아래 옛 2판 최종을 쓴다
    --보기  근거 없는 행을 다섯 줄까지 원문과 함께 보여 준다
"""
from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

csv.field_size_limit(10 ** 9)

열쇠 = "atomic_id"
원문칸 = ("atomic_voc", "original_voc")
_옛최종 = Path("_판독패키지") / "_결과" / "master_final" / "raw_voc.csv"
_빌드마스터 = Path(__file__).resolve().parents[1] / "plugin" / "shared" / "tools" / "build_master.py"

# 「값이 없다」 는 뜻의 값들 — 구체 브랜드를 적은 것이 아니므로 근거율에서 뺀다.
# unknown · creator_channel 은 [다5] 가 금지한 값이라 아래 ③ 에서 따로 센다.
빈값 = {"", "N/A", "n/a", "NA", "na", "none", "None", "unknown", "creator_channel", "product_brand"}

# ★ 손으로 적은 별명표다 (위 「한계를 숨기지 않는다」 를 보라).
#   LG 쪽은 제품 브랜드까지 넣는다 — 원문이 「트롬 건조기」 라고만 해도 LG 를 말한 것이다.
별명 = {
    "LG": (r"LG|엘지|엘쥐|트롬|TROMM|디오스|DIOS|휘센|WHISEN|오브제|OBJET|코드제로|CORDZERO"
           r"|스타일러|STYLER|퓨리케어|PURICARE|시그니처|SIGNATURE|워시타워|WASHTOWER"
           r"|틔운|TIIUN|씽큐|THINQ|프라엘|PRAEL|그램|GRAM"),
    "삼성": r"삼성|Samsung", "삼성전자": r"삼성|Samsung", "Samsung": r"삼성|Samsung",
    "로보락": r"로보락|Roborock", "Roborock": r"로보락|Roborock",
    "드리미": r"드리미|Dreame", "Dreame": r"드리미|Dreame",
    "샤오미": r"샤오미|Xiaomi", "Xiaomi": r"샤오미|Xiaomi",
    "다이슨": r"다이슨|Dyson", "Dyson": r"다이슨|Dyson",
    "BYD": r"BYD|비야디", "기아": r"기아|KIA", "현대": r"현대|Hyundai",
}


def 판정24칸() -> list[str]:
    """`build_master.py` 의 CC_FIELDS 를 긁는다 — 손으로 적으면 두 벌이 된다 (공통 규칙 6)."""
    글 = _빌드마스터.read_text(encoding="utf-8")
    i = 글.find("CC_FIELDS = [")
    if i < 0:
        raise SystemExit("못 찾음: build_master.py 의 CC_FIELDS — 손으로 적지 않는다")
    칸 = [x.strip().strip("'\"") for x in
          글[i + len("CC_FIELDS = ["):글.find("]", i)].replace("\n", " ").split(",")]
    칸 = [x for x in 칸 if x]
    if len(칸) != 24:
        raise SystemExit("CC_FIELDS 가 24칸이 아니다 — %d칸을 긁었다" % len(칸))
    return 칸


def 읽기(쪽: Path, 무엇: str) -> dict[str, dict]:
    if not 쪽.is_file():
        raise SystemExit("못 찾음: %s — %s" % (쪽, 무엇))
    with 쪽.open(encoding="utf-8-sig", newline="") as f:
        행들 = list(csv.DictReader(f))
    if not 행들:
        raise SystemExit("빈 파일이다: %s (%s)" % (쪽, 무엇))
    if 열쇠 not in 행들[0]:
        raise SystemExit("열쇠 `%s` 가 없다: %s (%s)" % (열쇠, 쪽, 무엇))
    return {r[열쇠]: r for r in 행들 if r.get(열쇠)}


def 근거있나(값: str, 글: str) -> bool:
    """적어 놓은 브랜드가 원문에 있나. 쉼표로 여러 개면 **하나라도 없으면 없음**이다."""
    조각 = [x.strip() for x in 값.split(",") if x.strip()]
    for c in 조각:
        if not re.search(별명.get(c, re.escape(c)), 글, re.I):
            return False
    return bool(조각)


def main() -> int:
    준것 = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--옛" in sys.argv:
        i = sys.argv.index("--옛") + 1
        옛쪽 = Path(sys.argv[i])
        준것 = [a for a in 준것 if a != sys.argv[i]]
    else:
        옛쪽 = BASELINE / "원본사본" / "2판" / _옛최종
    if len(준것) != 2:
        raise SystemExit("두 결과를 주십시오 — <codex바탕 raw_voc.csv> <claude바탕 raw_voc.csv>")
    보기낼까 = "--보기" in sys.argv

    옛 = 읽기(옛쪽, "옛 2판 최종 (비교 기준 — 정답지가 아니다)")
    코 = 읽기(Path(준것[0]), "바탕 = codex (지금 기본)")
    클 = 읽기(Path(준것[1]), "바탕 = claude")
    공통 = sorted(set(옛) & set(코) & set(클))
    N = len(공통)

    print("=" * 78)
    print("  일치율은 정확도가 아니다 — 쏠림 · 근거 · 기준서 위반으로 다시 본다")
    print("=" * 78)
    print("  옛 2판 %d행 · codex바탕 %d행 · claude바탕 %d행 · **셋 다 있는 %d행**"
          % (len(옛), len(코), len(클), N))
    if not N:
        print("  ★ 셋 다 있는 행이 **0개**다 — 맞출 자리가 없으면 통과가 아니다")
        return 1
    없는원문 = [c for c in 원문칸 if c not in 옛[공통[0]]]
    if 없는원문:
        print("  ★ 옛 2판에 **원문 칸이 없다** — %s" % " · ".join(없는원문))
        print("    원문을 못 보면 근거율을 **잴 수 없다.** 0%% 라고 답하면 거짓이다.")
        return 1
    칸들 = 판정24칸()
    없는칸 = [c for c in 칸들 if c not in 옛[공통[0]] or c not in 코[공통[0]] or c not in 클[공통[0]]]
    if 없는칸:
        print("  ★ 판정 24칸 가운데 **데이터에 없는 칸**이 있다 — 조용히 버리지 않는다:")
        for c in 없는칸:
            print("     · %s" % c)
        return 1

    # ── ① 멍청규칙(최빈값) 대비 ─────────────────────────────────────────
    print()
    print("  ① **멍청규칙 대비** — 「옛 2판의 최빈값만 적는 규칙」의 점수와 댄다")
    머리 = "  %-22s %9s %8s %8s %11s" % ("칸", "멍청규칙", "codex", "claude", "claude-멍청")
    print(머리)
    print("  " + "-" * (len(머리) - 2))
    못넘음 = []
    for c in 칸들:
        최값, 최수 = collections.Counter((옛[k].get(c) or "").strip() for k in 공통).most_common(1)[0]
        최율 = 100 * 최수 / N
        a = 100 * sum(1 for k in 공통
                      if (코[k].get(c) or "").strip() == (옛[k].get(c) or "").strip()) / N
        b = 100 * sum(1 for k in 공통
                      if (클[k].get(c) or "").strip() == (옛[k].get(c) or "").strip()) / N
        넘 = b - 최율
        꼬리 = "%+10.2f%%" % 넘
        if 넘 <= 0:
            못넘음.append((c, 최율, b, 넘, 최값))
            꼬리 += " ✗"
        print("  %-22s %8.2f%% %7.2f%% %7.2f%% %s" % (c, 최율, a, b, 꼬리))
    print("  " + "-" * (len(머리) - 2))
    if 못넘음:
        print("  ★ **claude 가 멍청규칙을 못 넘긴 칸 %d개 / 24개** — 이 칸의 일치율은" % len(못넘음))
        print("    「좋아졌다」 는 증거로 **쓸 수 없다**:")
        for c, 최율, b, 넘, v in sorted(못넘음, key=lambda x: x[3]):
            print("     · %-22s 멍청규칙 %6.2f%%  claude %6.2f%%  (%+.2f%%)  최빈값=「%s」"
                  % (c, 최율, b, 넘, (v[:28] if v else "(빈칸)")))
    else:
        print("  ★ 24칸 모두 멍청규칙을 넘었다")

    # ── ② 근거율 ────────────────────────────────────────────────────────
    print()
    print("  ② **근거율** — 적어 놓은 브랜드가 **원문에 실제로 있나** (`brand` 는 「원문 표기 브랜드」)")
    머리2 = "  %-9s %12s %14s %14s %10s" % ("", "구체브랜드", "원문에있음", "원문에없음", "N/A등")
    print(머리2)
    print("  " + "-" * (len(머리2) - 2))
    보기: dict[str, list] = {}
    근거 = {}
    for 이름, 표 in (("옛2판", 옛), ("codex", 코), ("claude", 클)):
        적음 = 있음 = 빈 = 0
        for k in 공통:
            v = (표[k].get("brand") or "").strip()
            if v in 빈값:
                빈 += 1
                continue
            적음 += 1
            글 = " ".join((옛[k].get(x) or "") for x in 원문칸)
            if 근거있나(v, 글):
                있음 += 1
            elif len(보기.setdefault(이름, [])) < 5:
                보기[이름].append((k, v, re.sub(r"\s+", " ", (옛[k].get("atomic_voc") or ""))[:52]))
        근거[이름] = (적음, 있음, 적음 - 있음, 빈)
        print("  %-9s %12d %7d(%5.1f%%) %7d(%5.1f%%) %10d"
              % (이름, 적음, 있음, 100 * 있음 / max(적음, 1),
                 적음 - 있음, 100 * (적음 - 있음) / max(적음, 1), 빈))
    print("  " + "-" * (len(머리2) - 2))
    for 이름 in ("옛2판", "claude"):
        적음, 있음, 없음, _ = 근거[이름]
        if 적음 and 100 * 없음 / 적음 > 50:
            print("  ★ **%s 는 적어 놓은 브랜드의 %.1f%% 가 원문에 없다** — 「원문 표기 브랜드」 가"
                  % (이름, 100 * 없음 / 적음))
            print("    아니라 **기본값**이다. 이 칸의 일치율이 높은 것은 분석이 맞다는 뜻이 아니다.")
    print("  ※ 별명표는 손으로 적은 것이므로 「없음」 이 조금 많게 나올 수 있다 — 근거율은 **최솟값**이다.")

    # ── ③ 다5 위반 ──────────────────────────────────────────────────────
    print()
    print("  ③ **[다5] 위반** — brand 칸에 entity_role 값 (unknown · creator_channel · product_brand)")
    금지 = ("unknown", "creator_channel", "product_brand")
    옛위반 = 0
    for 이름, 표 in (("옛2판", 옛), ("codex", 코), ("claude", 클)):
        c = collections.Counter((표[k].get("brand") or "").strip() for k in 공통)
        낱 = {x: c.get(x, 0) for x in 금지}
        if 이름 == "옛2판":
            옛위반 = sum(낱.values())
        print("  %-9s unknown %4d · creator_channel %4d · product_brand %4d  → **위반 %d행**"
              % (이름, 낱["unknown"], 낱["creator_channel"], 낱["product_brand"], sum(낱.values())))
    if 옛위반:
        print("  ★ 옛 2판에 위반이 **%d행** 있다 — 그 자리에서는 **옛 2판과 어긋나는 것이 맞는 것**이다."
              % 옛위반)
        print("    일치율은 거기서 오히려 **벌을 준다.** 이것도 일치율이 정확도가 아닌 까닭이다.")

    if 보기낼까:
        print()
        print("  근거 없는 행 보기 (쪽마다 다섯 줄까지)")
        for 이름 in ("옛2판", "codex", "claude"):
            for k, v, t in 보기.get(이름, []):
                print("     [%s] %s  brand=%s" % (이름, k, v))
                print("          원문「%s…」" % t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
