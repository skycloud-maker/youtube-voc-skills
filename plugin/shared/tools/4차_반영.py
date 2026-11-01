# -*- coding: utf-8 -*-
"""4차 실무자 결정을 데이터에 반영하고 최종 번들까지 만든다 — 총괄 자리.

★ sky 2026-08-25
  「그냥 그때그때 요청사항만 받기보단 그래도 어떤 식으로 움직인다는
    흐름을 만들어놓는 게 좋긴해보입니다」

  ★ 맞습니다. 오늘 제가 순서를 기억해서 손으로 돌렸는데,
    `PL이슈_뽑기` 하나가 빠져 있는 것을 나중에야 찾았습니다.
    **순서를 사람이 기억하면 반드시 하나가 빠집니다.**

★ 이 도구가 하지 **않는** 것 — 판정을 대신 정하지 않습니다.
  실무자가 정한 것을 데이터에 옮기고, 그 뒤 딸려 오는 일을 빠짐없이 돌립니다.

쓰기
    python 4차_반영.py                  ① ~ ⑦ 을 차례로
    python 4차_반영.py --확인만          무엇을 할지 보여만 준다
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기
번들 = ROOT / "_판독패키지" / "_결과" / "master_final"


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def _달리기(도구: str, *인자: str) -> tuple[int, str]:
    길 = _여기 / 도구
    if not 길.exists():
        return 1, "%s 가 없습니다" % 도구
    r = subprocess.run([sys.executable, str(길), *인자],
                       cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ── 사람이 해야 하는 것 — 이 도구가 대신 못 한다 ────────────────────
# ★ 실무자가 하는 것 — 파일에 의견을 적어 총괄에게 주는 것까지 (sky 2026-08-25)
#   「실무자의 역할은 … 합의 내용을 파일에 정리하여 총괄 AI에게 전달하는 것을 하고,
#     그 이후에는 총괄의 작업을 확인하고 작업 승인의 영역」
실무자몫 = [
    ("★사람이볼목록 시트", "행마다 의견 + 전체 규칙 의견"),
    ("★보정요청 시트", "건마다 의견 + 전체 규칙 의견"),
    ("분리제안 시트", "잘못 쪼갠 게 있나 · 나눠야 할 게 있나"),
]

# ★ 총괄이 하는 것 — 받은 파일을 읽고 **할 일을 먼저 뽑아** 하나씩 맞춘다
총괄몫 = [
    ("① 할 일 목록 뽑기",
     "받은 파일을 읽어 무엇을 고쳐야 하는지 먼저 정리한다.\n"
     "       ★ 바로 고치지 않는다. 목록을 사람과 맞춘 뒤에 손댄다"),
    ("② 기준서에 적기",
     "_판독패키지/9_택소노미_2차확장.md 에 규칙을 문장으로.\n"
     "       ★ 적히지 않은 라벨은 다음 판독자가 또 다르게 씁니다"),
    ("③ 데이터에 옮기기",
     "topic·status 를 고치고 수정로그를 남긴다.\n"
     "       ★ 기계로 밀지 않는다 — 정규식은 문맥을 안 본다.\n"
     "         4차에서 72행 후보 중 45행이 오탐이었다"),
    ("④ 보정요청 처리상태",
     "반영 / 해소 / 이월 중 하나를 적고 해소경위를 쓴다"),
]

# ── 이 도구가 돌리는 것 ─────────────────────────────────────────────
차례 = [
    # ★ 2026-08-26 — 분리제안 승인분을 **실제로 반영**한다.
    #   254건을 확정해 놓고 데이터에는 안 들어가고 있었다.
    #   행이 늘고 줄므로 xlsx 를 만들기 **전에** 해야 한다.
    ("⓪ 분리제안 반영", "apply_split.py", "승인된 분리·병합을 데이터에"),
    # ★★ 2026-11-01 — **조용히 버려지던 자리.** 2판을 통째로 다시 돌려 보고 찾았다.
    #   `apply_split.py` 는 `s15_master/raw_voc.csv` 를 읽고 **거기에 쓴다**(238줄).
    #   그런데 번들은 `master_final/raw_voc.csv` 로 만든다
    #   (`build_bundle.build_xlsx` 531줄이 `outdir/raw_voc.csv` 를 읽는다).
    #   그래서 **사람이 승인한 분리가 번들에 닿지 않았다.** 실측 —
    #       s15_master    6,530행 · 쪼개진 조각 316
    #       master_final  6,393행 · 쪼개진 조각 105   ← 번들이 이것을 담았다
    #   행 **137개** · 조각 **211개**가 **오류 하나 없이** 버려졌다 (종료 0 · 「끝났습니다」).
    #   옛 2판이 6,846행인 까닭의 상당 부분이 이 분리다.
    ("⓪-1 분리를 번들 자리로", None, "s15_master 의 분리 결과를 master_final 로"),
    # ★★ 2026-08-26 — topic_group 은 topic 에서 나오는 **파생 칸**인데,
    #   topic 을 바꾼 주체가 같이 안 고쳐 1,534행이 어긋나 있었다.
    #     reader_agree 0% · 3차 감독 27% · 총괄 55% · sky 100%(전부 빈칸)
    #   대시보드 필터가 이 칸을 쓴다(28번 D-1). 어긋난 만큼 집계가 틀린다.
    #   ★ xlsx 를 만들기 **전에** 해야 한다 — ① 이 raw_voc 을 그대로 담는다
    ("⓪-2 묶음 맞추기", "그룹_맞추기.py",
     "topic_group 을 topic 에서 다시 계산 (정본 매핑대로)"),
    ("① 최종 xlsx 다시 만들기", None, "raw_voc.csv 로 6시트를 새로"),
    ("② 개선 우선순위", "rank_two_axis.py", "건수 / 부정 강도 두 축"),
    # ★ 편향검사는 여기서 **다시 돌리지 않는다** (2026-08-25).
    #   편향은 「3차 감독이 자기 편을 들었나」 를 재는 것이다.
    #   감독 판정도 정답지도 4차에서 안 바뀌므로 결과가 같다.
    #   다시 재면 「잰_날짜」 만 바뀌어 **4차 데이터를 잰 것처럼 보인다.**
    #   3차 것을 그대로 쓴다.
    ("③ PL Issue 뽑기", "PL이슈_뽑기.py", "안전·위생 전량 (라벨이 바뀌었다)"),
    # ★★ 2026-08-26 — 시트를 붙이기 **전에** 총괄 판정을 목록에 옮긴다.
    #   sky 「아까 총괄이랑 다 정리했던 것 같은데.. 갑자기 이렇게 나온다고요?」
    #   426행 전부 총괄이 정해 raw_voc 에 근거까지 들어가 있었는데,
    #   사람이볼목록의 총괄_의견은 0/426 빈칸이었다.
    #   실무자에게는 「총괄이 아무것도 안 정했다」 로 보인다 —
    #   「실무자 개입을 최소화한다」 와 정반대다.
    ("③-2 총괄 판정 옮기기", "사람이볼목록_채우기.py",
     "raw_voc 의 decided_by·decided_note 를 사람이볼목록으로"),
    ("④ 시트 붙이기", "시트_붙이기.py", "★사람이볼목록·★보정요청·★PL·편향검사"),
    # ★ 2026-08-26 — 시트를 다 붙인 뒤 차례를 만든다.
    #   먼저 만들면 나중에 붙는 시트가 차례에서 빠진다.
    ("④-2 차례 만들기", "차례_만들기.py", "0_차례 + 시트 순서"),
    ("⑤ 번들 꾸미기", "번들_마무리꾸미기.py", "차례 · 색칠 · 데이터 안내"),
    ("⑥ 이력 맞추기", None, "정본 · 박힌 말 · 5차 기준 · 꾸러미"),
]


def _xlsx_다시() -> tuple[int, str]:
    """build_bundle 의 xlsx 만들기를 부른다 (1차 엔진의 export_bundle 사용)."""
    사이 = _여기 / "_4차_xlsx.py"
    사이.write_text(
        "import os, sys\n"
        "sys.path.insert(0, r'%s')\n"
        "os.chdir(r'%s')\n"
        "import build_bundle as B\n"
        "B.build_xlsx(r'%s', 'robot')\n"
        "print('xlsx 다시 만들었습니다')\n"
        % (str(_여기), str(ROOT), str(번들)),
        encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, str(사이)],
                           cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    finally:
        try:
            사이.unlink()
        except OSError:
            pass


def _분리_옮기기() -> tuple[int, str]:
    """`apply_split` 이 쓴 `s15_master/raw_voc.csv` 를 **번들이 읽는 자리**로 옮긴다.

    ★ 왜 — 위 ⓪-1 주석에 적었다. 분리가 번들에 닿지 않아 행 137개가 조용히 버려졌다.

    ★ **못 옮기면 크게 실패한다.** 「없음」 과 「못 찾음」 을 가른다 —
      · 분리가 하나도 없었으면(행 수가 같으면) 옮길 것이 없다 → 그대로 넘어간다
      · 분리가 있었는데 옮긴 뒤에도 행 수가 안 늘었으면 **멈춘다**
    """
    import csv as _csv
    import shutil as _shutil

    s15 = ROOT / "s15_master" / "raw_voc.csv"
    끝 = 번들 / "raw_voc.csv"
    if not s15.is_file():
        return 1, ("     ✗ s15_master/raw_voc.csv 가 없습니다 — %s\n"
                   "       (못 찾음은 통과가 아닙니다. apply_split 이 쓰는 자리입니다)" % s15)
    if not 끝.is_file():
        return 1, "     ✗ %s 가 없습니다" % 끝

    def 세기(p):
        with io.open(p, encoding="utf-8-sig", newline="") as h:
            줄들 = list(_csv.DictReader(h))
        조각 = sum(1 for r in 줄들 if (r.get("split_origin_atomic_id") or "").strip())
        칸 = set(줄들[0].keys()) if 줄들 else set()
        return len(줄들), 조각, 칸

    s행, s조각, s칸 = 세기(s15)
    m행, m조각, m칸 = 세기(끝)
    말 = ["     s15_master  %5d행 · 쪼개진 조각 %4d" % (s행, s조각),
         "     번들 자리    %5d행 · 쪼개진 조각 %4d" % (m행, m조각)]

    if s칸 != m칸:
        말.append("     ✗ 두 파일의 **칸이 다릅니다** — 옮기면 번들이 깨집니다")
        말.append("       s15 에만: %s" % (" · ".join(sorted(s칸 - m칸)) or "(없음)"))
        말.append("       번들에만: %s" % (" · ".join(sorted(m칸 - s칸)) or "(없음)"))
        return 1, "\n".join(말)

    if s행 == m행 and s조각 == m조각:
        말.append("     · 옮길 것이 없습니다 (분리가 더 생기지 않았습니다)")
        return 0, "\n".join(말)

    if s행 < m행:
        말.append("     ✗ s15 쪽이 **더 적습니다** — 덮으면 행을 잃습니다. 멈춥니다")
        return 1, "\n".join(말)

    _shutil.copy2(s15, 끝)
    뒤행, 뒤조각, _ = 세기(끝)
    말.append("     · 옮겼습니다 — 번들 자리 %d행 · 조각 %d" % (뒤행, 뒤조각))
    if 뒤행 != s행 or 뒤조각 != s조각:
        말.append("     ✗ 옮긴 뒤에도 수가 안 맞습니다 (%d/%d → %d/%d) — 멈춥니다"
                  % (s행, s조각, 뒤행, 뒤조각))
        return 1, "\n".join(말)
    말.append("     ★ 행 %+d · 조각 %+d — 분리가 번들에 **닿았습니다**"
              % (뒤행 - m행, 뒤조각 - m조각))
    return 0, "\n".join(말)


def _이력() -> tuple[int, str]:
    # ★ 새 저장소에서는 이 단계를 저장소가 맡는다 (sky 2026-09-21 「새 방식으로 대신한다」).
    #   옛 관리 도구 4개(정본_맞추기 · 박힌말_검사 · 5차기준_검사 · make_zip)는 옛 저장소 구조를 전제로 해서
    #   여기 없다. 부르면 늘 「못 찾았습니다」 로 막혀, 반영을 다 해 놓고도 「막혔습니다」 로 끝났다.
    #   원문은 저장소 docs/sources/옛관리도구/ 에 기록으로 있다.
    return 0, ("     이력 맞추기는 새 저장소가 맡습니다 — 쌍둥이 문서는 저장소 시험(test_shared),\n"
               "     꾸러미는 스킬의 폴더 차리기, 커밋·진행 기록은 저장소 절차가 합니다.")
    말 = []
    나쁨 = 0
    for 도구 in ("정본_맞추기.py", "박힌말_검사.py", "5차기준_검사.py",
                "make_zip.py"):
        코드, 글 = _달리기(도구)
        끝 = [x for x in 글.splitlines() if x.strip()][-3:]
        말.append("     %s" % 도구)
        말 += ["       %s" % x.strip() for x in 끝]
        나쁨 += (코드 != 0)
    return (1 if 나쁨 else 0), "\n".join(말)


def main() -> int:
    print("=" * 70)
    print("  4차 반영 — 실무자가 정한 것을 데이터에 옮기고 번들까지")
    print("=" * 70)
    print()

    print("  ── 실무자가 하는 것 (여기까지) ──")
    for 이름, 설명 in 실무자몫:
        print("     · %-18s %s" % (이름, 설명))
    print("     ★ 파일에 의견을 적어 총괄에게 주는 것까지입니다.")
    print("       파일을 직접 고치실 필요 없습니다.")
    print()
    print("  ── 총괄이 하는 것 (이 도구를 돌리기 전에) ──")
    for 이름, 설명 in 총괄몫:
        print("     %s" % 이름)
        print("       %s" % 설명)
    print()
    print("  ★ 이 도구는 판정을 대신 정하지 않습니다.")
    print("    위 ①~④ 가 끝난 뒤, 딸려 오는 일을 빠짐없이 돌립니다.")
    print()
    print("  ★ 편향검사는 다시 돌리지 않습니다 — 3차에서 잰 것이 맞습니다.")
    print("    감독 판정과 정답지는 4차에서 바뀌지 않습니다.")
    print()

    if "--확인만" in sys.argv:
        print("  ── 돌릴 차례 ──")
        for 이름, 도구, 설명 in 차례:
            print("     %-22s %-22s %s" % (이름, 도구 or "(안에서)", 설명))
        return 0

    # ★ 3차에서 잰 편향 결과가 있나 — 다시 재지 않고 그대로 쓴다
    편향 = 번들 / "편향검사.csv"
    if 편향.exists():
        try:
            첫줄 = io.open(편향, encoding="utf-8-sig").readline().strip()
            줄("·", "편향검사는 3차 것을 그대로 씁니다 (%s)" % 첫줄)
        except OSError:
            pass
    else:
        줄("!", "편향검사.csv 가 없습니다 — 3차_마무리를 먼저 돌리십시오")
        줄("", "   (없어도 나머지는 돕니다. 시트 하나가 빕니다)")
    print()

    if not (번들 / "raw_voc.csv").exists():
        줄("✗", "raw_voc.csv 를 못 찾았습니다 — %s" % 번들)
        return 1

    print("=" * 70)
    막힘 = []
    for 이름, 도구, 설명 in 차례:
        print()
        print("  %s — %s" % (이름, 설명))
        if 도구 is None:
            if 이름.startswith("⓪-1"):
                코드, 글 = _분리_옮기기()
            elif 이름.startswith("①"):
                코드, 글 = _xlsx_다시()
            else:
                코드, 글 = _이력()
        else:
            코드, 글 = _달리기(도구)
        끝 = [x for x in 글.splitlines() if x.strip()]
        for x in 끝[-6:]:
            print("     %s" % x.strip()[:96])
        if 코드 != 0:
            막힘.append(이름)
            줄("✗", "여기서 멈췄습니다 — 고치고 다시 돌리십시오")
            break

    print()
    print("=" * 70)
    if 막힘:
        print("  ★ %s 에서 막혔습니다." % " · ".join(막힘))
        print("    고친 뒤 다시 돌리면 처음부터 다시 갑니다 (덮어씁니다).")
        return 1
    print("  끝났습니다.")
    print()
    print("  받을 것 — %s" % (번들 / "voc_dashboard_export_bundle_2차시험본.xlsx"))
    print("    시트 17개 · 0_차례 · raw_voc · ★PL Issue · ★사람이볼목록")
    print("             ★보정요청 · 수정로그_재검토필요 · …")
    print("    ★ 0_차례 에 「무엇을 어디서 보는지」 가 적혀 있습니다.")
    print()
    print("  ★ 다음 — 이 xlsx 를 대시보드에 올리고 6차 동결을 찍습니다.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
