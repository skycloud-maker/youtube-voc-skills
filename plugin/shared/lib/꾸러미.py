# -*- coding: utf-8 -*-
"""역할별 작업 폴더를 옛 배포 꾸러미를 푼 것과 같은 모양으로 차린다 — 한 벌 (섹션 5 · 2026-09-21).

★ 왜 한 벌인가 — 판독(2차) · 감독(3차) 스킬이 같은 일을 한다. 스킬마다 사본을 두면 한쪽만 고쳐
  갈린다 (옛 저장소에서 겪었다). 스킬의 scripts/ 는 이것을 부르기만 한다.
★ 무엇을 어디에 — 옛 make_zip.py 의 PACKS · COMMON · engine · GUIDES · 판독대상 목록 그대로.
  재료는 이 플러그인의 최신판이다. `0_먼저_읽으십시오.md` 와 `대장/지문.json` 은
  옛 make_zip.py 의 readme() · 꾸러미_지문() 을 옮겨 와 같은 방식으로 만든다.
★ 이미 있는 파일은 **건드리지 않는다** — 판독·감독 중에 정당하게 바뀌는 것을 덮으면 망가진다.
★ 옛 make_zip 과 다르게 한 것 (까닭은 각 자리에 적었다)
  ① 지문에 engine/ 을 넣는다 (2026-09-21 교차점검 — 엔진을 고쳐도 통과하던 구멍)
  ② 감독 꾸러미에서 편향검사.py 를 뺀다 (98 전체흐름 08-25 「감독 폴더에는 편향검사가 아예 없습니다」.
     make_zip 에는 08-23 에 들어간 채 남아 있었다 — 최신판이 정본)
"""
from __future__ import annotations

import datetime as _d
import os
import re
import shutil
from pathlib import Path

_기준서 = ["1a_기준문서_정본_1부.md", "1b_기준문서_정본_2부.md", "2_택소노미.md",
          "3_데이터사전_Enum.md", "4_2차_확장부록.md", "6_판정대상_컬럼분류.md",
          "8_topic_그룹.md", "9_택소노미_2차확장.md"]
# ★ 새 저장소가 쓴 새 판 — 옛 꾸러미에 없던 파일이다. 판독 · 감독 폴더에 다 넣는다 (섹션 5b · sky 2026-09-22
#   「뒤에 스텝이 남아 있다고 판독을 부족하게 끝내면 안 된다」). 원래 기준서보다 먼저 읽힌다 — 스킬 SKILL.md 가 그렇게 시킨다
최신결정 = "0_최신결정_먼저.md"

# ── 꾸러미별 목록 — 옛 make_zip.py 의 PACKS 차례 그대로 ─────────────────────────
_판독도구 = ["build_bundle.py", "check_selfcheck.py", "check_submission.py", "check_lineage.py",
           "topic_registry.py", "run_status.py", "감독_읽기.py", "handoff.py", "엔진자리.py",
           "넘어가도_되나.py", "보정요청_논의본.py", "시트_붙이기.py", "편향검사.py",
           "apply_approved.py", "verify_quotes.py", "자가점검.py", "성실성검사.py",
           "조각덮개검사.py", "원문대조검사.py", "지문검사.py", "데이터_넣기.py",
           "최신결정_검사.py"]           # ★ 섹션 5b 새 도구 — 옛 꾸러미에 없다 (0_최신결정_먼저.md 의 라1~라8)
# 감독 꾸러미 도구 — make_zip 차례 그대로에서 편향검사.py 만 뺐다 (위 ②)
_감독도구 = ["감독_읽기.py", "build_bundle.py", "check_selfcheck.py", "rank_two_axis.py",
           "topic_registry.py", "make_grading_sheet.py", "handoff.py", "엔진자리.py",
           "넘어가도_되나.py", "보정요청_논의본.py", "시트_붙이기.py",
           "자가점검.py", "성실성검사.py", "조각덮개검사.py", "원문대조검사.py", "지문검사.py",
           "데이터_넣기.py"]

