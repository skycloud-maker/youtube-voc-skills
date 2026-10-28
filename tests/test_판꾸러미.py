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
스킬묶기 = pytest.importorskip("build_skills", reason="build_skills.py 를 못 읽었다")
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



def test_빈컴퓨터_안내가_꾸러미마다_있다(꾸러미):
    """★ 2026-10-20 재점검 — 받은 사람이 **무엇을 깔아야 하는지** 알 자리가 없었다.

    꾸러미만 주면 스킬은 서지만, 파이썬 꾸러미·키·AI 명령은 바깥에서 와야 한다.
    그것을 적어 두지 않으면 받은 사람이 스스로 알아내야 한다.
    """
    자리, 표 = 꾸러미
    이름 = "0_빈컴퓨터에서_무엇을_깔까.md"
    assert (자리 / 이름).is_file(), "꾸러미 바깥에 %s 가 없다" % 이름
    # ★ 2026-10-22 — 전에는 **폴더만** 봤다. 그래서 zip 안에 이 안내가 없는 것을 놓쳤다.
    #   사람에게 건네는 것은 zip 이다. 폴더는 묶개가 쓰다 남긴 자리일 뿐이다.
    for 판이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (판이름 + '.zip')) as zf:
            안 = '%s/%s' % (판이름, 이름)
            assert 안 in zf.namelist(), (
                "%s.zip 안에 %s 가 없다 — 받은 사람이 무엇을 깔지 알 수 없다" % (판이름, 이름))
            글 = zf.read(안).decode('utf-8')
            for 말 in ("YOUTUBE_API_KEY", "OPENAI_API_KEY", "requirements.txt",
                      "claude", "codex", "라이브"):
                assert 말 in 글, "%s.zip 의 안내에 「%s」 가 없다" % (판이름, 말)

    for 판이름 in 표["판"]:
        q = 자리 / 판이름 / 이름
        assert q.is_file(), "%s 안에 %s 가 없다" % (판이름, 이름)
        글 = q.read_text(encoding="utf-8")
        # 차수마다 다른 것 · 키 이름 · 깔 목록 자리 · 안 되는 것이 다 적혀 있어야 한다
        for 말 in ("YOUTUBE_API_KEY", "OPENAI_API_KEY", "requirements.txt",
                  "claude", "codex", "라이브"):
            assert 말 in 글, "%s 의 안내에 「%s」 가 없다" % (판이름, 말)
        assert "키도 AI 명령도 필요 없습니다" in 글, (
            "%s 의 안내가 「보기만 하는 사람은 키가 필요 없다」 를 말하지 않는다" % 판이름)


def test_막히면_안내가_zip_안에_있다(꾸러미):
    """★ sky 2026-10-27 — 「분명 한번에 안 돌아갈 것이니 수정보완은 시행착오를 통해」.

    그러면 막혔을 때 **무엇을 보고 무엇을 보낼지**가 꾸러미 안에 있어야 한다.
    ★ zip 안을 본다 — 폴더만 보면 2026-10-22 과 같은 것을 또 놓친다.
    ★ 이미 아는 함정(Codex 내장 파이썬)을 적어 두어야 한다. 그 자리가 없는 컴퓨터에서
      처음 막힐 자리이고, 안 적어 두면 받은 사람이 스스로 알아내야 한다.
    """
    자리, 표 = 꾸러미
    이름 = "0_막히면_이_순서로.md"
    assert (자리 / 이름).is_file(), "꾸러미 바깥에 %s 가 없다" % 이름
    # ★ 2026-10-27 실측 함정 — Codex 내장 파이썬에 yaml 이 없다 (결정 0007).
    #   넣는 명령까지 적어야 받은 사람이 스스로 알아내지 않는다.
    볼말 = ("--확인만", "상태.json", "기록", "--되감기", "codex-runtimes",
          "키 값은 보내지 마십시오", "pip install pyyaml", "CSV 는 나옵니다")
    for 판이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (판이름 + ".zip")) as zf:
            안 = "%s/%s" % (판이름, 이름)
            assert 안 in zf.namelist(), "%s.zip 안에 %s 가 없다" % (판이름, 이름)
            글 = zf.read(안).decode("utf-8")
            for 말 in 볼말:
                assert 말 in 글, "%s.zip 의 안내에 「%s」 가 없다" % (판이름, 말)


