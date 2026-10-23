# -*- coding: utf-8 -*-
"""코드·스킬에 옛 저장소 경로와 박힌 절대경로가 없는가.

★ 왜 (결정 0001 · 섹션 2)
  옛 도구는 경로를 파일마다 박아 두었고, 그 탓에 남의 PC 에서 세 번 따로 터졌다.
  이 저장소는 옛 폴더를 부르지 않는다. 경로는 `plugin/shared/paths.py` 한 곳에서만 정한다.

★ 보는 자리: plugin/ · tools/ · tests/ 와 저장소 맨 위 파일 몇 개
  (docs/ 는 「무엇을 어디서 복사했나」 를 적는 기록이라 뺀다)
★ 옛 저장소를 가리키는 말도 본다 — 드라이브 경로뿐 아니라 저장소 이름(youtube-comment-analyzer)까지.
  2026-09-21 교차점검에서 안내서 원문에 `git clone …/youtube-comment-analyzer.git` 이 살아 있는 것을 찾았다.
★ 「못 찾음」 은 통과가 아니다 — 검사한 파일이 0개면 실패한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import REPO, SHARED  # noqa: E402

보는곳 = ("plugin", "tools", "tests")
맨위파일 = ("README.md", "CHANGELOG.md", ".gitignore", ".gitattributes", ".claude-plugin/marketplace.json")
글파일 = {".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".sh", ".ps1", ".cfg", ".ini"}
코드파일 = {".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml", ".sh", ".ps1", ".cfg", ".ini"}

# 옛 저장소 폴더 — 어떤 파일에도 있으면 안 된다
옛경로 = re.compile(r"(?i)\b[a-z]:(?:\\\\|\\|/)+codex|codex_live_merge")
# 옛 경로 검사의 예외 — (파일, 줄 내용) 이 **둘 다** 맞아야 한다. 늘릴 때는 sky 에게 묻고 이유를 적는다.
옛경로_예외 = {
    # ★ 옛 저장소 **자리를 한 곳에서만 정하는** 줄이다 (2026-10-23 · 결정 0004).
    #   부르는 것이 아니라 **읽기만** 할 때 쓰는 자리다. 여기 없으면 시험마다 경로를 박게 된다.
    ("plugin/shared/paths.py",
     'or r"C:\\codex\\outputs\\voc_secondary")'),
    # sky 2026-09-18 「원문 그대로 + 검사 예외」 — 기준서 원문의 금지 문구다. 옛 폴더를 부르지 않는다.
    ("plugin/shared/standards/9_택소노미_2차확장.md",
     "하지 않는 것   C:\\codex_live_merge\\src\\voc_rebuild\\schema.py 수정"),
    # sky 2026-09-18 「원문 그대로 + 검사 예외」 (섹션 4) — 원문 속 설명·경고·금지 문구와, 옛 경로를 잡아내는 검사 문구.
    #   옛 폴더를 **부르는** 코드는 예외가 아니다 — 그런 9곳은 지웠다 (plugin/shared/출처_꾸러미.json 의 고친_이력).
    ('plugin/shared/common/98_전체흐름_1차부터_4차까지.md', '| 어디서 | `C:\\codex_live_merge` · 대시보드 「새로 분석 돌리기」 |'),
    ('plugin/shared/guides/63_대시보드_사용설명서.md', '로컬     C:\\codex_live_merge 에서'),
    ('plugin/shared/guides/63_대시보드_사용설명서.md', '★★ **`C:\\codex` 에서 띄우지 마십시오.**'),
    ('plugin/shared/guides/63_대시보드_사용설명서.md', 'C:\\codex_live_merge    브랜치 codex/voc-engine-rebuild   engine.py 4,500줄  ← 정상'),
    ('plugin/shared/guides/63_대시보드_사용설명서.md', 'C:\\codex               브랜치 codex/voc-second-stage     engine.py 1,934줄  ← 옛 엔진'),
    ('plugin/shared/guides/63_대시보드_사용설명서.md', '그런데 **`C:\\codex` 쪽은 옛 엔진이라 분석 결과가 달라집니다.**'),
    ('plugin/shared/guides/63_대시보드_사용설명서.md', '2026-08-20 까지 이 문서에 `C:\\codex` 로 적혀 있었습니다.'),
    ('plugin/shared/tools/자가점검.py', '# ★ 실제로 겪었다 (sky 2026-08-22) — 판독자가 `C:\\codex` 안에 폴더를 만들어'),
    ('plugin/shared/tools/자가점검.py', '#   돌았더니 그 아래 옛 엔진(`C:\\codex\\src`, 1,934줄)을 잡았다.'),
    ('plugin/shared/tools/자가점검.py', '#   남의 PC 에는 C:/codex_live_merge 가 없다. engine/ 이 그 자리다.'),
    ('plugin/shared/tools/자가점검.py', '줄("", "이 꾸러미를 C:\\\\codex 밖에 풀어 주십시오")'),
    ('plugin/shared/tools/자가점검.py', '문제.append("옛 엔진을 보고 있습니다 (꾸러미를 C:\\\\codex 밖에 푸십시오)")'),
    ('plugin/shared/tools/자가점검.py', 'if any(x in 줄내용 for x in ("C:/codex", "C:\\\\codex", "C:\\\\Users", "C:/Users")):'),
    ('plugin/skills/reading-voc-comments/references/0_붙여넣을_프롬프트_도구형.md', '(시스템 담당자 컴퓨터에서는 C:\\codex_live_merge\\src\\voc_rebuild\\schema.py)'),
    ('plugin/skills/reading-voc-comments/references/0_붙여넣을_프롬프트_도구형.md', '· C:\\codex 루트에서 엔진 실행 · 대상 목록에 없는 행을 판정'),
    # 2026-10-07 — sky 가 직접 한 번 돌리는 도우미다. **읽기만** 하고 옛 저장소를 고치지 않으며,
    #   저장소의 코드·스킬·엔진은 이 파일을 부르지 않는다 (가져오기 도구와 같은 자리).
    #   옛 .env 가 다른 자리에 있으면 `-EnvFile` 로 받는다 — 박힌 값이 아니라 기본값이다.
    ('tools/키_환경변수에_넣기.ps1', '[string]$EnvFile = "C:\\codex\\.env",'),
    # sky 2026-09-18 「원문 그대로 + 검사 예외」 — 원문이 자기 출처를 적어 둔 줄이다 (섹션 7 ③ 에 옮겨 온 파일).
    #   옛 폴더를 **부르는** 코드가 아니라 「어디서 왔나」 를 적은 글이다.
    ('plugin/shared/common/99_1차_실행조건_원문.md',
     '> 원본: `C:\\codex_live_merge\\src\\dashboard60\\analysis_runner.py` (마지막 커밋 8117810 2026-08-20 17:53:20 +0900)'),
}
# 옛 저장소 이름 — 새 코드·스킬이 옛것을 가리키면 안 된다 (기록으로 적은 자리만 예외)
옛저장소 = re.compile(r"(?i)youtube-comment-analyzer")
옛저장소_예외 = {
    # 출처 기록 — 「무엇을 어디서 복사했나」 다. 부르는 것이 아니다.
    ("plugin/shared/출처_꾸러미.json", None),
    ("plugin/shared/standards/출처.json", None),
    ("README.md", None),
    ("tools/옛꾸러미_가져오기.py", None),
    ("tools/옛꾸러미_가져오기_총괄.py", None),
    ("tools/엔진_가져오기.py", None),                 # 섹션 7 ① — 엔진을 어디서 들여왔나 (옛 자리는 명령 인자로 받는다)
    ("plugin/engine/출처_엔진.json", None),
    ("tests/test_no_old_paths.py", None),
    # sky 2026-09-18 「원문 그대로 + 검사 예외」 — 옛 대시보드 안내서 원문.
    #   ★ 새 안내서(guides/)를 쓸 때 이 자리를 새 저장소·새 사이트로 바꿔야 한다 (섹션 7a·8 에 적었다).
    ("plugin/shared/guides/63_대시보드_사용설명서.md", None),
}
# 절대경로 검사의 예외 — (파일, 줄 내용) 이 둘 다 맞아야 한다. 원문 주석 속 경로만 (sky 「원문 그대로 + 검사 예외」)
절대경로_예외 = {
    # 섹션 5 (2026-09-21) — build_master.py 원문 주석. 예전에 임시 폴더에서 돌린 흔적을 적은 것이다.
    ("plugin/shared/tools/build_master.py", r"#     judge_agree(C:\Users\blues\AppData\Local\Temp\...)"),
    # 섹션 7 ① (2026-09-22) — 엔진 원문(live_merge a94e731). Windows 기본 글꼴 자리 — 시스템 폴더라 사람 · 컴퓨터마다 같다.
    #   엔진이 그래프 글꼴을 찾는 후보 목록이다 (없으면 다음 후보로 · fonts/NanumGothic.ttf 가 먼저).
    ("plugin/engine/config/settings.example.yaml", "- C:/Windows/Fonts/malgun.ttf"),
    ("plugin/engine/config/settings.example.yaml", "- C:/Windows/Fonts/NanumGothic.ttf"),
    ("plugin/engine/src/config.py", 'Path("C:/Windows/Fonts/malgun.ttf"),'),
    ("plugin/engine/src/config.py", 'Path("C:/Windows/Fonts/NanumGothic.ttf"),'),
}
# 드라이브 글자로 시작하는 절대경로 — 코드에서는 paths.py 에만
절대경로 = re.compile(r"(?i)(?<![a-z])[a-z]:(?:\\\\|\\|/)[^\s'\"`]")


def _파일들():
    for 곳 in 보는곳:
        밑 = REPO / 곳
        if not 밑.is_dir():
            continue
        for p in sorted(밑.rglob("*")):
            if p.is_file() and p.suffix.lower() in 글파일 and "__pycache__" not in p.parts:
                yield p
    for 이름 in 맨위파일:
        p = REPO / 이름
        if p.is_file():
            yield p


def 찾기(글: str, 무늬: re.Pattern) -> list[tuple[int, str]]:
    return [(i, 줄.strip()) for i, 줄 in enumerate(글.splitlines(), 1) if 무늬.search(줄)]


def test_검사기가_일부러_틀린_것을_잡는다():
    # 검사기 자체를 먼저 시험한다 — 헛통과를 막으려고
    for 나쁨 in ("x = 'C:/codex/outputs'", r"p = r'C:\codex_live_merge'",
                 "p = 'c:\\\\codex\\\\x'", "import codex_live_merge"):
        assert 찾기(나쁨, 옛경로), 나쁨
    for 나쁨 in (r"p = r'D:\data\x.csv'", "p = 'C:/Users/x'"):
        assert 찾기(나쁨, 절대경로), 나쁨
    for 나쁨 in ("git clone https://github.com/skycloud-maker/youtube-comment-analyzer.git",
                 "cd youtube-comment-analyzer"):
        assert 찾기(나쁨, 옛저장소), 나쁨
    for 좋음 in ("# Codex 는 판독자다", "codex exec --json", "url = 'https://x'"):
        assert not 찾기(좋음, 옛저장소), 좋음
        assert not 찾기(좋음, 옛경로), 좋음
        assert not 찾기(좋음, 절대경로), 좋음


def test_옛_저장소_경로가_없다():
    본것, 걸림, 쓴예외 = 0, [], set()
    for p in _파일들():
        if p == Path(__file__).resolve():   # 일부러 틀린 예시가 이 파일에 있다
            continue
        본것 += 1
        rel = p.relative_to(REPO).as_posix()
        for i, 줄 in 찾기(p.read_text(encoding="utf-8", errors="replace"), 옛경로):
            if (rel, 줄) in 옛경로_예외:
                쓴예외.add((rel, 줄))
                continue
            걸림.append("%s:%d: %s" % (rel, i, 줄[:120]))
    assert 본것 > 0, "검사할 파일을 하나도 못 찾았다 — 통과가 아니다"
    assert not 걸림, "옛 저장소 경로가 남아 있다:\n" + "\n".join(걸림)
    # 예외가 가리키는 줄이 사라졌으면 예외도 치운다 — 쓰지 않는 예외는 다른 것을 숨길 수 있다
    assert 쓴예외 == 옛경로_예외, "쓰이지 않는 예외가 있다: %s" % (옛경로_예외 - 쓴예외)


def test_옛_저장소_이름을_부르지_않는다():
    본것, 걸림, 쓴예외 = 0, [], set()
    면제 = {r for r, _ in 옛저장소_예외}
    for p in _파일들():
        rel = p.relative_to(REPO).as_posix()
        본것 += 1
        줄들 = 찾기(p.read_text(encoding="utf-8", errors="replace"), 옛저장소)
        if not 줄들:
            continue
        if rel in 면제:
            쓴예외.add(rel)
            continue
        걸림 += ["%s:%d: %s" % (rel, i, x[:120]) for i, x in 줄들]
    assert 본것 > 0, "검사할 파일을 하나도 못 찾았다 — 통과가 아니다"
    assert not 걸림, "옛 저장소를 가리키는 곳이 있다:\n" + "\n".join(걸림)
    assert 쓴예외 == 면제, "쓰이지 않는 예외가 있다: %s" % (면제 - 쓴예외)


def test_절대경로는_paths_py_에만():
    본것, 걸림 = 0, []
    for p in _파일들():
        if p.suffix.lower() not in 코드파일 or p == SHARED / "paths.py" or p == Path(__file__).resolve():
            continue
        본것 += 1
        for i, 줄 in 찾기(p.read_text(encoding="utf-8", errors="replace"), 절대경로):
            if (p.relative_to(REPO).as_posix(), 줄) in 옛경로_예외 | 절대경로_예외:
                continue
            걸림.append("%s:%d: %s" % (p.relative_to(REPO).as_posix(), i, 줄[:120]))
    assert 본것 > 0, "검사할 코드 파일을 하나도 못 찾았다 — 통과가 아니다"
    assert not 걸림, "paths.py 밖에 절대경로가 있다 — paths.py 에서 가져올 것:\n" + "\n".join(걸림)


# ── 제어문자 ───────────────────────────────────────────────────────────────
# ★ 2026-10-09 — 진행 파일과 조사 기록에서 **세로탭(0x0B) 세 개**를 찾았다.
#   `Temp\voc` · `outputs\voc_secondary` · `skills\voc-probe-english` 를 적을 때
#   역슬래시+v 가 글자 그대로 남지 않고 **세로탭 한 글자로 바뀌어** 들어간 것이다
#   (셸 heredoc · 파이썬 문자열을 거치면서 생긴다).
#   눈으로는 공백처럼 보여서 안 보이고, 그 줄의 경로가 조용히 틀린 경로가 된다.
#   Ver2 결과를 적다가 또 같은 일이 나서, 사람 눈이 아니라 여기서 잡는다.
#
# ★ 줄을 `splitlines()` 로 나누면 **이 검사가 헛돈다** — 파이썬은 세로탭·폼피드에서도
#   줄을 나눠서, 찾으려는 글자가 줄 안에 남지 않는다 (처음 짰을 때 그래서 못 잡았다).
#   그래서 여기서는 `split(개행)` 으로만 나눈다.
제어문자 = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# ★ docs/ 도 본다 — 다른 검사는 「무엇을 복사했나」 기록이라 docs/ 를 빼지만,
#   깨진 경로는 그 기록에서 더 자주 생긴다 (찾은 셋 다 docs/ 에서 났다).
제어문자_보는곳 = ("plugin", "tools", "tests", "docs")


def 제어문자_찾기(글: str) -> list[tuple[int, str]]:
    """개행으로만 나눠서 찾는다 — `splitlines()` 를 쓰면 안 된다 (위 주석)."""
    return [(i, 줄.strip()[:70]) for i, 줄 in enumerate(글.split(chr(10)), 1)
            if 제어문자.search(줄)]


def _제어문자_볼파일():
    for 곳 in 제어문자_보는곳:
        밑 = REPO / 곳
        if not 밑.is_dir():
            continue
        for p in sorted(밑.rglob("*")):
            if p.is_file() and p.suffix.lower() in 글파일 and "__pycache__" not in p.parts:
                yield p
    for 이름 in 맨위파일:
        p = REPO / 이름
        if p.is_file():
            yield p


def test_제어문자_검사기가_일부러_틀린_것을_잡는다():
    assert 제어문자_찾기("자리(Temp" + chr(11) + "oc)만"), "세로탭을 못 잡는다"
    assert 제어문자_찾기("a" + chr(12) + "b"), "폼피드를 못 잡는다"
    assert 제어문자_찾기("a" + chr(0) + "b"), "널 문자를 못 잡는다"
    # ★ 헛통과 확인 — splitlines() 로 나누면 세로탭을 못 잡는다는 것을 여기서 못 박는다
    assert not [1 for 줄 in ("자리(Temp" + chr(11) + "oc)만").splitlines()
                if 제어문자.search(줄)], "splitlines() 가 세로탭을 남겼다 — 주석을 고쳐야 한다"
    for 좋음 in ("경로 " + chr(92) + "voc_Ver2판1", "탭\t도 괜찮다", "한글 · 화살표 → 별 ★"):
        assert not 제어문자_찾기(좋음), 좋음


def test_문서와_코드에_제어문자가_없다():
    본것, 걸림 = 0, []
    여기 = Path(__file__).resolve()
    for p in _제어문자_볼파일():
        if p == 여기:                       # 일부러 틀린 예시가 이 파일에 있다
            continue
        본것 += 1
        for 줄번호, 줄 in 제어문자_찾기(p.read_text(encoding="utf-8", errors="replace")):
            걸림.append("%s:%d  %s" % (p.relative_to(REPO), 줄번호, 줄))
    assert 본것 > 0, "검사한 파일이 0개다 — 「못 찾음」 은 통과가 아니다"
    assert not 걸림, ("제어문자가 든 줄 %d개 (경로가 조용히 틀어진다):\n  %s"
                     % (len(걸림), "\n  ".join(걸림[:10])))
