# -*- coding: utf-8 -*-
"""플러그인의 스킬을 낱개로 묶는다 — claude.ai 올리기용 zip 과 Codex 용 `.agents/skills` 사본 (섹션 6 · 2026-09-22).

★ 왜 — 플러그인 안에서 스킬은 옆 폴더의 `shared/` · `engine/` 을 쓴다. 스킬을 낱개로 떼면 폴더 밖을 못 가져간다
  (Claude Code 문서 · claude.ai 모두). 그래서 스킬마다 안에 복사한다. 손으로 복사하지 않는다 — 이 도구가 하고,
  `check_shared.py` 가 원본과 한 파일씩 대조한다 (같은 것이 두 벌이 되면 도구가 만든 것만 믿는다).
★ 규칙의 근거: docs/research/2026-09-22_스킬_묶음_배포_조사.md (skill-creator 의 package_skill.py · quick_validate.py).

쓰기
    python tools/build_skills.py              dist/ 를 새로 만든다
    python tools/build_skills.py <자리>       다른 자리에

만드는 것
    <자리>/claude/<스킬>.zip                  claude.ai 「Settings > Features」 에 올린다 (맨 위에 <스킬>/ 하나)
    <자리>/codex/.agents/skills/<스킬>/       Codex — 저장소나 $HOME 에 `.agents/` 를 통째로 둔다
    <자리>/차림표.json                          어느 파일이 어디서 왔나 (check_shared.py 가 읽는다)
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"

빼는_폴더 = {"__pycache__", "node_modules", ".git"}
빼는_파일 = {".DS_Store", "Thumbs.db"}
빼는_무늬 = (".pyc", ".pyo")
맨위_빼기 = {"evals"}                                  # package_skill.py 의 ROOT_EXCLUDE_DIRS
공통_빼기 = {"paths.py"}                               # 이 컴퓨터 경로가 적힌 개발용 — 나가는 코드가 부르지 않는다
허용키 = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
# 총괄 스킬은 판독 · 감독 스킬의 references · assets 를 쓴다 (총괄자리_차리기.py 의 _옆스킬)
옆스킬 = {"coordinating-voc-pipeline": ("reading-voc-comments", "supervising-voc-disagreements")}
용량한도 = 30 * 1024 * 1024                              # API 안내 「under 30 MB (uncompressed)」


def _뺄까(rel: Path) -> bool:
    return (bool(빼는_폴더 & set(rel.parts)) or rel.name in 빼는_파일 or rel.name.endswith(빼는_무늬))


def _파일들(뿌리: Path) -> list[Path]:
    return sorted(p for p in 뿌리.rglob("*") if p.is_file() and not _뺄까(p.relative_to(뿌리)))


def 스킬들() -> list[str]:
    return sorted(p.parent.name for p in PLUGIN.glob("skills/*/SKILL.md"))


def 차림표(스킬: str) -> list[tuple[Path, str]]:
    """(원본, 스킬 폴더 안 자리) — 낱개 스킬 하나에 들어갈 것 전부."""
    d = PLUGIN / "skills" / 스킬
    out = [(p, p.relative_to(d).as_posix()) for p in _파일들(d) if p.relative_to(d).parts[0] not in 맨위_빼기]
    out += [(p, "shared/" + p.relative_to(PLUGIN / "shared").as_posix()) for p in _파일들(PLUGIN / "shared")
            if p.name not in 공통_빼기]
    out += [(p, "engine/" + p.relative_to(PLUGIN / "engine").as_posix()) for p in _파일들(PLUGIN / "engine")]
    for 옆 in 옆스킬.get(스킬, ()):
        od = PLUGIN / "skills" / 옆
        for 칸 in ("references", "assets"):
            if (od / 칸).is_dir():
                out += [(p, "skills/%s/%s" % (옆, p.relative_to(od).as_posix())) for p in _파일들(od / 칸)]
    자리들 = [r for _, r in out]
    assert len(자리들) == len(set(자리들)), "같은 자리에 두 파일 — %s" % [r for r in 자리들 if 자리들.count(r) > 1][:3]
    return out


def 머리검사(skill_md: Path, 폴더이름: str) -> tuple[list[str], list[str]]:
    """(실패, 경고) — quick_validate.py 규칙 + 공식 문서의 예약어 · 폴더 이름 일치."""
    실패, 경고 = [], []
    글 = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", 글, re.S)
    if not m:
        return ["첫 줄이 --- 인 머리(frontmatter)가 없다"], 경고
    키 = dict(re.findall(r"^([A-Za-z][\w-]*):\s*(.*)$", m.group(1), re.M))
    if set(키) - 허용키:
        실패.append("허용하지 않는 키 %s" % sorted(set(키) - 허용키))
    이름, 설명 = 키.get("name", "").strip(), 키.get("description", "").strip()
    if not re.fullmatch(r"[a-z0-9-]{1,64}", 이름) or 이름.startswith("-") or 이름.endswith("-") or "--" in 이름:
        실패.append("name 규칙 — 소문자 · 숫자 · 하이픈 1~64자, 앞뒤 하이픈 · 연속 하이픈 금지: %r" % 이름)
    if re.search(r"anthropic|claude", 이름) or 이름 == "synced":
        실패.append("name 에 예약어 — %r" % 이름)
    if 이름 != 폴더이름:
        실패.append("폴더 이름(%s)과 name(%s)이 다르다" % (폴더이름, 이름))
    if not 설명:
        실패.append("description 이 비었다")
    if len(설명) > 1024:
        실패.append("description %d자 — 1024자를 넘는다" % len(설명))
    if "<" in 설명 or ">" in 설명:
        실패.append("description 에 < > 가 있다")
    if len(설명) > 200:
        경고.append("description %d자 — claude.ai 고객센터 문서는 200자라고 적었다 (다른 공식 문서는 1024자)" % len(설명))
    if 글.count("\n") > 500:
        경고.append("SKILL.md %d줄 — 모범사례는 500줄 아래" % 글.count("\n"))
    return 실패, 경고


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def 만들기(자리: Path) -> int:
    # ★ 2026-10-22 — 전에는 `dist/` 를 **통째로 지웠다.** 그래서 `판_묶기.py` 로 만든
    #   `dist/판/`(Ver1·Ver2 꾸러미)이 이 도구를 돌리는 순간 **말없이 사라졌다.**
    #   도구 둘이 같은 자리를 쓰는데 한쪽이 남의 것까지 치운 것이다.
    #   이제 **자기가 만드는 것만** 치운다 — `claude/` · `codex/` · 자기 차림표.
    for 내것 in ("claude", "codex"):
        if (자리 / 내것).exists():
            shutil.rmtree(자리 / 내것)
    if (자리 / "차림표.json").is_file():
        (자리 / "차림표.json").unlink()
    기록 = {"설명": "build_skills.py 가 만든 것 — 손으로 고치지 않는다. check_shared.py 가 원본과 대조한다", "스킬": {}}
    나쁨 = 0
    for 스킬 in 스킬들():
        표 = 차림표(스킬)
        실패, 경고 = 머리검사(PLUGIN / "skills" / 스킬 / "SKILL.md", 스킬)
        크기 = sum(p.stat().st_size for p, _ in 표)
        if 크기 >= 용량한도:
            실패.append("풀었을 때 %d바이트 — 30MB 를 넘는다" % 크기)
        for w in 경고:
            print("  ! %s — %s" % (스킬, w))
        if 실패:
            나쁨 += 1
            for f in 실패:
                print("  ✗ %s — %s" % (스킬, f))
            continue
        코덱스 = 자리 / "codex" / ".agents" / "skills" / 스킬
        for 원, 안 in 표:
            q = 코덱스 / 안
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(원, q)
        z = 자리 / "claude" / (스킬 + ".zip")
        z.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for 원, 안 in 표:
                zf.write(원, "%s/%s" % (스킬, 안))
        기록["스킬"][스킬] = {안: {"원본": 원.relative_to(REPO).as_posix(), "sha256": _sha(원)} for 원, 안 in 표}
        print("  · %s — %d개 · %.1f MB (풀었을 때)" % (스킬, len(표), 크기 / 1024 / 1024))
    (자리 / "차림표.json").parent.mkdir(parents=True, exist_ok=True)
    (자리 / "차림표.json").write_text(json.dumps(기록, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if 나쁨 else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    자리 = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "dist"
    print("스킬 묶기 → %s" % 자리)
    코드 = 만들기(자리)
    print("끝 — 종료코드 %d" % 코드)
    sys.exit(코드)
