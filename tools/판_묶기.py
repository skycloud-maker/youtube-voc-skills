# -*- coding: utf-8 -*-
"""Ver 마다 **건네줄 것 하나**를 만든다 — Claude Code 용 플러그인 꾸러미 (2026-10-09).

★ 왜 — sky 2026-10-09 「파일 하나? 아니면 zip 파일로 하나 AI 모델에게 주면 Ver1 을 수행하는
  방식이면 좋겠고(지금은 skill 파일 5개를 줘야 하는 것 같아서). Ver1, Ver2, Ver3용 파일이
  별개로 있으면 좋겠다는 게 의미입니다. 헷갈리지 않도록요. Ver2에는 뭐 파일하나만 같이
  넣으세요 보단 Ver2는 이 파일 하나만 전달하면 됩니다 라고 하는 게 더 쉬운 거니까요.」

★ 넘길 자리는 **Claude Code 하나**다 (sky 2026-10-09 고름).
  - Claude Code 는 플러그인 하나에 스킬 여럿이 든다 → **꾸러미 하나로 다섯이 다 간다.**
  - claude.ai 는 공식 문서가 「The ZIP should contain the skill folder as its root」 라
    zip 하나에 스킬 하나다 → 다섯이면 다섯 개. 그쪽은 `build_skills.py` 가 따로 만든다.
  - Codex 용 `.agents/skills/` 사본도 `build_skills.py` 가 만든다.

★ 어디서 꺼내나 — **Ver1 은 동결 태그에서, Ver2 는 지금 판에서.**
  Ver1 은 `한줄_돌리기.py` 가 생기기 **전에** 동결했다(태그 `ver1-유튜브VoC분석내부화`).
  그래서 「지금 코드에서 파일 하나 뺀 것」 이 아니라 태그에서 꺼낸다 —
  그러면 Ver1 꾸러미에는 한 줄 돌리개가 애초에 없어 **어느 판인지 헷갈릴 일이 없다.**
  Ver2 는 지금 판(HEAD)에서 꺼낸다 (「최신판이 정본」).
  ★ 손으로 복사하지 않는다. 이 도구가 만들고 `차림표.json` 에 원본·지문을 적고,
    `tests/test_판꾸러미.py` 가 태그/HEAD 와 한 파일씩 대조한다 (공통 규칙 6).

★ Ver3 은 꾸러미를 만들지 않는다 — **코드가 없다.**
  ②③④ 는 「Codex 를 Claude 로 바꿀 수 있나」 를 **재 본 것**이고, 결론이 「지금은 안 된다」 였다.
  되는 척하는 빈 꾸러미를 주면 그게 더 헷갈린다. 그래서 안내문 하나만 둔다 —
  쓸 수 없는 까닭(측정 결과)과 되는 날 무엇을 바꾸면 되는지(`판독자`·`감독자` 두 줄).

쓰기
    python tools/판_묶기.py                 dist/판/ 에 만든다
    python tools/판_묶기.py <자리>          다른 자리에
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"
Ver1태그 = "ver1-유튜브VoC분석내부화"

빼는_폴더 = {"__pycache__", "node_modules", ".git", ".pytest_cache"}
빼는_파일 = {".DS_Store", "Thumbs.db"}
빼는_무늬 = (".pyc", ".pyo")
# ★ 이 컴퓨터 경로가 적힌 개발용 — 나가는 꾸러미가 부르지 않는다 (build_skills.py 와 같은 규칙)
공통_빼기 = {"paths.py"}


def _뺄까(rel: Path) -> bool:
    return (bool(빼는_폴더 & set(rel.parts)) or rel.name in 빼는_파일
            or rel.name.endswith(빼는_무늬) or rel.name in 공통_빼기)


def _git(*인자: str, 글자: bool = True) -> subprocess.CompletedProcess:
    # ★ --no-optional-locks — 다른 창이 같은 저장소를 보고 있어도 잠그지 않는다
    return subprocess.run(["git", "--no-optional-locks", *인자], cwd=str(REPO),
                          capture_output=True, text=글자,
                          encoding="utf-8" if 글자 else None, errors="replace" if 글자 else None)


def _태그에서_꺼내기(태그: str, 받을곳: Path) -> None:
    """태그의 `plugin/` 만 꺼낸다. 지금 작업 자리는 건드리지 않는다."""
    r = _git("rev-parse", "--verify", 태그 + "^{commit}")
    if r.returncode:
        raise SystemExit("못 찾음: 태그 %s 가 없다 — 「못 찾음」 은 통과가 아니다\n%s" % (태그, r.stderr.strip()))
    받을곳.mkdir(parents=True, exist_ok=True)
    꾸러미 = 받을곳.parent / ("_%s.tar" % 받을곳.name)
    r2 = _git("archive", "--format=tar", "-o", str(꾸러미), 태그, "plugin")
    if r2.returncode:
        raise SystemExit("git archive 가 실패했다:\n%s" % r2.stderr.strip())
    import tarfile
    with tarfile.open(꾸러미) as t:
        t.extractall(받을곳, filter="data")
    꾸러미.unlink()


def _파일들(뿌리: Path) -> list[Path]:
    return sorted(p for p in 뿌리.rglob("*") if p.is_file() and not _뺄까(p.relative_to(뿌리)))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _담기(바탕: Path, 받을곳: Path) -> list[tuple[Path, str]]:
    """`바탕`(플러그인 폴더) 을 `받을곳/plugin/` 에 담고 (원본, 꾸러미 안 자리) 를 돌려준다."""
    표 = []
    for p in _파일들(바탕):
        안 = "plugin/" + p.relative_to(바탕).as_posix()
        q = 받을곳 / 안
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        표.append((p, 안))
    if not 표:
        raise SystemExit("못 찾음: %s 에서 담을 파일이 0개다" % 바탕)
    return 표


# ── 읽어주세요 ────────────────────────────────────────────────────────────
_Ver1_읽어주세요 = """# Ver1 — 스킬 다섯을 사람이 단계마다 부린다

