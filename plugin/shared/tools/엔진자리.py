# -*- coding: utf-8 -*-
"""1차 분석엔진이 어디 있는지 찾는다 — 이 일은 여기 한 곳에서만 한다.

★ 왜 (2026-08-23)
  도구마다 제각기 찾다가 남의 PC 에서 세 번 따로 터졌다.
    `No module named 'src'` · `src.voc_rebuild.engine` · `src.voc_secondary.na_rules`

  ★ 찾는 차례
    ① VOC_ENGINE 환경변수      — 총괄이 대놓고 가리킬 때
    ② 꾸러미가 지고 온 engine/  — **남의 PC 에서는 이것뿐이다**
    ③ 총괄 컴퓨터의 정본 엔진 자리 (아래 코드에 적혀 있다)
"""
import os
import sys

_여기 = os.path.dirname(os.path.abspath(__file__))
_뿌리 = (os.path.dirname(_여기)
        if os.path.basename(_여기) in ("스크립트", "scripts") else _여기)


def 앉히기() -> str:
    """엔진 자리를 sys.path 맨 앞에 놓고, 그 자리를 돌려준다.

    못 찾으면 빈 글자를 돌려준다 — 부르는 쪽이 판단한다.
    """
    for _c in (os.environ.get("VOC_ENGINE"),
               os.path.join(_뿌리, "engine"),
               os.path.join(_여기, "engine")):
        if _c and os.path.isdir(_c):
            while _c in sys.path:
                sys.path.remove(_c)
            sys.path.insert(0, _c)
            return _c
    return ""