def test_안내가_가리키는_파일이_zip_안에_다_있다(꾸러미):
    """★ 2026-10-28 설치 예행 — 빈 폴더에 zip 만 풀어 안내를 글자 그대로 따라가 봤다.

    두 안내가 「`Ver3_아직_못_씁니다.md` 를 보십시오」 라고 가리키는데 **그 파일이 zip 안에
    없었다.** `dist/판/` 에만 썼기 때문이다. 받는 사람에게 건네는 것은 zip 하나다 —
    `0_읽어주세요.md` 가 「**이 꾸러미 하나만** 건네면 됩니다」 라고 적는다.
    2026-10-22 에 `0_빈컴퓨터에서…` 로 같은 것을 겪었는데 Ver3 만 남아 있었다.

    ★ 이름을 하나 적어 두고 그것만 보지 않는다 — **안내에서 가리키는 것을 전부 긁어**
      본다. 그러지 않으면 다음에 새 안내가 새 파일을 가리킬 때 또 놓친다
      (「표본으로 재자」 가 아니라 전량으로 재는 쪽).
    """
    import re                                              # noqa: PLC0415
    자리, 표 = 꾸러미
    # ★ 돌면서 **생기는** 것은 꾸러미에 없는 것이 정상이다. 세 가지뿐이고 까닭이 있다:
    #   상태.json · 소견.md — 판자리에 생긴다 ·  .stderr.txt — 기록에 생긴다
    #   `<` 가 든 것은 「<판자리>/…」 처럼 자리를 비워 둔 글이다
    돌면서생김 = {"상태.json", "소견.md", ".stderr.txt"}
    안내들 = ("0_읽어주세요.md", "0_빈컴퓨터에서_무엇을_깔까.md", "0_막히면_이_순서로.md")
    본것 = 0
    for 판이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (판이름 + ".zip")) as zf:
            속 = set(zf.namelist())
            이름만 = {n.rsplit("/", 1)[-1] for n in 속}
            for 안내 in 안내들:
                안 = "%s/%s" % (판이름, 안내)
                assert 안 in 속, "%s.zip 안에 %s 가 없다" % (판이름, 안내)
                줄들 = zf.read(안).decode("utf-8").splitlines()
                for 줄 in 줄들:
                    for 가리킨것 in re.findall(r"`([^`]+\.(?:md|txt|example|json|py))`", 줄):
                        if "<" in 가리킨것 or 가리킨것 in 돌면서생김:
                            continue
                        본것 += 1
                        있나 = ("%s/%s" % (판이름, 가리킨것) in 속
                              or 가리킨것.rsplit("/", 1)[-1] in 이름만)
                        if 있나:
                            continue
                        # ★ 「없습니다」 라고 **일부러** 적은 것은 없는 것이 맞다 —
                        #   Ver1 안내는 「`한줄_돌리기.py` (한 줄 흐름) 가 없습니다」 로
                        #   이 판에 없는 것을 밝힌다. 그 말이 같은 줄에 있으면 넘긴다.
                        assert "없습니다" in 줄, (
                            "%s 의 %s 가 `%s` 를 가리키는데 zip 안에 없다 — 받은 사람이 "
                            "못 찾는다. 없는 것이 맞다면 안내에 「없습니다」 라고 적어라.%s  그 줄: %s"
                            % (판이름, 안내, 가리킨것, chr(10), 줄.strip()))
    # ★ 「못 찾음」 은 통과가 아니다 — 하나도 못 긁었으면 이 시험은 아무것도 안 잰 것이다
    assert 본것 >= 2, "안내에서 가리키는 파일을 %d개밖에 못 긁었다 — 정규식이 안 맞는다" % 본것


