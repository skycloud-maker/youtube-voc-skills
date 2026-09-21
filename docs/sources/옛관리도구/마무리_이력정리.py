# -*- coding: utf-8 -*-
"""판을 닫는다 — 문서 최신화 · 이력 · 커밋/푸시 · 현황 점검. 총괄 자리.

★ sky 2026-08-25
  「4차 결과를 가지고 최종 반영을 한 뒤에 변경사항에 대해서 정본 문서나
    그 외 관련된 문서들에 최신화 업데이트와 과거이력 관리, 그리고 구버전에
    대한 관리, 그리고 최신화된 문서를 로컬과 github에 커밋/푸시하고
    우리의 현재 전체 현황에 대해서 완료된 기준으로 다 정리가 되었는지
    이런 과정은 언제 들어가는 게 좋을지? 이것도 하나의 py로?」

  ★ 흩어져 있었습니다. `4차_반영.py` 의 ⑥ 이력 맞추기가 검사 넷만 돌리고,
    변경원장·오류대장·커밋·푸시·동결은 제가 매번 기억해서 했습니다.
    ★ 기억으로 하는 일은 반드시 하나가 빠집니다 — 오늘만 PL 하나가 빠졌습니다.

★ 이 도구가 하지 **않는** 것
  · 커밋 메시지를 대신 쓰지 않습니다 (무엇을 왜 바꿨는지는 사람이 압니다)
  · 동결 태그를 대신 찍지 않습니다 (어디까지가 끝인지는 사람이 정합니다)
  둘 다 **할 준비가 됐는지 검사하고, 할 명령을 보여 줍니다.**

쓰기
    python 마무리_이력정리.py            검사하고 무엇이 남았는지 보여 준다
    python 마무리_이력정리.py --고치기    고칠 수 있는 것은 고친다 (정본·꾸러미)
"""
from __future__ import annotations

import io
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
저장소 = ROOT.parent.parent          # outputs/voc_secondary → 저장소 뿌리
릴리스 = Path(r"C:\codex_live_merge")


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def _달리기(길: Path, *인자: str, 자리: Path | None = None):
    r = subprocess.run([sys.executable, str(길), *인자],
                       cwd=str(자리 or ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _깃(자리: Path, *인자: str):
    r = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(자리),
                        *인자], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "").strip()


