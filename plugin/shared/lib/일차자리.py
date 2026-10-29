# -*- coding: utf-8 -*-
"""1차 실행 자리를 차린다 — 섹션 7 ③ (`running-voc-engine` 스킬).

★ 파일 이름이 「일차자리」 인 까닭 — 파이썬 모듈 이름은 숫자로 시작할 수 없어 `import 1차자리` 가 문법 오류다.

★ 왜 저장소 **밖**인가 (2026-10-08 실제로 겪었다)
  1차 엔진은 결과를 **자기 폴더 아래**에 쓴다 — `data/raw` · `data/processed` · `data/exports` · `outputs/`.
  저장소 안(`plugin/engine/`)에서 돌리면 엔진 지문검사(`tests/test_engine.py`)가 깨진다.
  그래서 판독 · 감독 스킬과 같은 방식으로 **작업 폴더를 따로 차리고 엔진 사본을 그 안에 둔다.**

★ 모양
    <1차자리>/
        0_먼저_읽으십시오.md      차례 (이 파일이 스킬이 아니라 **작업 폴더**의 안내다)
        99_1차_실행조건_원문.md   ★ 대시보드 「새로 분석 돌리기」 입력 칸 원문 (요약 아님 — 칸 · 최댓값 · 안내문 그대로)
        1차_돌리기.py            ★ 어림을 내고 **승인 없이는 돌지 않는다** · 설정 자리를 자동으로 준다 · 끝나면 확인한다
        engine/                 1차 엔진 한 벌 (plugin/engine 전부 — 수집 · 분석 · 번들 · nlp_analyzer)
        engine/config/settings.yaml   ★ 이 자리에서만 덮어쓰는 설정 (아래 「왜 설정을 더하나」)
        engine/outputs/voc_dashboard_60/<이름>/   ★ 결과가 쌓이는 자리 (엔진 본래 자리)
                                — 대시보드가 여기를 스스로 찾아 띄운다 (data_contract.latest_dataset).
                                  전에는 `<자리>/결과/` 에 썼다가 대시보드가 「Dataset not found」 로 떴다 (2026-10-08 고침).

★ 왜 설정을 더하나 (sky 2026-10-08 결정 「OpenAI 로 바로 가게 한다」)
  엔진 기본값은 `analytics.nlp_analyzer.provider: claude` · `model: claude-sonnet-4-20250514` 인데
  이 PC 에는 Anthropic 키가 없고, 그 꾸러미의 `.env` 에 한글 자리표시자가 들어 있어 **댓글마다 호출이 실패**하고
  OpenAI 로 넘어간다(2026-10-08 실행에서 530회 전부). 결과는 OpenAI 가 낸 것이므로, 처음부터 OpenAI 를
  primary 로 적는다 — **결과는 그대로이고 헛호출과 경고만 없어진다.**
  동결 엔진의 기본값(`src/config.py`)은 원문 그대로 두고, 이 작업 폴더의 설정으로만 덮는다.
  설정 자리는 `YT_ANALYSIS_SETTINGS_PATH` 로 가리킨다 (`src/config.py:208`).

★ 이미 있는 파일은 건드리지 않는다. 다시 돌려도 안전하다.
"""
from __future__ import annotations

import shutil
from pathlib import Path

