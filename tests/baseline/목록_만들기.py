# -*- coding: utf-8 -*-
"""얼린 기준의 **파일 목록과 해시**를 `얼린기준_목록.json` 에 적는다.

★ 왜 도구인가 (2026-10-08) — 지금까지 이 목록은 손으로 만들었다. 기준이 늘 때마다 손으로 적으면
  빠지거나 틀린다. 기준 자체는 저장소 밖(`BASELINE/실행/`)에 있고 git 에는 이 목록만 들어가므로,
  목록이 틀리면 **기준이 바뀐 것을 못 잡는다.**

★ 이미 적혀 있는 실행은 **건드리지 않는다.** 얼린 기준을 지키는 것이 이 목록의 일이므로,
  이미 있는 것을 다시 적으면 「바뀐 것」 을 덮어 버린다. 다시 적으려면 `--다시` 를 같이 준다.

★ **이름을 반드시 받는다** (2026-10-08) — 처음에는 「기준 자리에 있는 실행을 모두」 더하게 만들었다가
  두 번째 실행(`*_2`) 까지 목록에 넣어 버렸다. `_2` 는 **매번 같은지 보려고** 돌린 것이고
  얼린 기준은 `_1` 이다. 무엇을 얼리는지는 사람이 정한다.

쓰기
    python tests/baseline/목록_만들기.py 번들꾸미기_1            그 실행을 목록에 더한다
    python tests/baseline/목록_만들기.py 번들꾸미기_1 --다시      이미 있어도 다시 적는다 (일부러 바꿨을 때)
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(여기.parents[1] / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

목록자리 = 여기 / "얼린기준_목록.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def 적기(이름: str) -> dict:
    뿌리 = BASELINE / "실행" / 이름
    if not 뿌리.is_dir():
        raise SystemExit("못 찾음: %s" % 뿌리)          # 「못 찾음」 은 「없음」 이 아니다
    파일 = {p.relative_to(뿌리).as_posix(): _sha(p) for p in sorted(뿌리.rglob("*")) if p.is_file()}
    if not 파일:
        raise SystemExit("비었습니다: %s" % 뿌리)
    return {"파일수": len(파일), "파일": 파일}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    이름들 = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not 이름들:
        print(__doc__)
        print("  지금 기준 자리에 있는 실행: %s"
              % " · ".join(sorted(p.name for p in (BASELINE / "실행").iterdir() if p.is_dir())))
        return 2
    목록 = json.loads(목록자리.read_text(encoding="utf-8"))
    다시 = "--다시" in sys.argv
    더함 = []
    for 이름 in 이름들:
        if 이름 in 목록 and not 다시:
            print("  · %s — 이미 적혀 있습니다 (얼린 기준은 덮지 않습니다 · 다시 적으려면 --다시)" % 이름)
            continue
        목록[이름] = 적기(이름)
        더함.append(이름)
        print("  · %s — 파일 %d개" % (이름, 목록[이름]["파일수"]))
    if not 더함:
        print("  더한 것이 없습니다 (목록에 %d개)" % len(목록))
        return 0
    io.open(목록자리, "w", encoding="utf-8", newline="\n").write(
        json.dumps(목록, ensure_ascii=False, indent=1) + "\n")
    print("  적었습니다 — 모두 %d개 실행" % len(목록))
    return 0


if __name__ == "__main__":
    sys.exit(main())
