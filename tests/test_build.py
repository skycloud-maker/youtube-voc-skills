# -*- coding: utf-8 -*-
"""낱개 스킬 묶기 (섹션 6) — build_skills.py 가 묶고 check_shared.py 가 원본과 대조한다.

★ 가장 중요한 시험은 「플러그인과 떨어진 빈 자리에서 실제로 도는가」 다 — 글자로 경로를 찾는 대신 풀어서 돌려 본다.
  스크립트는 「스킬 안 → 플러그인 옆」 차례로 재료를 찾으므로, 옆에 플러그인이 없는 자리에서 돌아야 스킬 안 사본만으로 되는지 안다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import build_skills  # noqa: E402
import check_shared  # noqa: E402


@pytest.fixture(scope="module")
def 묶음(tmp_path_factory):
    d = tmp_path_factory.mktemp("dist")
    assert build_skills.만들기(d) == 0
    return d


def test_스킬_넷을_다_묶었다(묶음):
    assert build_skills.스킬들() == ["coordinating-voc-pipeline", "reading-voc-comments",
                                 "running-voc-engine", "supervising-voc-disagreements"]
    for s in build_skills.스킬들():
        assert (묶음 / "claude" / (s + ".zip")).is_file()
        assert (묶음 / "codex" / ".agents" / "skills" / s / "SKILL.md").is_file()


def test_원본과_같다(묶음):
    assert check_shared.대조(묶음) == []


def test_빼야_할_것을_뺐다(묶음):
    for s in build_skills.스킬들():
        with zipfile.ZipFile(묶음 / "claude" / (s + ".zip")) as zf:
            이름 = zf.namelist()
        assert not [n for n in 이름 if "__pycache__" in n or n.endswith(".pyc")]
        assert not [n for n in 이름 if n.startswith("%s/evals/" % s)], "스킬 맨 위 evals 는 뺀다 (package_skill.py)"
        assert "%s/shared/paths.py" % s not in 이름, "이 컴퓨터 경로가 적힌 개발용 파일"
        assert "%s/SKILL.md" % s in 이름


# ── ★ 일부러 틀리게 — 대조가 정말 잡는가 ─────────────────────────────
def _사본(묶음: Path, tmp: Path) -> Path:
    import shutil
    d = tmp / "사본"
    shutil.copytree(묶음, d)
    return d


def test_Codex_사본을_고치면_잡는다(묶음, tmp_path):
    d = _사본(묶음, tmp_path)
    p = d / "codex" / ".agents" / "skills" / "reading-voc-comments" / "shared" / "standards" / "0_최신결정_먼저.md"
    p.write_bytes(p.read_bytes() + b"\n")
    assert any("Codex 사본이 원본과 다르다" in t for t in check_shared.대조(d))


def test_파일이_빠지거나_더_있으면_잡는다(묶음, tmp_path):
    d = _사본(묶음, tmp_path)
    뿌리 = d / "codex" / ".agents" / "skills" / "supervising-voc-disagreements"
    (뿌리 / "SKILL.md").unlink()
    (뿌리 / "덤.txt").write_text("x", encoding="utf-8")
    틀림 = check_shared.대조(d)
    assert any("Codex 사본에 없다: SKILL.md" in t for t in 틀림) and any("덤.txt" in t for t in 틀림), 틀림


def test_묶은_뒤_원본이_바뀌면_잡는다(묶음, tmp_path):
    d = _사본(묶음, tmp_path)
    기록 = json.loads((d / "차림표.json").read_text(encoding="utf-8"))
    기록["스킬"]["reading-voc-comments"]["SKILL.md"]["sha256"] = "0" * 64
    (d / "차림표.json").write_text(json.dumps(기록, ensure_ascii=False), encoding="utf-8")
    assert any("묶은 뒤 원본이 바뀌었다" in t for t in check_shared.대조(d))


def test_묶음이_없으면_통과가_아니다(tmp_path):
    assert check_shared.대조(tmp_path)


@pytest.mark.parametrize("머리, 무엇", [
    ("name: Reading_VOC\ndescription: x", "name 규칙"),
    ("name: claude-reader\ndescription: x", "예약어"),
    ("name: 시험\ndescription: <b>x</b>", "< >"),
    ("name: 시험\ndescription: x\nwhen_to_use: y", "허용하지 않는 키"),
    ("name: other-name\ndescription: x", "폴더 이름"),
])
def test_머리가_틀리면_잡는다(tmp_path, 머리, 무엇):
    p = tmp_path / "SKILL.md"
    p.write_text("---\n%s\n---\n\n# x\n" % 머리, encoding="utf-8")
    실패, _ = build_skills.머리검사(p, "시험" if "other" not in 머리 else "시험")
    assert any(무엇 in f for f in 실패), 실패


# ── ★ 떨어진 자리에서 실제로 돈다 ─────────────────────────────────────
def _풀기(묶음: Path, 스킬: str, 자리: Path) -> Path:
    with zipfile.ZipFile(묶음 / "claude" / (스킬 + ".zip")) as zf:
        zf.extractall(자리)
    assert not (자리 / "shared").exists() and not (자리 / "engine").exists(), "옆에 플러그인 재료가 있으면 시험이 안 된다"
    return 자리 / 스킬


def _돌리기(스크립트: Path, *인자) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(스크립트), *map(str, 인자)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


@pytest.mark.parametrize("스킬, 스크립트, 개수", [
    ("reading-voc-comments", "판독폴더_차리기.py", 90),
    ("supervising-voc-disagreements", "감독폴더_차리기.py", 74),
])
def test_낱개_스킬이_떨어진_자리에서_폴더를_차린다(묶음, tmp_path, 스킬, 스크립트, 개수):
    s = _풀기(묶음, 스킬, tmp_path / "풀린곳")
    작업 = tmp_path / "작업"
    r = _돌리기(s / "scripts" / 스크립트, 작업)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "못 찾" not in r.stdout, r.stdout
    assert len([p for p in 작업.rglob("*") if p.is_file()]) == 개수, r.stdout


def test_1차_스킬이_떨어진_자리에서_실행_자리를_차린다(묶음, tmp_path):
    """★ 1차 자리는 **엔진 한 벌**이 들어가야 한다 — 수집 · 분석 · 번들 · nlp_analyzer 를 다 쓴다.

    그리고 차린 자리에서 돌리개가 **승인 없이는 돌지 않는지**(종료 2)를 같이 본다 — 돈이 드는 일이다.
    """
    s = _풀기(묶음, "running-voc-engine", tmp_path / "풀린곳")
    자리 = tmp_path / "1차자리"
    r = _돌리기(s / "scripts" / "1차자리_차리기.py", 자리)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "못 찾" not in r.stdout, r.stdout
    for n in ("0_먼저_읽으십시오.md", "99_1차_실행조건_원문.md", "1차_돌리기.py",
              "engine/config/settings.yaml", "engine/scripts/run_dashboard60_youtube_collect_and_analyze.py",
              "engine/nlp_analyzer/__init__.py", "engine/src/cli.py"):
        assert (자리 / n).is_file(), n
    assert "provider: openai" in (자리 / "engine/config/settings.yaml").read_text(encoding="utf-8")
    # 엔진 한 벌(출처 기록 포함) + 글 3개 + 설정 1개
    엔진수 = len([p for p in (REPO / "plugin" / "engine").rglob("*") if p.is_file() and "__pycache__" not in p.parts])
    assert len([p for p in 자리.rglob("*") if p.is_file()]) == 엔진수 + 4, r.stdout
    # ★ 승인 없이는 돌지 않는다 (돈이 든다) — 어림만 내고 종료 2
    r2 = _돌리기(자리 / "1차_돌리기.py", "--검색어", "시험", "--영상", "1", "--댓글", "5")
    assert r2.returncode == 2, r2.stdout + r2.stderr
    assert "돌리지 않았습니다" in r2.stdout and "$" in r2.stdout, r2.stdout
    # ★ 볼 것을 못 찾으면 통과가 아니다 — 종료 2
    r3 = _돌리기(자리 / "1차_돌리기.py", "--이름", "없는이름", "--확인만")
    assert r3.returncode == 2 and "못 찾음" in r3.stdout, r3.stdout

    # ★ 이미 차린 자리가 **낡으면** 말하고 멈춘다 (2026-10-08 실제로 겪은 함정) ─────────────
    #   차리기는 「이미 있는 파일은 건드리지 않는다」 — 그래서 스킬을 고쳐도 옛 자리는 옛 코드를 쓴다.
    결과자리 = 자리 / "engine" / "outputs" / "voc_dashboard_60" / "지난실행"
    결과자리.mkdir(parents=True, exist_ok=True)
    (결과자리 / "voc_dashboard_dataset.csv").write_text("x\n", encoding="utf-8")   # 결과는 건드리면 안 된다
    (자리 / "1차_돌리기.py").write_text("# 낡은 사본\n", encoding="utf-8")
    r4 = _돌리기(s / "scripts" / "1차자리_차리기.py", 자리)
    assert r4.returncode == 1 and "다릅니다" in r4.stdout and "1차_돌리기.py" in r4.stdout, r4.stdout
    # `--새로` 로 갈아 끼우고, 결과 폴더는 그대로 둔다
    r5 = _돌리기(s / "scripts" / "1차자리_차리기.py", 자리, "--새로")
    assert r5.returncode == 0, r5.stdout + r5.stderr
    assert (자리 / "1차_돌리기.py").read_text(encoding="utf-8") != "# 낡은 사본\n"
    assert (결과자리 / "voc_dashboard_dataset.csv").read_text(encoding="utf-8") == "x\n", "결과를 건드렸다"
    r6 = _돌리기(s / "scripts" / "1차자리_차리기.py", 자리)
    assert r6.returncode == 0, r6.stdout


def test_총괄_스킬이_떨어진_자리에서_총괄_자리를_차린다(묶음, tmp_path):
    s = _풀기(묶음, "coordinating-voc-pipeline", tmp_path / "풀린곳")
    r = _돌리기(s / "scripts" / "총괄자리_차리기.py", tmp_path / "총괄", "시험판")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "못 찾" not in r.stdout, r.stdout
    판 = tmp_path / "총괄" / "시험판"
    assert len(list(판.glob("*.py"))) == 42
    with zipfile.ZipFile(판 / "_배포" / "VoC_3_3차감독.zip") as zf:
        assert len([n for n in zf.namelist() if not n.endswith("/")]) == 74