실행조건원문 = "99_1차_실행조건_원문.md"
# ★ 2026-10-22 (sky 「or 와 and 의 조건을 명확하게 해야 합니다」) — 결합 방식은 코드를 읽어야
#   알 수 있어 따로 적어 두었다. 1차 자리에서 사람에게 물을 때 이것을 읽는다.
결합기준 = "키워드결합_OR_AND_기준.md"
돌리개이름 = "1차_돌리기.py"      # ★ 원본 한 벌은 스킬의 scripts/ — 차릴 때 작업 폴더 맨 위로 복사한다
설정자리 = "engine/config/settings.yaml"
# ★ 이 자리에서만 덮는 설정 — 엔진 기본값(src/config.py NlpAnalyzerSettings)에서 두 줄만 바꾼다
설정내용 = """# 1차 실행 자리 설정 — `running-voc-engine` 스킬이 차렸다 (고쳐도 된다).
# 엔진 원본 설정은 config/settings.example.yaml 이고 이 파일이 그것을 대신한다
# (돌릴 때 YT_ANALYSIS_SETTINGS_PATH=config/settings.yaml).
#
# ★ 왜 이 두 줄인가 (sky 2026-10-08) — 엔진 기본값은 primary 가 Claude 인데 이 PC 에는 Anthropic 키가 없어
#   댓글마다 호출이 실패하고 OpenAI 로 넘어갔다(530회 전부). 결과는 OpenAI 가 낸 것이니 처음부터 그렇게 적는다.
#   Anthropic 키를 쓰게 되면 provider 를 claude 로 되돌리고 model 을 claude 판으로 바꾼다.
analytics:
  nlp_analyzer:
    provider: openai
    model: gpt-4o-mini
"""
안내문이름 = "0_먼저_읽으십시오.md"
안내문 = """# 1차 실행 자리 — 먼저 읽으십시오

이 폴더는 **1차 분석엔진을 돌리는 자리**다. 스킬이 차렸다 (`running-voc-engine`).

## 차례

1. **실행조건을 사람에게 받는다.** 칸 · 최댓값 · 기본값 · 안내문은 [`99_1차_실행조건_원문.md`](99_1차_실행조건_원문.md) 에
   원문 그대로 있다. 요약본이 아니다 — 그 파일을 열어 읽고 그 칸으로 묻는다.
   ★ **키워드 결합(OR · AND)은 [`키워드결합_OR_AND_기준.md`](키워드결합_OR_AND_기준.md) 를 읽고 묻는다.**
   AND 는 「키워드마다 검색해 교집합」 이 **아니다** — 맨 윗줄로만 검색하고 아랫줄은
   영상의 제목·설명·채널명·태그에서 글자로 걸러낸다. 그래서 **맨 윗줄이 모수를 정한다.**
   (2026-08-20 에 안내문이 코드와 달라 sky 가 고친 자리다. 짐작으로 말하지 않는다.)
2. **키가 있는지 본다** (값은 보지 않는다 — 있는지만).
   `YOUTUBE_API_KEY` · `OPENAI_API_KEY` 가 환경변수에 있어야 한다.
   없으면 **돌리지 않고** 사람에게 알린다 — 넣는 법은 꾸러미 안
   `0_빈컴퓨터에서_무엇을_깔까.md` 의 §③ 에 있고(저장소의 `.ps1` 은 꾸러미에 없다),
   그리고 **환경변수는 새로 켠 창에만 들어온다**(지금 창에서는 안 보인다).
3. **규모와 비용을 먼저 말하고 승인을 받는다.** 돈이 든다.
   잰 것 (2026-10-08 · 영상 5개 · 영상당 댓글 50개): 댓글 494개 → 조각 504개 · 약 63분 · 대략 $1 ·
   YouTube 할당량 108 / 하루 10,000. 이 숫자로 비례해 어림한다.
4. **어림을 낸다** — 이 폴더에서 `--승인` **없이** 돌린다. 숫자만 내고 멈춘다(종료 2).

   ```
   python 1차_돌리기.py --검색어 "<검색어>" --영상 <수> --댓글 <수>
   ```

   나온 숫자(모을 댓글 · 조각 · 분 · 달러 · 할당량)를 **사람에게 말하고 승인을 받는다.**
5. **돌린다** — 승인을 받은 뒤에만 `--승인` 을 붙인다. 설정 자리(`config/settings.yaml`)는 이 스크립트가 알아서 준다.

   ```
   python 1차_돌리기.py --검색어 "<검색어>" --영상 <수> --댓글 <수> --이름 <이름> --승인
   ```

   오래 걸린다 — 뒤로 돌리고 `engine/outputs/voc_dashboard_60/<이름>/progress.jsonl` 과 `실행기록.txt` 로 진행을 본다.
   끝나면 스크립트가 **확인까지 한다**(칸 66개 · 전부 빈 칸 · 조각 · 영상 · 제외 · 번들 · 설정이 먹었나).
   이미 돌린 결과만 다시 확인하려면 `python 1차_돌리기.py --이름 <이름> --확인만`.
6. **2차로 넘긴다.** 2차 판독 스킬(`reading-voc-comments`)이 차린 폴더에서
   `python 스크립트/데이터_넣기.py "<번들 xlsx>"` 를 돌리면 판독할 데이터로 앉는다
   (확인이 끝나면 그 명령을 그대로 찍어 준다).

## 하지 않는 것

- 엔진을 고치지 않는다 (`engine/` 은 동결 사본이다. 결함을 찾으면 적어만 둔다 — 7차 엔진 개정 창에서 모아 고친다).
- 키 값을 읽거나 옮기거나 화면에 찍지 않는다. 있는지만 본다.
- 승인 없이 돌리지 않는다. 규모를 바꿔 다시 돌릴 때도 다시 말한다.
- 결과를 지어내지 않는다. 못 돌렸으면 못 돌렸다고 말한다.
"""


