# -*- coding: utf-8 -*-
"""옛 판독 꾸러미(VoC_2_2차판독)의 재료를 최신판으로 한 번 복사해 온다 — 섹션 4 (2026-09-18).

★ 한 번만 쓰는 도구다. 기록으로 남긴다. 옛 자리를 **읽기만** 한다 (결정 0001 · 0002).
★ 무엇을 어디서 — 옛 `make_zip.py` 의 PACKS['2_2차판독'] · COMMON · GUIDES 목록 그대로.
  꾸러미 zip 은 쓰지 않는다 — zip 안의 기준서 2·8·9 와 자가점검.py 가 원본보다 옛 판이었다.
★ 글 파일은 줄바꿈만 LF 로 맞춘다 (.gitattributes). 엑셀·워드는 바이트 그대로.
★ 출처와 해시는 `plugin/shared/출처_꾸러미.json` 에 남긴다.

쓰기
    python tools/옛꾸러미_가져오기.py <옛 voc_secondary 자리>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import PLUGIN, SHARED  # noqa: E402

스킬 = PLUGIN / "skills" / "reading-voc-comments"

# (옛 자리 · 저장소 자리) — 기준서 8종은 섹션 3 에서 plugin/shared/standards/ 로 이미 옮겼다
_도구 = ["apply_approved.py", "build_bundle.py", "check_lineage.py", "check_selfcheck.py",
        "check_submission.py", "handoff.py", "run_status.py", "topic_registry.py",
        "verify_quotes.py", "감독_읽기.py", "넘어가도_되나.py", "데이터_넣기.py",
        "보정요청_논의본.py", "성실성검사.py", "시트_붙이기.py", "엔진자리.py",
        "원문대조검사.py", "자가점검.py", "조각덮개검사.py", "지문검사.py", "편향검사.py"]
옮길것 = (
    [(n, SHARED / "tools" / n) for n in _도구]
    + [("s9_group/%s" % n, SHARED / "registry" / n) for n in
       ("topic_group_map.json", "secondary_topics.json", "secondary_enums.json", "topic_registry.json")]
    + [
        ("_판독패키지/7_영상메타.csv", SHARED / "data" / "7_영상메타.csv"),
        ("40_2차판독_수행지시서.md", SHARED / "common" / "40_2차판독_수행지시서.md"),
        ("_판독패키지/_판독대상_안내.md", SHARED / "common" / "_판독대상_안내.md"),
        ("64_VoC_2차_pilot_전체안내.md", SHARED / "common" / "64_VoC_2차_pilot_전체안내.md"),
        ("_설계서/16_VoC_분석엔진_재현설계서_v13.docx", SHARED / "common" / "16_VoC_분석엔진_재현설계서_v13.docx"),
        ("15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx", SHARED / "common" / "15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx"),
        ("_판독패키지/_기준/출력칸목록.txt", SHARED / "common" / "출력칸목록.txt"),
        ("98_전체흐름_1차부터_4차까지.md", SHARED / "common" / "98_전체흐름_1차부터_4차까지.md"),
        ("_배포/VoC_데이터_안내.xlsx", SHARED / "common" / "VoC_데이터_안내.xlsx"),
    ]
    + [(n, SHARED / "guides" / n) for n in
       ("60_2차판독_실무자_사용가이드.md", "61_3차감독_실무자_사용가이드.md",
        "62_4차검토_및_번들해설.md", "63_대시보드_사용설명서.md")]
    + [
        ("_판독패키지/0_붙여넣을_프롬프트_도구형.md", 스킬 / "references" / "0_붙여넣을_프롬프트_도구형.md"),
        ("_판독패키지/0_붙여넣을_프롬프트_이어서.md", 스킬 / "references" / "0_붙여넣을_프롬프트_이어서.md"),
        ("30_VoC_2차_번들환원_사양_v0.1.md", 스킬 / "references" / "30_VoC_2차_번들환원_사양_v0.1.md"),
        ("_판독패키지/_결과/0_여기에_결과가_쌓입니다.md", 스킬 / "assets" / "0_여기에_결과가_쌓입니다.md"),
    ]
)
바이너리 = {".xlsx", ".docx"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    옛 = Path(sys.argv[1])
    엔진 = [(p.relative_to(옛).as_posix(), PLUGIN / p.relative_to(옛))
           for p in sorted((옛 / "engine").rglob("*"))
           if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")]
    기록 = {"설명": "옛 판독 꾸러미 재료의 출처. 옛 make_zip.py 의 목록 그대로 최신 원본에서 복사했다. "
                  "글 파일은 줄바꿈만 LF 로 맞췄고 글자는 바꾸지 않았다. 엑셀·워드는 바이트 그대로.",
            "복사한_날": "2026-09-18",
            "원본_자리": "옛 저장소 github.com/skycloud-maker/youtube-comment-analyzer 의 outputs/voc_secondary "
                     "(갈래 codex/voc-second-stage @ 90078f1, 커밋 안 된 변경 없음)",
            "고칠_때": "고치면 tests/test_package.py 가 실패한다 — 이유를 `고친_이력` 에 적고 `지금_sha256` 을 갱신한다.",
            "파일": {}}
    for 원, 새 in 옮길것 + 엔진:
        src = 옛 / 원
        raw = src.read_bytes()
        body = raw if src.suffix.lower() in 바이너리 else raw.replace(b"\r\n", b"\n")
        새.parent.mkdir(parents=True, exist_ok=True)
        새.write_bytes(body)
        기록["파일"][새.relative_to(PLUGIN.parent).as_posix()] = {
            "원본": 원, "원본_sha256": hashlib.sha256(raw).hexdigest(),
            "지금_sha256": hashlib.sha256(body).hexdigest(), "고친_이력": []}
    (SHARED / "출처_꾸러미.json").write_text(json.dumps(기록, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("옮김 %d개 (엔진 %d개 포함)" % (len(기록["파일"]), len(엔진)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