def 검사들(고치기: bool) -> list:
    """문서·꾸러미가 한 판인가."""
    남은것 = []
    for 도구, 말 in (("정본_맞추기.py", "같은 문서가 세 곳에서 갈렸나"),
                    ("박힌말_검사.py", "내 개발 폴더 이름·경로가 섞였나"),
                    ("5차기준_검사.py", "「감독자가 통합한다」 옛 서술이 남았나"),
                    # ★ 2026-08-26 — 용어 일괄 치환이 실제 댓글 본문을 덮은 일이
                    #   있었다(「담당자」→「총괄」). check_lineage 는 판 안에서만
                    #   보므로 원문과 조각이 같이 바뀌면 그냥 통과한다.
                    #   판을 닫기 전에 **1차 원본까지 거슬러** 견준다
                    ("원문대조검사.py", "원문이 1차 원본과 글자까지 같은가"),
                    # ★ 2026-08-26 — 파생 칸 topic_group 이 topic 을 안 따라가
                    #   1,534행이 어긋나 있었다. 대시보드 집계가 그만큼 틀린다
                    ("그룹_맞추기.py", "topic_group 이 topic 과 맞는가"),
                    # ★ 2026-09-07 — 분리 조각 570행이 13칸 넘게 통째로 비어
                    #   있던 것을 검사가 아니라 sky 가 물어서 찾았다.
                    #   값이 각각 유효하면 기존 검사는 다 지나간다.
                    #   「행을 만든 주체별로 빈칸률이 갈리는가」 를 따로 본다
                    ("아무도_안채우는칸_검사.py", "한 도구만 안 채우는 칸이 있나"),
                    # ★ 2026-09-07 — E-1 을 「영구 종결」 로 정했는데 그 전까지
                    #   여섯 문서가 「다음 엔진 개정 때 고친다」 고 적고 있었다.
                    #   한 곳만 고치면 다음 사람이 딴 문서를 보고 딴소리를 한다
                    ("문서_한말_검사.py", "문서들이 같은 말을 하나"),
                    ("make_zip.py", "꾸러미가 온전한가")):
        길 = _여기 / 도구
        if not 길.exists():
            남은것.append("%s 가 없습니다" % 도구)
            continue
        # ★ make_zip 은 고치는 도구이고 보기만 하는 판이 없다. --고치기 일 때만 돌린다.
        #   (꾸러미가 최신인지는 아래 릴리스검사가 따로 본다)
        if 도구 == "make_zip.py" and not 고치기:
            줄("·", "%-18s %s  (--고치기 로 돌립니다)" % (도구, 말))
            continue
        # ★ 고치는 도구를 검사 자리에서 돌릴 때는 「보기만」 인자를 붙인다.
        #   그룹_맞추기 는 인자 없이 돌리면 **데이터를 고친다** (2026-08-26).
        #   ★ 검사 자리에 고치는 도구를 그냥 두면, 「보기만 하려던」 실행이
        #     데이터를 바꾼다 — 자가점검이 정본 폴더를 지운 것과 같은 실수다.
        # ★★ 2026-09-18 — 정본_맞추기 는 전에 검사 모드에서 **아예 안 돌리고**
        #   「·」 통과로 찍었다. 기준서 5벌 중 1벌만 고쳐진 채로 그렇게 지나갔다.
        #   이제 --보기만 으로 돌리고, 갈렸으면 종료코드 1 이라 ✗ 로 찍힌다.
        보기만인자 = {"그룹_맞추기.py": ("--확인만",), "정본_맞추기.py": ("--보기만",)}
        인자 = () if 고치기 else 보기만인자.get(도구, ())
        코드, 글 = _달리기(길, *인자)
        끝 = [x.strip() for x in 글.splitlines() if x.strip()][-2:]
        표 = "·" if 코드 == 0 else "✗"
        줄(표, "%-18s %s" % (도구, " / ".join(끝)[:60]))
        if 코드 != 0:
            남은것.append(도구)
    남은것 += 판사본_검사(고치기)
    남은것 += 릴리스검사(고치기)
    return 남은것


def 판사본_검사(고치기: bool) -> list:
    """★ 판 폴더(_N판)의 사본이 원본과 같은가 (2026-08-26).

    왜 만들었나 — **같은 일로 네 번 당했습니다.**
      판을 하나 돌릴 때마다 `_2판/` 같은 폴더에 그 판이 쓴 도구와 문서를
      통째로 복사해 둡니다. 그래야 「그때 무엇으로 돌렸나」 가 남습니다.
      그런데 판이 끝난 뒤 원본만 고치면 **사본이 조용히 옛것으로 남습니다.**
      93_오류발견대장 의 마무리 절차 ⑤ 에 「원본과 사본의 지문을 맞춘다」
      라고 적어 놓고도, 적어 놓은 것만으로는 세 번을 못 막았습니다.
      ★ 적어 두는 것과 돌리는 것은 다릅니다 — 그래서 여기로 옮겼습니다.

    무엇을 맞추나 — 뿌리의 `*.py` · `*.md` 중 **사본에 이미 있는 것만**.
      사본에 없는 파일은 그 판 뒤에 새로 생긴 것이라 건드리지 않습니다.
    """
    import hashlib
    import shutil

    def 지문(f):
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()

    판들 = sorted(p for p in ROOT.glob("_*판")
                  if p.is_dir() and p.name[1:-1].isdigit())
    if not 판들:
        return []

    남은것 = []
    for 판 in 판들:
        다름 = []
        for f in sorted(list(ROOT.glob("*.py")) + list(ROOT.glob("*.md"))):
            g = 판 / f.name
            if g.exists() and 지문(f) != 지문(g):
                다름.append((f, g))
        if not 다름:
            줄("·", "%-18s 사본 %d개가 원본과 같습니다"
               % (판.name, sum(1 for f in
                               list(ROOT.glob("*.py")) + list(ROOT.glob("*.md"))
                               if (판 / f.name).exists())))
            continue
        if 고치기:
            for f, g in 다름:
                shutil.copy2(f, g)
            줄("·", "%-18s 어긋난 사본 %d개를 원본으로 맞췄습니다"
               % (판.name, len(다름)))
        else:
            줄("✗", "%-18s 사본 %d개가 원본과 다릅니다  (--고치기 로 맞춥니다)"
               % (판.name, len(다름)))
            for f, _g in 다름[:8]:
                print("       %s" % f.name)
            if len(다름) > 8:
                print("       … 그리고 %d개" % (len(다름) - 8))
            남은것.append("%s 사본" % 판.name)
    return 남은것


