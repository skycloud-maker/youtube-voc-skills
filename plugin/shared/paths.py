# -*- coding: utf-8 -*-
"""경로는 여기 한 곳에서만 정한다.

★ 왜 (섹션 2, 2026-09-18)
  옛 도구들은 경로를 파일마다 박아 두었다 (옛 엔진 자리 등 도구 7개).
  도구마다 엔진 찾는 순서도 달랐다. 새 저장소의 코드 · 스킬 · 시험은
  경로가 필요하면 반드시 이 파일에서 가져온다. 다른 파일에 절대경로를 쓰면
  `tests/test_no_old_paths.py` 가 실패한다.

★ 옛 저장소 폴더는 여기에도 없다 — 결정 0001.
"""
from __future__ import annotations

import os
from pathlib import Path

# 이 저장소 안의 자리 — 파일 위치로부터 센다 (어느 컴퓨터에서도 같다)
SHARED = Path(__file__).resolve().parent            # plugin/shared
PLUGIN = SHARED.parent                              # plugin
REPO = PLUGIN.parent                                # 저장소 맨 위
ENGINE = PLUGIN / "engine"                          # 1차 엔진 — 지금은 판독 꾸러미 엔진 사본 (섹션 7 에서 동결본과 맞춘다)
TESTS = REPO / "tests"

# 저장소 밖 — 기준 정답 데이터 (댓글 원문이 들어 있어 git 에 넣지 않는다)
#   다른 컴퓨터에서는 VOC_BASELINE 환경변수로 가리킨다.
#   못 찾으면 시험은 **실패**한다 — 「못 찾음」 은 「통과」 가 아니다.
BASELINE = Path(os.environ.get("VOC_BASELINE")
                or r"C:\작업\youtube-voc-skills_기준데이터")

# 스킬 시험(실제 AI)을 돌리는 외딴 자리 — 저장소 밖 · 기준 자리 밖 (2026-09-21)
#   ★ 시험 폴더들이 한자리에 모여 있으면 AI 가 옆 시험의 채점 결과를 읽거나 남의 스킬을 가져다 썼다
#     (스킬 없는 비교 시험 5개가 그렇게 오염됐다). 그래서 한 번에 한 시험만, 옆에 아무것도 없는 자리에서 돌리고
#     끝나면 기준 자리의 `스킬시험/` 으로 옮긴다. 다른 컴퓨터에서는 VOC_EVAL_ROOT 로 가리킨다.
EVAL_ROOT = Path(os.environ.get("VOC_EVAL_ROOT") or r"C:\voc_시험격리")
