# youtube-voc-skills

유튜브 댓글에서 제품 개선 포인트(VoC)를 찾는 업무를 **Claude 스킬로 넘기기 위한** 저장소.
스킬만 받으면 같은 순서·같은 기준으로 같은 업무를 할 수 있게 하는 것이 목표다.

> ## 「Ver2 한줄흐름 + 대시보드」 — 2026-10-23 동결
>
> Ver1 의 **스킬 다섯**에 둘을 더했다 — **한 줄 돌리개**와 **여섯 번째 스킬**(대시보드 HTML 한 장).
> 태그 `ver2-한줄흐름-대시보드` · [결정 0005](docs/decisions/0005-Ver2-동결.md).
>
> | 하고 싶은 일 | 건네는 것 |
> |---|---|
> | 단계마다 사람이 부린다 | `dist/판/Ver1_스킬다섯.zip` **하나** |
> | 한 줄 넣고 최종 엑셀·보고서·대시보드까지 간다 | `dist/판/Ver2_한줄흐름.zip` **하나** |
> | 최종본을 **보기만** 한다 | 대시보드 **HTML 한 장** (파이썬도 인터넷도 필요 없다) |
> | 구독을 하나로 줄인다 | `dist/판/Ver3_아직_못_씁니다.md` 를 먼저 읽는다 (아직 못 쓴다) |
>
> ★ 동결은 **「되돌아올 자리」** 다. **「검증 완료」 가 아니다** — 못 잰 것 셋(1차 · 보고서 ·
> 사람 결정이 든 4차)을 결정 0005 에 적었다. 다음 일은 **그 4차를 재는 것**이다.
>
> 아래는 Ver1 동결 때의 기록이다.

> ## 「유튜브VoC분석내부화 Ver1」 — 2026-10-09 동결
>
> 1차 수집·분석부터 사내 보고서까지 **스킬 다섯**으로 옮겼다. 기계 시험과 **실제 AI 시험** 양쪽을 통과했다.
> 태그 `ver1-유튜브VoC분석내부화` · [결정 0003](docs/decisions/0003-Ver1-동결.md) 에 재고·한계·되돌아갈 자리가 있다.
>
> | 역할 | 스킬 | 누가 |
> |---|---|---|
> | 1차 실행 (수집 + 분석엔진) | `running-voc-engine` | Claude Code |
> | 2차 판독 ×2 | `reading-voc-comments` | Claude Code · Codex |
> | 3차 감독 ×2 | `supervising-voc-disagreements` | Codex · Claude Code |
> | 차수 잇기 · 4차 반영 | `coordinating-voc-pipeline` | Claude Code |
> | 사내 보고서 | `building-voc-report` | Claude Code |
>
> 4차 검토는 **사람 몫**이다 (원래 그렇게 설계됐다).
> **다음은 Ver2** — Codex 가 하던 역할을 Claude 가 대신하게 해 AI 엔진 하나로 돌린다.

> **독립된 새 출발이다.** 원본 저장소 `youtube-comment-analyzer` 와 지금의 Streamlit 사이트는
> 새 구현이 안 될 때 돌아갈 예비로 그대로 두고, 여기서 제로부터 새로 세팅한다 (새 GitHub 저장소 ·
> 새 Streamlit 사이트). 옛 폴더는 한 번 복사할 때만 읽고, 그 뒤로 엮지 않는다 —
> [결정 0001](docs/decisions/0001-독립된-새-출발.md).
> 데이터(댓글 원문·결과 파일)는 넣지 않는다. 검증용 정답 사례만 가려서 둔다.

## 어디를 보면 되나

