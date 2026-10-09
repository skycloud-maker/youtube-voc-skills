# -*- coding: utf-8 -*-
"""Ver 마다 **건네줄 것 하나**가 제대로 묶이는가 (`tools/판_묶기.py`).

★ 왜 — sky 2026-10-09 「Ver1, Ver2, Ver3용 파일이 별개로 있으면 좋겠다... 헷갈리지 않도록요.
  Ver2에는 뭐 파일하나만 같이 넣으세요 보단 Ver2는 이 파일 하나만 전달하면 됩니다 라고 하는 게
  더 쉬운 거니까요.」

★ 여기서 지키는 것 — 꾸러미는 **손으로 만들지 않는다.** 도구가 만들고 여기서 원본과 대조한다
  (공통 규칙 6 「같은 것이 두 벌이 되지 않게」). Ver1·Ver2 는 파일이 거의 같은 사본이라,
  사람이 복사하기 시작하면 한쪽만 고쳐져 판이 갈린다 — 옛 저장소에서 기준서가 13벌까지 퍼진 일.

★ 어디서 꺼내나
  - Ver1 = **동결 태그** `ver1-유튜브VoC분석내부화` 에서. Ver1 은 한 줄 돌리개가 생기기
    **전에** 동결했다. 「지금 코드에서 파일 하나 뺀 것」 이 아니다.
  - Ver2 = **지금 판**에서 (「최신판이 정본」).
  그래서 둘의 차이는 **한 줄 돌리개 하나**여야 한다. 그보다 많아지면 둘 중 하나가
  의도 없이 갈린 것이니 여기서 멈춘다.

★ 「못 찾음」 은 통과가 아니다 — 태그가 없거나 담은 파일이 0개면 실패한다.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "tools"))
from paths import REPO  # noqa: E402

묶개 = pytest.importorskip("판_묶기", reason="판_묶기.py 를 못 읽었다")
돌리개자리 = "plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py"


@pytest.fixture(scope="module")
def 꾸러미(tmp_path_factory):
    자리 = tmp_path_factory.mktemp("판")  / "판"
    assert 묶개.만들기(자리) == 0
    표 = json.loads((자리 / "차림표.json").read_text(encoding="utf-8"))
    return 자리, 표


def test_판이_둘_묶이고_Ver3은_안내문뿐이다(꾸러미):
    자리, 표 = 꾸러미
    assert sorted(표["판"]) == ["Ver1_스킬다섯", "Ver2_한줄흐름"], \
        "묶인 판이 둘이 아니다 — %s" % sorted(표["판"])
    for 이름 in 표["판"]:
        assert (자리 / (이름 + ".zip")).is_file(), "%s.zip 이 없다" % 이름
        assert (자리 / 이름 / "0_읽어주세요.md").is_file(), "%s 에 읽어주세요가 없다" % 이름
    # ★ Ver3 은 꾸러미를 만들지 않는다 — 코드가 없다. 빈 꾸러미가 더 헷갈린다
    assert (자리 / "Ver3_아직_못_씁니다.md").is_file(), "Ver3 안내문이 없다"
    assert not (자리 / "Ver3_단일모델").exists(), \
        "Ver3 꾸러미가 생겼다 — 코드가 없는데 꾸러미를 주면 되는 줄 안다"
    assert (자리 / "0_어느_것을_쓰나.md").is_file(), "어느 것을 쓰나 안내가 없다"


def test_꾸러미가_비어있지_않다(꾸러미):
    _, 표 = 꾸러미
    for 이름, x in 표["판"].items():
        assert x["파일수"] > 100, "%s 가 %d개뿐이다 — 「못 찾음」 은 통과가 아니다" % (이름, x["파일수"])
        assert x["풀었을때바이트"] > 1_000_000, "%s 가 너무 작다" % 이름


def test_Ver1은_동결_태그에서_꺼냈다(꾸러미):
    """지금 작업 자리가 아니라 태그에서 꺼냈는가 — 태그 내용과 지문이 같아야 한다."""
    자리, 표 = 꾸러미
    r = 묶개._git("rev-parse", "--verify", 묶개.Ver1태그 + "^{commit}")
    assert r.returncode == 0, "동결 태그 %s 가 없다" % 묶개.Ver1태그
    받은것 = 표["판"]["Ver1_스킬다섯"]["파일"]
    # 태그의 plugin/ 파일 목록·지문을 git 에서 직접 읽는다 (꾸러미를 거치지 않는다)
    # ★ `core.quotePath=false` — 안 끄면 git 이 한글 경로를 8진수 따옴표로 내놓아
    #   목록이 통째로 안 맞는다 (2026-10-09 여기서 걸렸다).
    r2 = 묶개._git("-c", "core.quotePath=false", "ls-tree", "-r",
                 "--format=%(objectname) %(path)", 묶개.Ver1태그, "plugin/")
    assert r2.returncode == 0, r2.stderr
    태그것 = {}
    for 줄 in r2.stdout.splitlines():
        if not 줄.strip():
            continue
        oid, 길 = 줄.split(" ", 1)
        길 = 길.strip().strip('"')
        if 묶개._뺄까(Path(길).relative_to("plugin")):
            continue
        태그것[길] = oid
    assert 태그것, "못 찾음: 태그에 plugin/ 파일이 0개다"
    assert set(받은것) == set(태그것), \
        "태그와 꾸러미의 파일 목록이 다르다 — 꾸러미만: %s / 태그만: %s" % (
            sorted(set(받은것) - set(태그것))[:3], sorted(set(태그것) - set(받은것))[:3])
    # 내용도 같은가 — git 이 준 blob 과 꾸러미 안 파일을 바이트로 견준다
    for 길 in sorted(태그것)[:12]:
        blob = 묶개._git("cat-file", "blob", 태그것[길], 글자=False).stdout
        assert hashlib.sha256(blob).hexdigest() == 받은것[길], "%s 의 내용이 태그와 다르다" % 길


def test_Ver1에는_한줄_돌리개가_없다(꾸러미):
    """★ Ver1 과 Ver2 를 헷갈리지 않게 하는 핵심 — Ver1 에는 돌리개가 **아예 없다**."""
    자리, 표 = 꾸러미
    assert 돌리개자리 not in 표["판"]["Ver1_스킬다섯"]["파일"], \
        "Ver1 꾸러미에 한 줄 돌리개가 들었다 — 어느 판인지 헷갈린다"
    assert not (자리 / "Ver1_스킬다섯" / 돌리개자리).exists()
    assert 돌리개자리 in 표["판"]["Ver2_한줄흐름"]["파일"], "Ver2 꾸러미에 돌리개가 없다"
    assert (자리 / "Ver2_한줄흐름" / 돌리개자리).is_file()


def test_두_판의_차이는_태그_뒤에_바뀐_것뿐이다(꾸러미):
    """Ver2 는 **Ver1 태그 + 그 뒤 plugin/ 변경**이어야 한다.

    ★ 처음에는 「차이는 한 줄 돌리개 하나뿐」 으로 못 박았다. 그런데 동결 뒤에 공통 도구를
      더하면(2026-10-09 `글자_점검.py`) 차이가 둘이 되어 시험이 깨진다 — 그것은 사고가 아니다.
      그래서 **git 에 물어본다**: 태그에서 지금까지 `plugin/` 에서 더해지고 지워지고 고쳐진 것과
      두 꾸러미의 차이가 같은가. 그러면 의도 없이 갈린 것만 잡힌다.
    """
    _, 표 = 꾸러미
    아 = 표["판"]["Ver1_스킬다섯"]["파일"]
    브 = 표["판"]["Ver2_한줄흐름"]["파일"]
    a, b = set(아), set(브)
    # ★ 「태그 → **지금 작업 자리**」 로 댄다. HEAD 로 대면 **커밋 안 한 새 파일**이 빠져
    #   꾸러미에는 있는데 git 은 모른다고 해서 시험이 깨진다 (2026-10-09 `글자_점검.py`).
    #   묶개는 작업 자리를 담으니, 대는 쪽도 작업 자리여야 한다.
    r = 묶개._git("-c", "core.quotePath=false", "diff", "--name-status",
                묶개.Ver1태그, "--", "plugin/")
    assert r.returncode == 0, r.stderr
    더함, 지움, 고침 = set(), set(), set()
    for 줄 in r.stdout.splitlines():
        if not 줄.strip():
            continue
        갈래, _, 길 = 줄.partition(chr(9))
        길 = 길.strip().strip(chr(34))
        if 묶개._뺄까(Path(길).relative_to('plugin')):
            continue
        {"A": 더함, "D": 지움}.get(갈래[:1], 고침).add(길)
    # 아직 git 이 모르는 새 파일(untracked)도 꾸러미에는 들어간다
    r2 = 묶개._git("-c", "core.quotePath=false", "ls-files", "--others",
                 "--exclude-standard", "--", "plugin/")
    assert r2.returncode == 0, r2.stderr
    for 줄 in r2.stdout.splitlines():
        길 = 줄.strip().strip(chr(34))
        if 길 and not 묶개._뺄까(Path(길).relative_to('plugin')):
            더함.add(길)
    맞대기 = ((sorted(b - a), sorted(더함), '태그 뒤에 **더한** 것'),
            (sorted(a - b), sorted(지움), '태그 뒤에 **지운** 것'),
            (sorted({k for k in a & b if 아[k] != 브[k]}), sorted(고침), '태그 뒤에 **고친** 것'))
    for 꾸러미쪽, git쪽, 무엇 in 맞대기:
        assert 꾸러미쪽 == git쪽, chr(10).join([
            '%s 이 git 이 말하는 것과 다릅니다 — 동결본과 지금 판이 뜻 없이 갈렸습니다.' % 무엇,
            '  꾸러미: %s' % 꾸러미쪽,
            '  git  : %s' % git쪽])

def test_zip_맨위에_꾸러미_폴더_하나(꾸러미):
    """풀면 폴더 하나가 나와야 한다 — 받는 사람의 자리에 파일이 흩어지지 않게."""
    자리, 표 = 꾸러미
    for 이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (이름 + ".zip")) as zf:
            맨위 = {n.split("/")[0] for n in zf.namelist()}
            assert 맨위 == {이름}, "%s.zip 의 맨 위가 하나가 아니다 — %s" % (이름, sorted(맨위))
            assert "%s/0_읽어주세요.md" % 이름 in zf.namelist()
            assert any(n.endswith("/.claude-plugin/plugin.json") for n in zf.namelist()), \
                "%s.zip 에 plugin.json 이 없다 — Claude Code 가 플러그인으로 못 읽는다" % 이름


def test_개발용_경로파일은_안_들어간다(꾸러미):
    """`paths.py` 는 이 컴퓨터 경로가 적힌 개발용이다 — 나가는 꾸러미가 부르지 않는다."""
    _, 표 = 꾸러미
    for 이름, x in 표["판"].items():
        # ★ 도구의 `공통_빼기` 를 되비추면 안 된다 — 도구에서 그 값을 비우면
        #   시험의 기대도 같이 비어 **헛통과**한다 (2026-10-09 일부러 깨 보고 알았다).
        #   그래서 빼야 할 이름을 여기에 따로 적는다.
        반드시빼기 = {"paths.py"}
        assert 반드시빼기 <= 묶개.공통_빼기,             "도구가 %s 를 빼지 않는다 — 이 컴퓨터 경로가 적힌 개발용이다" % sorted(반드시빼기 - 묶개.공통_빼기)
        들어간것 = [k for k in x["파일"] if Path(k).name in 반드시빼기]
        assert not 들어간것, "%s 에 개발용 파일이 들었다 — %s" % (이름, 들어간것)
        쓰레기 = [k for k in x["파일"] if "__pycache__" in k or k.endswith((".pyc", ".pyo"))]
        assert not 쓰레기, "%s 에 캐시가 들었다 — %s" % (이름, 쓰레기[:3])


def test_읽어주세요가_claude_code_를_가리킨다(꾸러미):
    """넘길 자리는 Claude Code 하나다 (sky 2026-10-09). 읽어주세요가 그렇게 말하는가."""
    자리, _ = 꾸러미
    글1 = (자리 / "Ver1_스킬다섯" / "0_읽어주세요.md").read_text(encoding="utf-8")
    글2 = (자리 / "Ver2_한줄흐름" / "0_읽어주세요.md").read_text(encoding="utf-8")
    assert "--plugin-dir" in 글1, "Ver1 읽어주세요에 띄우는 법이 없다"
    assert "한줄_돌리기.py" in 글2 and "--4차반영" in 글2, "Ver2 읽어주세요에 두 인풋이 다 없다"
    for 글, 이름 in ((글1, "Ver1"), (글2, "Ver2")):
        assert "claude.ai" in 글, "%s 읽어주세요가 claude.ai 에서는 안 된다는 말을 안 한다" % 이름


def test_Ver3_안내가_왜_못쓰는지_숫자로_말한다(꾸러미):
    """「안 된다」 만 적으면 다음 사람이 또 재 본다. 재 본 숫자를 적는다."""
    자리, _ = 꾸러미
    글 = (자리 / "Ver3_아직_못_씁니다.md").read_text(encoding="utf-8")
    # ★ 「218」 만 보면 안 된다 — 본문 다른 자리의 「218행 중 161행」 으로 **헛통과**한다
    #   (2026-10-09 일부러 숫자를 지워 봤는데 통과했다). 재 본 값을 짝으로 본다.
    for 숫자 in ("175/218", "58/218"):
        assert 숫자 in 글, "Sonnet 측정값 %s 가 없다 — 「안 된다」 만 적으면 다음 사람이 또 잰다" % 숫자
    assert "판독자" in 글 and "감독자" in 글, "되는 날 무엇을 바꾸면 되는지가 없다"