SPEC = {
    "2_2차판독": {'설명': '2차 LLM 판독자를 돌리는 데 필요한 전부입니다.',
                '차수': '2차 · 판독자 LLM 둘',
                '가이드': ('60_2차판독_실무자_사용가이드.md', '1_사용가이드.md')},
    "3_3차감독": {'설명': '3차 LLM 감독자(감독자)를 돌리는 데 필요한 전부입니다.',
                '차수': '3차 · 감독자 LLM 둘',
                '가이드': ('61_3차감독_실무자_사용가이드.md', '1_사용가이드.md')},
}


def 꾸러미파일(이름: str, 공통: Path, 참고: Path, 틀: Path) -> list:
    """PACKS[이름]['파일'] — (재료, 자리). 참고 = 스킬의 references, 틀 = 스킬의 assets."""
    if 이름 == "2_2차판독":
        return ([(참고 / "0_붙여넣을_프롬프트_도구형.md", "프롬프트/0_붙여넣을_프롬프트_도구형.md"),
                 (참고 / "0_붙여넣을_프롬프트_이어서.md", "프롬프트/0_붙여넣을_프롬프트_이어서.md")]
                + [(공통 / "standards" / 최신결정, "판독패키지/" + 최신결정)]
                + [(공통 / "standards" / n, "판독패키지/" + n) for n in _기준서[:6]]
                + [(공통 / "data" / "7_영상메타.csv", "판독패키지/7_영상메타.csv")]
                + [(공통 / "standards" / n, "판독패키지/" + n) for n in _기준서[6:]]
                + [(참고 / "30_VoC_2차_번들환원_사양_v0.1.md", "판독패키지/30_VoC_2차_번들환원_사양_v0.1.md"),
                   (공통 / "common" / "40_2차판독_수행지시서.md", "공통/40_2차판독_수행지시서.md")]
                + [(공통 / "tools" / n, "스크립트/" + n) for n in _판독도구]
                + [(틀 / "0_여기에_결과가_쌓입니다.md", "_판독패키지/_결과/0_여기에_결과가_쌓입니다.md")]
                + [(공통 / "registry" / n, "대장/" + n) for n in
                   ("topic_group_map.json", "secondary_topics.json", "secondary_enums.json", "topic_registry.json")])
    if 이름 == "3_3차감독":
        return ([(참고 / "0_붙여넣을_프롬프트_감독.md", "프롬프트/0_붙여넣을_프롬프트_감독.md")]
                + [(공통 / "standards" / n, "판독패키지/" + n)
                   for n in (최신결정, "2_택소노미.md", "8_topic_그룹.md", "9_택소노미_2차확장.md")]
                + [(공통 / "common" / "40_2차판독_수행지시서.md", "공통/40_2차판독_수행지시서.md")]
                + [(공통 / "tools" / n, "스크립트/" + n) for n in _감독도구]
                + [(공통 / "registry" / n, "대장/" + n) for n in ("topic_group_map.json", "secondary_topics.json")])
    raise KeyError(이름)


def _공통목록(공통: Path) -> list:
    """COMMON — 어느 꾸러미에나 들어간다."""
    return [(공통 / "common" / "64_VoC_2차_pilot_전체안내.md", "0_전체안내.md"),
            (공통 / "common" / "16_VoC_분석엔진_재현설계서_v13.docx", "공통/16_VoC_분석엔진_재현설계서_v13.docx"),
            (공통 / "common" / "15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx", "공통/15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx"),
            (공통 / "common" / "출력칸목록.txt", "공통/출력칸목록.txt"),
            (공통 / "common" / "98_전체흐름_1차부터_4차까지.md", "0_전체흐름_누가_무엇을.md"),
            (공통 / "common" / "VoC_데이터_안내.xlsx", "공통/VoC_데이터_안내.xlsx")]


