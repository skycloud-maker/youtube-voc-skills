# -*- coding: utf-8 -*-
"""메일 자리(`dist/메일/`)를 **지금 판으로 맞춘다** (2026-10-29).

★ 왜 — 2026-10-28 판 2.0.8 의 「못 한 것 ⑤」 가 이것이다. 메일 자리를 **통째로 만드는 도구가
  없어** 사람이 손으로 베껴 두었고, 그래서 판을 올려도 메일 자리에는 **옛 판이 남아** 있었다.
  같은 것이 두 벌이 되면 숫자가 둘이 된다 (공통 규칙 6).

★ 이 도구가 하는 것 — **새로 만들지 않고 맞춘다.**
  ① `Ver2_한줄흐름.zip`      `dist/판/` 것을 **바이트 그대로** 베끼고 지문을 댄다
  ② `0_메일에_붙일_것.md`     `docs/메일_붙일_것.md` 를 베낀다
  ③ `0_점검요청_붙여넣을_것.md` `docs/점검요청_원본과_skill_대조.md` 를 베낀다
  ④ 옛 쪽 zip 둘            `메일_대조자료_갱신.py` 를 불러 **그 안의 대조 자료만** 갈아 끼운다
                            (다시 묶지 않는다 — 나머지는 바이트 그대로 남는다)

★ 안 하는 것 — **옛 쪽 zip 을 새로 만들지 않는다.** 그 안에는 옛 배포 꾸러미와 댓글 원문이
  들어 있고, 그것은 저장소에 없다(801 MB). 없는 것을 만들 수 있다고 하지 않는다.
  그러므로 옛 쪽 zip 이 없으면 **멈춘다** — 「못 찾음」 은 0개가 아니다.

★ 키 값과 댓글 원문은 이 도구가 **만들지도 옮기지도 않는다.** ①②③ 은 저장소 파일을
  베끼는 것뿐이고, ④ 는 이미 있는 zip 안의 글 몇 칸을 갈아 끼운다.

쓰기
    python tools/메일자리_갱신.py            맞춘다
    python tools/메일자리_갱신.py --확인만    무엇이 어긋났는지만 말하고 아무것도 안 고친다
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
메일자리 = REPO / "dist" / "메일"

# 베낄 것 — (메일 자리 이름, 저장소 원본)
베낄것 = {
    "Ver2_한줄흐름.zip": REPO / "dist" / "판" / "Ver2_한줄흐름.zip",
    "0_메일에_붙일_것.md": REPO / "docs" / "메일_붙일_것.md",
    "0_점검요청_붙여넣을_것.md": REPO / "docs" / "점검요청_원본과_skill_대조.md",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def 재어보기() -> list[str]:
    """어긋난 것을 글로 돌려준다 (고치지 않는다)."""
    난것 = []
    for 이름, 원 in 베낄것.items():
        q = 메일자리 / 이름
        if not 원.is_file():
            난것.append("%s — 저장소 원본이 없다 (%s)" % (이름, 원))
        elif not q.is_file():
            난것.append("%s — 메일 자리에 없다" % 이름)
        elif _sha(q) != _sha(원):
            난것.append("%s — 저장소 원본과 다르다" % 이름)
    return 난것


def main(인자: list[str]) -> int:
    확인만 = "--확인만" in 인자
    if not 메일자리.is_dir():
        print("못 찾음: %s 가 없다 — 메일 자리를 먼저 만들어야 한다" % 메일자리)
        print("  (이 도구는 **맞추는** 도구다. 옛 쪽 zip 은 저장소에 없어 새로 만들 수 없다)")
        return 2

    없는원본 = [str(원) for 원 in 베낄것.values() if not 원.is_file()]
    if 없는원본:
        print("못 찾음: 베낄 원본이 없다 — %s" % " · ".join(없는원본))
        print("  `python tools/판_묶기.py` 를 먼저 돌리십시오.")
        return 2

    print("메일 자리 — %s" % 메일자리)
    난것 = 재어보기()
    if not 난것:
        print("  ① ② ③  이미 맞다 — 베낄 것 없음")
    else:
        for ㄹ in 난것:
            print("  ! %s" % ㄹ)
        if not 확인만:
            for 이름, 원 in 베낄것.items():
                shutil.copyfile(원, 메일자리 / 이름)
            남은 = 재어보기()
            if 남은:
                print("  ✗ 베낀 뒤에도 어긋난 것이 남았다 — %s" % 남은)
                return 1
            print("  · %d개를 베꼈다 — 이제 저장소 원본과 지문이 같다" % len(베낄것))

    # ④ 옛 쪽 zip 안의 대조 자료 — 있는 도구를 부른다 (같은 일을 두 벌 적지 않는다)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import 메일_대조자료_갱신 as 갱신개                                   # noqa: PLC0415
    print()
    print("④ 옛 쪽 zip 안의 대조 자료")
    코드 = 갱신개.main(["--확인만"] if 확인만 else [])
    if 코드:
        return 코드

    if 확인만:
        return 1 if 난것 else 0

    # 기록 — 무엇을 어떤 지문으로 넣었나
    기록자리 = 메일자리 / "_기록"
    기록자리.mkdir(exist_ok=True)
    (기록자리 / "_메일자리_갱신.json").write_text(json.dumps({
        "설명": "메일자리_갱신.py 가 적은 것 — 손으로 고치지 않는다",
        "판": json.loads((REPO / "plugin" / ".claude-plugin" / "plugin.json")
                        .read_text(encoding="utf-8"))["version"],
        "베낀것": {이름: {"원본": str(원.relative_to(REPO)).replace("\\", "/"),
                     "sha256": _sha(원)} for 이름, 원 in 베낄것.items()},
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print()
    print("메일 자리에 든 것")
    for q in sorted(메일자리.iterdir()):
        if q.is_file():
            print("  %-26s %7.2f MB" % (q.name, q.stat().st_size / 1048576))
    print("끝 — 종료코드 0")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
