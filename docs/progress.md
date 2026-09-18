# 진행 파일 — 새 대화는 이것과 `git log` 를 먼저 읽는다

규칙 (building-agents 하네스): 한 번에 한 섹션 · 섹션마다 커밋 ·
**시험을 통과한 뒤에만 「통과」 로 표시**한다.

## 섹션

| # | 섹션 | 상태 | 확인 |
|---|---|---|---|
| 1 | 판 차리기 — 뼈대 · 역할 지도 · 진행 파일 · 비공개 원격 | 진행 중 | — |
| 2 | 경로 한 자리(`paths.py`) + 옛 도구·새 도구 결과 맞대기 시험 | 대기 | — |
| 3 | `plugin/shared/` — 기준서·택소노미·Enum 원본 한 벌 + 대조 검사 | 대기 | — |
| 4 | 첫 스킬 `reading-voc-comments` — 시험 3개 먼저 | 대기 | — |
| 5 | 나머지 스킬 다섯 | 대기 | — |
| 6 | `tools/build_skills.py` · `check_shared.py` → `dist/*.skill` | 대기 | — |
| 7 | 엔진(동결본) · 대시보드 옮기기 + 동작 확인 | 대기 | — |

## 원본 자리 (복사해 오는 곳 — 원본은 고치지 않는다)

```
2차 문서·도구   C:\codex\outputs\voc_secondary        갈래 codex/voc-second-stage
엔진·대시보드   C:\codex_live_merge                   갈래 codex/voc-engine-rebuild
엔진 동결       d78dc8c
```

## 알게 된 함정

- 원본 도구들이 경로를 파일마다 박아 둠 → 섹션 2 에서 `paths.py` 한 곳으로 모은다.
- 원본 저장소의 push 검사기가 zip 만 바뀐 커밋을 「올라가는 파일 0개」 로 셌다 (2026-09-18).
