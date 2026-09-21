# -*- coding: utf-8 -*-
"""옛 감독 꾸러미(VoC_3_3차감독)에만 있는 재료를 최신판으로 한 번 복사해 온다 — 섹션 5 (2026-09-21).

★ 판독 꾸러미와 겹치는 재료는 섹션 4 에서 이미 옮겼다 (`tools/옛꾸러미_가져오기.py`).
  여기서는 감독 꾸러미에만 있는 셋만 가져온다. 옛 자리를 **읽기만** 한다.
★ 꾸러미 zip 은 쓰지 않는다 — zip 안의 감독 프롬프트와 rank_two_axis.py 가 원본보다 옛 판이었다
  (08-26 에 더한 「조각은 원래 글을 빠짐없이 덮어야 한다」 규칙 · 없는 파일 안내가 zip 에 없다).
★ 기존 출처 기록(`plugin/shared/출처_꾸러미.json`)의 다른 항목과 `고친_이력` 은 건드리지 않고 더하기만 한다.

쓰기
    python tools/옛꾸러미_가져오기_3차.py <옛 voc_secondary 자리>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import PLUGIN, SHARED  # noqa: E402

스킬 = PLUGIN / "skills" / "supervising-voc-disagreements"
옮길것 = [
    ("_판독패키지/0_붙여넣을_프롬프트_감독.md", 스킬 / "references" / "0_붙여넣을_프롬프트_감독.md"),
    ("rank_two_axis.py", SHARED / "tools" / "rank_two_axis.py"),
    ("make_grading_sheet.py", SHARED / "tools" / "make_grading_sheet.py"),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    옛 = Path(sys.argv[1])
    기록p = SHARED / "출처_꾸러미.json"
    기록 = json.loads(기록p.read_text(encoding="utf-8"))
    for 원, 새 in 옮길것:
        자리 = 새.relative_to(PLUGIN.parent).as_posix()
        if 자리 in 기록["파일"]:
            print("  이미 있어 건너뜀 — %s" % 자리)
            continue
        raw = (옛 / 원).read_bytes()
        body = raw.replace(b"\r\n", b"\n")
        새.parent.mkdir(parents=True, exist_ok=True)
        새.write_bytes(body)
        기록["파일"][자리] = {"원본": 원, "원본_sha256": hashlib.sha256(raw).hexdigest(),
                            "지금_sha256": hashlib.sha256(body).hexdigest(), "고친_이력": [],
                            "복사한_날": "2026-09-21"}
        print("  옮김 — %s" % 자리)
    기록p.write_text(json.dumps(기록, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