def test_읽어주세요가_승인_관문을_적는다(꾸러미):
    """★ 2026-10-22 — 돌리개는 `--승인` 없이는 돌지 않는다. 받은 사람이 그걸 알아야 한다.

    모르면 「돌렸는데 안 돌아간다」 가 된다 (종료코드 2 로 멈춘다).
    """
    자리, 표 = 꾸러미
    for 판이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (판이름 + ".zip")) as zf:
            안 = "%s/0_읽어주세요.md" % 판이름
            글 = zf.read(안).decode("utf-8")
            # ★ Ver1 안내도 「Ver1 에는 한줄_돌리기.py 가 없습니다」 라고 **이름을 말한다.**
            #   그래서 이름만으로 가르면 Ver1 까지 걸린다 (처음에 그렇게 적어 걸렸다).
            #   실제로 그 명령을 쓰는 쪽만 본다 — `--조건` 이 있는 안내가 그것이다.
            if "--조건" not in 글:
                continue                      # Ver1 에는 돌리개가 없다 — 적을 것도 없다
            assert "--승인" in 글, "%s 의 안내에 `--승인` 이 없다" % 판이름
            assert "어림" in 글, "%s 의 안내가 어림을 말하지 않는다" % 판이름


def test_묶개_둘이_서로의_것을_지우지_않는다(tmp_path):
    """★ 2026-10-22 — `build_skills.py` 가 `dist/` 를 **통째로 지워** `판_묶기.py` 가 만든
    `dist/판/`(Ver1·Ver2 꾸러미)이 말없이 사라졌다. 도구 둘이 같은 자리를 쓰는데 한쪽이
    남의 것까지 치운 것이다. 실제로 겪었다 — 낱개 zip 을 만들고 보니 판 꾸러미가 없었다.

    차례를 **바꿔 가며** 둘 다 돌려, 뒤에 돈 쪽이 앞의 것을 지우지 않는지 본다.
    """
    import shutil                                            # noqa: PLC0415
    자리 = tmp_path / "dist"
    for 먼저, 나중 in ((묶개.만들기, 스킬묶기.만들기), (스킬묶기.만들기, 묶개.만들기)):
        if 자리.exists():
            shutil.rmtree(자리)
        assert 먼저(자리 / "판" if 먼저 is 묶개.만들기 else 자리) == 0
        assert 나중(자리 / "판" if 나중 is 묶개.만들기 else 자리) == 0
        남아야할것 = [자리 / "판" / "Ver1_스킬다섯.zip", 자리 / "판" / "Ver2_한줄흐름.zip",
                 자리 / "claude", 자리 / "codex", 자리 / "차림표.json"]
        없는것 = [p.name for p in 남아야할것 if not p.exists()]
        assert not 없는것, ("%s 를 뒤에 돌리니 %s 가 사라졌다"
                         % (getattr(나중, "__module__", "?"), 없는것))


# ── 2026-10-28 · 판 2.0.8 — **은퇴한 틀린 말이 꾸러미에 다시 들어가지 않게** ────────────
#
#   ★ 왜 이 시험이 생겼나 — 독립 점검이 「③ 을 채점으로 잰다고 적었는데 채점할 정답지가
#     없다」 를 짚었다(F01). 그날 `대조_원본과_skill.md` 의 머리와 ③ 을 고쳤다.
#     그런데 같은 말이 **네 벌**이었다 —
#       ① 그 문서의 「한 줄 결론」            (고치고도 남아 있었다)
#       ② `점검요청_…md` 의 ③               (같은 표를 베꼈다)
#       ③ `점검요청_…md` 의 ⑥               (「점수가 유지된다」 로 말만 바꿔 적혀 있었다)
#       ④ `판_묶기.py` 의 `_대조_안내`        ← **두 zip 의 `0_읽어주세요.md` 에 들어가는 글**
#     ④ 를 못 보고 묶었으면, 고쳤다고 적힌 문서와 틀린 말이 **같은 zip 안에** 같이 갔다.
#
#   ★ 그래서 글자로 막는다. 「이 말은 은퇴했다」 를 꾸러미가 나가는 자리에서 검사한다
#     (공통 규칙 — 「가드는 돌리는 자리에」). 글자 검사는 무른 방법이지만, 지금 막아야 하는
#     것이 바로 **글자를 베끼다 생긴 어긋남**이다.
은퇴한_말 = (
    ("채점으로 잰다",
     "F01 — 채점할 정답지(판독·감독)가 빈 칸이라 정확도를 못 잰다. "
     "「정확도는 아직 못 잰다 — 지금 재는 것은 절차와 형식이다」 로 적는다"),
    ("채점**으로 잽니다",
     "F01 — 위와 같은 말의 다른 꼴 (`_대조_안내` 에 이 꼴로 있었다)"),
    ("점수가 유지된다",
     "F01 — 점수를 낼 정답지가 없다. 「점수」 라는 말 자체를 쓰지 않는다"),
    ("정답지 채점**으로 잰다",
     "F01 — 같은 말의 표 안 꼴"),
)

