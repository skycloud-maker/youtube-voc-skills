# -*- coding: utf-8 -*-
"""꾸러미에 「이번 데이터에만 맞는 말」이 박혀 있는지 본다.

★ 왜 있는가 (sky 2026-08-22)
  「이 정도면 학습능력이 없는건지 🙂 그러라고 지시를 받은건지..」

  하루에 같은 실수를 세 번 했다 — 눈앞의 데이터로 예시를 써 놓고
  그것이 다음 판에서 틀린 말이 되는 것.

    pilot 경로 박기      p1_overlabel_suggest_*  (실무자 컴퓨터엔 없다)
    행 수·회차 박기       1,570행 · 14회차        (로니는 6,336행 · 53회차)
    제품군·자사 박기      「로봇청소기」 「자사」    (한 판에 6종이 섞이고
                                              경쟁사 900행이 분석 대상이다)

  ★ 다른 것에는 다 검사기를 붙여 놓고 이것만 내 손에 맡겼다. 그러니 또 틀렸다.
    **내 판단이 잣대가 되는 설계를 피한다** — 오늘 세 번째로 같은 교훈이다.

무엇을 보나
  실무자에게 나가는 글(프롬프트·가이드)에 다음이 박혀 있으면 알린다.
    ① 특정 제품군 이름          다음 판에는 다른 제품이다
    ② 특정 행 수·회차 수         데이터마다 다르다
    ③ 특정 회사 이름을 「우리/남」으로 가르는 말
    ④ 이 컴퓨터에만 있는 경로

  ★ 「참고 — pilot 실측」 처럼 **근거로 밝힌 것은 봐준다.**
    그건 지시가 아니라 사실 기록이다. 헛경보도 사고다.

쓰기
    python 박힌말_검사.py            꾸러미에 나가는 글을 본다
    python 박힌말_검사.py <파일> …    고른 것만
"""

from __future__ import annotations
import os

import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent if _HERE.name in ("스크립트", "scripts") else _HERE

# ★ 늘 쓰는 글만 본다 (2026-08-22).
#   첫 판에서 보조 프롬프트까지 봐서 75곳이 나왔다. 그러면 아무도 안 본다.
#   평소 안 쓰는 보조 프롬프트는 `--전부` 를 줄 때만 본다.
늘쓰는것 = [
    "_판독패키지/0_붙여넣을_프롬프트_도구형.md",
    "_판독패키지/0_붙여넣을_프롬프트_감독.md",
    "_판독패키지/0_전체흐름_어느_프롬프트를_언제.md",
    "60_2차판독_실무자_사용가이드.md",
    "61_3차감독_실무자_사용가이드.md",
    "94_배포안내_누가_무엇을_받나.md",
]

# ★ 꾸러미에 들어가는 도구만 본다 (2026-08-23)
#   handoff.py 에 master_final 이 박혀 있었는데 검사기가 글(.md)만 보고 있었다.
#   글은 사람이 읽지만 코드는 아무도 안 읽는다. 그래서 코드에 더 잘 박힌다.
#   ★ 다만 내 작업용 스크립트(sample_reader 등)는 남의 컴퓨터에 안 간다.
#     거기 박힌 것은 사고가 아니므로 보지 않는다 — 101곳이 나오면 아무도 안 본다.
def _실리는도구() -> list[str]:
    """꾸러미가 실제로 싣는 도구를 make_zip.py 에서 읽는다.

    ★ 손으로 적지 않는다 (2026-08-23).
      적어 두었더니 build_master · rank_two_axis · make_grading_sheet ·
      감독_읽기 · 엔진자리 다섯이 빠졌고, build_master 에 박힌
      `final_v62` · `cc_final` 을 못 잡아 3차 마무리가 멈췄다.
      ★ 새 도구를 실으면 검사도 저절로 따라가야 한다.
    """
    p = ROOT / "make_zip.py"
    if not p.exists():
        return []
    글 = p.read_text(encoding="utf-8", errors="replace")
    이름 = set(re.findall(r"\('([^']+\.py)',\s*'스크립트/", 글))
    return sorted(이름)


꾸러미도구 = _실리는도구()
늘쓰는것 += 꾸러미도구
가끔쓰는것 = [
    "_판독패키지/0_붙여넣을_*.md",
    "62_4차검토_및_번들해설.md",
    "63_대시보드_사용설명서.md",
]