유튜브 댓글 VoC 분석을 **AI 역할별 스킬 다섯**으로 담은 것입니다.
단계마다 사람이 AI 창을 열고 폴더를 넘겨 줍니다.

## 건네주는 법 (Claude Code)

이 폴더를 풀고, 그 자리를 가리켜 Claude Code 를 띄우십시오.

```
claude --plugin-dir "<이 폴더>/plugin"
```

그 다음 하고 싶은 일을 그냥 말하면 됩니다. 보기 —

```
LG 로봇청소기 영상 2개, 댓글 50개씩 모아서 1차 분석을 해 주세요.
```

```
이 폴더에 있는 1차 분석 결과로 2차 판독을 해 주세요.
```

## 든 것 — 스킬 다섯

| 스킬 | 누가 쓰나 | 무엇을 하나 |
|---|---|---|
| `running-voc-engine` | 1차 | 유튜브에서 모아 1차 분석을 돌린다 (66칸) |
| `reading-voc-comments` | 2차 판독 **둘** | 조각마다 라벨을 붙인다. 둘을 **따로** 돌려 교차검증한다 |
| `supervising-voc-disagreements` | 3차 감독 **둘** | 판독 둘이 갈린 행을 본다 |
| `coordinating-voc-pipeline` | 총괄 | 통합 · 편향검사 · 최종 번들 |
| `building-voc-report` | 보고서 | 최종 엑셀에서 사내 HTML 보고서 |

4차 검토는 **사람이 합니다** — 일부러 그렇게 두었습니다.

## 이 판에 **없는** 것

`한줄_돌리기.py` (한 줄 흐름) 가 없습니다. 그것은 **Ver2** 입니다.
단계를 사람이 잇는 것이 Ver1 이고, 총괄이 잇는 것이 Ver2 입니다.

## 쓰기 전에 넣을 것

```
YOUTUBE_API_KEY     1차 수집용
OPENAI_API_KEY      1차 분석용
```

★ 1차(유튜브에서 모으기)는 **Claude Code 에서만** 됩니다. claude.ai 웹에서는 안 돕니다.
"""

_Ver2_읽어주세요 = """# Ver2 — 한 줄 흐름. **이 꾸러미 하나만** 건네면 됩니다

인풋 두 번으로 최종 엑셀까지 갑니다. 중간에 폴더를 넘기는 심부름을 **총괄이 합니다.**

```
인풋 1  1차 조건 (검색어 · 영상 수 · 댓글 수)
          ↓
        1차 → 2차 판독 둘 → 총괄 검수 → 3차 감독 둘 → 3차 마무리
          ↓
아웃풋 1  회의에서 정할 것 (사람이볼목록 · 보정요청 · 분리제안 · 감독_분리제안 · 총괄 소견)
          ↓
인풋 2  회의에서 정한 값
          ↓
아웃풋 2  최종 엑셀 하나 + 사내 보고서
```

## 건네주는 법 (Claude Code)

① 이 폴더를 풉니다.
② 한 줄 넣습니다 — **이것 하나입니다.**

```
python "<이 폴더>/plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py" "<판자리>" --조건 "검색어=LG 로봇청소기; 영상=2; 댓글=50; 이름=판1"
```

★ `<판자리>` 는 **저장소 밖 빈 폴더**를 새로 하나 주십시오. 그 안에 판의 모든 것이 쌓입니다.

★ **한 줄입니다.** 줄을 나누어 적지 마십시오 — 줄 나누는 글자는 셸(cmd · PowerShell · bash)마다 달라 붙여 넣는 곳에서 깨집니다 (2026-10-28 설치 예행).

③ 그 명령은 **어림(규모 · 시간 · 비용 · 유튜브 할당량)을 말하고 멈춥니다.**
   숫자가 괜찮으면 `--승인` 을 붙여 같은 명령을 다시 넣으십시오 — 그때부터 끝까지 갑니다.

```
python "<이 폴더>/plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py" "<판자리>" --조건 "검색어=LG 로봇청소기; 영상=2; 댓글=50; 이름=판1" --승인
```

   ★ 한 번 승인하면 `상태.json` 에 적힙니다 — 멈춘 뒤 이어갈 때는 다시 묻지 않습니다.
④ `아웃풋1_회의에서_정할것` 이 나오면 회의에서 정하고, 그 파일에 적습니다.
⑤ 마지막 한 줄 —

