# -*- coding: utf-8 -*-
"""건드리면 안 되는 파일이 바뀌었는지 **사실로** 확인한다.

★ 왜 있는가 (sky 2026-08-22)
  「절대 건드리면 안되는것과 그래도 수정하여 분석작업 진행해도 되는것을
    구분해야하는데 당신이 분리하는데 실수하시면 어떻게해요..?」

  옳은 물음이다. 나는 목록으로 갈랐다 —
    「도구 로직·기준서·택소노미는 안 되고, 파이썬·패키지는 된다」
  그런데 **그 목록이 틀리면 아무도 못 잡는다.** 새 상황은 목록에 없다.
  오늘만 해도 내가 네 번 잘못 갈랐다.

  그래서 목록에 기대지 않는다. **바뀌었다는 사실 자체**를 잡는다.

    꾸러미를 만들 때  건드리면 안 되는 파일의 지문(sha256)을 떠 둔다
    판독이 끝날 때    다시 떠서 견준다 — 하나라도 다르면 반려

  ★ 이러면 내가 무엇을 「고쳐도 된다」 고 잘못 말했어도,
    그 파일이 실제로 바뀌면 드러난다. 내 판단에 안 기댄다.

  ★ 「고쳐도 되는 것」 은 애초에 꾸러미 밖이다 —
    파이썬·패키지·인코딩은 이 폴더 안에 없다. 그래서 지문이 안 흔들린다.

쓰기
    python 지문검사.py            지금 지문을 떠서 견준다
    python 지문검사.py --만들기    지금 것으로 지문을 새로 뜬다 (총괄만)

하나라도 다르면 종료코드 1.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent if _HERE.name in ("스크립트", "scripts") else _HERE

# 건드리면 안 되는 자리 — 판정에 영향을 준다
# ★ 「누구도 바꿀 이유가 없는 것」 만 지킨다 (2026-08-22).
#   처음엔 판독대상·회차배치·대장까지 지키게 했더니 손도 안 댄 꾸러미가
#   반려로 나왔다. 그 셋은 판독 흐름이 **정당하게** 바꾸는 자리다 —
#     판독대상·회차배치  `데이터_넣기.py` 가 엑셀을 앉히며 새로 만든다
#     대장             `topic_registry --register` 가 신설 라벨을 등록한다
#   헛경보도 사고다.
지킬곳 = [
    ("스크립트", "*.py", "판독 도구"),
    ("판독패키지", "*", "판정 기준 (기준서·택소노미·데이터사전)"),
    ("공통", "*", "정본 문서"),
    ("프롬프트", "*.md", "붙여넣는 글"),
    # ★ 1차 엔진 사본 — 동결본이다. 판독자가 고치면 드러나야 한다.
    ("engine", "**/*.py", "1차 분석엔진 (읽기 전용)"),
]

지문파일 = "대장/지문.json"

# ★ 돌리면서 저절로 생기는 것은 뺀다 — 이것까지 잡으면 헛경보다
건너뜀 = {"__pycache__", "지문.json", "_쓰기시험.tmp"}


찾은자리: list[str] = []      # ★ 실제로 본 자리 — 「이상 없음」 을 말해도 되는지 가른다


def 지문뜨기() -> dict[str, str]:
    나온것: dict[str, str] = {}
    찾은자리.clear()
    for 폴더, 무늬, _ in 지킬곳:
        바탕 = ROOT / 폴더
        if not 바탕.is_dir():
            continue
        찾은자리.append(폴더)
        for 길 in sorted(바탕.glob(무늬)):
            if not 길.is_file():
                continue
            if 건너뜀 & set(길.parts) or 길.name in 건너뜀:
                continue
            # ★ 줄바꿈(CRLF/LF)이 판마다 달라 지문이 흔들린 적이 있다.
            #   글자만 보고, 줄바꿈은 하나로 맞춰 센다
            바이트 = 길.read_bytes()
            try:
                글 = 바이트.decode("utf-8")
                재료 = 글.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            except UnicodeDecodeError:
                재료 = 바이트
            상대 = 길.relative_to(ROOT).as_posix()
            나온것[상대] = hashlib.sha256(재료).hexdigest()[:16]
    return 나온것


def main() -> int:
    지금 = 지문뜨기()
    자리 = ROOT / 지문파일

    # ★ 아무것도 안 보고 「이상 없음」 이라 하지 않는다 (2026-08-23).
    #   개발 폴더에서 파일 1개만 보고 이상 없다고 한 적이 있다.
    if len(찾은자리) < len(지킬곳) - 1:
        print("=" * 70)
        print("  ★ 지킬 자리를 못 찾았습니다 — %d곳 중 %d곳만 있습니다"
              % (len(지킬곳), len(찾은자리)))
        for _폴더, _, _쓰임 in 지킬곳:
            print("     %s %-12s %s"
                  % ("있음" if _폴더 in 찾은자리 else "  ✗ ", _폴더, _쓰임))
        print()
        print("  이 폴더는 판독 꾸러미가 아닙니다.")
        print("  꾸러미를 푼 폴더에서 돌리십시오 — 검사한 척하지 않습니다.")
        print("=" * 70)
        return 1

    if "--만들기" in sys.argv:
        # ★ 다시 뜬 사실을 숨길 수 없게 이력을 남긴다 (sky 2026-08-22).
        #   이 명령이 꾸러미 안에도 들어가므로, 판독자가 도구를 고친 뒤
        #   이것을 돌리면 지문이 새로 떠져 아무도 모르게 된다.
        #   막지는 않는다 — 총괄이 정당하게 다시 떠야 할 때가 있다.
        #   대신 **몇 번 다시 떴는지**를 남기고, 검사가 먼저 말한다.
        이력자리 = 자리.parent / "지문_이력.json"
        이력 = []
        if 이력자리.exists():
            try:
                이력 = json.loads(이력자리.read_text(encoding="utf-8"))
            except Exception:
                이력 = []
        옛것 = {}
        if 자리.exists():
            try:
                옛것 = json.loads(자리.read_text(encoding="utf-8"))
            except Exception:
                옛것 = {}
        이제 = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
        if 옛것:
            바뀐것 = sorted(k for k, v in 지금.items()
                          if (옛것.get("지문") or {}).get(k) not in (None, v))
            이력.append({"언제": 이제, "옛것을_뜬날": 옛것.get("뜬날"),
                        "바뀐파일수": len(바뀐것), "바뀐것": 바뀐것[:20]})
            이력자리.write_text(json.dumps(이력, ensure_ascii=False, indent=1),
                             encoding="utf-8")

        자리.parent.mkdir(parents=True, exist_ok=True)
        자리.write_text(json.dumps(
            {"뜬날": 이제, "파일수": len(지금), "다시뜬횟수": len(이력),
             "지문": 지금},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("지문을 떴습니다 — 파일 %d개 → %s" % (len(지금), 지문파일))
        if 이력:
            print("★ 이 꾸러미에서 지문을 다시 뜬 것은 %d번째입니다." % len(이력))
            print("  마지막에 바뀐 파일 %d개 — 이력은 대장/지문_이력.json 에 남습니다."
                  % 이력[-1]["바뀐파일수"])
            print("  ※ 판독자는 이 명령을 쓰지 않습니다. 총괄만 씁니다.")
        return 0

    print("=" * 70)
    print("  지문 검사 — 건드리면 안 되는 것이 바뀌지 않았는가")
    print("=" * 70)

    if not 자리.exists():
        print("  ! 지문 파일이 없습니다 (%s)" % 지문파일)
        print("    옛 꾸러미이거나, 총괄이 아직 안 뜬 것입니다.")
        print("    이 검사만 건너뜁니다 — 판독은 하셔도 됩니다.")
        print("=" * 70)
        return 0

    옛것 = json.loads(자리.read_text(encoding="utf-8"))
    옛지문 = 옛것.get("지문", {})
    print("  기준: %s 에 뜬 것 · 파일 %d개" % (옛것.get("뜬날", "?"), len(옛지문)))

    # ★ 지문을 다시 뜬 적이 있으면 먼저 말한다 (sky 2026-08-22).
    #   그래야 「고치고 지문을 다시 떠서 덮은 것」 이 숨지 않는다
    이력자리 = 자리.parent / "지문_이력.json"
    if 이력자리.exists():
        try:
            이력 = json.loads(이력자리.read_text(encoding="utf-8"))
        except Exception:
            이력 = []
        if 이력:
            print()
            print("  ★ 이 꾸러미는 지문을 %d번 다시 떴습니다." % len(이력))
            for 칸 in 이력[-3:]:
                print("     %s · 바뀐 파일 %d개" % (칸.get("언제", "?"),
                                                칸.get("바뀐파일수", 0)))
            print("     총괄이 한 것이면 정상입니다.")
            print("     ※ 판독자는 `--만들기` 를 쓰지 않습니다. 썼다면 물어보십시오.")
    print()

    바뀜 = [k for k in 옛지문 if k in 지금 and 지금[k] != 옛지문[k]]
    사라짐 = [k for k in 옛지문 if k not in 지금]
    새로생김 = [k for k in 지금 if k not in 옛지문]

    if not (바뀜 or 사라짐):
        print("  · 건드리면 안 되는 파일 %d개가 그대로입니다" % len(옛지문))
        if 새로생김:
            print("  · 새로 생긴 파일 %d개 (돌리면서 생긴 것일 수 있습니다)"
                  % len(새로생김))
            for k in 새로생김[:5]:
                print("       %s" % k)
        print()
        print("=" * 70)
        print("  이상 없음")
        print("=" * 70)
        return 0

    print("  ★ 바뀐 파일이 있습니다 — 판정에 영향을 주는 자리입니다")
    print()
    for k in 바뀜[:15]:
        print("     [바뀜]   %s" % k)
    for k in 사라짐[:10]:
        print("     [사라짐] %s" % k)
    if len(바뀜) + len(사라짐) > 25:
        print("     … 그 밖 %d개" % (len(바뀜) + len(사라짐) - 25))
    print()
    print("=" * 70)
    print("  ★ 이 판독은 다른 판독자와 견줄 수 없습니다.")
    print()
    print("  판독자가 도구나 기준을 고쳤다는 뜻입니다.")
    print("  고칠 수 있는 것은 이 폴더 **밖**에 있습니다 —")
    print("  파이썬·패키지·인코딩은 여기 없으므로 지문이 흔들리지 않습니다.")
    print()
    print("  이 화면을 그대로 시스템 담당자에게 보내십시오.")
    print("  총괄이 판단합니다 — 되돌릴지, 그 고침을 모두에게 반영할지.")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
