# -*- coding: utf-8 -*-
"""바탕 번들을 바꾸면 **무엇을 얻고 무엇을 버리나** — 칸마다 세어 댄다 (2026-11-02).

★ 왜 이 도구가 있나 — sky 물음 2026-11-02

  > 「바탕 claude로 돌려보고 버려지는 수까지 재서 보고해주세요」

  앞서 내가 「바탕을 claude 로 바꾸면 `brand` 46.6 → 92.4%」 라고 말했는데
  그것은 **미리 계산한 값**이었다. 그리고 「버려지는 것」 을 나는
  「codex 가 이긴 251건」 이라고 말했는데, 그 251건은 **감독 판정이 이기므로
  바탕과 무관하게 살아남는다.** 즉 내가 댄 수가 **틀린 수**였다.

  정말 버려지는 것은 **감독이 판정하지 않아 바탕이 값을 정하는 자리**에서
  codex 가 옛 2판과 맞고 claude 가 안 맞는 칸이다. 그 수를 **센다.**

어떻게 세나 — 추론하지 않고 **실제로 낸 두 결과를 댄다**
---------------------------------------------------------
  같은 입력(판독자 번들 둘 · 감독결과)에 바탕만 바꿔 `build_master` 를 두 번 돌리면,
  두 결과에서 **값이 다른 칸이 곧 「바탕이 정한 자리」** 다. 감독 판정이 이긴 칸과
  판독자 둘이 같았던 칸은 두 결과에서 **똑같이 나온다.**

  그 다른 칸들을 옛 2판과 대면 네 가지로 갈린다 —

      얻음    claude 쪽이 옛 2판과 맞고 codex 쪽은 아니다
      버림    codex 쪽이 옛 2판과 맞고 claude 쪽은 아니다   ← ★ sky 가 물은 수
      둘다틀림  어느 쪽도 옛 2판과 안 맞는다
      둘다맞음  (있을 수 없다 — 값이 다른데 둘 다 맞을 수는 없다. 나오면 **크게 실패**한다)

★ 「못 찾음」 을 「없음」 으로 돌려주지 않는다
  바탕을 바꿨는데 **다른 칸이 0개**면 그것은 「차이가 없다」 가 아니라
  **「인자가 안 닿았다」** 는 뜻이다 (`--바탕` 이 스킬 경로에서 버려지던 고장이 실제로
  있었다 — 2026-11-02). 그때는 종료코드 1 로 멈춘다.

쓰기
    python tools/바탕바꾼효과_재기.py <codex바탕 raw_voc.csv> <claude바탕 raw_voc.csv>
                                     [--옛 <옛 2판 raw_voc.csv>] [--자세히]

    --옛      안 주면 `paths.py` 의 BASELINE 아래 옛 2판 최종을 쓴다
    --자세히   칸마다 보기를 세 줄까지 보여 준다
    --일치율   칸마다 **옛 2판과 몇 % 같은가**를 양쪽 다 찍는다 (같은 행에서)

★ `--일치율` 이 왜 도구 안에 있나 — 이 숫자를 처음엔 **임시 스크립트**로 냈다.
  임시 스크립트는 사라지고, 그러면 문서의 숫자를 **다시 낼 수 없다.**
  증거는 다시 낼 수 있어야 증거다. 그래서 도구 안으로 넣었다 (2026-11-02).
"""
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

열쇠 = "atomic_id"
_옛최종 = Path("_판독패키지") / "_결과" / "master_final" / "raw_voc.csv"

# 판정 24칸 — `build_master.py` 의 CC_FIELDS 와 **같아야 한다.** 손으로 적지 않고 긁어 온다.
_빌드마스터 = Path(__file__).resolve().parents[1] / "plugin" / "shared" / "tools" / "build_master.py"


def 판정24칸() -> list[str]:
    """`build_master.py` 에서 CC_FIELDS 를 긁는다 — 두 벌이 되지 않게 (공통 규칙 6)."""
    글 = _빌드마스터.read_text(encoding="utf-8")
    i = 글.find("CC_FIELDS = [")
    if i < 0:
        raise SystemExit("못 찾음: build_master.py 의 CC_FIELDS — 손으로 적지 않는다")
    j = 글.find("]", i)
    칸 = [x.strip().strip("'\"") for x in 글[i + len("CC_FIELDS = ["):j].replace("\n", " ").split(",")]
    칸 = [x for x in 칸 if x]
    if len(칸) != 24:
        raise SystemExit("CC_FIELDS 가 24칸이 아니다 — %d칸을 긁었다. 도구가 바뀐 것인지 보십시오" % len(칸))
    return 칸