```
python "<이 폴더>/plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py" "<판자리>" --4차반영
```

## 또 하나의 길 — **플러그인으로 등록해 말로 시키기** (2026-10-29 더함)

위 ②는 **명령 한 줄**로 돌리는 길입니다. 이 꾸러미는 플러그인으로 **등록**할 수도 있습니다.
등록하면 새 채팅방에서 「유튜브 댓글 VoC 분석 해 주세요」 **한마디**로 됩니다 —
AI 가 스킬을 스스로 집어 실행조건을 묻고, 갖춤새를 보고, 어림을 말한 뒤 승인을 기다립니다.

```
claude plugin marketplace add "<이 폴더>"
claude plugin install youtube-voc@youtube-voc-skills
```

그다음 **Claude Code 를 닫고 다시 여십시오** — 등록은 다시 열 때 읽힙니다.
`claude plugin list` 에 `youtube-voc@youtube-voc-skills` 가 보이면 된 것입니다.

★ **윈도 PowerShell 에서 「이 시스템에서 스크립트를 실행할 수 없으므로 … `claude.ps1` …」**
  이 나오면 **꾸러미 탓이 아닙니다.** npm 이 `claude.ps1`(PowerShell 스크립트)과
  `claude.cmd`(배치 파일)를 같이 깔아 두는데, PowerShell 창에서 `claude` 라고 치면 `.ps1` 을
  먼저 집고 그 실행이 **정책으로 막혀** 있는 것입니다.
  → `claude` 대신 **`claude.cmd`** 를 치십시오 (배치 파일이라 정책을 거치지 않습니다).
    `cmd /c "claude plugin list"` 도 됩니다.
  ★ 실행 정책을 **바꾸는 것은 보안 설정**입니다. 회사 컴퓨터라면 전산 담당자에게 물어야 합니다.

★ 이미 같은 이름(`youtube-voc-skills`)으로 등록해 둔 컴퓨터에서는 **다시 등록하지 마십시오** —
  이름이 겹칩니다. `claude plugin list` 로 먼저 보시고, 판이 낡았으면
  `claude plugin update youtube-voc` 만 하면 됩니다.

★ 어느 길이든 **같은 코드가 돕니다.** 명령 한 줄은 자리를 손으로 가리키고, 플러그인은
  AI 가 스스로 집는 차이입니다.

## 중간에 멈추면 — **같은 명령을 그대로 다시** 넣으십시오

어디까지 했는지 `<판자리>/상태.json` 에 적혀 있습니다.
끝난 단계는 **다시 돌리지 않습니다** (AI 를 다시 띄우지 않으니 돈이 두 번 나가지 않습니다).

```
--확인만              무엇을 할지만 보여 주고 아무것도 돌리지 않는다
                      ★ **갖춤새도 같이 봅니다** — 파이썬 꾸러미 · `claude`·`codex` 명령 ·
                        키(이름만). 모자라면 무엇이 모자란지 말하고 종료코드 2 로 멈춥니다.
--승인                어림을 보고 괜찮을 때 붙입니다. 이것 없이는 돌지 않습니다
--되감기 <단계>       그 단계부터 다시 한다 (단계 이름을 틀리면 쓸 수 있는 이름을 알려 준다)
```

## 멈추는 것과 싣고 가는 것

| | 보기 | 어떻게 |
|---|---|---|
| **멈춘다** | 판독자가 죽음 · 결과 안 나옴 · 키 없음 · 칸 계약 깨짐 | 총괄이 **즉시 멈추고 알린다.** 하나만 가지고 다음 차수로 안 넘긴다 |
| **싣고 간다** | 담을 라벨이 모자람 · 기준서가 애매함 | **아웃풋 1 의 `소견.md`** 에 실어 회의에서 정하게 한다 |

## 누가 판독하나 — 바꿀 수 있습니다

```python
# plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py
판독자 = [("판독A", "claude"), ("판독B", "codex")]
감독자 = [("감독1", "codex"), ("감독2", "claude")]
```

지금은 **Claude 와 Codex 둘**을 씁니다 (교차검증). 구독을 하나로 줄여야 하면 **Ver3** 인데,
`Ver3_아직_못_씁니다.md` 를 보십시오 — 지금은 권하지 않습니다.

## 쓰기 전에 넣을 것

```
YOUTUBE_API_KEY     1차 수집용
OPENAI_API_KEY      1차 분석용
claude · codex      둘 다 이 컴퓨터에서 돌아가야 합니다 (총괄이 띄웁니다)
```

★ Claude Code 에서만 됩니다. claude.ai 웹에서는 1차도, 총괄이 AI 를 띄우는 것도 안 됩니다.
"""

_Ver3_안내 = """# Ver3 — 아직 못 씁니다 (꾸러미를 만들지 않았습니다)

Ver3 은 **구독을 하나로 줄여야 할 때**를 위한 판입니다 —
Codex 가 하던 2차 판독 한 자리 · 3차 감독 한 자리를 **Claude 가 대신** 맡는 것입니다.

## 왜 꾸러미가 없나 — 재 봤고, 지금은 안 됩니다

★ 「되는 척하는 빈 꾸러미」 를 주면 그게 더 헷갈립니다. 그래서 안 만들었습니다.

