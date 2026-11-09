# -*- coding: utf-8 -*-
"""Codex 자리를 차리려면 Git 이 있어야 한다 — 갖춤새가 그것을 보는가 (2026-11-09).

★ 왜 이 시험이 있나 — 돌리개는 Codex 판독·감독·총괄 자리를 차릴 때 `git init` 을 부른다
  (Codex 가 `.agents/skills/` 를 찾을 때 저장소 뿌리까지 올라가므로, 그 자리를 뿌리로 묶는다).
  그런데 ① `0_빈컴퓨터에서_무엇을_깔까.md` 에 Git 이 없었고 ② `--확인만` 의 갖춤새도
  `claude` · `codex` 만 보고 Git 은 안 봤다. 이 컴퓨터에는 Git 이 있어서 한 번도 안 드러났다.
  Git 없는 컴퓨터에서는 갖춤새가 「다 됐습니다」 라고 통과하고, 승인 뒤 2차에서
  `FileNotFoundError` traceback 으로 멈춘다 — **돈 관문을 지난 뒤에.**
  (sky 2026-11-09 「1번부터 해주세요」 — 코드를 읽고 찾았다. Git 없는 컴퓨터에서 밟은 것은 아니다.)

★ 재는 것
  · Git 이 없고 Codex 를 띄울 차례면 갖춤새가 잡고, 어느 자리 때문인지 말한다
  · Codex 를 띄울 일이 없으면 Git 을 요구하지 않는다 (끝난 자리 · 4차 총괄이 claude)
  · 자리를 차리는 도우미가 Git 없을 때 traceback 대신 `멈춤` 으로 알린다
  · 받는 사람 안내서(묶는 도구가 쓰는 글)에 Git 이 있다
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared" / "tools"))
sys.path.insert(0, str(_뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))
sys.path.insert(0, str(_뿌리 / "tools"))
총괄 = pytest.importorskip("한줄_돌리기", reason="총괄 스크립트를 못 읽었다")

_다끝남 = ["1차", "2차준비", "2차판독", "총괄검수1", "3차준비", "3차감독"]


def _깃만_없다(monkeypatch):
    monkeypatch.setattr(총괄.shutil, "which", lambda n: None if n == "git" else "/시험/" + n)
    for k in 총괄._키이름들():
        monkeypatch.setenv(k, "시험용-값-아님")


def test_깃이_없으면_갖춤새가_잡고_codex_자리를_말한다(monkeypatch):
    _깃만_없다(monkeypatch)
    말들 = 총괄.갖춤새_점검([])
    깃말 = [x for x in 말들 if "`git`" in x]
    assert 깃말, "Git 이 없는데 갖춤새가 「다 됐다」 고 했다 — %r" % (말들,)
    codex자리 = [자리 for 자리, 누구 in list(총괄.판독자) + list(총괄.감독자) if 누구 == "codex"]
    assert codex자리, "codex 자리를 못 찾았다 — 못 찾음은 통과가 아니다"
    for 자리 in codex자리:
        assert 자리 in 깃말[0], "어느 자리 때문에 Git 이 필요한지 말하지 않았다 — %s" % 깃말[0]


def test_codex_를_띄울_일이_없으면_깃을_요구하지_않는다(monkeypatch):
    _깃만_없다(monkeypatch)
    assert not [x for x in 총괄.갖춤새_점검(_다끝남) if "`git`" in x], "끝난 자리 때문에 Git 을 요구했다"
    assert 총괄.총괄누구 != "codex", "이 시험은 4차 총괄이 codex 가 아닐 때를 본다"
    assert not [x for x in 총괄.갖춤새_점검(["1차"], 사차=True) if "`git`" in x], \
        "4차 총괄이 claude 인데 Git 을 요구했다"


def test_4차_총괄이_codex_면_깃을_본다(monkeypatch):
    _깃만_없다(monkeypatch)
    monkeypatch.setattr(총괄, "총괄누구", "codex")
    assert [x for x in 총괄.갖춤새_점검(["1차"], 사차=True) if "`git`" in x], \
        "4차 총괄이 codex 인데 Git 을 안 봤다"


def test_자리_차리는_도우미는_깃이_없으면_멈춤으로_알린다(monkeypatch, tmp_path):
    monkeypatch.setattr(총괄.shutil, "which", lambda n: None)
    with pytest.raises(총괄.멈춤) as 잡음:
        총괄._깃_자리묶기(tmp_path)
    assert "Git" in str(잡음.value) and "0_빈컴퓨터에서_무엇을_깔까" in str(잡음.value), str(잡음.value)
    assert not (tmp_path / ".git").exists()


def test_자리_차리는_도우미는_깃이_있으면_묶는다(tmp_path):
    if not 총괄.shutil.which("git"):
        pytest.skip("이 컴퓨터에 git 이 없다")
    총괄._깃_자리묶기(tmp_path)
    assert (tmp_path / ".git").is_dir()


def test_돌리개가_git_init_을_도우미로만_부른다():
    """`git init` 을 맨손으로 부르는 자리가 다시 생기면 Git 없는 컴퓨터에서 traceback 이 난다."""
    글 = Path(총괄.__file__).read_text(encoding="utf-8")
    맨손 = 글.count('subprocess.run(["git", "init"')
    assert 맨손 == 1, "git init 을 부르는 자리가 도우미 하나여야 한다 — %d 곳" % 맨손
    assert 글.count("_깃_자리묶기(") >= 4, "도우미를 부르는 자리가 셋보다 적다 (정의 하나 + 부름 셋)"


def test_받는_사람_안내서에_깃이_있다():
    묶기 = pytest.importorskip("판_묶기", reason="묶는 도구를 못 읽었다")
    글 = 묶기._빈컴퓨터_안내
    assert "git --version" in 글, "안내서에 Git 을 갖췄는지 보는 법이 없다"
    assert "Git" in 글 and "Codex" in 글