def 대장들() -> list:
    """사람이 적어야 하는 이력 — 도구가 대신 못 쓴다."""
    적을것 = []
    for 이름, 무엇 in (
        ("90_변경원장_LEDGER.md", "이번 판에서 무엇을 왜 바꿨나"),
        ("93_오류발견대장.md", "겪은 결함 — 고쳤나 남겨 뒀나"),
        ("28_대시보드_반영대기_목록.md", "대시보드가 아직 안 받은 것"),
        ("92_동결운영규칙.md", "이 판의 동결에 무엇이 담기나"),
    ):
        길 = ROOT / 이름
        if not 길.exists():
            적을것.append("%s 가 없습니다" % 이름)
            continue
        from datetime import datetime, timedelta
        오래됨 = datetime.fromtimestamp(길.stat().st_mtime) < \
            datetime.now() - timedelta(days=1)
        줄("!" if 오래됨 else "·",
           "%-28s %s%s" % (이름, 무엇, "  ★ 하루 넘게 안 고쳤습니다"
                           if 오래됨 else ""))
        if 오래됨:
            적을것.append(이름)
    return 적을것


def 구버전() -> None:
    """옛 판을 어디에 두었나 — 지우지 않고 자리를 보여 준다."""
    for 자리, 말 in ((ROOT / "_작업이력", "지난 판의 산출물"),
                    (ROOT / "_되돌린것", "다시 돌리며 치운 것"),
                    (ROOT / "_보관", "따로 둔 것")):
        if 자리.is_dir():
            n = sum(1 for _ in 자리.rglob("*") if _.is_file())
            줄("·", "%-14s %5d개  %s" % (자리.name, n, 말))


def 릴리스검사(고치기: bool) -> list:
    """★ 릴리스(codex_live_merge)가 이 판을 싣고 있나 (2026-08-26).

    왜 넣었나 — **push 훅이 막을 때까지 몰랐습니다.**
      릴리스를 새로 만드는 단계가 둘 있는데, 그 스크립트는 **다른 저장소**
      (`C:\\codex_live_merge\\scripts\\`)에 있습니다. 이 도구는 그것을 몰랐고,
      아는 것은 push 훅뿐이었습니다. 그래서 6차 동결 때 ⑥ 을 다 끝내고
      push 를 눌러서야 「배포 꾸러미 · 동결 기준점이 낡았다」 를 만났습니다.
      ★ 맨 끝에서 막히면, 앞의 검사를 전부 다시 돌려야 합니다.

    그래서 **판을 닫기 시작할 때** 여기서 먼저 묻습니다.
      `--고치기` 면 두 스크립트를 순서대로 돌립니다 (갈아 끼우고 → 다시 만듦).
    """
    if not (릴리스 / ".git").exists():
        return []
    남은것 = []
    for 도구, 말 in (("refresh_release_packages.py", "배포 꾸러미가 최신인가"),
                    ("build_freeze_release.py", "동결 기준점이 최신인가")):
        길 = 릴리스 / "scripts" / 도구
        if not 길.exists():
            줄("!", "%s 가 없습니다 — 릴리스 검사를 건너뜁니다" % 도구)
            continue
        코드, 글 = _달리기(길, "--check", 자리=릴리스)
        if 코드 == 0:
            끝 = [x.strip() for x in 글.splitlines() if x.strip()][-1:]
            줄("·", "%-30s %s" % (도구, (끝[0] if 끝 else 말)[:44]))
            continue
        if not 고치기:
            줄("✗", "%-30s %s  (--고치기 로 다시 만듭니다)" % (도구, 말))
            남은것.append(도구)
            continue
        코드2, 글2 = _달리기(길, 자리=릴리스)
        끝 = [x.strip() for x in 글2.splitlines() if x.strip()][-1:]
        표 = "·" if 코드2 == 0 else "✗"
        줄(표, "%-30s 다시 만들었습니다 — %s"
           % (도구, (끝[0] if 끝 else "")[:38]))
        if 코드2 != 0:
            남은것.append(도구)
    return 남은것