| 하려는 일 | 볼 폴더 |
|---|---|
| 역할별로 무엇을 하는지 | [`docs/ROLES.md`](docs/ROLES.md) — 원문을 가리키는 지도 |
| 사람(운영자 · 4차 실무자)이 읽는 안내서 — 새 구현에 맞춰 새로 쓴다 (아직 없음) | `guides/` |
| 옛 저장소에서 옮겨 온 원문 (문서·코드·화면 문구 그대로 · 옛 자리가 적혀 있음) | `docs/sources/` |
| 기준서·어휘·검사 규칙 (원본 한 벌) | `plugin/shared/` |
| 역할별 스킬 | `plugin/skills/<스킬 이름>/` |
| 1차 분석 엔진 + 대시보드 — 옛 live_merge 동결본 (고치지 않음 · 아래 「지키는 것」) | `plugin/engine/` |
| 대시보드 — 새로 만든다 (아직 없음 · 섹션 7a) | `plugin/dashboard/` |
| 스킬을 낱개로 묶기 — `python tools/build_skills.py` 가 묶고 `python tools/check_shared.py` 가 원본과 한 파일씩 대조한다 (섹션 6) | `tools/` → 결과는 `dist/` (생성물 · git 에 넣지 않음) |
| 옛 도구와 결과가 같은지 시험 | `tests/` — 기준 정답은 댓글 원문이 있어 **저장소 밖**에 둔다. 자리는 `plugin/shared/paths.py` 의 `BASELINE` ([결정 0002](docs/decisions/0002-기준정답은-도구사본을-돌려-만든다.md)) |
| 무엇을 왜 정했나 · 진행 상황 | `docs/decisions/` · [`docs/progress.md`](docs/progress.md) |

## ★ 판마다 **건네줄 것 하나** (sky 2026-10-09)

```
python tools/판_묶기.py        →  dist/판/
```

| 하고 싶은 일 | 건네는 것 | 들머리 |
|---|---|---|
| 단계마다 사람이 부린다 | `Ver1_스킬다섯.zip` **하나** | `claude --plugin-dir <풀린자리>/plugin` 하고 말로 시킨다 |
| 한 줄 넣고 최종 엑셀까지 간다 | `Ver2_한줄흐름.zip` **하나** | `python …/한줄_돌리기.py <판자리> --조건 "…"` |
| 구독을 하나로 줄인다 | `Ver3_아직_못_씁니다.md` | 아직 못 쓴다 — 왜인지와 측정값이 적혀 있다 |

- 셋 다 **Claude Code** 용이다. claude.ai 웹은 공식 제한으로 **zip 하나에 스킬 하나**라
  다섯 개를 올려야 하고, 1차(유튜브 수집)와 총괄의 AI 띄우기가 돌지 않는다 → 아래 2번을 쓴다.
- **Ver1 은 동결 태그 `ver1-유튜브VoC분석내부화` 에서, Ver2 는 지금 판에서** 꺼낸다.
  Ver1 은 한 줄 돌리개가 생기기 전에 동결했으니 그 꾸러미에는 돌리개가 **아예 없다** — 어느 판인지
  헷갈리지 않는다. 두 꾸러미의 차이는 **돌리개 파일 하나뿐**이어야 하고,
  `tests/test_판꾸러미.py` 가 태그·지금 판과 한 파일씩 대조해 그것을 지킨다.
- Ver3 은 **코드가 없어 꾸러미를 만들지 않는다.** 되는 척하는 빈 꾸러미가 더 헷갈린다.

## 나눠 주는 방식 (세 가지)

1. **플러그인 하나 (Claude Code)** — 저장소 맨 위 `.claude-plugin/marketplace.json` 이 마켓플레이스다.
   받는 사람이 Claude Code 에서 `/plugin marketplace add skycloud-maker/youtube-voc-skills` →
   `/plugin install youtube-voc@youtube-voc-skills`. 비공개 저장소라 받는 사람의 git 로그인(`gh auth login` 등)이 필요하다.
2. **낱개 스킬 (claude.ai · Claude 데스크톱)** — `dist/claude/<스킬>.zip` 을 「Settings > Features」 에 올린다.
   zip 맨 위에 스킬 폴더 하나 · 공통 파일(`shared/` · `engine/`)은 조립 도구가 스킬 안에 복사해 넣는다.
   `.skill` 은 확장자만 다른 같은 파일이다.
