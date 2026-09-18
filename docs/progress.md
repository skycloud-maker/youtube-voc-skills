# 진행 파일 — 새 대화는 이것과 `git log` 를 먼저 읽는다

규칙 (building-agents 하네스): 한 번에 한 섹션 · 섹션마다 커밋 ·
**시험을 통과한 뒤에만 「통과」 로 표시**한다.

## 섹션

| # | 섹션 | 상태 | 확인 |
|---|---|---|---|
| 1 | 판 차리기 — 뼈대 · 역할 지도 · 진행 파일 · 비공개 원격 | 통과 | `claude plugin validate` 둘 다 통과 · 원격 PRIVATE · 차이 0 (2026-09-18) |
| 2 | 경로 한 자리(`paths.py`) + 옛 도구·새 도구 결과 맞대기 시험 | 대기 | — |
| 3 | `plugin/shared/` — 기준서·택소노미·Enum 원본 한 벌 + 대조 검사 | 대기 | — |
| 3a | 조사 — Codex 가 SKILL.md 스킬을 읽는지 (판독·감독에 Codex 가 한 자리씩) | 대기 | — |
| 4 | 첫 스킬 `reading-voc-comments` — 시험 3개 먼저 | 대기 | — |
| 5 | `supervising-voc-disagreements` → `coordinating-voc-pipeline` → `running-voc-engine` | 대기 | — |
| 6 | `tools/build_skills.py` · `check_shared.py` → `dist/*.skill` | 대기 | — |
| 7 | 엔진(동결본) · 대시보드(09-07 최신판) 옮기기 + 동작 확인 | 대기 | — |
| 8 | ★ 마지막 — `building-voc-report`: 최종 결과로 사내 전용 HTML 보고서. 전부 사내 스킬로 | 대기 | — |

스킬 구성은 [ROLES.md](ROLES.md) 가 정본 (2026-09-18 확정: 스킬 넷 + 보고서 스킬, 사람은 안내서).
갈라진 판은 **최신판이 정본**, 옛판은 `docs/history/` 에 이력으로만 (sky 2026-09-18).

## 작업 규칙은 어디에

- **공통 규칙**(모든 프로젝트): `C:\_공통_작업규칙\` — 규칙 · 절차 스킬 · 훅. 이 저장소에 복사하지 않는다.
- **이 저장소 전용 규칙**: 아직 없다. 유튜브 VoC 스킬만을 위한 규칙이 생기면 그때
  이 저장소 맨 위에 `CLAUDE.md` 를 만들어 추가한다 (sky 2026-09-18).

## 원본 자리 (복사해 오는 곳 — 원본은 고치지 않는다)

```
2차 문서·도구   C:\codex\outputs\voc_secondary        갈래 codex/voc-second-stage
엔진·대시보드   C:\codex_live_merge                   갈래 codex/voc-engine-rebuild
엔진 동결       d78dc8c
```

## 알게 된 함정

- 원본 도구들이 경로를 파일마다 박아 둠 → 섹션 2 에서 `paths.py` 한 곳으로 모은다.
- 원본 꾸러미 조사 (2026-09-18): 도구 7개에 절대경로 · 엔진 찾는 순서가 도구마다 다름 ·
  엔진 핵심 voc_rebuild 는 꾸러미/정상본 15파일 같음 · dashboard60 8파일 다름(정상본이 09-07 최신) ·
  voc_secondary 는 정상본에 없고 voc-secondary-p0 워크트리와 꾸러미에만 있음 · build_bundle 이 꾸러미 4곳에 복사돼 있음
- 원본 저장소의 push 검사기가 zip 만 바뀐 커밋을 「올라가는 파일 0개」 로 셌다 (2026-09-18).