| 재 본 것 | 결과 |
|---|---|
| ② Codex 에게 자기 판독의 **까닭을 묻고** 지시문으로 옮기기 | 받은 규칙을 번들에 대 보니, **대조군(같은 Claude 둘)에서도 같은 차이가 나는 것**이 절반이었다. 즉 「Codex 라서」 가 아니라 **판독이 매번 흔들려서**다. 글로 옮길 수 있는 규칙은 **셋**뿐이었다 |
| ④ 둘째 판독자를 **다른 Claude 모델(Sonnet)** 로 바꾸기 | 정본과 맞은 행이 **175/218 → 58/218** 로 떨어졌다. 218행 중 161행이 갈렸다 — 교차검증이 아니라 잡음이다 |

**그래서 구독을 하나로 줄이면 교차검증은 지금만큼 지켜지지 않습니다.**
자세한 숫자와 방법은 저장소 `docs/Ver3_단일모델/` 에 있습니다.

## 되는 날 무엇을 바꾸면 되나 — **두 줄입니다**

Ver2 를 짤 때 그 자리를 미리 뚫어 두었습니다.

```python
# plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py
판독자 = [("판독A", "claude"), ("판독B", "codex")]      # ← 이 codex 를
감독자 = [("감독1", "codex"), ("감독2", "claude")]      # ← 이 codex 를  claude 로
```

여기에 **지시문 파일 하나**(Codex 가 하던 판독 방식을 적은 것)를 더하면 됩니다.
흐름 코드를 다시 쓰는 일이 아닙니다. 그래서 Ver2 꾸러미와 Ver3 이 **같은 코드**입니다 —
다른 판이 아니라 **설정이 다른 같은 판**입니다.

## 지금 권하는 것

구독 둘을 유지하고 **Ver2** 를 쓰십시오 (`Ver2_한줄흐름`).
"""


_막히면_안내 = """# 막히면 이 순서로 (다른 컴퓨터에서 처음 돌릴 때)

★ 왜 이 글이 있나 (sky 2026-10-27) — 「분명 한번에 안 돌아갈 것이니 그에 따른 수정보완은
  시행착오를 통해 고쳐야 하는 건데」. 맞습니다. **한 번에 안 돌아가는 것이 정상입니다.**
  이 글은 막혔을 때 **무엇을 보고 무엇을 보내면 되는지**를 적은 것입니다.

## ① 돈 쓰기 전에 — 갖춤새부터 봅니다

```bash
python <스킬>/scripts/한줄_돌리기.py <판자리> --조건 "검색어=…; 영상=5; 댓글=50" --확인만
```

**돈이 들지 않습니다.** 무엇을 할지 보여 주고, 파이썬 꾸러미 · `claude`·`codex` 명령 ·
키(이름만)를 보고 **못 갖춘 것을 하나씩** 말하고 멈춥니다.
여기서 멈추면 그 목록대로 갖춘 뒤 **같은 명령을 그대로 다시** 넣으십시오.

## ② 실제로 돌릴 때

```bash
python <스킬>/scripts/한줄_돌리기.py <판자리> --조건 "…" --승인
```

어림(비용)을 먼저 말합니다. `--승인` 이 없으면 **돌지 않습니다.**

## ③ 멈췄을 때 — 어디를 보나

| 보는 것 | 무엇이 있나 |
|---|---|
| `<판자리>/상태.json` | **끝난 단계** · 조건 · 승인 여부 |
| `<판자리>/기록/<이름>.jsonl` | 판독자·감독자가 **실제로 한 일** (명령·답) |
| `<판자리>/기록/<이름>.stderr.txt` | 그 자리가 뱉은 오류 |
| `<판자리>/소견.md` | 멈출 일은 아니지만 사람이 정할 거리 |

## ④ 이어가기 — 돈을 두 번 쓰지 않습니다

- **같은 명령을 그대로 다시** 넣으면 멈춘 단계부터 이어갑니다. 끝난 단계는 다시 돌리지 않습니다.
- 한 단계를 처음부터 다시 하려면 — `--되감기 3차감독` 처럼 단계 이름을 줍니다.

## ⑤ 이미 아는 함정 (여기서 막힐 가능성이 큽니다)

1. **Codex 가 pandas 를 못 읽는다** — 돌리개가 Codex 내장 파이썬
   (`~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python`)을 **먼저 잡게** 해 두었습니다.
   그 자리가 없는 컴퓨터에서는 「못 찾았습니다」 라고 알리고 넘어가는데, 거기서 막힐 수 있습니다.
   ★ **이것은 만든 사람 컴퓨터에 맞춘 가정입니다.** 다른 컴퓨터에서 처음 밟힐 자리입니다.
2. **Codex 내장 파이썬에는 `yaml` 이 없습니다** (pandas · openpyxl 은 있습니다 — 2026-10-27 실측).
   그러면 codex 쪽 판독자는 **XLSX 번들과 계약·제출 검사를 못 만듭니다** (CSV 는 나옵니다).
   `--확인만` 이 매번 「! Codex 내장 파이썬에 꾸러미가 없습니다 — yaml」 로 알리고 넣는 명령을 줍니다:

   ```
   "%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" -m pip install pyyaml
   ```

   ★ **멈추지는 않습니다.** 안 넣어도 흐름은 CSV 로 끝까지 갑니다.