# ★ 빠져나갈 길 — **그 말을 은퇴시키는 글**은 그 말을 따다 써야 한다.
#   「전에는 「채점으로 잰다」 로 적었는데 그것이 틀렸다」 같은 줄이다. 그 줄까지 막으면
#   무엇이 어떻게 틀렸었는지를 꾸러미 안에 남길 수 없다 (공통 규칙 7 — 경위를 지우지 않는다).
#   그래서 **같은 줄에** 「틀렸다」 거나 지적 번호를 적어야 넘어간다. 기존
#   `test_안내가_가리키는_파일이_zip_안에_다_있다` 의 「없습니다」 와 같은 꼴이다.
#   ★ 이 길이 넓으면 검사가 헐거워진다 — 그래서 **아래 일곱 개뿐**이고, 모두
#     「그 말이 틀렸다 · 고쳤다 · 남아 있었다」 를 뜻하는 말이다. 「채점」 처럼 그 말 자체를
#     면제말로 넣지 않는다 (그러면 아무것도 안 잡는다).
면제말 = ("F01", "틀렸", "틀린 말", "고침", "고쳤", "은퇴", "남아 있었")


def test_꾸러미에_은퇴한_틀린_말이_없다(꾸러미):
    """두 zip 의 **글 파일 전부**를 긁어, 은퇴한 말이 하나라도 있으면 실패한다."""
    자리, 표 = 꾸러미
    본파일 = 0
    걸린것 = []
    for 판이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (판이름 + ".zip")) as zf:
            for 안 in zf.namelist():
                if not 안.endswith((".md", ".txt")):
                    continue
                본파일 += 1
                글 = zf.read(안).decode("utf-8")
                for 말, 왜 in 은퇴한_말:
                    for 줄 in 글.splitlines():
                        if 말 not in 줄:
                            continue
                        if any(ㅁ in 줄 for ㅁ in 면제말):
                            continue          # 그 말을 은퇴시키는 글이다 — 남겨 둔다
                        걸린것.append("%s 안 `%s` 에 「%s」 — %s%s    그 줄: %s"
                                    % (판이름, 안, 말, 왜, chr(10), 줄.strip()))
    # ★ 「못 찾음」 은 통과가 아니다 — 글 파일을 하나도 못 긁었으면 아무것도 안 잰 것이다
    assert 본파일 >= 8, "두 꾸러미에서 글 파일을 %d개밖에 못 긁었다 — 검사가 안 돌았다" % 본파일
    assert not 걸린것, (
        "은퇴한 틀린 말이 꾸러미에 들어 있다 (%d곳)%s%s"
        % (len(걸린것), chr(10), (chr(10) + chr(10)).join(걸린것)))


