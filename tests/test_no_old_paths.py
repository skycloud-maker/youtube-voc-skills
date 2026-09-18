# -*- coding: utf-8 -*-
"""코드·스킬에 옛 저장소 경로와 박힌 절대경로가 없는가.

★ 왜 (결정 0001 · 섹션 2)
  옛 도구는 경로를 파일마다 박아 두었고, 그 탓에 남의 PC 에서 세 번 따로 터졌다.
  이 저장소는 옛 폴더를 부르지 않는다. 경로는 `plugin/shared/paths.py` 한 곳에서만 정한다.

★ 보는 자리: plugin/ · tools/ · tests/ (docs/ 는 출처를 적는 기록이라 뺀다)
★ 「못 찾음」 은 통과가 아니다 — 검사한 파일이 0개면 실패한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import REPO, SHARED  # noqa: E402

보는곳 = ("plugin", "tools", "tests")
글파일 = {".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".sh", ".ps1", ".cfg", ".ini"}
코드파일 = {".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml", ".sh", ".ps1", ".cfg", ".ini"}

# 옛 저장소 폴더 — 어떤 파일에도 있으면 안 된다
옛경로 = re.compile(r"(?i)\b[a-z]:(?:\\\\|\\|/)+codex|codex_live_merge")
# 옛 경로 검사의 예외 — (파일, 줄 내용) 이 **둘 다** 맞아야 한다. 늘릴 때는 sky 에게 묻고 이유를 적는다.
옛경로_예외 = {
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


def 찾기(글: str, 무늬: re.Pattern) -> list[tuple[int, str]]:
    return [(i, 줄.strip()) for i, 줄 in enumerate(글.splitlines(), 1) if 무늬.search(줄)]


def test_검사기가_일부러_틀린_것을_잡는다():
    # 검사기 자체를 먼저 시험한다 — 헛통과를 막으려고
    for 나쁨 in ("x = 'C:/codex/outputs'", r"p = r'C:\codex_live_merge'",
                 "p = 'c:\\\\codex\\\\x'", "import codex_live_merge"):
        assert 찾기(나쁨, 옛경로), 나쁨
    for 나쁨 in (r"p = r'D:\data\x.csv'", "p = 'C:/Users/x'"):
        assert 찾기(나쁨, 절대경로), 나쁨
    for 좋음 in ("# Codex 는 판독자다", "codex exec --json", "url = 'https://x'"):
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


def test_절대경로는_paths_py_에만():
    본것, 걸림 = 0, []
    for p in _파일들():
        if p.suffix.lower() not in 코드파일 or p == SHARED / "paths.py" or p == Path(__file__).resolve():
            continue
        본것 += 1
        for i, 줄 in 찾기(p.read_text(encoding="utf-8", errors="replace"), 절대경로):
            if (p.relative_to(REPO).as_posix(), 줄) in 옛경로_예외:
                continue
            걸림.append("%s:%d: %s" % (p.relative_to(REPO).as_posix(), i, 줄[:120]))
    assert 본것 > 0, "검사할 코드 파일을 하나도 못 찾았다 — 통과가 아니다"
    assert not 걸림, "paths.py 밖에 절대경로가 있다 — paths.py 에서 가져올 것:\n" + "\n".join(걸림)