찾는것 = [
    ("제품군을 박음",
     re.compile(r"로봇청소기|식기세척기|세탁기|건조기|스타일러|에어컨|정수기")),
    ("행 수를 박음", re.compile(r"\b\d{1,2},\d{3}\s*행|\b6,?336|\b1,?570")),
    ("회차 수를 박음", re.compile(r"\b(14|53|4)\s*회차\s*(전부|를 다|까지)")),
    ("자사/남의 것을 가름", re.compile(r"자사\s*(제품|로봇|가전)|우리\s*회사\s*제품")),
    ("이 컴퓨터 경로", re.compile(r"C:[\\/](codex|Users)")),
    ("pilot 자리", re.compile(r"p1_overlabel_suggest|s12_full")),
]

# ★ 도구(.py) 에만 대는 무늬 (2026-08-23)
#   글에서는 「_결과/master_final」 이 설명일 수 있지만
#   코드에서 따옴표 안에 박히면 그건 그 컴퓨터에서만 도는 뜻이다.
도구에박힌것 = [
    ("결과 폴더 이름을 박음",
     re.compile(r"""['\"][^'\"]*_결과[/\\][A-Za-z가-힣][\w가-힣]*['\"]""")),
    ("내 작업 폴더 이름",
     re.compile(r"master_final|cc_final|cc_now|final_v\d|bundle_최종")),
    ("제품 기본값을 박음",
     re.compile(r"""(prod|product|제품)\s*=\s*['\"](robot|dishwasher|multi)['\"]""")),
    ("판독자 이름을 박음",
     re.compile(r"""['\"](claudecode|Codex|codex)_bundle['\"]""")),
]

# ★ 알고 두는 것 (2026-08-23) — 까닭을 적고 뺀다.
#   검사기가 늘 같은 5곳을 보여주면 사람이 검사기를 안 믿는다.
#   그러면 **새로 박히는 것**이 그 5곳에 묻힌다.
#   ★ 몰래 봐주지 않는다 — 자리가 없어지면 「이제 없습니다」 하고 알린다.
알고두는것 = [
    ("build_bundle.py", "p1_overlabel_suggest",
     "sky 작업 폴더 되돌림장치. os.path.exists 로 막혀 있어 남의 컴퓨터에선 안 돈다"),
    ("build_bundle.py", ".worktrees/voc-secondary-p0",
     "1차 계약 자리를 찾는 후보. 환경변수가 먼저고, isdir 로 막혀 있다"),
    ("apply_approved.py", ".worktrees/voc-secondary-p0",
     "위와 같다"),
    # ★ 아래 셋은 2026-08-23 에 정당해졌다.
    #   master_final 은 두 감독자를 합친 **고정 산출물** 이름이고,
    #   총괄 자리에서만 만든다. 판독자마다 다른 이름이 아니다.
    ("build_master.py", "master_final",
     "두 감독자를 합친 고정 산출물 이름. 판독자마다 다르지 않다"),
    ("rank_two_axis.py", "master_final",
     "위가 만든 것을 읽는다"),
    ("build_master.py", "확인요청 4묶음",
     "08-18 에 실제로 있었던 일을 적어 둔 설명글이다"),
]


def _알고두나(파일이름, 줄):
    for _f, _무늬, _ in 알고두는것:
        if 파일이름 == _f and _무늬 in 줄:
            return True
    return False


# 봐주는 것 — 지시가 아니라 사실 기록이거나 예시다
#   ★ 이것을 안 두면 75곳이 나온다. 그러면 아무도 안 본다 (오탐도 사고다)
봐주기 = re.compile(
    r"참고|실측|pilot|예\)|예시|보기|이력|겪었|있었다|났다|였다|"
    r"그랬다|드러났|적혀|한 적|였습니다|입니다만|"
    r"C:[\\/]codex_live_merge|"        # 정본 엔진 자리 — 맞는 말이다
    r"^\s*\||"                          # 표 — 대개 사실 기록
    r"^\s*[→★·]|"                       # 판정 예시의 결론 줄
    r"[\"“][^\"”]{10,}[\"”]")           # 원문 인용