def 재료(공통: Path, 엔진: Path, 스킬스크립트: Path | None = None) -> list:
    """(재료, 작업 폴더 안 자리) — 엔진은 폴더째 복사하므로 여기서는 글 파일과 돌리개만."""
    것 = [(공통 / "common" / 실행조건원문, 실행조건원문),
        (공통 / "common" / 결합기준, 결합기준)]
    if 스킬스크립트 is not None:
        것.append((스킬스크립트 / 돌리개이름, 돌리개이름))
    return 것


def _다른것(자리: Path, 재료: list, 엔진: Path) -> list[str]:
    """이미 차려진 자리에서 **원본과 내용이 다른** 파일을 찾는다 (낡은 사본).

    ★ 왜 (2026-10-08 실제로 겪었다) — 차리기는 「이미 있는 파일은 건드리지 않는다」. 판 중간에 다시 돌려도
      안전하라는 규칙인데, 그 때문에 **스킬을 고쳐도 이미 차린 자리는 옛 코드를 쓴다.**
      `1차_돌리기.py` 를 고치고 작업 폴더에서 돌렸다가 옛 동작을 보고 한참 헤맸고,
      그 뒤 세어 보니 대시보드 자리도 옛 돌리개를 들고 있었다. 조용히 다르면 안 된다 — **찾아서 말한다.**
    """
    import hashlib
    def _h(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    다름 = []
    for 원본, 안자리 in 재료:
        p = 자리 / 안자리
        if p.is_file() and 원본.is_file() and _h(p) != _h(원본):
            다름.append(안자리)
    엔진자리 = 자리 / "engine"
    for 원본 in sorted(엔진.rglob("*")):
        if not 원본.is_file() or "__pycache__" in 원본.parts:
            continue
        p = 엔진자리 / 원본.relative_to(엔진)
        if p.is_file() and _h(p) != _h(원본):
            다름.append("engine/" + 원본.relative_to(엔진).as_posix())
    return 다름


def 차리기(자리: Path, 공통: Path, 엔진: Path, 스킬스크립트: Path | None = None,
         새로: bool = False) -> tuple[int, int, list[str]]:
    """차린 수 · 이미 있어 그대로 둔 수 · **낡은 사본 목록**.

    이미 있는 파일은 건드리지 않는다(판 중간에 다시 돌려도 안전하게).
    다만 원본과 **내용이 다른** 것은 찾아서 돌려준다 — 조용히 옛 코드를 쓰지 않게.
    `새로=True` 면 그 낡은 것들을 **덮어쓴다** (결과 폴더는 건드리지 않는다).
    """
    자리.mkdir(parents=True, exist_ok=True)
    (자리 / "engine" / "outputs" / "voc_dashboard_60").mkdir(parents=True, exist_ok=True)
    차림, 그대로 = 0, 0
    for 원본, 안자리 in 재료(공통, 엔진, 스킬스크립트):
        p = 자리 / 안자리
        if p.exists():
            그대로 += 1
            continue
        if not 원본.is_file():
            raise FileNotFoundError("못 찾음: %s" % 원본)      # 「못 찾음」 은 「없음」 이 아니다
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(원본, p)
        차림 += 1
    # 엔진 한 벌 — 1차는 수집(src/collectors) · 파이프라인(src/pipelines) · 번들 · nlp_analyzer 를 다 쓴다
    엔진자리 = 자리 / "engine"
    for 원본 in sorted(엔진.rglob("*")):
        if not 원본.is_file() or "__pycache__" in 원본.parts:
            continue
        p = 엔진자리 / 원본.relative_to(엔진)
        if p.exists():
            그대로 += 1
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(원본, p)
        차림 += 1
    for 이름, 글 in ((설정자리, 설정내용), (안내문이름, 안내문)):
        p = 자리 / 이름
        if p.exists():
            그대로 += 1
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(글, encoding="utf-8", newline="\n")
        차림 += 1
    # ★ 이미 있던 것 가운데 **원본과 다른 것**을 찾는다 — 조용히 옛 코드를 쓰지 않게 (2026-10-08)
    낡음 = _다른것(자리, 재료(공통, 엔진, 스킬스크립트), 엔진)
    if 새로 and 낡음:
        for 안자리 in 낡음:
            원본 = (엔진 / 안자리[len("engine/"):]) if 안자리.startswith("engine/") else None
            if 원본 is None:
                원본 = dict((b, a) for a, b in 재료(공통, 엔진, 스킬스크립트))[안자리]
            shutil.copy2(원본, 자리 / 안자리)
        낡음 = []
    return 차림, 그대로, 낡음