# ★ 판독 · 감독 폴더의 engine/ — 폴더의 도구가 **실제로 불러 쓰는 엔진 파일만** 싣는다 (섹션 7 ① · 2026-09-22).
#   plugin/engine 은 1차 엔진 전체(옛 live_merge 동결본 · 140개)다. 폴더에는 최종 xlsx 번들을 만드는 데 드는 것만 간다.
#   ★ 목록을 손으로 적지 않는다 — 처음에 옛 꾸러미의 28개 자리를 그대로 적었더니, 동결본 대시보드 파일이 부르는
#     src.v5.pipeline 이 빠져 2차 번들 xlsx 가 안 만들어졌다. 그래서 도구가 부르는 입구에서 import 를 코드로 따라가 뽑는다.
엔진입구 = ["src.dashboard60.export_bundle", "src.voc_rebuild", "src.voc_rebuild.schema", "src.voc_secondary",
          "src.voc_secondary.contracts", "src.voc_secondary.na_rules"]      # shared/tools 가 부르는 것 (grep 으로 확인)
엔진안내문 = "0_이 폴더는 무엇입니까.md"


def _모듈자리(엔진: Path, m: str) -> Path | None:
    p = 엔진.joinpath(*m.split("."))
    for c in (p.with_suffix(".py"), p / "__init__.py"):
        if c.is_file():
            return c
    return None


def _부르는것(엔진: Path, 파일: Path) -> set:
    import ast
    rel = 파일.relative_to(엔진).with_suffix("")
    패키지 = list(rel.parts[:-1]) if 파일.name != "__init__.py" else list(rel.parts[:-1])
    out = set()
    for n in ast.walk(ast.parse(파일.read_text(encoding="utf-8-sig"))):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names if a.name.startswith("src")}
        elif isinstance(n, ast.ImportFrom):
            m = ".".join(패키지[:len(패키지) - n.level + 1] + ([n.module] if n.module else [])) if n.level else (n.module or "")
            if m.startswith("src"):
                out.add(m)
                out |= {m + "." + a.name for a in n.names}
    return out


def 꾸러미엔진(엔진: Path) -> list:
    """입구에서 import 를 따라가 닿는 .py + 그 패키지 폴더의 설정(yaml · json) + 안내문 — 엔진 안 상대 자리."""
    본것, 할것 = set(), list(엔진입구)
    while 할것:
        m = 할것.pop()
        p = _모듈자리(엔진, m)
        if p is None or p in 본것:
            continue
        본것.add(p)
        조각 = m.split(".")
        할것 += [".".join(조각[:i]) for i in range(1, len(조각))]          # 부모 패키지의 __init__
        할것 += sorted(_부르는것(엔진, p))
    자리 = {p.relative_to(엔진).as_posix() for p in 본것}
    for 폴더 in {p.parent for p in 본것}:
        for q in 폴더.rglob("*"):
            if q.is_file() and q.suffix.lower() in (".yaml", ".yml", ".json") and "__pycache__" not in q.parts:
                자리.add(q.relative_to(엔진).as_posix())
    if (엔진 / 엔진안내문).is_file():
        자리.add(엔진안내문)
    return sorted(자리)


def _엔진목록(엔진: Path) -> list:
    if not 엔진.is_dir():
        return [(엔진 / "src", "engine/src")]       # 못 찾은 재료로 드러나게
    return [(엔진 / n, "engine/" + n) for n in 꾸러미엔진(엔진)]


def 전체_차림표(이름: str, 공통: Path, 엔진: Path, 참고: Path, 틀: Path) -> list:
    """옛 make_zip.main() 이 담던 차례 — 파일 · COMMON · engine · GUIDES · 판독대상."""
    return (꾸러미파일(이름, 공통, 참고, 틀) + _공통목록(공통) + _엔진목록(엔진)
            + [(공통 / "guides" / n, "가이드/" + n) for n in
               ("60_2차판독_실무자_사용가이드.md", "61_3차감독_실무자_사용가이드.md",
                "62_4차검토_및_번들해설.md", "63_대시보드_사용설명서.md")]
            # ★ 안내서 63 이 가리키는 그림 6개 (섹션 7a ③ · 2026-10-08) — 옛 꾸러미부터 빠져 있어
            #   `![…](캡쳐/01_전체화면.png)` 가 전부 깨져 있었다. 안내서 **바로 옆**에 두어야 그 상대경로가 맞는다.
            + [(p, "가이드/캡쳐/" + p.name) for p in sorted((공통 / "guides" / "캡쳐").glob("*.png"))]
            + [(공통 / "common" / "_판독대상_안내.md", "판독대상/0_이_폴더는.md")])