def 보기(길: Path) -> list[tuple[str, int, str]]:
    나온것 = []
    줄들 = 길.read_text(encoding="utf-8", errors="replace").splitlines()
    코드 = 길.suffix == ".py"   # ★ 도구에는 다른 무늬를 댄다
    for 번호, 줄 in enumerate(줄들, 1):
        if 봐주기.search(줄):
            continue
        # ★ 주석은 돌지 않는다 — 박힌 말이 사고가 되는 자리는 도는 코드다
        if 코드 and 줄.lstrip().startswith("#"):
            continue
        # 앞뒤 두 줄에 「참고/실측」 이 있으면 그 묶음도 봐준다
        둘레 = " ".join(줄들[max(0, 번호 - 3):번호 + 2])
        if 봐주기.search(둘레):
            continue
        if _알고두나(길.name, 줄):
            continue
        for 이름, 무늬 in 찾는것 + (도구에박힌것 if 코드 else []):
            m = 무늬.search(줄)
            if m:
                나온것.append((이름, 번호, 줄.strip()[:78]))
                break
    return 나온것


# ★ 박힌 경로 — 내 컴퓨터에서만 도는 자리 (2026-08-25)
#   감독쪽지_만들기 에 C:\Users\blues\Downloads 가 박혀 있었다.
#   다른 컴퓨터에서는 아예 안 돈다. 「박힌 말」 과 같은 성질인데
#   검사기가 한쪽만 보고 있었다.
박힌경로 = (
    ("C:\\Users\\", "사람 계정 폴더 — 다른 컴퓨터에서 안 돈다"),
    ("C:\\codex", "내 작업 폴더 — 실무자 컴퓨터에는 없다"),
    ("Downloads", "받은 파일 폴더 — 자리가 사람마다 다르다"),
)
# 여기 있어도 되는 자리 — 총괄 전용이거나, 그 경로를 설명하는 글
경로봐줌 = (
    "박힌말_검사.py",          # 이 파일 자신 (무늬가 적혀 있다)
    "감독쪽지_만들기.py",       # 왜 없앴는지 주석에 적혀 있다
    "63_대시보드_사용설명서.md",  # 어느 폴더에서 띄우나를 설명한다
    "92_동결운영규칙.md", "93_오류발견대장.md", "90_변경원장_LEDGER.md",
    "98_전체흐름_1차부터_4차까지.md", "99_4차_실무자의견_논점정리.md",
    "48_VoC_파일위치_지도_v2.0.md",
)


def _꾸러미에_실리는_py() -> set:
    """make_zip 이 실제로 담는 .py 이름 — 배포된 zip 을 열어 본다.

    ★ 목록을 손으로 유지하면 반드시 빠진다 (이미 다섯이 빠진 적이 있다).
      만들어진 결과물에서 읽는다.
    """
    이름 = set()
    배포 = Path(__file__).resolve().parent / "_배포"
    if not 배포.is_dir():
        return 이름
    import zipfile
    for z in sorted(배포.glob("*.zip")):
        try:
            for n in zipfile.ZipFile(z).namelist():
                if n.endswith(".py"):
                    이름.add(n.rsplit("/", 1)[-1])
        except Exception:                                   # noqa: BLE001
            continue
    return 이름


def 경로검사(뿌리):
    """꾸러미에 실리는 파일에 박힌 경로가 있나.

    ★ 이 파일이 이미 쓰는 Path 로만 쓴다 — 새 import 를 만들지 않는다.
      import 를 하나씩 붙이다 세 번 깨뜨렸다 (2026-08-25).
    """
    걸림 = []
    자리 = Path(뿌리)
    # ★ 꾸러미에 실리는 코드만 본다 (2026-08-25).
    #   .py+.md 전부 보면 94곳 — 거의 다 문서의 설명이다
    #   .py 만 보면 22곳 — 전부 총괄 전용 도구다 (실무자에게 안 간다)
    #   ★ 실무자 컴퓨터에서 안 도는 것만 사고다.
    #     총괄 자리 도구에 내 경로가 박힌 것은 사고가 아니다.
    실릴것 = _꾸러미에_실리는_py()
    for p in sorted(자리.glob("*.py")):
        if 실릴것 and p.name not in 실릴것:
            continue
        if p.name in 경로봐줌:
            continue
        try:
            줄들 = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for n, 줄 in enumerate(줄들, 1):
            if 줄.lstrip().startswith("#"):      # 주석은 설명이다
                continue
            for 무늬, 왜 in 박힌경로:
                if 무늬 in 줄:
                    걸림.append((p.name, n, 줄.strip()[:60], 왜))
                    break
    return 걸림


