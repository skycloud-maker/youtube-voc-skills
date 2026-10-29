# -*- coding: utf-8 -*-
"""옛 꾸러미의 파일을 **전량 줄 세워** 「왔나 / 안 왔나 / 아직 안 봤나」 를 센다 (2026-10-29).

★ 왜 이것을 만들었나 — sky 물음 2026-10-29
    「근데 늘 이런식이면... 애초에 제가 100프로로는 안되더라도 그 전에걸 그대로 가져와서
      옮겨달라고 했는데... 왜 누락이 계속 생기는지 모르겠네요」

  재어 보니 **옮기다 글을 줄인 적은 없었다.** 기준 문서 정본은 539줄 = 539줄 로 통째로 왔고,
  출처 기록 네 벌(`출처_꾸러미.json` 76 · `출처_엔진.json` 152 · `standards/출처.json` 9 ·
  `옛관리도구/출처.json`)이 **옮긴 것이 변하지 않았음**을 지문으로 지키고 있다.

  **그런데 그 기록은 「옮긴 것」 만 센다.** 「안 옮긴 것」 을 세는 자리가 **없었다.**
  그래서 빠진 것은 검사에 걸릴 수가 없었다 — 애초에 셈에 들어오지 않으니까.
  `docs/대조_원본과_skill.md` 의 「원본 기록 76개 / 옮긴 것 76개」 도 **우리가 고른 76개**를
  둘로 센 것이어서, 옛 꾸러미에 **몇 개가 있었는지**는 어디에도 없었다.
  검사기가 「못 찾음」 을 「없음」 으로 돌려주던 것과 **같은 병이 한 층 위에** 있었다.

  → 이 도구는 **옛 꾸러미 쪽에서 센다.** 옛 파일 하나하나가 네 칸 중 어디에 있는지 적고,
    **「아직 안 봤다」 칸의 수를 못 박아** 그 수가 늘면 시험이 실패하게 한다.
    수는 줄어들 수만 있다. 누락이 생기면 **다음 커밋에서 바로 드러난다.**

★ 옛 저장소는 **읽기만 한다** (공통 규칙 3 · `_공통_작업규칙/손대지말것_전역.txt`).
  자리는 `paths.py` 의 `옛저장소` 에서 가져온다 (`VOC_옛저장소` 로 바꿀 수 있다).
  이 도구는 읽어서 **새 저장소에 목록(`docs/옛꾸러미_목록.json`)을 적을 뿐**이고,
  옛 저장소에는 아무것도 쓰지 않고 옛 코드를 돌리지도 않는다.

★ 옛 저장소가 없는 컴퓨터에서도 시험이 돌아야 하므로, 센 결과를 **목록 파일로 저장소에
  넣는다.** 시험은 그 목록을 본다 (`tests/test_옛꾸러미_대장.py`). 옛 저장소가 있는
  컴퓨터에서 이 도구를 다시 돌리면 목록이 갱신되고, 그때 수가 늘면 시험이 잡는다.

쓰기
    python tools/옛꾸러미_대장.py            다시 세어 목록을 갱신한다
    python tools/옛꾸러미_대장.py --확인만    세어서 말만 하고 목록을 고치지 않는다
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin" / "shared"))
from paths import 옛저장소 as 옛자리  # noqa: E402
# ★ 절대경로를 여기 박지 않는다 — `paths.py` 한 자리에서만 정한다
#   (`tests/test_no_old_paths.py` 가 그것을 지킨다. 실제로 이 파일이 한 번 걸렸다)
목록자리 = REPO / "docs" / "옛꾸러미_목록.json"
까닭글 = REPO / "docs" / "옛꾸러미_대장.md"

# 셈에서 빼는 자리 — **일부러 옛것**인 폴더 · 캐시 · **지난 판의 산출물**이다.
#   뺀다는 것을 수까지 적는다 (규율 2-2). 끝의 `*` 는 「이 말로 시작하는 폴더」 다.
#   ★ 산출물을 빼는 까닭 — 그것은 **옮길 재료가 아니라 돌려서 나오는 것**이다. 새 꾸러미로
#     가져오면 「같은 것이 두 벌」 이 되고, 판독자에게 주면 정답지가 된다.
#   ★ **재료가 든 폴더는 빼지 않는다** — `_설계서/` · `_정본/` · `_인계/` · `_배포/` 는
#     글이 든 자리라서 「아직 안 봤다」 에 남는다. 산출물과 섞어 빼면 누락을 덮는다.
뺀자리 = {
    "_작업이력": "옛 작업 기록 — 일부러 옛것이다 (지금 쓰는 것이 아니다)",
    "_구버전": "옛판 — 일부러 옛것이다",
    "구버전": "옛판 — 일부러 옛것이다 (밑줄 없는 이름으로도 있다)",
    "unpacked": "docx 를 풀어 놓은 내부 파일 — 재료는 풀기 전 docx 다",
    "_되돌리기_20260821": "되돌리기용 사본 — 일부러 옛것이다",
    "_라벨바꾸기전_*": "라벨 바꾸기 전 사본 — 일부러 옛것이다",
    "__pycache__": "파이썬 캐시 — 자료가 아니다",
    ".git": "git 내부",
    "_결과": "지난 판독·감독을 돌려서 나온 산출물 — 옮길 재료가 아니다",
    "_2판": "2판을 돌린 작업 폴더 — 그 판의 산출물이다",
    "_발표시연": "발표 시연용으로 돌린 것 — 그 판의 산출물이다",
    "_preserved": "보존 사본 — 일부러 옛것이다",
    "s4_results": "한 단계를 돌려서 나온 결과 — 산출물이다",
    "s12_full": "한 단계를 돌려서 나온 결과 — 산출물이다",
    "s13_judge": "감독 입력을 만들어 낸 결과 — 산출물이다",
    "s15_master": "통합해서 나온 결과 — 산출물이다",
    "p1_overlabel_*": "2026-08-14 파일럿을 돌려서 나온 산출물이다",
    "p0_na303_*": "2026-08-14 점검을 돌려서 나온 산출물이다",
}
글꼴 = {".md", ".py", ".csv", ".txt", ".json", ".js", ".jsonl", ".yaml", ".yml", ".sql"}


def 지문(p: Path) -> str:
    """글 파일은 줄바꿈을 LF 로 고른 뒤 잰다 — 새 저장소는 LF 로 담았다(.gitattributes)."""
    b = p.read_bytes()
    if p.suffix.lower() in 글꼴:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def 출처기록() -> tuple[set, set, set]:
    """출처 기록 **전부**를 읽는다 — 하나만 읽으면 옮긴 것을 안 옮겼다고 센다."""
    적힌sha, 적힌이름, 고친것 = set(), set(), set()

    def 훑기(x, 이름=None):
        if isinstance(x, dict):
            이_이름 = os.path.basename(x["원본"]) if isinstance(x.get("원본"), str) else 이름
            if isinstance(x.get("원본_sha256"), str):
                적힌sha.add(x["원본_sha256"])
            if 이_이름:
                적힌이름.add(이_이름)
                if x.get("고친_이력"):
                    고친것.add(이_이름)
            for k, v in x.items():
                if k not in ("원본", "원본_sha256", "지금_sha256", "고친_이력"):
                    훑기(v, 이_이름)
        elif isinstance(x, list):
            for v in x:
                훑기(v, 이름)

    기록들 = [q for q in sorted(REPO.rglob("출처*.json")) if "/dist/" not in q.as_posix()]
    if not 기록들:
        raise SystemExit("못 찾음: 출처 기록이 하나도 없다 — 셀 수 없다 (통과가 아니다)")
    for q in 기록들:
        훑기(json.loads(q.read_text(encoding="utf-8")))
    return 적힌sha, 적힌이름, 고친것


def 까닭들() -> list:
    """`docs/옛꾸러미_대장.md` 에서 「안 옮긴 까닭」 을 읽는다 — 무늬 한 줄에 까닭 하나."""
    if not 까닭글.is_file():
        raise SystemExit("못 찾음: %s — 안 옮긴 까닭을 읽을 수 없다" % 까닭글)
    난것 = []
    for 줄 in 까닭글.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|", 줄)
        if m:
            난것.append((m.group(1).strip(), m.group(2).strip()))
    if not 난것:
        raise SystemExit("못 찾음: %s 에 무늬가 없다 — 까닭을 읽을 수 없다" % 까닭글.name)
    return 난것


def 맞나(이름: str, 무늬: str) -> bool:
    """무늬는 `시작*` · `*끝` · `*가운데*` · 그대로 넷만 쓴다 (정규식을 쓰지 않는다)."""
    if 무늬.startswith("*") and 무늬.endswith("*") and len(무늬) > 2:
        return 무늬[1:-1] in 이름
    if 무늬.startswith("*"):
        return 이름.endswith(무늬[1:])
    if 무늬.endswith("*"):
        return 이름.startswith(무늬[:-1])
    return 이름 == 무늬


def 세기() -> dict:
    if not 옛자리.is_dir():
        raise SystemExit("못 찾음: %s — 옛 꾸러미가 없는 컴퓨터다.\n"
                         "  목록을 갱신할 수 없다. 시험은 이미 담긴 목록으로 돈다." % 옛자리)
    적힌sha, 적힌이름, 고친것 = 출처기록()
    무늬들 = 까닭들()

    새지문 = {}
    for p in REPO.rglob("*"):
        q = p.as_posix()
        if p.is_file() and "/.git/" not in q and "/dist/" not in q and "__pycache__" not in q:
            try:
                새지문.setdefault(지문(p), []).append(p.relative_to(REPO).as_posix())
            except OSError:
                pass

    셈 = {"그대로있다": [], "고쳤다": [], "안옮겼다": [], "아직안봤다": []}
    뺀셈: dict = {}
    for p in sorted(옛자리.rglob("*")):
        if not p.is_file():
            continue
        쪽 = p.relative_to(옛자리)
        빼는것 = next((무늬 for d in 쪽.parts[:-1] for 무늬 in 뺀자리 if 맞나(d, 무늬)), None)
        if 빼는것:
            뺀셈[빼는것] = 뺀셈.get(빼는것, 0) + 1
            continue
        try:
            s = 지문(p)
        except OSError:
            s = ""
        말 = 쪽.as_posix()
        if s and s in 새지문:
            셈["그대로있다"].append(말)
        elif p.name in 고친것:
            셈["고쳤다"].append(말)
        elif p.name in 적힌이름 or (s and s in 적힌sha):
            셈["고쳤다"].append(말)
        else:
            까닭 = next((ㄴ for 무늬, ㄴ in 무늬들 if 맞나(p.name, 무늬)), None)
            (셈["안옮겼다"] if 까닭 else 셈["아직안봤다"]).append(말)

    센것 = sum(len(v) for v in 셈.values())
    return {
        "설명": "옛 꾸러미 전량을 줄 세워 센 것 — tools/옛꾸러미_대장.py 가 적는다. 손으로 고치지 않는다",
        "센_날": "2026-10-29",
        "옛_자리": str(옛자리),
        "뺀_자리": {d: {"수": 뺀셈.get(d, 0), "까닭": 까닭} for d, 까닭 in 뺀자리.items()},
        "센_파일수": 센것,
        "수": {k: len(v) for k, v in 셈.items()},
        "아직안봤다": sorted(셈["아직안봤다"]),
        "안옮겼다": sorted(셈["안옮겼다"]),
    }


def main(인자: list) -> int:
    확인만 = "--확인만" in 인자
    난것 = 세기()
    print("옛 꾸러미 — %s" % 난것["옛_자리"])
    print("  셈에서 뺀 자리 — %d개 파일" % sum(v["수"] for v in 난것["뺀_자리"].values()))
    for d, v in 난것["뺀_자리"].items():
        print("     %-22s %4d개   %s" % (d, v["수"], v["까닭"]))
    print("  센 파일 %d개" % 난것["센_파일수"])
    for k, n in 난것["수"].items():
        print("     %-12s %4d개" % (k, n))
    아직 = 난것["수"]["아직안봤다"]

    옛수 = None
    if 목록자리.is_file():
        옛수 = json.loads(목록자리.read_text(encoding="utf-8"))["수"]["아직안봤다"]
        print("  지난번 「아직 안 봤다」 %d개 → 이번 %d개 (%+d)" % (옛수, 아직, 아직 - 옛수))

    if 확인만:
        print("확인만 — 목록을 고치지 않았다")
        return 1 if (옛수 is not None and 아직 > 옛수) else 0

    if 옛수 is not None and 아직 > 옛수:
        print("  ✗ 「아직 안 봤다」 가 **늘었다** (%d → %d). 늘어난 것을 먼저 보십시오 —" % (옛수, 아직))
        print("    옮기거나, 안 옮길 까닭을 docs/옛꾸러미_대장.md 에 적으십시오.")
        print("    목록은 고치지 않았다 (늘어난 수를 그냥 못 박으면 누락을 덮는 것이다).")
        return 1

    목록자리.write_text(json.dumps(난것, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8", newline="\n")
    print("  · %s 를 갱신했다" % 목록자리.relative_to(REPO).as_posix())
    print("끝 — 종료코드 0")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