def 저장소들() -> list:
    """로컬과 github 이 같은가."""
    남은것 = []
    for 자리 in (저장소, 릴리스):
        if not (자리 / ".git").exists() and not (자리 / ".git").is_file():
            continue
        코드, 상태 = _깃(자리, "status", "-sb")
        첫 = 상태.splitlines()[0] if 상태 else ""
        바뀐것 = len([x for x in 상태.splitlines()[1:] if x.strip()])
        코드2, 미추적 = _깃(자리, "ls-files", "--others", "--exclude-standard")
        미 = len([x for x in 미추적.splitlines() if x.strip()])
        앞섬 = "ahead" in 첫
        표 = "·" if (바뀐것 == 0 and not 앞섬) else "!"
        줄(표, "%-22s %s" % (자리.name, 첫))
        if 바뀐것:
            줄(" ", "   커밋 안 한 것 %d개" % 바뀐것)
            남은것.append("%s 커밋" % 자리.name)
        if 앞섬:
            줄(" ", "   push 안 한 것이 있습니다")
            남은것.append("%s push" % 자리.name)
        if 미:
            줄(" ", "   미추적 %d개 (일부러 둔 것일 수 있습니다)" % 미)
    return 남은것


def 동결() -> None:
    코드, 태그 = _깃(저장소, "tag", "--list", "freeze_phase*")
    있는것 = [x for x in 태그.splitlines() if x.strip()]
    줄("·", "동결 태그 %d개 — %s" % (len(있는것), " · ".join(있는것[-3:])))


def main() -> int:
    고치기 = "--고치기" in sys.argv
    print("=" * 70)
    print("  마무리 — 판을 닫습니다")
    print("=" * 70)
    print()

    print("  ① 문서·꾸러미가 한 판인가")
    남은1 = 검사들(고치기)
    print()
    print("  ② 이력을 적었나  ★ 도구가 대신 못 씁니다")
    남은2 = 대장들()
    print()
    print("  ③ 구버전은 어디에")
    구버전()
    print()
    print("  ④ 로컬과 github 이 같은가")
    남은3 = 저장소들()
    print()
    print("  ⑤ 동결")
    동결()

    print()
    print("=" * 70)
    남은 = 남은1 + 남은2 + 남은3
    if not 남은:
        print("  다 정리됐습니다.")
        print()
        print("  ★ 동결을 찍으시려면 (사람이 정합니다):")
        print('     git tag -a freeze_phaseN_YYYYMMDD -m "N차 동결 — 무엇" HEAD')
        print("     git push origin freeze_phaseN_YYYYMMDD")
        return 0

    print("  ★ 남은 것 %d가지" % len(남은))
    for x in 남은:
        print("     · %s" % x)
    print()
    print("  ★ 커밋 메시지와 동결 태그는 대신 쓰지 않습니다 —")
    print("    무엇을 왜 바꿨는지, 어디까지가 끝인지는 사람이 압니다.")
    if not 고치기:
        print()
        print("  고칠 수 있는 것을 고치려면:  python 마무리_이력정리.py --고치기")
    return 1


if __name__ == "__main__":
    sys.exit(main())