# ── 옛 make_zip.py 에서 옮겨 온 것 ─────────────────────────────────────────────
def 꾸러미_지문(담긴것):
    """담은 파일 중 「건드리면 안 되는 것」 의 지문을 뜬다.

    ★ 지문검사.py 와 같은 자리·같은 방식이어야 한다.
      줄바꿈(CRLF/LF)은 하나로 맞춰 센다 — 판마다 달라 흔들린 적이 있다.
    """
    import hashlib as _h
    import json as _j

    # ★ 지문검사.py 와 같아야 한다 — 「누구도 바꿀 이유가 없는 것」 만
    #   판독대상·회차배치·대장은 판독 흐름이 정당하게 바꾼다. 빼야 한다
    # ★ 2026-09-21 교차점검에서 고침 — `engine/` 을 더했다.
    #   지문검사.py 의 지킬곳에는 ("engine", "**/*.py", "1차 분석엔진 (읽기 전용)") 가 있는데
    #   지문을 뜨는 이 자리에 engine 이 없어서, 엔진을 고쳐도 「새로 생김」 알림만 뜨고
    #   검사가 통과했다 (실제로 engine.py 에 한 줄을 더해 확인했다). 옛 꾸러미부터 있던 구멍이다.
    볼곳 = ('스크립트/', '판독패키지/', '공통/', '프롬프트/', 'engine/')
    지문 = {}
    for 원본, 자리 in 담긴것:
        n = 자리.replace(os.sep, '/')
        if not n.startswith(볼곳):
            continue
        if '__pycache__' in n or n.endswith('지문.json'):
            continue
        if n.startswith('스크립트/') and not n.endswith('.py'):
            continue
        if n.startswith('engine/') and not n.endswith('.py'):
            continue                      # 지문검사의 engine 무늬가 **/*.py 다
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


# ── 글이 다른 이름으로 가리키는 자리 (2026-10-29 · 작게 한 번 돌려 보고 나왔다) ─────────
#   ★ 무엇이 있었나 — 판독A(claude)가 실제 판독 중에 걸렸다. 기준 문서 셋(`0_전체안내.md` ·
#     `8_topic_그룹.md` · `4_2차_확장부록.md`)이 대장을 `s9_group/topic_group_map.json` 으로
#     가리키는데, 이 꾸러미에 들어가는 자리는 `대장/topic_group_map.json` 이다. 그 어긋남 때문에
#     판독이 반려 1건과 계약 위반 24행을 안고 끝났고, 판독자는 **자기가 맞춰도 될지 sky 에게
#     물어야** 했다 (판독B 와 조건이 달라지므로 혼자 고치지 않았다).
#   ★ 고르지 않은 길 둘 — 기준 문서 원문을 고치는 것(공통 규칙 7 · 축약·개작 금지)과
#     `s9_group/` 에 사본을 하나 더 두는 것(공통 규칙 6 · 같은 것이 두 벌). 둘 다 안 한다.
#   ★ 고른 길 — **이름 대응을 안내문에 적는다.** 손으로 적지 않는다. 담은 글을 긁어
#     **실제로 어긋난 것만** 뽑으므로 재료가 바뀌면 안내문도 따라 바뀐다.
_낱말 = "A-Za-z0-9가-힣_"
_가리키는무늬 = re.compile(
    "(?<![" + _낱말 + "./-])"
    "([" + _낱말 + "][" + _낱말 + "-]{1,30})/"
    "([" + _낱말 + "./-]{1,60}[.](?:json|csv|md|py|xlsx|txt|docx|png))")