3. `claude` · `codex` 는 윈도에서 npm `.cmd` 입니다 — 경로에 한글이 있으면 깨질 수 있습니다.
   ★ **PowerShell 에서 「이 시스템에서 스크립트를 실행할 수 없으므로 … `claude.ps1` …」** 이
     나오면 꾸러미 탓이 아닙니다. `claude` 대신 **`claude.cmd`** 를 치십시오 — 배치 파일이라
     PowerShell 실행 정책을 거치지 않습니다. `cmd /c "claude plugin list"` 도 됩니다.
     실행 정책을 바꾸는 것은 **보안 설정**이라 회사 컴퓨터에서는 전산 담당자에게 물어야 합니다.
4. **라이브 재분석은 외부망이 필요합니다** — 사내망에서 유튜브·OpenAI 를 못 부르면 1차가 막힙니다.
   이미 나온 결과를 보는 것(보고서·대시보드 HTML)은 인터넷 없이 됩니다.

## ⑥ 고쳐 달라고 보낼 것

- 화면의 **오류 글 그대로** (줄여 쓰지 마십시오)
- `<판자리>/상태.json`
- 막힌 자리의 `기록/<이름>.jsonl` **마지막 20줄** 과 `.stderr.txt`

★ **키 값은 보내지 마십시오.** 키는 「있다/없다」만 있으면 됩니다.
"""


_빈컴퓨터_안내 = """# 빈 컴퓨터에서 — 이것만 갖추면 됩니다

★ 2026-10-20 재점검에서 찾은 빈 칸입니다. 전에는 받은 사람이 **스스로 알아내야** 했습니다.

## 차수마다 필요한 것이 다릅니다

| 하려는 것 | 필요한 것 | 키 |
|---|---|---|
| **보고서 · 대시보드 HTML** (최종본을 보기만) | 파이썬 + `pandas` `openpyxl` | **없음** |
| **2차 판독 · 3차 감독 · 총괄** | 거기에 `claude` · `codex` 명령 + **Git** | 없음 |
| **1차 수집·분석** (유튜브에서 모으기) | 거기에 엔진 꾸러미 전부 | **둘 필요** |

즉 **최종본만 받아 보는 사람은 키도 AI 명령도 필요 없습니다.**

## ① 파이썬

```
python 3.11 이상   —  python --version 으로 확인
```

## ② 파이썬 꾸러미

보기만 할 때 (보고서 · 대시보드 HTML) —
★ `pyyaml` 은 **대시보드 HTML** 에 필요합니다 — 엔진의 계산 모듈이 설정 yaml 을 읽습니다.
  2026-10-26 빈 환경에서 밟아 보고 알았습니다 (전에는 둘만 적혀 있어 **빈 컴퓨터에서 막혔습니다**).
  보고서만 만들 때는 `pandas` · `openpyxl` 둘로 됩니다.

```bash
python -m pip install pandas openpyxl pyyaml
```

1차까지 돌릴 때 — 깔 목록이 꾸러미에 **들어 있습니다** —

```bash
python -m pip install -r plugin/engine/requirements.txt
```

## ③ 키 둘 — 1차를 돌릴 때만

본보기가 `plugin/engine/.env.example` 에 있습니다. 환경변수로 넣으십시오.

```
YOUTUBE_API_KEY     댓글을 모읍니다
OPENAI_API_KEY      1차 분석을 합니다 (gpt-4o-mini)
```

**넣는 법** — 한 줄씩 넣고 **창을 새로 켭니다** (환경변수는 새로 켠 창에만 들어옵니다).

PowerShell (윈도우 · 영구)
```
setx YOUTUBE_API_KEY "<받은 키>"
setx OPENAI_API_KEY "<받은 키>"
```

cmd (윈도우 · 영구)
```
setx YOUTUBE_API_KEY "<받은 키>"
```

mac · linux (`~/.zshrc` 나 `~/.bashrc` 에 적고 창을 새로 켭니다)
```
export YOUTUBE_API_KEY="<받은 키>"
export OPENAI_API_KEY="<받은 키>"
```

들어갔는지 보기 — **값이 아니라 「있다/없다」** 만 찍습니다
```
python -c "import os; print('키', [k for k in ('YOUTUBE_API_KEY','OPENAI_API_KEY') if os.environ.get(k)])"
```

★ 키를 이 꾸러미 안의 파일에 적지 마십시오. 꾸러미는 사람에게 건네는 것입니다.
★ 키 **값**을 메일·채팅에 붙이지 마십시오. 「넣었습니다」 만 알려 주시면 됩니다.

## ④ AI 명령 — 2·3·4차를 돌릴 때만

```
claude     Claude Code      2차 판독 한 자리 · 3차 감독 한 자리 · 총괄
codex      Codex CLI        2차 판독 한 자리 · 3차 감독 한 자리
```

★ 판독·감독을 **둘씩 따로** 돌리는 것이 이 분석의 교차검증입니다. 하나로 줄이면
  지금만큼 지켜지지 않습니다 — `Ver3_아직_못_씁니다.md` 에 재 본 숫자가 있습니다.

