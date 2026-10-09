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
sys.path.insert(0, str(REPO / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402
import build_skills  # noqa: E402
import check_shared  # noqa: E402


@pytest.fixture(scope="module")
def 묶음(tmp_path_factory):
    d = tmp_path_factory.mktemp("dist")
    assert build_skills.만들기(d) == 0
    return d


def test_스킬_다섯을_다_묶었다(묶음):
    assert build_skills.스킬들() == ["building-voc-report", "coordinating-voc-pipeline",
                                 "reading-voc-comments", "running-voc-engine",
                                 "supervising-voc-disagreements"]
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


def test_보고서_스킬이_떨어진_자리에서_보고서를_만든다(묶음, tmp_path):
    """★ 섹션 8 — 낱개 스킬 폴더 하나만으로 **실제 최종 산출물**에서 보고서가 나오는가.

    보는 것 — ① 보고서가 만들어지나 ② 원문 전량(raw_voc)이 안 담기나 ③ 링크·이메일·사용자명이 0건이고
    **치운 건수를 보고서가 적었나**(「했다」 가 아니라 「확인했다」 · 65 §3) ④ 숫자에 출처가 붙었나
    ⑤ 못 찾거나 담을 시트가 없으면 **통과로 넘기지 않나**(종료 2).
    """
    import re
    s = _풀기(묶음, "building-voc-report", tmp_path / "풀린곳")
    도구 = s / "scripts" / "보고서_만들기.py"
    최종 = BASELINE / "실행" / "4차반영_1" / "2판" / "_최종결과" / "3차_최종데이터.xlsx"
    if not 최종.is_file():
        pytest.skip("얼린 4차 결과가 없다")

    낼것 = tmp_path / "보고서.html"
    r = _돌리기(도구, 최종, 낼것)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 낼것.is_file()
    글 = 낼것.read_text(encoding="utf-8")
    assert "★PL Issue" in 글 and "improvement_priority" in 글, "담아야 할 것이 없다"
    assert 글.count("class=\"출처\"") >= 3, "숫자에 출처가 안 붙었다"
    # 원문 전량은 「안 담았다」 는 설명에만 나와야 한다
    assert 글.count("raw_voc") <= 6, "원문 전량이 담긴 것 같다"
    assert not re.search(r"https?://", 글), "링크가 남았다"
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", 글), "이메일이 남았다"
    assert "다시 훑은 결과" in 글 and "치운 것" in 글, "「했다」 가 아니라 「확인했다」 가 들어가야 한다"

    # ★ 못 찾으면 통과가 아니다
    r2 = _돌리기(도구, tmp_path / "없는것.xlsx")
    assert r2.returncode == 2 and "못 찾음" in r2.stdout, r2.stdout
    # ★ 담을 시트가 하나도 없어도 통과가 아니다
    import openpyxl
    엉뚱 = tmp_path / "엉뚱.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["a", "b"])
    wb.save(엉뚱)
    r3 = _돌리기(도구, 엉뚱, tmp_path / "엉뚱.html")
    assert r3.returncode == 2, r3.stdout


def test_스킬마다_시험과_돌리개가_실제로_있다():
    """★ 2026-10-09 — 보고서 스킬의 evals.json 에 「돌리는 도구: …보고서시험_돌리기.py」 라고
    적어 놓고 **그 파일을 안 만든** 적이 있다. 적어 두기만 하고 없으면 「시험이 있다」 고 착각한다.

    스킬마다 ① evals.json 이 있고 ② 그 안에 시험이 3개 이상이고 ③ 「돌리는 도구」 가 적혀 있고
    ④ 그 파일이 **실제로 있는지** 본다. (못 찾으면 통과가 아니다.)
    """
    import re
    없음 = []
    for s in build_skills.스킬들():
        ev = REPO / "plugin" / "skills" / s / "evals" / "evals.json"
        if not ev.is_file():
            없음.append("%s — evals.json 이 없다" % s)
            continue
        d = json.loads(ev.read_text(encoding="utf-8"))
        if len(d.get("evals") or []) < 3:
            없음.append("%s — 시험이 %d개뿐이다 (3개 이상)" % (s, len(d.get("evals") or [])))
        m = re.search(r"돌리는 도구:\s*([^\s\"',]+)", d.get("설명") or "")
        if not m:
            없음.append("%s — 「돌리는 도구」 가 안 적혀 있다" % s)
        elif not (REPO / m.group(1)).is_file():
            없음.append("%s — 돌리개가 없다: %s" % (s, m.group(1)))
    assert build_skills.스킬들(), "스킬을 하나도 못 찾았다 — 통과가 아니다"
    assert not 없음, "스킬의 시험·돌리개가 갖춰지지 않았다 — %s" % 없음


def test_한줄흐름이_이어가고_되감고_조건없이는_안돈다(tmp_path):
    """★ Ver2 ①② — 총괄이 단계를 잇고, 멈추면 **그대로 다시 넣어 이어간다**.

    돈을 쓰지 않고 본다(`--확인만`) — ① 끝난 단계는 건너뛰나 ② 되감으면 그 앞부터인가
    ③ 조건 없이 처음 돌리면 막히나(지어내고 돌리지 않는다).
    """
    import importlib.util as u
    도구 = REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts" / "한줄_돌리기.py"
    assert 도구.is_file(), "한줄_돌리기.py 를 못 찾았다"
    s = u.spec_from_file_location("한줄", 도구)
    m = u.module_from_spec(s)
    s.loader.exec_module(m)

    판 = tmp_path / "판"
    상태 = m.상태읽기(판)
    상태["조건"] = {"검색어": "시험", "영상": "1", "댓글": "5", "이름": "시험판"}
    상태["끝난단계"] = ["1차", "2차준비", "2차판독"]
    m.상태쓰기(판, 상태)
    # 소견 — 분석에 지장 없는 지적은 **싣고 간다**
    m.소견더하기(판, 상태, "총괄검수1", "라벨이 모자란 행이 있습니다")
    assert "라벨이 모자란" in (판 / m.소견이름).read_text(encoding="utf-8")

    def 돌려(*인자):
        return subprocess.run([sys.executable, "-B", str(도구), str(판), *인자],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    r = 돌려("--확인만")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "이미 끝난 단계: 1차 · 2차준비 · 2차판독" in r.stdout, r.stdout
    assert "아무것도 돌리지 않았고" in r.stdout

    r2 = 돌려("--되감기", "2차판독", "--확인만")
    assert "이미 끝난 단계: 1차 · 2차준비" in r2.stdout and "2차판독 —" not in r2.stdout, r2.stdout

    # ★ 조건 없이 처음 돌리면 막힌다 (지어내고 돌리지 않는다)
    새판 = tmp_path / "새판"
    r3 = subprocess.run([sys.executable, "-B", str(도구), str(새판)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r3.returncode == 2 and "--조건 이 필요합니다" in r3.stdout, r3.stdout