def 읽기(쪽: Path, 무엇: str) -> dict[str, dict]:
    if not 쪽.is_file():
        raise SystemExit("못 찾음: %s — %s" % (쪽, 무엇))
    with 쪽.open(encoding="utf-8-sig", newline="") as f:
        행들 = list(csv.DictReader(f))
    if not 행들:
        raise SystemExit("빈 파일이다: %s (%s)" % (쪽, 무엇))
    if 열쇠 not in 행들[0]:
        raise SystemExit("열쇠 `%s` 가 없다: %s (%s) — 맞출 수 없으면 0%% 라고 답하면 거짓이다"
                         % (열쇠, 쪽, 무엇))
    return {r[열쇠]: r for r in 행들 if r.get(열쇠)}


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
    자세히 = "--자세히" in sys.argv

    옛 = 읽기(옛쪽, "옛 2판 최종 (정답지 쪽)")
    코 = 읽기(Path(준것[0]), "바탕 = codex (지금 기본)")
    클 = 읽기(Path(준것[1]), "바탕 = claude")

    칸들 = 판정24칸()
    공통행 = sorted(set(옛) & set(코) & set(클))

    print("=" * 76)
    print("  바탕을 바꾸면 무엇을 얻고 무엇을 버리나 — 판정 24칸")
    print("=" * 76)
    print("  옛 2판      %s" % 옛쪽)
    print("  바탕=codex  %s" % 준것[0])
    print("  바탕=claude %s" % 준것[1])
    print()
    print("  행 — 옛 %d · codex바탕 %d · claude바탕 %d · **셋 다 있는 행 %d**"
          % (len(옛), len(코), len(클), len(공통행)))
    if not 공통행:
        print("  ★ 셋 다 있는 행이 **0개**다 — 맞출 자리가 없으면 통과가 아니다")
        return 1
    없는칸 = [c for c in 칸들 if c not in 코[공통행[0]] or c not in 클[공통행[0]] or c not in 옛[공통행[0]]]
    if 없는칸:
        print("  ★ 판정 24칸 가운데 **데이터에 없는 칸**이 있다 — 조용히 버리지 않는다:")
        for c in 없는칸:
            print("     · %s" % c)
        return 1
    print()

    머리 = "  %-24s %7s %7s %7s %7s %7s" % ("칸", "바탕정함", "얻음", "버림", "둘다틀림", "순이득")
    print(머리)
    print("  " + "-" * (len(머리) - 2))
    합 = collections.Counter()
    보기: dict[str, list] = {}
    for c in 칸들:
        정함 = 얻음 = 버림 = 둘다 = 0
        for aid in 공통행:
            vk, vc, vo = (코[aid].get(c) or "").strip(), (클[aid].get(c) or "").strip(), (옛[aid].get(c) or "").strip()
            if vk == vc:
                continue                      # 바탕이 안 정한 칸 (감독이 이겼거나 둘이 같았다)
            정함 += 1
            if vc == vo and vk != vo:
                얻음 += 1
            elif vk == vo and vc != vo:
                버림 += 1
                보기.setdefault(c, []).append((aid, vo, vk, vc))
            elif vk != vo and vc != vo:
                둘다 += 1
            else:
                print("  ★ 있을 수 없는 일 — 값이 다른데 둘 다 옛것과 같다: %s %s" % (c, aid))
                return 1
        합["정함"] += 정함; 합["얻음"] += 얻음; 합["버림"] += 버림; 합["둘다"] += 둘다
        print("  %-24s %7d %7d %7d %7d %+7d" % (c, 정함, 얻음, 버림, 둘다, 얻음 - 버림))

    print("  " + "-" * (len(머리) - 2))
    print("  %-24s %7d %7d %7d %7d %+7d"
          % ("합", 합["정함"], 합["얻음"], 합["버림"], 합["둘다"], 합["얻음"] - 합["버림"]))
    print()

    # ★ 「못 찾음」 을 「없음」 으로 돌려주지 않는다
    if 합["정함"] == 0:
        print("  ★ 바탕을 바꿨는데 **다른 칸이 0개**입니다 — 「차이가 없다」 가 아니라")
        print("    **「인자가 안 닿았다」** 는 뜻입니다. `--바탕` 이 build_master 까지")
        print("    갔는지(화면에 「바탕 번들 = …」 줄이 찍혔는지) 보십시오.")
        return 1

    print("  ★ **버림 %d칸** — 감독이 판정하지 않아 바탕이 값을 정한 자리에서," % 합["버림"])
    print("    codex 가 옛 2판과 맞고 claude 가 안 맞은 칸입니다. 이것이 버려지는 수입니다.")
    print("  ★ **얻음 %d칸** · 순이득 **%+d칸**" % (합["얻음"], 합["얻음"] - 합["버림"]))

    if "--일치율" in sys.argv:
        print()
        print("  칸마다 — 옛 2판과 몇 %% 같은가 (같은 %d행에서)" % len(공통행))
        머리2 = "  %-24s %9s %9s %9s" % ("칸", "바탕codex", "바탕claude", "차이")
        print(머리2)
        print("  " + "-" * (len(머리2) - 2))
        내림 = []
        for c in 칸들:
            a = sum(1 for k in 공통행
                    if (코[k].get(c) or "").strip() == (옛[k].get(c) or "").strip())
            b = sum(1 for k in 공통행
                    if (클[k].get(c) or "").strip() == (옛[k].get(c) or "").strip())
            차 = 100 * (b - a) / len(공통행)
            print("  %-24s %8.2f%% %8.2f%% %+8.2f%%"
                  % (c, 100 * a / len(공통행), 100 * b / len(공통행), 차))
            if 차 < 0:
                내림.append((c, 차))
        print("  " + "-" * (len(머리2) - 2))
        # ★ 내려간 칸을 **따로 다시 적는다** — 표 속에 섞어 두면 좋은 쪽만 읽힌다
        if 내림:
            print("  ★ **내려간 칸이 %d개다** (숨기지 않는다) — %s"
                  % (len(내림), " · ".join("%s %+.2f%%" % x for x in sorted(내림, key=lambda y: y[1]))))
        else:
            print("  ★ 내려간 칸이 없다")

    if 자세히 and 보기:
        print()
        print("  버림 보기 (칸마다 세 줄까지) — [옛 2판] / [codex바탕] / [claude바탕]")
        for c in 칸들:
            for aid, vo, vk, vc in 보기.get(c, [])[:3]:
                print("     %s %s" % (c, aid))
                print("        옛 %s" % vo[:70])
                print("        코 %s" % vk[:70])
                print("        클 %s" % vc[:70])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
