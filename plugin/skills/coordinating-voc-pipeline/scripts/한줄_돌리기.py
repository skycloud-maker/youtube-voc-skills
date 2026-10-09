# -*- coding: utf-8 -*-
"""1차부터 4차 앞까지 **한 줄로** 잇는다 — Ver2.

★ 무엇이 달라지나 (sky 2026-10-09)
  지금(Ver1)은 사람이 창을 7~8번 열고 회차마다 프롬프트를 붙여넣는다.
  Ver2 는 그 심부름을 총괄이 한다 — **인풋 두 번**으로 끝난다.

      인풋 1  1차 조건  →  1차 → 2차 판독 둘 → 총괄 검수 → 3차 감독 둘 → 총괄 검수
              →  아웃풋 1  사람이 회의로 정할 것
      인풋 2  회의 결정  →  아웃풋 2  최종 엑셀 + 사내 보고서

  ★ 판독자·감독자 구성은 **Ver1 그대로**다 (Claude · Codex). 분석 방식은 하나도 바뀌지 않는다.

★ 멈춤과 싣고 가기 (sky 2026-10-09 결정)
  - **비용으로 멈추지 않는다.** 예상액을 먼저 말하고, 벗어나면 **알리면서 계속** 간다.
  - **멈추는 것** — 판독자가 죽음 · 결과가 안 나옴 · 키 없음 · 칸 계약이 깨짐.
    지어내지 않고, 하나만 가지고 다음 차수로 넘기지 않는다.
  - **싣고 가는 것** — 담을 라벨이 모자람 · 기준서가 애매함 · 판독자 둘이 체계적으로 다름.
    `소견.md` 에 적어 **아웃풋 1 과 함께** 사람에게 간다.

★ 멈춰도 **그대로 다시 넣으면 이어진다** — 단계마다 `상태.json` 에 적는다.
  끝난 단계는 다시 돌리지 않는다(돈과 시간을 다시 쓰지 않는다).

★ Ver3 을 위해 — 「누가 판독하나」 를 **설정으로** 둔다(`판독자` · `감독자`). 코드에 박지 않는다.
  그래야 나중에 구독을 줄일 때 값만 바꾸면 된다.

쓰기
    python 한줄_돌리기.py <판자리> --조건 "검색어=LG 로봇청소기; 영상=5; 댓글=50"
    python 한줄_돌리기.py <판자리> --확인만          무엇을 할지만 보여 준다 (돈 안 든다)
    python 한줄_돌리기.py <판자리>                   멈춘 지점부터 이어간다
    python 한줄_돌리기.py <판자리> --되감기 3차감독   그 단계부터 다시 한다
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _찾기(이름: str) -> Path:
    """스킬 안 사본 → 플러그인 옆 한 벌 (낱개로 꾸리면 스킬 안에 들어 있다)."""
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


def _옆스킬(이름: str) -> Path:
    for d in (스킬 / "skills" / 이름, 스킬.parent / 이름):
        if d.is_dir():
            return d
    return 스킬.parent / 이름


# ── 누가 하나 — ★ 설정이다. 코드에 박지 않는다 (Ver3 에서 값만 바꾼다) ──────────────
판독자 = [("판독A", "claude"), ("판독B", "codex")]
감독자 = [("감독1", "codex"), ("감독2", "claude")]
# 「claude:모델」 꼴로 모델을 고를 수 있다 (예: ("판독B", "claude:sonnet"))

상태이름 = "상태.json"
소견이름 = "소견.md"


def 상태읽기(판: Path) -> dict:
    p = 판 / 상태이름
    if not p.is_file():
        return {"만든날": datetime.now().strftime("%Y-%m-%d %H:%M"), "끝난단계": [], "소견": [], "기록": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def 상태쓰기(판: Path, 상태: dict) -> None:
    판.mkdir(parents=True, exist_ok=True)
    (판 / 상태이름).write_text(json.dumps(상태, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def 소견더하기(판: Path, 상태: dict, 단계: str, 말: str) -> None:
    """분석에 지장은 없지만 **사람이 회의에서 정할 거리** — 아웃풋 1 과 함께 간다."""
    상태.setdefault("소견", []).append({"단계": 단계, "때": datetime.now().strftime("%m-%d %H:%M"), "말": 말})
    상태쓰기(판, 상태)
    줄 = ["# 총괄 검수 소견 — 회의에서 정할 거리\n",
          "> 분석을 멈출 일은 아니지만 **사람이 정해야** 하는 것들이다. 아웃풋 1 과 함께 본다.\n"]
    for s in 상태["소견"]:
        줄.append("- **[%s]** %s  <sub>%s</sub>" % (s["단계"], s["말"], s["때"]))
    (판 / 소견이름).write_text("\n".join(줄) + "\n", encoding="utf-8", newline="\n")


# ★ Codex 는 **내장 파이썬**을 먼저 잡게 한다 (2026-09-21 에 두 번, 2026-10-09 에 한 번 더 막혔다).
#   Codex 샌드박스 안에서는 사용자 파이썬(AppData)의 pandas 가 **이름만 보이고 내용이 안 읽혀**
#   자가점검이 「pandas 를 못 씁니다」 로 멈춘다. 내장 파이썬에는 pandas · openpyxl 이 있다.
#   2차 판독이 지나간 것은 Codex 가 **우연히** 내장 파이썬을 골랐기 때문이고, 3차 감독에서 터졌다.
#   스킬 시험(`tests/evals/스킬시험_돌리기.py:_codex_env`)은 이미 이렇게 하고 있었다 —
#   ★ 총괄만 빠져 있었다. 시험에서만 고치고 실제 흐름에 안 넣으면 똑같이 다시 터진다.
#   ※ 사용자 파이썬 설정은 건드리지 않는다. 이 한 번의 실행에서 PATH 앞에만 놓는다.
_코덱스파이썬 = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python"


def _코덱스파이썬_먼저(환경: dict) -> dict:
    if not _코덱스파이썬.is_dir():
        print("   ! Codex 내장 파이썬을 못 찾았습니다 (%s) — pandas 로 막힐 수 있습니다" % _코덱스파이썬)
        return 환경
    환경 = dict(환경)
    환경["PATH"] = (str(_코덱스파이썬) + os.pathsep + str(_코덱스파이썬 / "Scripts")
                  + os.pathsep + 환경.get("PATH", ""))
    return 환경


def AI돌리기(누구: str, 작업: Path, 프롬프트: str, 기록자리: Path, 분: int = 240) -> tuple[int, str]:
    """판독자·감독자를 **띄우고 거둬** 온다. 돌려주는 것 — (종료코드, 마지막 답).

    ★ 이것이 Ver2 의 핵심이다 — 지금까지 사람이 창을 열어 붙여넣던 일이다.
      되는 것은 증명됐다 (2026-10-09 · 이 방식으로 돌린 1차 Codex 시험이 8/8 통과).
    """
    기록자리.parent.mkdir(parents=True, exist_ok=True)
    환경 = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    if 누구 == "codex":
        환경 = _코덱스파이썬_먼저(환경)
    if 누구.startswith("claude"):
        명령 = [shutil.which("claude"), "-p", "--output-format", "stream-json", "--verbose",
              "--dangerously-skip-permissions", "--plugin-dir", str(스킬.parents[1])]
        모델 = 누구.split(":", 1)[1] if ":" in 누구 else ""
        if 모델:
            명령 += ["--model", 모델]
    elif 누구 == "codex":
        명령 = [shutil.which("codex"), "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "-"]
    else:
        raise SystemExit("모르는 판독자 종류: %s" % 누구)
    if not 명령[0]:
        raise SystemExit("못 찾음: %s 명령이 이 컴퓨터에 없습니다" % 누구.split(":")[0])
    r = subprocess.run(명령, input=프롬프트, cwd=str(작업), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=환경, timeout=분 * 60)
    기록자리.write_text(r.stdout, encoding="utf-8")
    (기록자리.with_suffix(".stderr.txt")).write_text(r.stderr, encoding="utf-8")
    return r.returncode, _마지막답(r.stdout)


def _마지막답(스트림: str) -> str:
    말 = []
    for 줄 in 스트림.splitlines():
        try:
            e = json.loads(줄)
        except ValueError:
            continue
        if e.get("type") == "result" and isinstance(e.get("result"), str):      # claude
            말.append(e["result"])
        it = e.get("item") or {}
        if e.get("type") == "item.completed" and it.get("type") == "agent_message":   # codex
            말.append(it.get("text") or "")
    return 말[-1] if 말 else ""


class 멈춤(Exception):
    """크리티컬 — 여기서 멈추고 사람에게 알린다. 지어내지 않는다."""


_합계줄 = re.compile(r"✗\s*\d+건\s*[·|]")   # 자가점검 맨 끝의 합계 줄 — 지적이 아니다


def _파이썬(스크립트: Path, *인자, 작업: Path | None = None) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", str(스크립트), *map(str, 인자)],
                       cwd=str(작업) if 작업 else None, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"))
    return r.returncode, r.stdout + r.stderr


# ── 단계들 ────────────────────────────────────────────────────────────────
#   각 단계는 (이름, 하는 일, 무엇을 남기나) 다. 끝나면 상태에 적고 다시 돌리지 않는다.

def 단계_1차(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """1차 수집·분석. ★ 돌리기 전에 어림을 내고 **승인**을 받는다 (1차 돌리개가 한다)."""
    자리 = 판 / "1차"
    차리기 = _옆스킬("running-voc-engine") / "scripts" / "1차자리_차리기.py"
    돌리개 = 자리 / "1차_돌리기.py"
    if 확인만:
        print("   · 1차 자리를 차리고(%s) 어림을 낸 뒤 승인받아 돌린다" % 자리.name)
        return
    코드, 말 = _파이썬(차리기, 자리, "--새로")
    if 코드:
        raise 멈춤("1차 자리를 못 차렸습니다:\n%s" % 말[-800:])
    코드, 말 = _파이썬(돌리개, "--검색어", 조건["검색어"], "--영상", 조건["영상"], "--댓글", 조건["댓글"],
                   "--이름", 조건["이름"], "--승인", 작업=자리)
    상태.setdefault("기록", {})["1차"] = 말[-1500:]
    if 코드:
        raise 멈춤("1차가 끝나지 못했습니다 (종료 %d):\n%s" % (코드, 말[-800:]))
    print(말.strip()[-600:])


def 단계_2차준비(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """판독 폴더 둘을 차리고 1차 결과를 앉힌다 — **둘은 서로 모른다**(따로 돌린다)."""
    번들 = _가장새것((판 / "1차" / "engine" / "outputs" / "voc_dashboard_60" / 조건["이름"]).glob(
        "voc_dashboard_export_bundle*.xlsx")) if not 확인만 else None
    if 확인만:
        print("   · 판독 폴더 둘(%s)을 차리고 1차 번들을 앉힌다" % " · ".join(n for n, _ in 판독자))
        return
    if 번들 is None:
        raise 멈춤("1차 번들을 못 찾았습니다 — 1차가 제대로 끝났는지 보십시오")
    차리기 = _옆스킬("reading-voc-comments") / "scripts" / "판독폴더_차리기.py"
    for 이름, _ in 판독자:
        자리 = 판 / 이름
        코드, 말 = _파이썬(차리기, 자리)
        if 코드:
            raise 멈춤("%s 폴더를 못 차렸습니다:\n%s" % (이름, 말[-500:]))
        코드, 말 = _파이썬(자리 / "스크립트" / "데이터_넣기.py", 번들, "--덮어쓰기", 작업=자리)
        if 코드:
            raise 멈춤("%s 에 1차 결과를 못 앉혔습니다:\n%s" % (이름, 말[-500:]))
        if "없습니다" in 말 and "7_영상메타" in 말:
            소견더하기(판, 상태, "2차준비", "%s — 1차가 만든 영상메타가 없어 옛 판 것을 썼습니다. "
                               "판독자가 영상 제목만 보고 판단했을 수 있습니다." % 이름)
        print("   · %s 차림 — %s" % (이름, [l for l in 말.splitlines() if "회차" in l][:1]))


def 단계_2차판독(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """판독자 둘을 **따로** 띄운다. 하나가 죽으면 멈춘다 — 하나만 가지고 3차로 넘기지 않는다."""
    if 확인만:
        print("   · 판독자 둘을 따로 띄운다: %s" % " · ".join("%s(%s)" % (n, w) for n, w in 판독자))
        return
    for 이름, 누구 in 판독자:
        자리 = 판 / 이름
        끝남 = list((자리 / "_판독패키지" / "_결과").glob("*_bundle/raw_voc.csv"))
        if 끝남:
            print("   · %s — 이미 끝나 있어 건너뜁니다" % 이름)
            continue
        if 누구 == "codex":
            d = 자리 / ".agents"
            if not d.exists():
                shutil.copytree(_옆스킬("reading-voc-comments"), d / "skills" / "reading-voc-comments")
                shutil.copytree(_찾기("shared"), d / "shared")
                shutil.copytree(_찾기("engine"), d / "engine")
            subprocess.run(["git", "init", "-q"], cwd=str(자리))
        코드, 답 = AI돌리기(누구, 자리, "이 폴더에 있는 1차 분석 결과로 2차 판독을 해 주세요.",
                        판 / "기록" / ("%s.jsonl" % 이름))
        상태.setdefault("기록", {})[이름] = 답[-1200:]
        번들 = sorted((자리 / "_판독패키지" / "_결과").glob("*_bundle/raw_voc.csv"))
        if 코드 or not 번들:
            raise 멈춤("%s(%s) 판독이 끝나지 못했습니다 (종료 %d · 번들 %d개).\n마지막 답:\n%s"
                     % (이름, 누구, 코드, len(번들), 답[-700:]))
        print("   · %s 판독 끝 — 번들 %s" % (이름, 번들[0].parent.name))


def 단계_총괄검수1(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """2차 결과를 총괄이 **검수**한다 — 칸 계약은 멈춤, 나머지는 소견으로 싣는다."""
    if 확인만:
        print("   · 판독 번들 둘을 검수한다 (check_selfcheck · 최신결정_검사 번들)")
        return
    for 이름, _ in 판독자:
        자리 = 판 / 이름
        번들 = _가장새것((자리 / "_판독패키지" / "_결과").glob("*_bundle"))
        if 번들 is None:
            raise 멈춤("%s 의 번들을 못 찾았습니다" % 이름)
        코드, 말 = _파이썬(자리 / "스크립트" / "check_selfcheck.py", 번들, 작업=자리)
        # ★ 맨 끝의 **합계 줄**(`✗ 0건 · ! 2건`)도 ✗ 로 시작한다 (check_selfcheck.py:703).
        #   그것까지 지적으로 세면 **깨끗한 번들에도 늘 소견이 하나 붙는다** (2026-10-09 잡음).
        나쁨 = [l for l in 말.splitlines()
              if l.strip().startswith("✗") and not _합계줄.match(l.strip())]
        if 나쁨:
            # 칸 계약이 깨진 것은 멈춤 · 그 밖의 지적은 소견으로
            if any("칸" in l or "계약" in l or "컬럼" in l for l in 나쁨):
                raise 멈춤("%s 번들의 칸 계약이 깨졌습니다:\n%s" % (이름, "\n".join(나쁨[:5])))
            소견더하기(판, 상태, "총괄검수1", "%s 자가점검 지적 %d건 — %s"
                     % (이름, len(나쁨), " / ".join(l.strip()[:70] for l in 나쁨[:3])))
        코드2, 말2 = _파이썬(자리 / "스크립트" / "최신결정_검사.py", "번들", 작업=자리)
        if 코드2 == 2:
            소견더하기(판, 상태, "총괄검수1", "%s — 최신결정_검사가 볼 것을 못 찾았습니다(확인 필요)" % 이름)
        elif 코드2:
            소견더하기(판, 상태, "총괄검수1", "%s 최신결정 위반 — %s"
                     % (이름, " / ".join(l.strip()[:70] for l in 말2.splitlines() if "✗" in l)[:200]))
        print("   · %s 검수 — 자가점검 지적 %d · 최신결정 종료 %d" % (이름, len(나쁨), 코드2))


def 단계_3차준비(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """총괄 자리를 차리고 `3차_준비` 로 갈린 행을 뽑아 감독 폴더 둘을 만든다."""
    if 확인만:
        print("   · 총괄 자리를 차리고 3차_준비 로 감독 폴더 둘을 만든다")
        return
    총괄 = 판 / "총괄"
    코드, 말 = _파이썬(스킬 / "scripts" / "총괄자리_차리기.py", 총괄, 조건["이름"])
    if 코드:
        raise 멈춤("총괄 자리를 못 차렸습니다:\n%s" % 말[-600:])
    판자리 = 총괄 / 조건["이름"]
    결과 = 판자리 / "_판독패키지" / "_결과"
    결과.mkdir(parents=True, exist_ok=True)
    for 이름, _ in 판독자:
        for b in sorted((판 / 이름 / "_판독패키지" / "_결과").glob("*_bundle")):
            목표 = 결과 / b.name
            if not 목표.exists():
                shutil.copytree(b, 목표)
    코드, 말 = _파이썬(판자리 / "3차_준비.py", 작업=판자리)
    상태.setdefault("기록", {})["3차준비"] = 말[-1200:]
    if 코드:
        raise 멈춤("3차_준비가 끝나지 못했습니다 (종료 %d):\n%s" % (코드, 말[-800:]))
    감독폴더 = sorted((판자리 / "_감독폴더").glob("*")) if (판자리 / "_감독폴더").is_dir() else []
    if len(감독폴더) < 2:
        raise 멈춤("감독 폴더가 둘이 아닙니다 (%d개)" % len(감독폴더))
    print("   · 감독 폴더 %d개 — %s" % (len(감독폴더), " · ".join(p.name for p in 감독폴더)))


def 단계_3차감독(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """감독자 둘을 **따로** 띄운다."""
    if 확인만:
        print("   · 감독자 둘을 따로 띄운다: %s" % " · ".join("%s(%s)" % (n, w) for n, w in 감독자))
        return
    판자리 = 판 / "총괄" / 조건["이름"]
    폴더들 = sorted((판자리 / "_감독폴더").glob("*"))
    for (이름, 누구), 자리 in zip(감독자, 폴더들):
        # ★ 감독 결과는 `자리/_결과` 가 아니라 `자리/_판독패키지/_결과` 에 떨어진다 (2026-10-09 실측).
        #   엉뚱한 자리를 봐서 「이미 끝났나」 가 **한 번도 참이 안 됐다** — 이어 돌리면 끝난 감독을
        #   또 띄워 돈을 두 번 쓴다. sky 「토큰을 최소화하며 최종 분석까지」 에 어긋난다.
        끝남 = list(자리.rglob("감독결과_*.md"))
        if 끝남:
            print("   · %s — 이미 끝나 있어 건너뜁니다" % 이름)
            continue
        if 누구 == "codex":
            d = 자리 / ".agents"
            if not d.exists():
                shutil.copytree(_옆스킬("supervising-voc-disagreements"), d / "skills" / "supervising-voc-disagreements")
                shutil.copytree(_찾기("shared"), d / "shared")
                shutil.copytree(_찾기("engine"), d / "engine")
            subprocess.run(["git", "init", "-q"], cwd=str(자리))
        코드, 답 = AI돌리기(누구, 자리, "이 폴더에서 3차 감독을 해 주세요.", 판 / "기록" / ("%s.jsonl" % 이름))
        상태.setdefault("기록", {})[이름] = 답[-1200:]
        낸것 = list(자리.rglob("감독결과_*.md"))
        if 코드 or not 낸것:
            raise 멈춤("%s(%s) 감독이 끝나지 못했습니다 (종료 %d · 판정 %d개).\n%s"
                     % (이름, 누구, 코드, len(낸것), 답[-700:]))
        print("   · %s 감독 끝 — 판정 %d개" % (이름, len(낸것)))


def 단계_3차마무리(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """통합 · 편향검사 · 보정요청 · 최종 번들까지. 여기서 **아웃풋 1** 이 나온다."""
    if 확인만:
        print("   · 3차_마무리 · 폐기라벨_정리 · 번들_마무리꾸미기 → 아웃풋 1")
        return
    판자리 = 판 / "총괄" / 조건["이름"]
    for 도구 in ("3차_마무리.py", "폐기라벨_정리.py", "번들_마무리꾸미기.py"):
        코드, 말 = _파이썬(판자리 / 도구, 작업=판자리)
        상태.setdefault("기록", {})[도구] = 말[-900:]
        if 코드:
            raise 멈춤("%s 가 끝나지 못했습니다 (종료 %d):\n%s" % (도구, 코드, 말[-900:]))
        print("   · %s 끝" % 도구)


# ★ 「최종」 이 어느 자리인지 **순서로** 적어 둔다 (2026-10-09).
#   그 전에는 `sorted(판자리.rglob(이름))[0]` — 즉 **글자 순 첫 번째**를 담았다.
#   `claudecode_bundle` 이 `master_final` 보다 글자 순으로 앞서서, 아웃풋 1 에
#   **판독A 의 중간 번들**이 담겼다. 사람이 받은 분리제안은 4행인데 같은 꾸러미 안의
#   최종 엑셀 시트는 2행이었다 — 한 꾸러미에서 같은 것이 두 벌, 숫자가 둘.
#   네 파일이 맞았던 것은 운이었다(중간 번들에 그 이름이 없었다).
최종자리 = ("_최종결과", "_인계", "_판독패키지/_결과/master_final", "s15_master")


def _가장새것(것들) -> Path | None:
    """여러 개면 **가장 새 것**을 집는다 — `next(glob(...))` 는 순서가 정해져 있지 않다.

    (2026-10-09 아웃풋1 이 글자 순 첫 번째를 집어 중간 사본을 담았다. 같은 실수를 안 하게
     여기 한 군데로 모았다.)
    """
    것들 = sorted(것들, key=lambda q: q.stat().st_mtime)
    return 것들[-1] if 것들 else None


def _최종사본(판자리: Path, 이름: str) -> tuple[Path | None, list[Path]]:
    """최종 자리에서 `이름` 을 집고, **다른 내용의 중간 사본**을 같이 돌려준다.

    못 찾으면 (None, …) — 부르는 쪽이 멈춘다. 「못 찾음」 을 「중간 것으로 때우기」 로 바꾸지 않는다.
    """
    모든것 = sorted(판자리.rglob(이름))
    고른것 = None
    for 자리 in 최종자리:
        것 = 판자리 / 자리 / 이름
        if 것.is_file():
            고른것 = 것
            break
    if 고른것 is None:
        return None, []
    기준 = 고른것.read_bytes()
    다름 = [p for p in 모든것 if p != 고른것 and p.read_bytes() != 기준]
    return 고른것, 다름


def 단계_아웃풋1(판: Path, 상태: dict, 조건: dict, 확인만: bool) -> None:
    """사람이 회의로 정할 것을 한자리에 모은다 — 여기서 **사람 차례**다."""
    if 확인만:
        print("   · 사람이 볼 것을 모은다 (사람이볼목록 · 보정요청 · 분리제안 · 총괄 소견)")
        return
    판자리 = 판 / "총괄" / 조건["이름"]
    모을곳 = 판 / "아웃풋1_회의에서_정할것"
    모을곳.mkdir(parents=True, exist_ok=True)
    찾을것 = ["사람이볼목록.csv", "보정요청.csv", "보정요청_논의본.md", "분리제안.csv", "3차_최종데이터.xlsx"]
    모음, 다름 = [], []
    for 이름 in 찾을것:
        고른것, 나머지 = _최종사본(판자리, 이름)
        if 고른것 is None:
            raise 멈춤(chr(10).join([
                "아웃풋 1 에 담을 %s 을 **최종 자리**에서 못 찾았습니다." % 이름,
                "   본 자리: %s" % " · ".join(최종자리),
                "   (중간 번들에 있는 것을 몰래 담지 않습니다 — 숫자가 둘이 됩니다)"]))
        shutil.copy2(고른것, 모을곳 / 이름)
        모음.append(이름)
        # ★ 중간 사본이 최종과 다르면 **회의에 알린다** — 멈추지 않는다.
        #   실제로 본 것 (2026-10-09): 판독A 가 분리제안 4행을 냈는데 최종은 2행이었다.
        #   엔진이 그렇게 하기로 되어 있다 (build_master.py:638 「분리·기준서·결함은 판독자 2 의
        #   번들에서 그대로 잇는다」). 그래도 판독A 가 낸 2건이 조용히 사라지는 것은 사람이 알아야 한다.
        if 나머지:
            다름.append("%s — 최종은 %s 것이고, %s 에 다른 사본이 있습니다"
                      % (이름, 고른것.parent.name, " · ".join(sorted(x.parent.name for x in 나머지))))
    for 말 in 다름:
        소견더하기(판, 상태, "아웃풋1", 말)
    if (판 / 소견이름).is_file():
        shutil.copy2(판 / 소견이름, 모을곳 / 소견이름)
        모음.append(소견이름)
    if not 모음:
        raise 멈춤("아웃풋 1 에 담을 것을 하나도 못 찾았습니다 — 3차가 제대로 끝났는지 보십시오")
    (모을곳 / "0_여기서_정하십시오.md").write_text(
        "# 회의에서 정할 것\n\n"
        "```\n"
        "① 사람이볼목록.csv   감독도 갈린 행 — 사람이 정한다\n"
        "② 보정요청.csv       담을 라벨이 없는 것 — 회사가 정한다\n"
        "③ 분리제안.csv       잘못 쪼갠 게 있나 확인\n"
        "★ 소견.md            총괄이 보기에 사람이 정해야 할 것\n"
        "```\n\n"
        "정한 뒤 — `python 한줄_돌리기.py <판자리> --4차반영` 을 돌리면 최종 엑셀과 보고서가 나옵니다.\n"
        "(정한 값은 위 파일에 적어 두십시오. 총괄이 그대로 데이터에 넣습니다.)\n\n"
        "담긴 것: %s\n" % " · ".join(모음), encoding="utf-8", newline="\n")
    print("   · 아웃풋 1 — %s" % 모을곳)
    print("     담긴 것: %s" % " · ".join(모음))


단계들 = [("1차", 단계_1차), ("2차준비", 단계_2차준비), ("2차판독", 단계_2차판독),
        ("총괄검수1", 단계_총괄검수1), ("3차준비", 단계_3차준비), ("3차감독", 단계_3차감독),
        ("3차마무리", 단계_3차마무리), ("아웃풋1", 단계_아웃풋1)]


def 사차반영(판: Path, 상태: dict, 조건: dict) -> int:
    """인풋 2 — 회의에서 정한 값을 데이터에 넣고 최종 엑셀과 보고서를 낸다."""
    판자리 = 판 / "총괄" / 조건["이름"]
    코드, 말 = _파이썬(판자리 / "4차_반영.py", 작업=판자리)
    print(말.strip()[-900:])
    if 코드:
        print("  ✗ 4차_반영이 멈췄습니다 — 위를 보고 고친 뒤 다시 돌리십시오.")
        return 1
    # ★ 4차 반영이 **내놓는 것**을 집는다 (2026-10-09 에 틀렸던 자리).
    #   처음에는 `3차_최종데이터.xlsx` 를 집었는데, 그것은 **4차 반영 전** 엑셀이다.
    #   4차_반영.py:231 이 스스로 「받을 것」 으로 적는 것은
    #   `_판독패키지/_결과/master_final/voc_dashboard_export_bundle_*.xlsx` 다 (17시트).
    #   그래서 아웃풋 2 에 4차가 안 반영된 파일이 들어갔다 — 최종이 최종이 아니었다.
    #   ★ 「더 새 것」 을 확인한다. 4차가 아무것도 안 만들었는데 옛 파일을 최종이라 부르지 않는다.
    번들자리 = 판자리 / "_판독패키지" / "_결과" / "master_final"
    낸것 = sorted(번들자리.glob("voc_dashboard_export_bundle*.xlsx"))
    삼차, _ = _최종사본(판자리, "3차_최종데이터.xlsx")
    if not 낸것:
        print("  ✗ 4차 반영 산출물(voc_dashboard_export_bundle*.xlsx)을 %s 에서 못 찾았습니다"
              % 번들자리)
        print("    (못 찾음은 통과가 아닙니다 — 3차 엑셀을 최종이라 부르지 않습니다)")
        return 2
    최종 = _가장새것(낸것)
    if 삼차 is not None and 최종.stat().st_mtime < 삼차.stat().st_mtime:
        print("  ✗ 4차 산출물이 3차 엑셀보다 **낡았습니다** — 4차 반영이 실제로 돌지 않았습니다")
        print("    4차: %s" % 최종)
        print("    3차: %s" % 삼차)
        return 2
    보고서도구 = _옆스킬("building-voc-report") / "scripts" / "보고서_만들기.py"
    코드2, 말2 = _파이썬(보고서도구, 최종, 판 / "아웃풋2_최종" / "VoC_분석보고서.html")
    print(말2.strip()[-700:])
    shutil.copy2(최종, 판 / "아웃풋2_최종" / 최종.name)
    상태["끝난단계"] = list(dict.fromkeys(상태.get("끝난단계", []) + ["4차반영"]))
    상태쓰기(판, 상태)
    return 0 if 코드2 == 0 else 1


def _조건풀기(글: str, 판: Path) -> dict:
    """「검색어=LG 로봇청소기; 영상=5; 댓글=50」 을 푼다."""
    d = {}
    for 쪽 in (글 or "").split(";"):
        if "=" in 쪽:
            k, v = 쪽.split("=", 1)
            d[k.strip()] = v.strip()
    return {"검색어": d.get("검색어", ""), "영상": d.get("영상", "2"), "댓글": d.get("댓글", "10"),
            "이름": d.get("이름") or ("판_" + datetime.now().strftime("%Y%m%d_%H%M"))}


def _엔진_가리키기() -> None:
    """★ 도구들에게 **엔진이 어디 있는지** 알려 준다 (`VOC_ENGINE`).

    2026-10-09 에 실제로 터진 것 —
      총괄검수1 이 「번들에서 빠진 칸 2 — video_tags / video_description」 으로 흐름을 멈췄다.
      그런데 원문 `25_판정대상_컬럼분류.md:52` 는 이렇게 적어 두었다 —
      「video_tags · video_description 은 66컬럼에 없다. 1차가 LLM 입력으로만 쓰고
        출력에서 뺐다 (D-30). 판독자는 이 두 값을 볼 수 없다.」
      즉 **판독자 잘못이 아니었고, 내 검수가 틀렸다.**

    까닭은 칸 이름이 아니라 **환경**이었다. `check_selfcheck` 의 `_일차가_내놓는가()` 는
    엔진의 `TARGET_COLUMNS` 를 봐서 「번들 만들다 잃은 칸」 과 「1차가 애초에 안 내놓는 칸」 을
    가른다. 그런데 엔진을 못 보면 `return True` — 「엔진을 못 보면 예전대로 반려한다」 로
    떨어진다. 총괄이 `VOC_ENGINE` 을 안 줘서 그 눈먼 길로 갔다.
    기준 만들개(`tests/baseline/기준_만들기.py:96`) · 스킬 시험(`tests/evals/스킬시험_돌리기.py:152`)
    은 이미 주고 있었다. **총괄만 빠져 있었다.**

    그래서 칸 이름을 코드에 박지 않고 엔진을 가리킨다 — 진짜로 칸을 잃으면 그대로 멈춘다.
    덧붙여, 이것이 없으면 옛 도구가 **옛 엔진 자리**로 내려간다 (progress.md 「옛 도구 엔진 찾기」).
    옛 저장소는 변화 0 이어야 하므로 가리켜 두는 것이 안전하기도 하다.
    """
    엔진 = _찾기("engine")
    if 엔진.is_dir():
        os.environ["VOC_ENGINE"] = str(엔진)
    else:
        print("  ! 엔진 폴더를 못 찾았습니다 (%s) — 칸 검수가 눈먼 길로 갈 수 있습니다" % 엔진)


def main() -> int:
    _엔진_가리키기()
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("판자리")
    p.add_argument("--조건", default="")
    p.add_argument("--확인만", action="store_true")
    p.add_argument("--되감기", default="")
    p.add_argument("--4차반영", dest="사차", action="store_true")
    a = p.parse_args()
    판 = Path(a.판자리).resolve()
    상태 = 상태읽기(판)
    조건 = _조건풀기(a.조건 or 상태.get("조건글", ""), 판)
    if a.조건:
        상태["조건글"] = a.조건
        상태["조건"] = 조건
        상태쓰기(판, 상태)
    elif 상태.get("조건"):
        조건 = 상태["조건"]

    if a.사차:
        return 사차반영(판, 상태, 조건)
    if a.되감기:
        # ★ 모르는 이름이면 **먼저 말한다**. 그 전에는 `.index()` 가 ValueError 로 터져
        #   무슨 이름을 써야 하는지 알 수 없었다 (2026-10-09).
        이름들 = [n for n, _ in 단계들]
        if a.되감기 not in 이름들:
            print("  ✗ --되감기 에 쓸 수 있는 단계 이름이 아닙니다: %s" % a.되감기)
            print("    쓸 수 있는 것 — %s" % " · ".join(이름들))
            return 2
        # ★ `4차반영` 처럼 **단계 목록에 없는 것**도 끝난단계에 들어온다 (사차반영이 적는다).
        #   목록에 없는 것은 자리를 셀 수 없으니 되감을 때 같이 지운다.
        벽 = 이름들.index(a.되감기)
        상태["끝난단계"] = [s for s in 상태.get("끝난단계", [])
                       if s in 이름들 and 이름들.index(s) < 벽]
        상태쓰기(판, 상태)
        print("  되감았습니다 — %s 부터 다시 합니다" % a.되감기)
    if not a.확인만 and not 조건["검색어"] and "1차" not in 상태.get("끝난단계", []):
        print("  ✗ --조건 이 필요합니다. 예: --조건 \"검색어=LG 로봇청소기; 영상=5; 댓글=50\"")
        print("    받는 칸은 1차 실행조건 원문(99_1차_실행조건_원문.md)에 있습니다.")
        return 2

    print("=" * 66)
    print("  한 줄 흐름 — %s" % 판)
    print("  조건: 검색어 「%s」 · 영상 %s · 댓글 %s · 이름 %s"
          % (조건["검색어"] or "(이어받음)", 조건["영상"], 조건["댓글"], 조건["이름"]))
    print("  판독자 %s · 감독자 %s"
          % (" · ".join("%s(%s)" % x for x in 판독자), " · ".join("%s(%s)" % x for x in 감독자)))
    끝난 = 상태.get("끝난단계", [])
    if 끝난:
        print("  이미 끝난 단계: %s — 다시 돌리지 않습니다" % " · ".join(끝난))
    print("=" * 66)

    for 이름, 하기 in 단계들:
        if 이름 in 끝난:
            continue
        print("\n── %s" % 이름)
        try:
            하기(판, 상태, 조건, a.확인만)
        except 멈춤 as e:
            print("\n  ✗ 여기서 멈췄습니다 — %s" % 이름)
            print("  %s" % e)
            print("\n  고친 뒤 **같은 명령을 그대로 다시** 넣으면 이 단계부터 이어갑니다.")
            상태쓰기(판, 상태)
            return 1
        if not a.확인만:
            상태["끝난단계"] = list(dict.fromkeys(상태.get("끝난단계", []) + [이름]))
            상태쓰기(판, 상태)
    if a.확인만:
        print("\n  (확인만 했습니다 — 아무것도 돌리지 않았고 돈도 쓰지 않았습니다)")
        return 0
    print("\n" + "=" * 66)
    print("  ★ 아웃풋 1 이 나왔습니다 — %s" % (판 / "아웃풋1_회의에서_정할것"))
    print("  회의에서 정한 뒤:  python %s \"%s\" --4차반영" % (Path(__file__).name, 판))
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
