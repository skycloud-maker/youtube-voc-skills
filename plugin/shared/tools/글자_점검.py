# -*- coding: utf-8 -*-
"""글자가 깨졌거나 라벨 이름에 오타가 있는지 **전수로** 본다 (2026-10-09).

★ 왜 — sky 2026-10-09 「모든 글자들에 이상하게 깨져서 들어가거나,, 오타가 들어가거나,,
  그런 오류 없는지 한번 점검해볼 필요도 있겠네요,,, 신뢰를 실뢰라고 쓴다거나..
  아까 그런 경우가 불러오는 경우에 일시적으로 발생한 오류인지,, 전체적인 저장에서
  오류가 발생한건지... 모르니까요..」

  맞는 걱정이다. 그날 나온 「실뢰」 는 **내가 질문을 쓰다 틀린 것**이었지만,
  데이터·기준서 쪽을 전수로 재 본 적은 없었다. 그래서 여기서 잰다.
  ★ 라벨 이름이 한 글자 틀리면 집계가 **조용히 둘로 갈린다** —
    「제조사 신뢰/품질」 과 「제조사 실뢰/품질」 은 사람 눈에 거의 같아 보인다.

보는 것 넷
  ① 깨진 글자        치환문자(U+FFFD) · 제어문자 · 혼자 떨어진 서러게이트
  ② 라벨 오타        정본 대장(`registry/topic_group_map.json`)에 없는 라벨 중
                     **한두 글자 차이로 정본과 비슷한 것** → 오타로 본다
                     (아예 다른 것은 「새 라벨」 일 수 있어 `topic_registry.py` 몫이다)
  ③ 인코딩           UTF-8 로 못 읽는 파일 · BOM 이 섞인 CSV
  ④ 자모 섞임        한글 음절 사이에 끼어든 낱자모 (예: 「신ㄹ뢰」)
                     ★ `ㅋㅋ` `ㅜㅜ` 처럼 **혼자 서 있는** 자모는 사람이 쓴 것이라 뺀다

쓰기
    python 글자_점검.py                     이 꾸러미(또는 저장소)를 본다
    python 글자_점검.py <폴더> [<폴더> ...]   그 자리들을 본다

종료코드
    0  깨끗하다        1  틀린 것이 있다        2  볼 것을 못 찾았다
★ 「못 찾음」 은 통과가 아니다 — 볼 파일이 0개면 2 로 끝낸다.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent if _여기.name in ("스크립트", "scripts", "tools") else _여기

글파일 = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".csv", ".ps1"}
표파일 = {".csv"}
안보는곳 = {"__pycache__", ".git", ".pytest_cache", "node_modules", "dist"}

치환문자 = re.compile("[�]")
제어문자 = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# ★ 자모가 음절 **사이에 끼어든** 것만 본다 — 「신ㄹ뢰」 꼴.
#   처음에는 「음절 앞이나 뒤」 로 봤더니 사람이 쓴 `아닌가ㅋㅋ` · `발생했습니다ㅠㅠ` ·
#   `"ㅂ니다"` 같은 말과 정규식 글자묶음(`가-힣ㄱ-ㅎㅏ-ㅣ`)이 줄줄이 걸렸다 (2026-10-09).
자모섞임 = re.compile(r"[가-힣][㄰-㆏][가-힣]")
# ★ 한글 음절에 **한자가 맞붙은** 것 — UTF-8 글을 cp949 로 읽었을 때 나오는 꼴이다
#   (보기: 「留ㅻ쾲」 · 「諛섎젮」). 사람이 쓴 한국어에는 한자가 붙어 나오지 않는다.
한자섞임 = re.compile(r"(?:[가-힣][一-鿿]|[一-鿿][가-힣])")
# ★ **정본 대장이 다스리는 칸만** 본다 (2026-10-09).
#   처음에는 `rootcause_problem` · `na_class` 도 넣었는데, 그 둘은 **자유기술·등급 서술** 칸이라
#   문장이 들어간다 (`check_selfcheck.py` 의 FREE · GRADE_LIKE 목록). 그래서 문장 60종이
#   「정본에 없는 라벨」 로 줄줄이 나왔다 — 거짓 경보다.
라벨칸 = ("topic", "topic_group")


def _라벨정본() -> set[str]:
    """정본 대장에서 라벨 이름을 모은다. 못 찾으면 빈 집합 — 부르는 쪽이 판단한다."""
    이름들: set[str] = set()
    for 자리 in (_뿌리 / "registry", _뿌리 / "shared" / "registry", _여기.parent / "registry"):
        q = 자리 / "topic_group_map.json"
        if not q.is_file():
            continue
        m = json.loads(q.read_text(encoding="utf-8"))
        for 그룹, 라벨들 in (m.get("그룹") or {}).items():
            이름들.add(그룹)
            이름들.update(라벨들)
        break
    return 이름들


def _거리(a: str, b: str) -> int:
    """글자 몇 개를 고치면 같아지나 (Levenshtein). 짧은 글이라 단순하게 짠다."""
    if a == b:
        return 0
    앞 = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        이번 = [i]
        for j, y in enumerate(b, 1):
            이번.append(min(앞[j] + 1, 이번[j - 1] + 1, 앞[j - 1] + (x != y)))
        앞 = 이번
    return 앞[-1]


def _파일들(터: Path) -> list[Path]:
    out = []
    for p in sorted(터.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in 글파일:
            continue
        if 안보는곳 & set(p.relative_to(터).parts):
            continue
        out.append(p)
    return out


def 보기(터들: list[Path]) -> int:
    정본 = _라벨정본()
    본파일, 걸림 = 0, []
    라벨본것, 라벨값 = 0, {}

    for 터 in 터들:
        if not 터.is_dir():
            print("  ! 폴더가 아닙니다 — %s" % 터)
            continue
        for p in _파일들(터):
            if p.resolve() == Path(__file__).resolve():
                continue                      # 이 파일에는 일부러 둔 본보기가 있다
            본파일 += 1
            바이트 = p.read_bytes()
            # ③ 인코딩 — UTF-8 로 못 읽는가
            try:
                글 = 바이트.decode("utf-8-sig")
            except UnicodeDecodeError as e:
                걸림.append("[인코딩] %s — UTF-8 로 못 읽습니다 (%s)" % (p, e))
                continue
            # ① 깨진 글자 (개행으로만 나눈다 — splitlines() 는 세로탭에서도 줄을 나눠 검사가 헛돈다)
            for i, 줄 in enumerate(글.split(chr(10)), 1):
                for 이름, 무늬 in (("치환문자", 치환문자), ("제어문자", 제어문자),
                                ("자모섞임", 자모섞임), ("한자섞임", 한자섞임)):
                    m = 무늬.search(줄)
                    if m:
                        걸림.append("[%s] %s:%d — %r" % (이름, p, i, 줄.strip()[:60]))
            if unicodedata.normalize("NFC", 글) != 글:
                걸림.append("[정규화] %s — NFC 가 아닙니다 (자모 분리 저장)" % p)
            # ② 라벨 오타 — 표에서 라벨 칸만 본다
            if p.suffix.lower() in 표파일 and 정본:
                try:
                    줄들 = list(csv.DictReader(io.StringIO(글)))
                except csv.Error:
                    continue
                for r in 줄들:
                    for 칸 in 라벨칸:
                        v = (r.get(칸) or "").strip()
                        # ★ 특수값 — `8_topic_그룹.md` 의 「미판정」 줄에 적힌 것들이다.
                        #   대장 JSON 의 그룹 이름에는 없어서 그냥 두면 「새 라벨」 로 나온다.
                        if not v or v in ("N/A", "미분류", "미판정", "-", "없음"):
                            continue
                        라벨본것 += 1
                        라벨값.setdefault(v, set()).add(str(p))

    if not 본파일:
        print("  ✗ 볼 파일이 0개입니다 — 「못 찾음」 은 통과가 아닙니다")
        return 2
    if not 정본:
        걸림.append("[정본없음] topic_group_map.json 을 못 찾아 라벨 오타를 못 봤습니다")

    오타, 새것 = [], []
    for v, 자리들 in sorted(라벨값.items()):
        if v in 정본:
            continue
        가까운 = sorted(((_거리(v, c), c) for c in 정본))[:1]
        if 가까운 and 가까운[0][0] <= 2 and len(v) >= 4:
            오타.append((v, 가까운[0][1], 가까운[0][0], sorted(자리들)[:1]))
        else:
            새것.append((v, sorted(자리들)[:1]))

    print("  본 파일 %d개 · 라벨 값 %d개(고유 %d종) · 정본 라벨 %d종"
          % (본파일, 라벨본것, len(라벨값), len(정본)))
    for v, c, d, 자리 in 오타:
        걸림.append("[라벨오타] 「%s」 — 정본 「%s」 와 %d글자 차이 (%s)" % (v, c, d, 자리[0]))
    if 새것:
        print("  ! 정본에 없지만 **오타로 보기엔 먼** 라벨 %d종 — 새 라벨일 수 있습니다"
              % len(새것))
        for v, 자리 in 새것[:8]:
            print("      %s   (%s)" % (v, 자리[0]))
        print("      → 새 라벨이면 `topic_registry.py --register` 로 대장에 올립니다")

    if 걸림:
        print()
        print("  ✗ 틀린 것 %d건" % len(걸림))
        for x in 걸림[:40]:
            print("     %s" % x)
        if len(걸림) > 40:
            print("     … 그리고 %d건 더" % (len(걸림) - 40))
        return 1
    print("  · 깨진 글자 0 · 라벨 오타 0 · 인코딩 0 · 자모 섞임 0")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    터들 = [Path(x).resolve() for x in sys.argv[1:]] or [_뿌리]
    print("글자 점검 — %s" % " · ".join(str(x) for x in 터들))
    return 보기(터들)


if __name__ == "__main__":
    raise SystemExit(main())