3. **Codex** — `dist/codex/.agents/` 를 저장소 맨 위나 `$HOME` 에 통째로 둔다 (Codex 는 `.agents/skills/` 를 읽는다 · 섹션 3a).

낱개 묶음은 원본과 한 글자라도 다르면 `check_shared.py` 가 실패한다. 묶은 뒤 원본을 고쳤으면 다시 묶는다.
근거: [조사 2026-09-22](docs/research/2026-09-22_스킬_묶음_배포_조사.md).

## 지키는 것

- **축약 금지** (sky 2026-09-18). 원본의 역할·절차·도구·안내문은 원문 그대로 옮기고,
  새 문서는 원문을 가리킨다. 줄여야 하면 줄이기 전에 sky 에게 묻는다.
- 갈라진 판은 **최신판이 정본**. 옛판은 이력으로만 둔다.
- API 키 등 비밀값은 저장소에 넣지 않는다. 받는 사람 환경에서 읽는다.
- `plugin/engine/` 은 **1차 분석 엔진 정본**이다 — 옛 live_merge 동결본(커밋 a94e731 · 엔진 코드는 동결 `d78dc8c` 와 같다 · 대시보드 09-07)에서
  섹션 7 ① (2026-09-22 · sky 결정)에 한 번 들여왔다. 파일마다 출처는 `plugin/engine/출처_엔진.json`. 고치지 않는다.
  판독 · 감독 폴더에는 이 가운데 옛 꾸러미가 싣던 28개 자리만 간다(`shared/lib/꾸러미.py` 의 `꾸러미엔진`).
  API 키는 저장소에 넣지 않는다 — sky 결정: **Windows 사용자 환경변수** `YOUTUBE_API_KEY` · `OPENAI_API_KEY`.
- `dist/` 는 생성물이다. 손으로 고치지 않는다.

## 글자 점검 — 깨짐과 라벨 오타

```
python plugin/shared/tools/글자_점검.py [<폴더> ...]
```

★ 왜 — 라벨이 **한 글자** 틀리면 집계가 조용히 둘로 갈린다
(「제조사 신뢰/품질」 과 「제조사 실뢰/품질」 은 사람 눈에 거의 같아 보인다).
sky 2026-10-09 요청으로 만들었다.

| 보는 것 | 무엇 |
|---|---|
| 깨진 글자 | 치환문자(U+FFFD) · 제어문자 · 한글 사이에 끼어든 자모 · 한글에 맞붙은 한자(cp949 깨짐 꼴) |
| 라벨 오타 | 정본 대장(`registry/topic_group_map.json`)과 **한두 글자 차이**인 라벨 |
| 인코딩 | UTF-8 로 못 읽는 파일 · NFC 가 아닌 저장 |

`tests/test_글자점검.py` 가 점검기를 지킨다 (일부러 다섯 가지로 깨 보고, 사람이 쓴
`ㅋㅋ`·`ㅜㅜ` 는 안 걸리는 것까지 확인한다).

★ **엔진 동결 사본의 「깨진 글자」 둘은 일부러 둔 것이다** (2026-10-20 확인 · 고치지 않는다).
`engine/voc-classifier/src/classifier.py:47` 은 `# Mojibake compatibility markers
(existing harness data)` — 옛 데이터에 든 깨진 글자를 **알아보려고** 목록에 넣었다.
`engine/src/application/shadow/semantic_sidecar.py:4868` 은 「옛 동작을 산출물 호환을 위해
보존하고, 실행 때는 일부러 덧붙인 깨끗한 v2 규칙을 쓴다」 고 적어 두었다.
고치면 옛 산출물을 못 알아본다. 그래서 시험은 「고쳤나」 가 아니라
**「수가 늘지 않았나」** 를 지킨다 — 새로 깨진 파일이 생기면 그것은 진짜 결함이다.
