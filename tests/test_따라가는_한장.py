# -*- coding: utf-8 -*-
"""따라가는 한 장(`docs/지금_어디인가.md`)이 **거짓말을 하지 못하게** 지킨다 (2026-10-29).

★ 왜 이 시험이 있나 — sky 물음 2026-10-29
    「이제 매번 뭐가 헷갈려서 잘 지시를 못하겠고 팔로업도 못하겠어요」

  글이 7개 · 2,886줄이 되어 따라갈 수가 없었다. 그래서 **한 장**을 만들었다.
  그런데 그 한 장이 ① 없는 파일을 가리키거나 ② 안 본 글의 수를 틀리게 적으면
  **따라가는 자리가 거짓말을 하는 것**이고, 그러면 없는 것보다 나쁘다.

  → 가리킨 자리가 정말 있는지 · 센 수가 대장과 맞는지 · 뿌리 글들이 이 한 장을
    가리키는지를 본다. 「못 찾음」 은 통과가 아니다 — 크게 실패한다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(_여기.parent / "plugin" / "shared"))
from paths import REPO  # noqa: E402

한장자리 = REPO / "docs" / "지금_어디인가.md"
목록자리 = REPO / "docs" / "옛꾸러미_목록.json"
못박음자리 = REPO / "docs" / "decisions" / "0009-못박는-지점.md"


@pytest.fixture(scope="module")
def 한장() -> str:
    assert 한장자리.is_file(), (
        "못 찾음: %s — 따라가는 한 장이 없다.\n"
        "  이 글이 없으면 sky 가 따라갈 자리가 없어진다 (결정 0009) — 통과가 아니다" % 한장자리)
    return 한장자리.read_text(encoding="utf-8")


def test_못박는_지점_기록이_있다():
    """못 박는 지점이 결정 기록으로 남아 있어야 한다 — 한 장은 그것을 가리킬 뿐이다."""
    assert 못박음자리.is_file(), "못 찾음: %s" % 못박음자리
    글 = 못박음자리.read_text(encoding="utf-8")
    for 꼭 in ("cf4481e", "2.0.10", "336"):
        assert 꼭 in 글, "못 박는 지점 기록에 「%s」 가 없다" % 꼭
    # ⓐ/ⓑ 가르는 기준이 글에 있어야 한다 (없으면 또 전부 고치게 된다)
    assert "적기만 하고 안 고친다" in 글, "ⓑ 를 고치지 않는다는 말이 없다"


def test_가리킨_자리가_정말_있다(한장):
    """★ 「못 찾음」 을 「없음」 으로 넘기지 않는다 — 가리킨 파일이 하나라도 없으면 실패한다."""
    가리킨것 = re.findall(r"\]\(([^)#]+)\)", 한장)
    assert 가리킨것, "가리키는 자리가 하나도 없다 — 글이 비었나 보라"
    없는것 = []
    for 쪽 in 가리킨것:
        if 쪽.startswith(("http://", "https://")):
            continue
        if not (한장자리.parent / 쪽).exists():
            없는것.append(쪽)
    assert not 없는것, "한 장이 **없는 자리**를 가리킨다 — %s" % sorted(없는것)


def test_안_본_수가_대장과_맞는다(한장):
    """★ 한 장의 「본 것 n / N」 과 대장의 수가 어긋나면, 따라가는 자리가 틀린 수를 보여 준다."""
    assert 목록자리.is_file(), "못 찾음: %s — `python tools/옛꾸러미_대장.py` 를 돌리십시오" % 목록자리
    대장 = json.loads(목록자리.read_text(encoding="utf-8"))["수"]["아직안봤다"]
    m = re.search(r"본 것 (\d+) / (\d+)", 한장)
    assert m, "한 장에 「본 것 n / N」 이 없다 — ② 가 어디까지 갔는지 알 수 없다"
    본것, 전체 = int(m.group(1)), int(m.group(2))
    assert 전체 - 본것 == 대장, (
        "한 장은 안 본 것이 %d개(%d − %d)라고 하는데 대장은 %d개다 — 둘을 맞추십시오.\n"
        "  (114개를 보고 났으면 `python tools/옛꾸러미_대장.py` 를 다시 돌리고\n"
        "   `tests/test_옛꾸러미_대장.py` 의 못 박은 수도 같이 내린다)"
        % (전체 - 본것, 전체, 본것, 대장))
    assert 본것 <= 전체, "본 것이 전체보다 많다 (%d / %d)" % (본것, 전체)


def test_뿌리_글들이_한_장을_가리킨다():
    """★ 한 장을 만들어도 **아무도 가리키지 않으면** 못 찾는다 (가드는 돌리는 자리에)."""
    for 쪽, 이름 in ((REPO / "README.md", "README.md"),
                   (REPO / "docs" / "progress.md", "docs/progress.md")):
        assert 쪽.is_file(), "못 찾음: %s" % 쪽
        assert "지금_어디인가.md" in 쪽.read_text(encoding="utf-8"), (
            "%s 가 따라가는 한 장을 가리키지 않는다" % 이름)


def test_해야_할_순서가_여섯_칸_다_있다(한장):
    """①~⑥ 가운데 하나라도 빠지면 「끝이 언제인가」 가 사라진다.

    ★ 처음에는 글자 `⑥` 이 글 안에 있는지만 봤다. **그 시험은 못 잡았다** —
      그 글자가 ⓐ 칸에도 쓰여 있어서, 순서 표에서 줄을 빼도 글자는 남았다.
      그래서 **표의 줄**을 센다 (일부러 깨뜨려 보고 고친 것이다).
    """
    줄들 = [c for c in 한장.splitlines() if re.match(r"^\| *[①-⑥] *\|", c)]
    번호 = [re.match(r"^\| *([①-⑥]) *\|", c).group(1) for c in 줄들]
    없는것 = [n for n in "①②③④⑤⑥" if n not in 번호]
    assert not 없는것, (
        "순서 표에서 줄이 빠졌다 — %s (표에 있는 것: %s)" % (없는것, 번호))
    for 꼭 in ("새 채팅방 시험", "Ver2.1 동결", "메일 2통"):
        assert 꼭 in 한장, "끝까지 가는 길에 「%s」 가 없다" % 꼭