### Git — Codex 자리를 차릴 때

```
git        Git              Codex 판독·감독 자리를 Git 저장소로 묶습니다 (`git init`)
```

★ 한 줄 흐름(`Ver2_한줄흐름`)은 Codex 자리를 차릴 때마다 그 폴더를 Git 저장소로 묶습니다 —
  Codex 가 스킬(`.agents/skills/`)을 찾을 때 저장소 뿌리까지 올라가기 때문입니다.
  **GitHub 계정은 필요 없습니다.** 내 컴퓨터 안에서만 쓰고 어디에도 올리지 않습니다.
★ 윈도우는 https://git-scm.com 에서 받아 깔고 **창을 새로 켭니다.** `git --version` 이 찍히면 됩니다.
★ 2026-11-09 에 더했습니다 — 전에는 이 줄이 없었고 `--확인만` 도 Git 을 안 봐서,
  Git 없는 컴퓨터는 승인 뒤 2차에서 멈췄을 것입니다 (코드를 읽고 찾았습니다 · 밟아 본 것은 아닙니다).

## ⑤ 안 되는 것 하나

**라이브 재분석**은 이 꾸러미만으로 안 됩니다 — 유튜브와 OpenAI 를 부르려면 외부망이 필요합니다.
이미 나온 결과를 보는 것은 **HTML 파일 하나로 어디서든** 됩니다 (인터넷도 필요 없습니다).

## 갖췄는지 확인하는 법

```bash
python -c "import pandas, openpyxl, yaml; print('보기 준비됨')"
python -c "import streamlit, altair, pydantic; print('대시보드 준비됨')"
python -c "import os; print('키', [k for k in ('YOUTUBE_API_KEY','OPENAI_API_KEY') if os.environ.get(k)])"
git --version
```
"""


_대조_안내 = """
## 옛 꾸러미와 **같은 것이 나오는가** — `대조_원본과_skill.md`

이 꾸러미는 2026년 유튜브 VoC 분석에 쓰던 **옛 꾸러미를 옮겨 지은 것**입니다.
옮기면서 같은 것이 나오는지를 실제로 재었고, **그 결과가 `대조_원본과_skill.md` 에** 있습니다.

세 갈래로 갈려 있습니다 — 재료(기준서 · 프롬프트 · 엔진 228개)는 복사한 것이라 **파일마다
지문**으로 댔고, 도구(파이썬)는 다시 지었으므로 **옛 도구 사본을 돌려 만든 정답 8개**와
파일 전량을 댔으며(파일 2,167개분 · 대조 시험 26개), AI 가 판정하는 세 자리(1차 분석 ·
2차 판독 · 3차 감독)는 바이트로 댈 수 없고 **정확도는 아직 못 잽니다** — 지금 재는 것은
**절차와 형식**입니다. 채점할 정답지(판독 · 감독)는 아직 빈 칸입니다.

얼린 기준을 재현할 때 허용한 차이는 `brand_display` 와 거기서 파생되는 칸뿐이고,
**몇 칸이 다른지까지** 못 박았습니다. **기본으로 돌릴 때는 N/A·미분류 처리가 하나 더
다릅니다**(사람이 정한 변경입니다 — 그 문서에 적어 두었습니다).

`대조장치/` 에 그 대조를 **어떻게 했는지 읽을 수 있는 파일 6개**가 들어 있습니다.
★ 다만 그 대조를 **이 꾸러미만으로 다시 돌리실 수는 없습니다** — 옛 입력 데이터가 801 MB 라
  담지 못했습니다. 왜 그런지도 그 문서에 적어 두었습니다.
"""

# ★ 2026-10-28 — Ver1 만 붙는 꼬리. **Ver1 은 동결 태그에서 꺼낸다**(이 파일 머리 참조).
#   그래서 2026-10-28 독립 점검으로 고친 도구 둘(`PL이슈_뽑기.py` 의 열 누락 멈춤 ·
#   `3차_마무리.py` 의 실패 코드 전달)이 **Ver1 안에는 들어 있지 않다.**
#   그런데 위 대조 안내와 `대조_원본과_skill.md` 는 「고쳤다」 고 적는다 —
#   그대로 담으면 **한 꾸러미에서 말이 둘**이 된다 (2.0.6 에서 겪은 그 종류).
#   동결판을 고치지는 않는다(동결의 뜻이 사라진다). 대신 **어긋남을 꾸러미 안에 적는다.**
_Ver1_대조_꼬리 = """
### ★ 이 판(Ver1)에만 해당하는 것 — 위 문서의 **고침이 이 판에는 안 들어 있습니다**

Ver1 은 **동결한 판**이라 태그(`ver1-유튜브VoC분석내부화`)에서 그대로 꺼냅니다.
2026-10-28 독립 점검으로 **도구 둘을 고쳤는데, 그 고침은 Ver2 에만 들어 있습니다.**

| 고친 것 | Ver2 | 이 판(Ver1) |
|---|---|---|
| `PL이슈_뽑기.py` — `topic`·`status`·`atomic_id` 가 없으면 **멈춘다**(종료코드 2) | 들어 있음 | **없음** — 머리만 있는 `PL이슈.csv` 를 만들고 0 으로 끝납니다 |
| `3차_마무리.py` — PL 뽑기가 실패하면 **거기서 멈춘다** | 들어 있음 | **없음** — ★PL Issue 시트가 빠진 채 끝까지 갑니다 |

