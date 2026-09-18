# -*- coding: utf-8 -*-
"""2차 판독 작업 폴더를 차린다 — 옛 판독 꾸러미(VoC_2_2차판독.zip)를 푼 것과 같은 모양으로.

★ 왜 (sky 2026-09-18 결정 「폴더 차려 주고 원래 프롬프트 그대로」)
  판독 프롬프트(references/0_붙여넣을_프롬프트_도구형.md)와 도구들은 이 모양의 폴더를
  전제로 쓰였고, 그 모양에서 검증됐다. 모양을 그대로 차려 주면 한 글자도 고치지 않고 돈다.

★ 무엇을 어디에 — 옛 make_zip.py 의 PACKS['2_2차판독'] · COMMON · engine · GUIDES ·
  판독대상 목록 그대로 (`차림표` 아래). 재료는 이 플러그인의 최신판이다.
  `0_먼저_읽으십시오.md` 와 `대장/지문.json` 은 옛 make_zip.py 의 readme() · 꾸러미_지문() 을
  옮겨 와 같은 방식으로 만든다.

★ 이미 있는 파일은 **건드리지 않는다.** 판독 중에 정당하게 바뀌는 것(판독대상 · 회차배치 · 대장 ·
  _결과)을 덮으면 판독이 망가진다. 없는 것만 채운다. 다시 돌려도 안전하다.

쓰기
    python <이 스킬>/scripts/판독폴더_차리기.py <작업 폴더>
끝나면 차린 것 · 이미 있던 것 · 못 찾은 재료 수를 알린다. 못 찾은 재료가 있으면 종료코드 1.
"""
from __future__ import annotations

import datetime as _d
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]


def _찾기(이름: str) -> Path:
    """공통 재료 자리 — 플러그인 안에서는 ../../<이름>, 낱개 스킬로 꾸리면 스킬 안 <이름>."""
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름          # 없으면 아래에서 「못 찾은 재료」 로 드러난다


공통 = _찾기("shared")
엔진 = _찾기("engine")
참고 = 스킬 / "references"

_도구 = ["build_bundle.py", "check_selfcheck.py", "check_submission.py", "check_lineage.py",
        "topic_registry.py", "run_status.py", "감독_읽기.py", "handoff.py", "엔진자리.py",
        "넘어가도_되나.py", "보정요청_논의본.py", "시트_붙이기.py", "편향검사.py",
        "apply_approved.py", "verify_quotes.py", "자가점검.py", "성실성검사.py",
        "조각덮개검사.py", "원문대조검사.py", "지문검사.py", "데이터_넣기.py"]
_기준서 = ["1a_기준문서_정본_1부.md", "1b_기준문서_정본_2부.md", "2_택소노미.md",
          "3_데이터사전_Enum.md", "4_2차_확장부록.md", "6_판정대상_컬럼분류.md",
          "8_topic_그룹.md", "9_택소노미_2차확장.md"]

# (재료, 작업 폴더 안 자리) — 옛 make_zip.py 에 담긴 차례 그대로
차림표 = (
    [(참고 / "0_붙여넣을_프롬프트_도구형.md", "프롬프트/0_붙여넣을_프롬프트_도구형.md"),
     (참고 / "0_붙여넣을_프롬프트_이어서.md", "프롬프트/0_붙여넣을_프롬프트_이어서.md")]
    + [(공통 / "standards" / n, "판독패키지/" + n) for n in _기준서[:6]]
    + [(공통 / "data" / "7_영상메타.csv", "판독패키지/7_영상메타.csv")]
    + [(공통 / "standards" / n, "판독패키지/" + n) for n in _기준서[6:]]
    + [(참고 / "30_VoC_2차_번들환원_사양_v0.1.md", "판독패키지/30_VoC_2차_번들환원_사양_v0.1.md"),
       (공통 / "common" / "40_2차판독_수행지시서.md", "공통/40_2차판독_수행지시서.md")]
    + [(공통 / "tools" / n, "스크립트/" + n) for n in _도구]
    + [(스킬 / "assets" / "0_여기에_결과가_쌓입니다.md", "_판독패키지/_결과/0_여기에_결과가_쌓입니다.md")]
    + [(공통 / "registry" / n, "대장/" + n) for n in
       ("topic_group_map.json", "secondary_topics.json", "secondary_enums.json", "topic_registry.json")]
    # COMMON
    + [(공통 / "common" / "64_VoC_2차_pilot_전체안내.md", "0_전체안내.md"),
       (공통 / "common" / "16_VoC_분석엔진_재현설계서_v13.docx", "공통/16_VoC_분석엔진_재현설계서_v13.docx"),
       (공통 / "common" / "15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx", "공통/15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx"),
       (공통 / "common" / "출력칸목록.txt", "공통/출력칸목록.txt"),
       (공통 / "common" / "98_전체흐름_1차부터_4차까지.md", "0_전체흐름_누가_무엇을.md"),
       (공통 / "common" / "VoC_데이터_안내.xlsx", "공통/VoC_데이터_안내.xlsx")]
)