def test_읽어주세요의_대조_숫자가_대조문서와_같다(꾸러미):
    """`0_읽어주세요.md` 끝의 대조 안내와 `대조_원본과_skill.md` 가 **같은 숫자**를 말하는가.

    ★ 왜 — 같은 숫자를 두 자리에 손으로 적어 두었더니, 시험이 25 → 26 으로 늘 때
      한쪽만 고쳐졌다. 두 자리가 어긋나면 **받는 사람이 보는 한 꾸러미 안에서 말이 둘**이다.
      (두 숫자가 **함께** 틀릴 수는 있다 — 그것까지는 이 시험이 못 잡는다. 못 잡는 것을
       잡는다고 적지 않는다.)
    """
    import re                                                # noqa: PLC0415
    자리, 표 = 꾸러미
    꼴 = re.compile(r"대조 시험 (\d+)개")
    본것 = 0
    for 판이름 in 표["판"]:
        with zipfile.ZipFile(자리 / (판이름 + ".zip")) as zf:
            안내 = zf.read("%s/0_읽어주세요.md" % 판이름).decode("utf-8")
            문서 = zf.read("%s/대조_원본과_skill.md" % 판이름).decode("utf-8")
        ㄱ = 꼴.findall(안내)
        ㄴ = 꼴.findall(문서)
        assert ㄱ, "%s 의 0_읽어주세요.md 에 「대조 시험 N개」 가 없다 — 꼴이 바뀌었다" % 판이름
        assert ㄴ, "%s 의 대조_원본과_skill.md 에 「대조 시험 N개」 가 없다" % 판이름
        본것 += 1
        assert set(ㄱ) == set(ㄴ) and len(set(ㄱ)) == 1, (
            "%s — 안내는 대조 시험 %s개, 문서는 %s개라고 말한다 (한 꾸러미에서 말이 둘)"
            % (판이름, " · ".join(sorted(set(ㄱ))), " · ".join(sorted(set(ㄴ)))))
    assert 본것 == 2, "판 %d개만 봤다 — 둘을 다 봐야 한다" % 본것


def test_Ver1_안내가_안_들어간_고침을_밝힌다(꾸러미):
    """Ver1 은 동결 태그에서 꺼내므로 2026-10-28 고침이 **없다.** 그 어긋남을 적었는가.

    ★ 왜 — 2.0.8 에서 `대조_원본과_skill.md` 가 「도구 둘을 고쳤다」 로 바뀌었다.
      그 문서는 두 판에 다 담기는데 **Ver1 의 코드에는 그 고침이 없다** — 그대로 담으면
      한 꾸러미에서 말이 둘이다. 동결판을 고치지는 않고(동결의 뜻이 사라진다)
      **어긋남을 꾸러미 안에 적는 쪽**을 골랐다. 그 글이 정말 들어갔는지 여기서 본다.
      그리고 **Ver2 에는 그 꼬리가 붙지 않아야 한다** (Ver2 에는 고침이 들어 있으므로).
    """
    자리, _ = 꾸러미
    표시 = "고침이 이 판에는 안 들어 있습니다"
    with zipfile.ZipFile(자리 / "Ver1_스킬다섯.zip") as zf:
        글 = zf.read("Ver1_스킬다섯/0_읽어주세요.md").decode("utf-8")
        도구 = zf.read("Ver1_스킬다섯/plugin/shared/tools/PL이슈_뽑기.py").decode("utf-8")
    assert 표시 in 글, "Ver1 안내가 「고침이 없다」 를 밝히지 않는다"
    assert "PL이슈_뽑기.py" in 글 and "3차_마무리.py" in 글, (
        "Ver1 안내가 어느 도구에 고침이 없는지 이름을 적지 않는다")
    # ★ 밝힌 말이 사실인지도 본다 — 「없다」 고 적었는데 실은 들어 있으면 그 글이 거짓이다
    assert "꼭 필요한 열이 없습니다" not in 도구, (
        "Ver1 안내는 「고침이 없다」 고 적는데 PL이슈_뽑기.py 에는 고침이 들어 있다 — "
        "태그가 바뀌었으면 안내도 고쳐야 한다")
    with zipfile.ZipFile(자리 / "Ver2_한줄흐름.zip") as zf:
        글2 = zf.read("Ver2_한줄흐름/0_읽어주세요.md").decode("utf-8")
        도구2 = zf.read("Ver2_한줄흐름/plugin/shared/tools/PL이슈_뽑기.py").decode("utf-8")
    assert 표시 not in 글2, "Ver2 에 Ver1 전용 꼬리가 붙었다 — Ver2 에는 고침이 들어 있다"
    assert "꼭 필요한 열이 없습니다" in 도구2, "Ver2 의 PL이슈_뽑기.py 에 고침이 없다"