★ 이 구멍은 **옛 꾸러미에도 있던 것**이고(옮기다 깨진 것이 아닙니다), 옛 실제 데이터는
  필요한 칸 89개를 다 갖고 있어 **터진 적은 없습니다**(PL 213행 정상). 그래도 적어 둡니다 —
  칸이 빠진 입력을 넣으면 「안전·위생 0 건」 으로 조용히 끝납니다. **PL 은 제품 안전 건입니다.**
  동결판을 고치면 동결의 뜻이 사라지므로, 고치지 않고 **어긋남을 적는 쪽**을 골랐습니다.
  이 일이 걸리는 자리라면 **Ver2 를 쓰십시오.**
"""

# 꾸러미마다 같이 담을 대조 자료 — **원본은 저장소 한 벌**이고 여기서 베껴 담는다.
#   ★ 왜 꾸러미 안에 넣나 (sky 2026-10-28 「실무 단계로 성공적으로 넘어가면 skill zip만
#     줄것입니다」) — 그러면 원본 바탕자료를 같이 주지 않는다. 「옛 것과 같은가」 를 재어 본
#     기록이 받는 사람 손에 하나도 남지 않으므로, 꾸러미 안에 같이 넣는다.
_대조자료 = {
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


def _대조자료_담기(받을곳: Path) -> int:
    """대조 문서와 대조 장치를 꾸러미에 베껴 담는다. 하나라도 없으면 **멈춘다**."""
    for 안, 원 in _대조자료.items():
        if not 원.is_file():
            raise SystemExit("못 찾음: 대조 자료 %s 가 없다 — 꾸러미를 만들지 않는다" % 원)
        q = 받을곳 / 안
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(원, q)
    return len(_대조자료)


def 만들기(자리: Path) -> int:
    if 자리.exists():
        shutil.rmtree(자리)
    자리.mkdir(parents=True)
    기록 = {"설명": "판_묶기.py 가 만든 것 — 손으로 고치지 않는다. tests/test_판꾸러미.py 가 원본과 대조한다",
          "판": {}}

    # ── Ver1 — 동결 태그에서
    임시 = 자리 / "_태그사본"
    _태그에서_꺼내기(Ver1태그, 임시)
    태그플러그인 = 임시 / "plugin"
    if not (태그플러그인 / "skills").is_dir():
        raise SystemExit("못 찾음: 태그 %s 에 plugin/skills 가 없다" % Ver1태그)
    돌리개 = 태그플러그인 / "skills" / "coordinating-voc-pipeline" / "scripts" / "한줄_돌리기.py"
    if 돌리개.exists():
        raise SystemExit("태그 %s 에 한줄_돌리기.py 가 있다 — Ver1 의 뜻이 바뀐 것이니 멈춘다" % Ver1태그)
    판들 = [("Ver1_스킬다섯", 태그플러그인, _Ver1_읽어주세요, "태그 " + Ver1태그,
           _Ver1_대조_꼬리),
          ("Ver2_한줄흐름", PLUGIN, _Ver2_읽어주세요, "지금 판(작업 자리)", "")]
    for 이름, 바탕, 읽어주세요, 어디서, 대조꼬리 in 판들:
        받을곳 = 자리 / 이름
        표 = _담기(바탕, 받을곳)
        덧붙인것: dict = {}        # plugin/ 밖에 담는 것 — 차림표에 따로 적는다
        # ★ 2026-10-28 — 안내 끝에 **대조 안내**를 붙인다. 실무에서는 이 zip 하나만
        #   가므로, 「옛 것과 같은가」 를 재어 본 기록을 꾸러미 안에서 찾을 수 있어야 한다.
        (받을곳 / "0_읽어주세요.md").write_text(
            읽어주세요.rstrip() + "\n" + _대조_안내 + 대조꼬리,
            encoding="utf-8", newline=chr(10))
        # ★ 2026-10-22 — 전에는 이 안내를 **zip 을 봉한 뒤** 폴더에만 썼다. 그래서
        #   사람에게 건네는 zip 안에는 없었다 (푼 자리에 `0_읽어주세요.md` 와 `plugin` 뿐).
        #   시험은 **폴더**를 보고 있어 통과했다 — 폴더에는 있었으니까.
        (받을곳 / "0_빈컴퓨터에서_무엇을_깔까.md").write_text(
            _빈컴퓨터_안내, encoding="utf-8", newline=chr(10))
        # ★ 2026-10-27 — 다른 컴퓨터에서 **한 번에 안 돌아가는 것이 정상**이다 (sky).
        #   그때 무엇을 보고 무엇을 보내면 되는지를 꾸러미 안에 같이 넣는다.
        (받을곳 / "0_막히면_이_순서로.md").write_text(
            _막히면_안내, encoding="utf-8", newline=chr(10))
        # ★ 2026-10-28 설치 예행 — 빈 폴더에 zip 만 풀어 보니, 두 안내가 「`Ver3_아직_못
        #   _씁니다.md` 를 보십시오」 라고 가리키는데 **그 파일이 꾸러미 안에 없었다.**
        #   `dist/판/` 에만 썼기 때문이다. 받는 사람에게 건네는 것은 zip 하나다
        #   (`0_읽어주세요.md` 가 「**이 꾸러미 하나만** 건네면 됩니다」 라고 적는다).
        #   2026-10-22 에 `0_빈컴퓨터에서…` 로 같은 것을 겪었는데 Ver3 만 남아 있었다.
        (받을곳 / "Ver3_아직_못_씁니다.md").write_text(
            _Ver3_안내, encoding="utf-8", newline=chr(10))
        # ★ 2026-10-29 — Ver2 에만 `.claude-plugin/marketplace.json` 을 담는다.
        #   왜 — 꾸러미에 `plugin/.claude-plugin/plugin.json` 은 있는데 **마켓플레이스 쪽이
        #   없어** `claude plugin marketplace add` 가 안 됐다. 즉 받는 사람은 명령 한 줄로만
        #   돌릴 수 있고 **새 채팅방에서 말로 시키는 길이 막혀 있었다** — 스킬로 옮긴 뜻의
        #   절반이 빠진다. 저장소 것을 그대로 베낀다 (손으로 적지 않는다 · 공통 규칙 6).
        #   `source` 가 `./plugin` 이라 **푼 폴더 뿌리에서 바로** 맞는다 (실제로 validate 로 확인).
        #   ★ Ver1 에는 담지 않는다 — Ver1 은 동결 태그에서 꺼내므로 안내문이 이 길을 모른다.
        if 이름 == "Ver2_한줄흐름":
            장터 = REPO / ".claude-plugin" / "marketplace.json"
            if not 장터.is_file():
                raise SystemExit("못 찾음: %s — Ver2 를 플러그인으로 등록할 수 없게 된다" % 장터)
            받을장터 = 받을곳 / ".claude-plugin" / "marketplace.json"
            받을장터.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(장터, 받을장터)
            덧붙인것[".claude-plugin/marketplace.json"] = _sha(장터)
        담은대조 = _대조자료_담기(받을곳)
        크기 = sum(p.stat().st_size for p, _ in 표)
        z = 자리 / (이름 + ".zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for q in sorted(받을곳.rglob("*")):
                if q.is_file():
                    zf.write(q, "%s/%s" % (이름, q.relative_to(받을곳).as_posix()))
        기록["판"][이름] = {"어디서": 어디서, "파일수": len(표),
                        "풀었을때바이트": 크기, "zip바이트": z.stat().st_size,
                        "파일": {안: _sha(원) for 원, 안 in 표},
                        # ★ `파일` 은 **`plugin/` 것만**이다 — 그 목록을 git 과 대는 시험이 있다
                        #   (`test_두_판의_차이는_태그_뒤에_바뀐_것뿐이다`). plugin/ 밖에 담은 것을
                        #   거기 섞으면 그 시험이 「뜻 없이 갈렸다」 고 잡는다. 그래서 따로 적는다.
                        "덧붙인것": 덧붙인것}
        print("  · %-16s %3d개 (+대조자료 %d개) · %4.1f MB (풀었을 때) · zip %4.1f MB — %s"
              % (이름, len(표), 담은대조, 크기 / 1048576,
                 z.stat().st_size / 1048576, 어디서))
    shutil.rmtree(임시)

    (자리 / "Ver3_아직_못_씁니다.md").write_text(_Ver3_안내, encoding="utf-8", newline="\n")
    (자리 / "0_빈컴퓨터에서_무엇을_깔까.md").write_text(
        _빈컴퓨터_안내, encoding="utf-8", newline=chr(10))
    (자리 / "0_막히면_이_순서로.md").write_text(_막히면_안내, encoding="utf-8", newline=chr(10))
    print("  · Ver3            꾸러미 없음 — 안내문 하나 (코드가 없다)")
    (자리 / "차림표.json").write_text(json.dumps(기록, ensure_ascii=False, indent=1) + "\n",
                                  encoding="utf-8", newline="\n")
    (자리 / "0_어느_것을_쓰나.md").write_text(
        "# 어느 것을 건네면 되나\n\n"
        "| 하고 싶은 일 | 건네는 것 |\n"
        "|---|---|\n"
        "| 단계마다 사람이 부린다 | `Ver1_스킬다섯.zip` **하나** |\n"
        "| 한 줄 넣고 최종 엑셀까지 간다 | `Ver2_한줄흐름.zip` **하나** |\n"
        "| 구독을 하나로 줄인다 | `Ver3_아직_못_씁니다.md` 를 먼저 읽으십시오 (아직 못 씁니다) |\n\n"
        "셋 다 **Claude Code** 용입니다. 풀고 각 꾸러미의 `0_읽어주세요.md` 를 보십시오.\n\n"
        "claude.ai 웹에 올릴 스킬 zip(스킬당 하나)과 Codex 용 `.agents/skills/` 사본은\n"
        "`python tools/build_skills.py` 가 따로 만듭니다.\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    자리 = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "dist" / "판"
    print("판 묶기 → %s" % 자리)
    코드 = 만들기(자리)
    print("끝 — 종료코드 %d" % 코드)
    sys.exit(코드)