def _엔진목록():
    if not 엔진.is_dir():
        return [(엔진 / "src", "engine/src")]       # 못 찾은 재료로 드러나게
    return [(p, "engine/" + p.relative_to(엔진).as_posix())
            for p in sorted(엔진.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")]


def 전체_차림표():
    return (차림표 + _엔진목록()
            + [(공통 / "guides" / n, "가이드/" + n) for n in
               ("60_2차판독_실무자_사용가이드.md", "61_3차감독_실무자_사용가이드.md",
                "62_4차검토_및_번들해설.md", "63_대시보드_사용설명서.md")]
            + [(공통 / "common" / "_판독대상_안내.md", "판독대상/0_이_폴더는.md")])


# ── 옛 make_zip.py 에서 옮겨 온 것 (고치지 않았다 — 이 꾸러미 하나만 남겼다) ──────────
SPEC = {'설명': '2차 LLM 판독자를 돌리는 데 필요한 전부입니다.',
        '차수': '2차 · 판독자 LLM 둘',
        '가이드': ('60_2차판독_실무자_사용가이드.md', '1_사용가이드.md')}


def 꾸러미_지문(담긴것):
    """담은 파일 중 「건드리면 안 되는 것」 의 지문을 뜬다.

    ★ 지문검사.py 와 같은 자리·같은 방식이어야 한다.
      줄바꿈(CRLF/LF)은 하나로 맞춰 센다 — 판마다 달라 흔들린 적이 있다.
    """
    import hashlib as _h
    import json as _j

    # ★ 지문검사.py 와 같아야 한다 — 「누구도 바꿀 이유가 없는 것」 만
    #   판독대상·회차배치·대장은 판독 흐름이 정당하게 바꾼다. 빼야 한다
    볼곳 = ('스크립트/', '판독패키지/', '공통/', '프롬프트/')
    지문 = {}
    for 원본, 자리 in 담긴것:
        n = 자리.replace(os.sep, '/')
        if not n.startswith(볼곳):
            continue
        if '__pycache__' in n or n.endswith('지문.json'):
            continue
        if n.startswith('스크립트/') and not n.endswith('.py'):
            continue
        try:
            재료 = open(원본, 'rb').read()
        except OSError:
            continue
        try:
            재료 = 재료.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        except UnicodeDecodeError:
            pass
        지문[n] = _h.sha256(재료).hexdigest()[:16]
    return _j.dumps({'뜬날': _d.datetime.now().strftime('%Y-%m-%d %H:%M'),
                     '파일수': len(지문), '지문': 지문},
                    ensure_ascii=False, indent=1)


def readme(name, spec, files):
    L = ['# %s\n' % spec['차수'], spec['설명'], '',
         '기준 2026-08-19 · VoC 2차 판독 pilot 1차 완료본\n', '---\n',
         # ★ 첫 벽은 「AI 에게 이 폴더를 어떻게 열어 주나」 다 (sky 2026-08-22)
         '## ★ 시작하는 법 — 세 줄\n', '```',
         '1. 이 폴더 빈 곳에서 마우스 오른쪽 → 「터미널에서 열기」',
         '   (안 보이면 「추가 옵션 표시」 를 먼저)',
         '2. 까만 창에   claude   또는   codex   를 치고 Enter',
         '3. 프롬프트/ 안의 글을 통째로 붙여넣기',
         '',
         '★ 그다음은 AI 가 알아서 합니다. 명령어를 치실 일이 없습니다',
         '```\n',
         '## 먼저 여십시오\n', '```', '가이드/%s' % os.path.basename(spec['가이드'][0]),
         '   ★ 여기에 무엇을 어떤 순서로 하는지 다 적혀 있습니다', '```\n',
         '## 이 꾸러미에 든 것\n', '```']
    for f in sorted(files):
        L.append('  %s' % f)
    L += ['```\n', '## 정본이 무엇인지\n', '```',
          '공통/재현설계서_v13.docx        ★ 문서끼리 어긋나면 이것이 이깁니다',
          '공통/데이터사전_v3.2_90컬럼.xlsx  칸 90개의 정의',
          '0_전체안내.md                   프로젝트 전체 지도', '```\n',
          '## 규칙이 없거나 이상하면\n', '```',
          '★ 그 자리에서 고치지 마십시오.',
          '  판독자는 「무엇이 없었는지」 를 적어서 넘기고,',
          '  실무자는 보정요청서를 시스템 담당자에게 전달합니다.',
          '  수정은 총괄이 다음 판에 반영합니다', '```']
    return '\n'.join(L)
# ─────────────────────────────────────────────────────────────────────────


def 차리기(작업: Path) -> dict:
    작업.mkdir(parents=True, exist_ok=True)
    셈 = {"차림": 0, "이미있음": 0, "못찾음": []}
    담긴것, 목록 = [], []
    for 원, 자리 in 전체_차림표():
        if not Path(원).is_file():
            셈["못찾음"].append(자리)
            continue
        담긴것.append((str(원), 자리))
        목록.append(자리)
        q = 작업 / 자리
        if q.exists():
            셈["이미있음"] += 1
            continue
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(원, q)
        셈["차림"] += 1
    목록.append("대장/지문.json")
    for 자리, 글 in (("대장/지문.json", lambda: 꾸러미_지문(담긴것)),
                    ("0_먼저_읽으십시오.md", lambda: readme("2_2차판독", SPEC, 목록))):
        q = 작업 / 자리
        if q.exists():
            셈["이미있음"] += 1
            continue
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(글().encode("utf-8"))
        셈["차림"] += 1
    return 셈


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    작업 = Path(sys.argv[1]).resolve()
    셈 = 차리기(작업)
    print("  판독 폴더 — %s" % 작업)
    print("  차림 %d개 · 이미 있어 그대로 둠 %d개" % (셈["차림"], 셈["이미있음"]))
    if 셈["못찾음"]:
        print("  ✗ 재료를 못 찾았습니다 %d개 — 스킬이 온전하지 않습니다:" % len(셈["못찾음"]))
        for x in 셈["못찾음"][:10]:
            print("     · %s" % x)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
