# -*- coding: utf-8 -*-
"""메일로 보낼 **옛 쪽 zip** 안의 대조 자료를 저장소 원본으로 **갈아 끼운다** (2026-10-28).

★ 왜 이 도구가 생겼나 — 판 2.0.8 로 다시 묶다가 찾았다. `대조_원본과_skill.md` 와
  `대조장치/` 6개는 **원본이 저장소 한 벌**인데(공통 규칙 6), 옛 쪽 zip 둘에는
  **2026-10-28 고치기 전의 사본**이 들어 있었다 (문서 13,639 → 지금 22,864 바이트).
  새 쪽 꾸러미(`Ver2_한줄흐름.zip`)는 `tools/판_묶기.py` 가 매번 베껴 담아 늘 맞는데,
  옛 쪽 zip 은 **갈아 끼울 자리가 저장소에 없어** 임시 스크립트로 한 번 넣고 끝이었다.
  그래서 같은 문서가 **한 꾸러미에서는 고쳐지고 다른 꾸러미에서는 안 고쳐졌다.**

★ 다시 묶지 않는다 — 있던 항목을 **바이트 그대로 베끼고** 대조 자료 칸만 갈아 끼운다.
  다시 묶으면 옛 저장소를 또 읽어야 하고, 배포 zip 여섯 개가 바이트로 같다는 보장을
  처음부터 다시 세워야 한다. 베끼면 그 보장이 **구조상** 유지된다.
  (옛 저장소는 「변화 0」 자리다 — 이 도구는 거기를 읽지도 않는다.)

★ 여러 번 돌려도 같다 (쓸 때마다 겹쳐 적히지 않는다). 끝에 **스스로 대 보고**,
  뜻한 칸 말고 바뀐 것이 있으면 **종료코드 1 로 멈춘다.**

쓰기
    python tools/메일_대조자료_갱신.py              dist/메일/ 의 옛 쪽 zip 전부
    python tools/메일_대조자료_갱신.py --확인만      갈아 끼우지 않고 맞는지만 본다
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
메일자리 = REPO / "dist" / "메일"
# 옛 쪽 zip 둘 — 하나는 원문이 든 것, 하나는 원문을 뺀 점검용
옛쪽_zip = ("원본_바탕자료.zip", "점검용_원본바탕자료.zip")
안_뿌리 = "원본_바탕자료"

# 갈아 끼울 칸 — **원본은 저장소 한 벌**이고 여기서 베낀다.
#   ★ `tools/판_묶기.py` 의 `_대조자료` 와 같은 아홉 벌이어야 한다. 아래 시험이 그것을 댄다
#     (`tests/test_메일자료.py::test_옛쪽과_새쪽이_같은_벌을_담는다`).
#     ★ 이 주석이 가리키는 이름이 정말 있는지 그 파일의
#       `test_가리킨_시험이름이_정말_있다` 가 댄다 — 전에 **없는 파일을 가리켰다.**
#     ★ 2026-10-29 — 이 주석이 가리키던 **그 파일이 없었다.** 가리키기만 하고 없는
#       가드였다 (꾸러미 안내가 없는 `.ps1` 을 가리킨 것과 같은 갈래). 이제 있다.
갈아끼울것 = {
    "대조_원본과_skill.md": REPO / "docs" / "대조_원본과_skill.md",
    "대조장치/얼린기준_목록.json": REPO / "tests" / "baseline" / "얼린기준_목록.json",
    "대조장치/맞대기.py": REPO / "tests" / "baseline" / "맞대기.py",
    "대조장치/기준_만들기.py": REPO / "tests" / "baseline" / "기준_만들기.py",
    "대조장치/기준_만들기_2차.py": REPO / "tests" / "baseline" / "기준_만들기_2차.py",
    "대조장치/보고서기준_만들기.py": REPO / "tests" / "baseline" / "보고서기준_만들기.py",
    "대조장치/test_baseline.py": REPO / "tests" / "test_baseline.py",
    # ★ 2026-10-29 — 「안 옮긴 것」 을 세는 대장. 점검요청 문서가 이 둘을 가리킨다
    "옛꾸러미_대장.md": REPO / "docs" / "옛꾸러미_대장.md",
    "옛꾸러미_목록.json": REPO / "docs" / "옛꾸러미_목록.json",
}

안내자리 = "0_읽어주세요.md"

# ★ 안내문 ④ 의 가운데 세 줄 — 여기에도 **은퇴한 틀린 말**이 들어 있었다 (F01).
#   「대조 시험 25개」 와 「허용한 차이가 brand_display 와 거기서 파생되는 칸뿐」 이다.
#   옛 글을 무늬로 찾아 새 글로 바꾼다. 못 찾으면 **조용히 넘어가지 않고 멈춘다.**
옛_안내꼴 = re.compile(
    r"파일 전량 대어 본 것\(파일 2,167개분 · 대조 시험 \d+개\), 허용한 차이가 "
    r"`brand_display` 와\n거기서 파생되는 칸뿐이고 \*\*몇 칸이 다른지까지 못 박았다\*\*는 "
    r"것이 거기 적혀 있습니다\.")
새_안내글 = (
    "파일 전량 대어 본 것(파일 2,167개분 · 대조 시험 26개)이 거기 적혀 있습니다.\n"
    "\n"
    "★ **2026-10-28 고침** — 전에 이 자리에 「허용한 차이가 `brand_display` 와 거기서\n"
    "  파생되는 칸뿐」 이라고 적었습니다. 그것은 **얼린 기준을 재현할 때**의 이야기이고,\n"
    "  **기본으로 돌릴 때는 N/A·미분류 처리가 하나 더 다릅니다**(사람이 정한 변경입니다).\n"
    "  그리고 AI 가 판정하는 세 자리는 **정확도를 아직 못 잽니다** — 채점할 정답지가\n"
    "  빈 칸입니다. 독립 점검에서 지적받아 고쳤고, 고친 글이 그 문서에 들어 있습니다.")


def _sha(바이트: bytes) -> str:
    return hashlib.sha256(바이트).hexdigest()


def _새안내(글: str, 이름: str) -> str:
    """안내문 ④ 의 은퇴한 말을 새 글로 바꾼다. 이미 바뀐 글이면 그대로 돌려준다."""
    if 새_안내글.splitlines()[0] in 글:
        return 글                                   # 이미 갈아 끼웠다 — 또 쓰지 않는다
    새, 몇 = 옛_안내꼴.subn(새_안내글, 글)
    if 몇 != 1:
        raise SystemExit(
            "못 찾음: %s 의 `%s` 에서 갈아 끼울 안내 줄을 %d개 찾았다 (1개여야 한다).\n"
            "  안내문이 바뀌었으면 이 도구의 `옛_안내꼴` 도 같이 고쳐야 한다 — "
            "조용히 넘어가지 않는다." % (이름, 안내자리, 몇))
    return 새


def 재어보기(zip길: Path) -> list[str]:
    """zip 안의 대조 자료가 저장소 원본과 같은가. 다른 것을 **글로** 돌려준다."""
    다름: list[str] = []
    with zipfile.ZipFile(zip길) as zf:
        속 = set(zf.namelist())
        for 안, 원 in 갈아끼울것.items():
            키 = "%s/%s" % (안_뿌리, 안)
            if 키 not in 속:
                다름.append("%s — 꾸러미에 **없다**" % 안)
                continue
            ㄱ, ㄴ = _sha(zf.read(키)), _sha(원.read_bytes())
            if ㄱ != ㄴ:
                다름.append("%s — 꾸러미 %s / 저장소 %s" % (안, ㄱ[:16], ㄴ[:16]))
        키 = "%s/%s" % (안_뿌리, 안내자리)
        if 키 not in 속:
            다름.append("%s — 꾸러미에 **없다**" % 안내자리)
        elif 새_안내글.splitlines()[0] not in zf.read(키).decode("utf-8"):
            다름.append("%s — 은퇴한 안내 글이 그대로다 (2026-10-28 고침 전)" % 안내자리)
    return 다름


def 갱신(zip길: Path) -> int:
    """대조 자료 칸만 갈아 끼운다. 나머지는 바이트 그대로 베낀다. 바꾼 칸 수를 돌려준다."""
    없는원본 = [str(원) for 원 in 갈아끼울것.values() if not 원.is_file()]
    if 없는원본:
        raise SystemExit("못 찾음: 담을 원본이 없다 — %s" % " · ".join(없는원본))

    임시 = zip길.with_suffix(".갱신중.zip")
    바뀜 = 0
    본것: set = set()        # 옛 zip 에 이미 있던 대조 자료 이름
    더함: list = []          # 없어서 **더해 넣은** 항목 (전체 이름)
    with zipfile.ZipFile(zip길) as 옛, \
         zipfile.ZipFile(임시, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as 새:
        for i in 옛.infolist():
            재료 = 옛.read(i)
            짧은 = i.filename[len(안_뿌리) + 1:] if i.filename.startswith(안_뿌리 + "/") else ""
            if 짧은 in 갈아끼울것:
                새재료 = 갈아끼울것[짧은].read_bytes()
                if _sha(새재료) != _sha(재료):
                    바뀜 += 1
                    print("     · %-34s %6d → %6d 바이트" % (짧은, len(재료), len(새재료)))
                재료 = 새재료
            elif 짧은 == 안내자리:
                글 = _새안내(재료.decode("utf-8"), zip길.name)
                새재료 = 글.encode("utf-8")
                if _sha(새재료) != _sha(재료):
                    바뀜 += 1
                    print("     · %-34s %6d → %6d 바이트" % (짧은, len(재료), len(새재료)))
                재료 = 새재료
            새.writestr(i, 재료, zipfile.ZIP_DEFLATED)
            본것.add(짧은)

        # ★ 2026-10-29 — 전에는 **갈아 끼우기만** 했다. 대조 자료가 7벌에서 9벌로 늘었을 때
        #   옛 쪽 zip 에 없는 둘을 **넣을 수가 없어** 「꾸러미에 없다」 로 끝까지 남았다.
        #   「맞추는 도구」 가 맞출 수 없으면 도구가 아니다 — **없는 것은 더해 넣는다.**
        #   (옛 쪽 zip 을 **새로 만드는** 것은 여전히 안 한다. 있는 항목은 바이트 그대로 베낀다)
        for 짧은, 원 in 갈아끼울것.items():
            if 짧은 in 본것:
                continue
            더함.append("%s/%s" % (안_뿌리, 짧은))
            새.writestr(더함[-1], 원.read_bytes(), zipfile.ZIP_DEFLATED)
            바뀜 += 1
            print("     + %-34s %6d 바이트 (없어서 **더해 넣었다**)" % (짧은, 원.stat().st_size))

    # ★ 뜻한 칸 말고 바뀐 것이 있으면 멈춘다 — 베끼다 흘린 것이 없는지 **항목마다** 댄다
    뜻한것 = {"%s/%s" % (안_뿌리, k) for k in list(갈아끼울것) + [안내자리]}
    흘린것 = []
    with zipfile.ZipFile(zip길) as 옛, zipfile.ZipFile(임시) as 새:
        ㄱ, ㄴ = 옛.namelist(), 새.namelist()
        if ㄴ != ㄱ + 더함:
            임시.unlink(missing_ok=True)
            raise SystemExit("항목 목록이 **뜻한 것과 다르게** 달라졌다 (%d → %d · 더한 것 %d) — 멈춘다"
                             % (len(ㄱ), len(ㄴ), len(더함)))
        for n in ㄱ:
            if n in 뜻한것:
                continue
            if _sha(옛.read(n)) != _sha(새.read(n)):
                흘린것.append(n)
    if 흘린것:
        임시.unlink(missing_ok=True)
        raise SystemExit("뜻하지 않은 칸이 바뀌었다 (%d개) — 멈춘다\n  %s"
                         % (len(흘린것), "\n  ".join(흘린것[:10])))

    shutil.move(str(임시), str(zip길))
    return 바뀜


def main(인자: list[str]) -> int:
    확인만 = "--확인만" in 인자
    if not 메일자리.is_dir():
        print("못 찾음: %s 가 없다 — 메일 자리를 먼저 만들어야 한다" % 메일자리)
        return 2
    있는것 = [메일자리 / n for n in 옛쪽_zip if (메일자리 / n).is_file()]
    if not 있는것:
        # ★ 「못 찾음」 은 통과가 아니다
        print("못 찾음: %s 에 옛 쪽 zip 이 하나도 없다 — %s" % (메일자리, " · ".join(옛쪽_zip)))
        return 2

    탈났나 = False
    for z in 있는것:
        print("  %s" % z.name)
        전 = 재어보기(z)
        if not 전:
            print("     이미 맞다 — 갈아 끼울 것 없음")
            continue
        print("     맞지 않는 것 %d개:" % len(전))
        for ㄹ in 전:
            print("       - %s" % ㄹ)
        if 확인만:
            탈났나 = True
            continue
        바뀜 = 갱신(z)
        남은 = 재어보기(z)
        if 남은:
            print("     ★ 갈아 끼운 뒤에도 맞지 않는다:")
            for ㄹ in 남은:
                print("       - %s" % ㄹ)
            탈났나 = True
        else:
            print("     갈아 끼웠다 — %d칸 · 이제 저장소 원본과 같다" % 바뀜)
    if 탈났나:
        print("끝 — 맞지 않는 것이 남았다 (종료코드 1)")
        return 1
    print("끝 — 종료코드 0")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main(sys.argv[1:]))