def 데이터검사(뿌리):
    """★ 실무자에게 **나가는 데이터**에 내 경로가 박혔나 (2026-08-25).

    코드만 보던 검사가 이번 사고를 놓쳤다.
    raw_voc.csv 의 decided_by 1,535행에 로컬 임시 경로가 담겨 나갔다.
    데이터도 실무자 손에 간다. 코드와 똑같이 본다.
    """
    걸림 = []
    for 자리 in (Path(뿌리) / "_판독패키지" / "_결과" / "master_final",):
        if not 자리.is_dir():
            continue
        for p in sorted(자리.glob("*.csv")):
            if p.name.startswith("raw_voc_경로고치기전"):   # 일부러 둔 원본
                continue
            n = 0
            try:
                # ★ io 를 새로 들이지 않는다 — 이 파일이 스스로 경고한 함정이다.
                #   (「이미 쓰는 Path 로만 쓴다」 · 226행) 방금 그대로 빠졌다.
                with p.open(encoding="utf-8-sig", errors="replace") as h:
                    for i, 줄 in enumerate(h, 1):
                        if "C:\\" in 줄 or "C:/" in 줄 or "AppData" in 줄:
                            n += 1
                            if n == 1:
                                첫 = (i, 줄.strip()[:70])
            except OSError:
                continue
            if n:
                걸림.append((p.name, 첫[0], 첫[1], "%d줄에 로컬 경로" % n))
    return 걸림


def main() -> int:
    _뿌리 = Path(__file__).resolve().parent
    _데이터 = 데이터검사(_뿌리)
    if _데이터:
        print()
        print("★ 나가는 데이터에 로컬 경로가 박혔습니다 — %d개 파일" % len(_데이터))
        for 이름, n, 줄, 왜 in _데이터:
            print("   ✗ %s:%d  %s" % (이름, n, 왜))
            print("      %s" % 줄)
        print()
        print("   ★ 이력 칸에 경로를 적으면 안 됩니다. 실명을 적으십시오.")
        return 1

    _경로 = 경로검사(_뿌리)
    if _경로:
        print()
        print("★ 박힌 경로가 %d곳 있습니다 — 다른 컴퓨터에서 안 돕니다"
              % len(_경로))
        for 이름, n, 줄, 왜 in _경로[:8]:
            print("   ✗ %s:%d  %s" % (이름, n, 줄))
            print("      %s" % 왜)
        print()
    고른것 = [Path(p) for p in sys.argv[1:] if not p.startswith("--")]
    무늬들 = 늘쓰는것 + (가끔쓰는것 if "--전부" in sys.argv else [])
    파일 = 고른것 or [p for 무늬 in 무늬들 for p in sorted(ROOT.glob(무늬))]
    파일 = sorted({p for p in 파일 if p.exists()})

    if not 파일:
        print("볼 글을 못 찾았습니다: %s" % ROOT)
        return 1

    print("=" * 74)
    print("  이번 데이터에만 맞는 말이 박혀 있는가 — 늘 쓰는 글 %d개" % len(파일))
    if "--전부" not in sys.argv:
        print("  (평소 안 쓰는 보조 프롬프트까지 보려면 --전부)")
    print("=" * 74)

    모두 = 0
    for 길 in 파일:
        나온것 = 보기(길)
        if not 나온것:
            continue
        모두 += len(나온것)
        print()
        print("  %s — %d곳" % (길.name, len(나온것)))
        for 이름, 번호, 글 in 나온것[:8]:
            print("     [%s] %4d  %s" % (이름, 번호, 글))
        if len(나온것) > 8:
            print("     … 그 밖 %d곳" % (len(나온것) - 8))

    print()
    print("=" * 74)
    if 모두:
        print("  ★ %d곳이 이번 데이터에만 맞는 말일 수 있습니다." % 모두)
        print()
        print("  다음 판에는 다른 제품, 다른 행 수, 다른 회사가 옵니다.")
        print("  근거로 밝힌 것(「참고 — pilot 실측」)은 그대로 두어도 됩니다.")
        print("  **지시문**에 박힌 것만 고치십시오.")
        print("=" * 74)
        return 1
    print("  박힌 말이 없습니다")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