def 이름대응(작업: Path) -> list:
    """담긴 글이 가리키는 「폴더/파일」 가운데 **이 꾸러미에 다른 폴더 이름으로 들어 있는 것**을
    (글이 말하는 자리, 이 꾸러미의 자리, 파일 이름들) 로 돌려준다.

    ★ 넣지 않는 것 두 가지 — 둘 다 이름 어긋남이 아니다.
      ① 글 옆에서 상대경로로 그대로 열리는 것 — 안내서 63 의 `캡쳐/01_전체화면.png` 는 안내서
         바로 옆에 있어서 그대로 열린다 (섹션 7a ③ 에서 그렇게 넣었다).
      ② 가리키는 파일이 이 꾸러미에 아예 없는 것 — 총괄 자리의 `s13_judge/judge_input.csv` ·
         `s15_master/raw_voc.csv`, 옛 저장소의 `outputs/...` 처럼 **다른 자리를 설명하는 글**이다.
         없는 것을 「이름이 다르다」 고 적으면 안내문이 거짓말을 한다.
    """
    있는것: dict = {}
    for q in sorted(작업.rglob("*")):
        if q.is_file() and "__pycache__" not in q.parts:
            있는것.setdefault(q.name, []).append(q.relative_to(작업).as_posix())
    본것: dict = {}
    for 글 in sorted(작업.rglob("*.md")):
        if 글.relative_to(작업).parts[:1] == ("engine",):
            continue                      # 엔진 안 안내문은 엔진 자리를 말한다
        for m in _가리키는무늬.finditer(글.read_text(encoding="utf-8", errors="replace")):
            말한자리, 뒤 = m.group(1), m.group(2)
            if (작업 / 말한자리 / 뒤).is_file() or (글.parent / 말한자리 / 뒤).is_file():
                continue                  # ① 그대로 열린다
            이름 = 뒤.rsplit("/", 1)[-1]
            자리들 = 있는것.get(이름)
            if not 자리들:
                continue                  # ② 이 꾸러미에 없는 것
            실제 = 자리들[0].rsplit("/", 1)[0] if "/" in 자리들[0] else ""
            본것.setdefault((말한자리, 실제), set()).add(이름)
    return [(ㄱ, ㄴ, sorted(ㄷ)) for (ㄱ, ㄴ), ㄷ in sorted(본것.items())]


def readme(name, spec, files, 대응=()):
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
    # ★ 글이 다른 이름으로 가리키는 자리 — 실제로 어긋난 것만 적는다 (2026-10-29)
    if 대응:
        L += ['', '## ★ 글이 다른 이름으로 가리키는 자리', '', '```',
              '기준 문서와 안내서는 옛 저장소의 폴더 이름으로 적혀 있습니다.',
              '글이 아래 왼쪽을 가리키면 **이 꾸러미에서는 오른쪽**을 여십시오.',
              '원문은 고치지 않았고(원문 그대로 둡니다) 사본도 만들지 않았습니다.', '']
        # ★ 한글은 두 칸을 차지한다 — len() 으로 맞추면 표가 어긋난다
        import unicodedata as _u

        def _폭(s):
            return sum(2 if _u.east_asian_width(c) in 'WF' else 1 for c in s)
        왼쪽 = [ㄱ + '/' for ㄱ, _, _ in 대응]
        칸 = max(_폭(x) for x in 왼쪽) + 2
        for (말한자리, 실제, 이름들), ㄱ in zip(대응, 왼쪽):
            L.append('  %s%s->  %s' % (ㄱ, ' ' * (칸 - _폭(ㄱ)), (실제 + '/') if 실제 else './'))
            L.append('  %s    %s' % (' ' * 칸, ' · '.join(이름들)))
        L.append('```')
    return '\n'.join(L)
# ─────────────────────────────────────────────────────────────────────────────


def 차리기(작업: Path, 이름: str, 공통: Path, 엔진: Path, 참고: Path, 틀: Path) -> dict:
    작업.mkdir(parents=True, exist_ok=True)
    셈 = {"차림": 0, "이미있음": 0, "못찾음": []}
    담긴것, 목록 = [], []
    for 원, 자리 in 전체_차림표(이름, 공통, 엔진, 참고, 틀):
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
                    ("0_먼저_읽으십시오.md",
                     lambda: readme(이름, SPEC[이름], 목록, 이름대응(작업)))):
        q = 작업 / 자리
        if q.exists():
            셈["이미있음"] += 1
            continue
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(글().encode("utf-8"))
        셈["차림"] += 1
    return 셈
