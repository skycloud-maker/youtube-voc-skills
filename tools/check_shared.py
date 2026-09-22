# -*- coding: utf-8 -*-
"""build_skills.py 가 만든 낱개 스킬이 원본과 한 파일도 다르지 않은가 (섹션 6 · 2026-09-22).

★ 같은 것이 두 벌이 되면 어긋난다 — 그래서 사본은 도구만 만들고, 이 검사기가 원본과 대조한다.
  보는 것
    ① Codex 사본 폴더 · claude zip 안의 파일 목록이 차림표와 **똑같다** (빠진 것 · 더 있는 것 없음)
    ② 파일마다 내용이 **지금 원본**과 같다 (묶은 뒤 원본을 고쳤으면 「다시 묶으라」 고 실패한다)
    ③ zip 맨 위에 <스킬>/ 하나만 있다
  ★ 볼 것을 못 찾으면 실패다 — 「못 찾음」 을 「같음」 으로 돌려주지 않는다.

쓰기
    python tools/check_shared.py            dist/ 를 본다
    python tools/check_shared.py <자리>
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_skills  # noqa: E402


def 대조(자리: Path) -> list[str]:
    틀림: list[str] = []
    기록파일 = 자리 / "차림표.json"
    if not 기록파일.is_file():
        return ["차림표를 못 찾았다 — %s (build_skills.py 를 먼저)" % 기록파일]
    기록 = json.loads(기록파일.read_text(encoding="utf-8"))["스킬"]
    지금스킬 = build_skills.스킬들()
    if sorted(기록) != 지금스킬:
        틀림.append("묶은 스킬 %s 와 플러그인의 스킬 %s 가 다르다 — 다시 묶는다" % (sorted(기록), 지금스킬))
    for 스킬 in 지금스킬:
        지금표 = {안: 원 for 원, 안 in build_skills.차림표(스킬)}
        if 스킬 not in 기록:
            continue
        if set(기록[스킬]) != set(지금표):
            빠짐 = sorted(set(지금표) - set(기록[스킬]))[:3]
            더있음 = sorted(set(기록[스킬]) - set(지금표))[:3]
            틀림.append("%s — 차림표가 지금 원본과 다르다 (빠짐 %s · 더 있음 %s) — 다시 묶는다" % (스킬, 빠짐, 더있음))
        코덱스 = 자리 / "codex" / ".agents" / "skills" / 스킬
        있는것 = {p.relative_to(코덱스).as_posix() for p in 코덱스.rglob("*") if p.is_file()} if 코덱스.is_dir() else set()
        if not 있는것:
            틀림.append("%s — Codex 사본을 못 찾았다: %s" % (스킬, 코덱스))
        z = 자리 / "claude" / (스킬 + ".zip")
        if not z.is_file():
            틀림.append("%s — zip 을 못 찾았다: %s" % (스킬, z))
            zip안 = {}
        else:
            with zipfile.ZipFile(z) as zf:
                zip안 = {n: zf.read(n) for n in zf.namelist() if not n.endswith("/")}
            맨위 = {n.split("/", 1)[0] for n in zip안}
            if 맨위 != {스킬}:
                틀림.append("%s — zip 맨 위가 %s 하나가 아니다: %s" % (스킬, 스킬, sorted(맨위)[:5]))
        for 안, v in 기록[스킬].items():
            원 = REPO / v["원본"]
            if not 원.is_file():
                틀림.append("%s — 원본이 없어졌다: %s" % (스킬, v["원본"]))
                continue
            원내용 = 원.read_bytes()
            if hashlib.sha256(원내용).hexdigest() != v["sha256"]:
                틀림.append("%s — 묶은 뒤 원본이 바뀌었다: %s — 다시 묶는다" % (스킬, v["원본"]))
            q = 코덱스 / 안
            if not q.is_file():
                틀림.append("%s — Codex 사본에 없다: %s" % (스킬, 안))
            elif q.read_bytes() != 원내용:
                틀림.append("%s — Codex 사본이 원본과 다르다: %s" % (스킬, 안))
            zn = "%s/%s" % (스킬, 안)
            if zip안 and zn not in zip안:
                틀림.append("%s — zip 에 없다: %s" % (스킬, 안))
            elif zip안 and zip안[zn] != 원내용:
                틀림.append("%s — zip 안 파일이 원본과 다르다: %s" % (스킬, 안))
        for 더 in sorted(있는것 - set(기록[스킬]))[:5]:
            틀림.append("%s — Codex 사본에 차림표에 없는 파일: %s" % (스킬, 더))
        for 더 in sorted({n.split("/", 1)[1] for n in zip안} - set(기록[스킬]))[:5]:
            틀림.append("%s — zip 에 차림표에 없는 파일: %s" % (스킬, 더))
    return 틀림


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    자리 = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "dist"
    틀림 = 대조(자리)
    for t in 틀림[:30]:
        print("  ✗ %s" % t)
    if not 틀림:
        n = sum(len(v) for v in json.loads((자리 / "차림표.json").read_text(encoding="utf-8"))["스킬"].values())
        print("  · 낱개 스킬이 원본과 같다 — 파일 %d개 (Codex 사본 · zip 둘 다)" % n)
    sys.exit(1 if 틀림 else 0)
