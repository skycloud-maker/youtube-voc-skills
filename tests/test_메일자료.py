# -*- coding: utf-8 -*-
"""메일 자리에 들어가는 자료가 **저장소 원본과 같은가** (2026-10-29).

★ 왜 이제 만들었나 — `tools/메일_대조자료_갱신.py:40` 이 주석으로
  「`tests/test_메일자료.py::test_옛쪽과_새쪽이_같은_일곱벌을_담는다` 가 그것을 댄다」 고
  (그때 주석에 적혀 있던 이름 그대로다. 2026-10-29 에 벌 수가 아홉으로 늘어
   이름에서 숫자를 뺐다 — **번호로 이름을 지으면 겹친다**. 아래가 지금 이름이다)
  적어 두었는데 **그 파일이 없었다.** 가리키기만 하고 없는 가드다 — 2026-10-28 에 꾸러미
  안내가 없는 `.ps1` 을 가리킨 것과 같은 갈래다. 가리킨 것을 **있게 만든다.**

보는 것
  ① 옛 쪽(메일 zip)과 새 쪽(판 꾸러미)이 **같은 아홉 벌**을 담는가 — 두 도구의 목록을 댄다.
  ② 그 아홉 벌의 원본이 저장소에 **정말 있는가** (「못 찾음」 은 통과가 아니다).
  ③ 메일 자리를 맞추는 도구가 베끼는 셋의 원본이 있고, **어긋나면 어긋났다고 말하는가.**
  ④ 메일 자리가 없을 때 **0 으로 끝내지 않는가** (종료코드 2).

★ 메일 자리(`dist/메일/`)는 gitignore 되어 있다. 그 자리가 없으면 ③④ 는 건너뛰는 대신
  **도구가 멈추는지**를 본다 — 자리 없이도 잴 수 있는 것만 잰다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "tools"))
from paths import REPO  # noqa: E402

묶개 = pytest.importorskip("판_묶기", reason="판_묶기.py 를 못 읽었다")
갱신개 = pytest.importorskip("메일_대조자료_갱신", reason="메일_대조자료_갱신.py 를 못 읽었다")
메일개 = pytest.importorskip("메일자리_갱신", reason="메일자리_갱신.py 를 못 읽었다")


def test_옛쪽과_새쪽이_같은_벌을_담는다():
    """★ 한쪽만 늘거나 줄면 **같은 꾸러미에서 자료가 두 벌**이 된다 (공통 규칙 6).

    ★ 2026-10-29 — 7벌에서 **9벌**로 늘었다. 「안 옮긴 것」 을 세는 대장 둘
      (`옛꾸러미_대장.md` · `옛꾸러미_목록.json`)을 더했다 — 점검요청 문서가
      그 둘을 가리키므로, 안 담으면 **가리키기만 하고 없는 자리**가 된다.
    """
    새쪽 = 묶개._대조자료
    옛쪽 = 갱신개.갈아끼울것
    assert len(새쪽) == 9, "새 쪽 대조 자료가 9벌이 아니다 — %d" % len(새쪽)
    assert set(새쪽) == set(옛쪽), (
        "담는 자료가 다르다 — 새 쪽만: %s / 옛 쪽만: %s"
        % (sorted(set(새쪽) - set(옛쪽)), sorted(set(옛쪽) - set(새쪽))))
    다른원본 = {k: (새쪽[k], 옛쪽[k]) for k in 새쪽 if 새쪽[k] != 옛쪽[k]}
    assert not 다른원본, "같은 이름인데 **다른 원본**을 베낀다 — %s" % 다른원본


def test_그_벌들의_원본이_저장소에_있다():
    없음 = [str(원) for 원 in 묶개._대조자료.values() if not Path(원).is_file()]
    assert not 없음, "대조 자료의 원본이 없다 — %s" % 없음
    # ★ 하나도 못 찾으면 그것도 실패다
    assert len(묶개._대조자료) >= 9


def test_메일자리_갱신이_베끼는_셋의_원본이_있다():
    베낄것 = 메일개.베낄것
    assert set(베낄것) == {"Ver2_한줄흐름.zip", "0_메일에_붙일_것.md", "0_점검요청_붙여넣을_것.md"}, \
        sorted(베낄것)
    # 판 꾸러미는 `판_묶기.py` 를 안 돌렸으면 없을 수 있다 — 그것은 이 시험의 몫이 아니다
    글원본 = {k: v for k, v in 베낄것.items() if not str(v).endswith(".zip")}
    없음 = [str(v) for v in 글원본.values() if not Path(v).is_file()]
    assert not 없음, "메일에 붙일 글의 원본이 저장소에 없다 — %s" % 없음
    # 메일 자리 글의 원본은 **docs/ 안**이어야 한다 (gitignore 되는 자리를 원본으로 삼지 않는다)
    for k, v in 글원본.items():
        assert Path(v).parent == REPO / "docs", "%s 의 원본이 docs/ 가 아니다 — %s" % (k, v)


def test_메일자리가_없으면_0으로_끝내지_않는다(tmp_path, monkeypatch):
    """★ 「못 찾음」 은 통과가 아니다 — 자리가 없는데 0 이면 아무것도 안 하고 「됐다」 가 된다."""
    monkeypatch.setattr(메일개, "메일자리", tmp_path / "없는자리")
    assert 메일개.main(["--확인만"]) == 2
    monkeypatch.setattr(갱신개, "메일자리", tmp_path / "없는자리")
    assert 갱신개.main(["--확인만"]) == 2


def test_옛쪽_zip이_하나도_없으면_0으로_끝내지_않는다(tmp_path, monkeypatch):
    빈자리 = tmp_path / "빈메일자리"
    빈자리.mkdir()
    monkeypatch.setattr(갱신개, "메일자리", 빈자리)
    assert 갱신개.main(["--확인만"]) == 2, "옛 쪽 zip 이 없는데 0 으로 끝났다"


def test_어긋나면_어긋났다고_말한다(tmp_path, monkeypatch):
    """베낄 것이 메일 자리에 없거나 다르면 `재어보기()` 가 그것을 말해야 한다."""
    자리 = tmp_path / "메일자리"
    자리.mkdir()
    monkeypatch.setattr(메일개, "메일자리", 자리)
    난것 = 메일개.재어보기()
    assert len(난것) == len(메일개.베낄것), "없는 것을 못 찾았다 — %s" % 난것
    assert all("메일 자리에 없다" in x or "저장소 원본이 없다" in x for x in 난것), 난것
    # 내용이 다를 때도 말하는가
    글이름 = "0_메일에_붙일_것.md"
    (자리 / 글이름).write_text("다른 글", encoding="utf-8")
    난것 = [x for x in 메일개.재어보기() if x.startswith(글이름)]
    assert 난것 and "다르다" in 난것[0], 난것


def test_가리킨_시험이름이_정말_있다():
    """★ 도구 주석이 「이 시험이 그것을 댄다」 고 가리키는 이름이 **정말 있는가.**

    2026-10-28 에 꾸러미 안내가 없는 `.ps1` 을 가리켰고, 2026-10-29 에
    `메일_대조자료_갱신.py` 가 **없는 파일**을 가리키고 있었다. 가리키기만 하고 없는 가드는
    **가드가 있다는 착각**을 준다. 그래서 이제 가리킨 이름을 기계가 댄다.
    """
    도구 = (_뿌리 / "tools" / "메일_대조자료_갱신.py").read_text(encoding="utf-8")
    나 = Path(__file__).read_text(encoding="utf-8")
    있는이름 = set(re.findall(r"^def (test_[^\(]+)\(", 나, re.M))
    assert 있는이름, "이 파일에서 시험 함수를 하나도 못 찾았다 — 통과가 아니다"
    가리킨것 = set(re.findall(r"test_메일자료\.py::(test_[^\s`]+)", 도구))
    assert 가리킨것, "도구가 가리키는 이름이 하나도 없다 — 주석이 지워졌나 보라"
    없는것 = sorted(가리킨것 - 있는이름)
    assert not 없는것, "도구가 가리킨 시험 이름이 이 파일에 없다 — %s" % 없는것
