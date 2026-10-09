# youtube-voc-skills

유튜브 댓글에서 제품 개선 포인트(VoC)를 찾는 업무를 **Claude 스킬로 넘기기 위한** 저장소.
스킬만 받으면 같은 순서·같은 기준으로 같은 업무를 할 수 있게 하는 것이 목표다.

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
