# -*- coding: utf-8 -*-
"""스킬 시험(evals.json)을 실제 AI 로 돌리고 기계로 채점한다 — 섹션 4.

★ 돌리는 자리: **외딴 자리** `EVAL_ROOT/<누구>_<시험>_<번>/` (paths.py) — 한 번에 한 시험만.
  끝나면 기준 자리의 `스킬시험/` 으로 옮기고, 채점용 파일(시험.json · 입력해시 등)은 **그 뒤에** 쓴다.
  ★ 왜 (2026-09-21) — 시험 폴더가 한자리에 모여 있으니 AI 가 옆 시험의 채점 결과를 읽고 남의 스킬을
    가져다 썼다 (스킬 없는 비교 시험 5개 오염). 그래서 모든 시험에 「밖을 보지 않았다」 항목도 넣었다.
  그 아래 `작업/` 이 판독자의 작업 폴더다. AI 는 거기서 시작한다.
★ 누구
    claude       claude -p · 이 저장소의 plugin/ 을 --plugin-dir 로 싣는다
    codex        codex exec · 그릇/.agents/skills/ 에 스킬을, 그 옆에 shared · engine 을 둔다
                 (플러그인 모양 그대로 — 섹션 6 의 dist/codex 는 shared · engine 을 스킬 안에 넣는다. 둘 다 스크립트가 찾는다)
    claude-낱개 · codex-낱개   ★ **낱개 스킬 폴더 하나만** 준다 (sky 2026-10-07 염려) — `tools/build_skills.py` 로 묶은
                 그 폴더(공통 파일 · 엔진이 스킬 안에 들어 있다)를 claude 는 `작업/.claude/skills/<스킬>/` 에,
                 codex 는 `그릇/.agents/skills/<스킬>/` 에 둔다. 플러그인은 주지 않는다.
    claude-없이 · codex-없이   스킬 없이 같은 과제 (빈틈 재기)
★ **깨끗한 자리에서 돌린다** (2026-10-27 · 결정 0006) — `claude` 는 내 컴퓨터 설정(전역 CLAUDE.md ·
  훅 · 남의 스킬 · MCP)을 그대로 물려받는다. 그래서 `깨끗한깃발` 로 끄고 띄우고, 어떤 깃발로
  돌렸는지 `시험.json` 에 적는다. claude 를 띄우는 자리는 `claude_명령()` **한 곳**이다.
★ 채점은 evals.json 의 expectations 를 기계로 확인한 것이다. 못 본 것은 「못 봄」 이지 통과가 아니다.
★ 시험마다 볼 항목을 `기대항목` 에 못박아 둔다 (2026-09-21). 앞 단계가 없어 확인하지 못한 항목은
  「못 봄」 **실패**로 남는다 — 전에는 항목 자체가 안 만들어져 9/9 처럼 후하게 보였다.

쓰기
    python tests/evals/스킬시험_돌리기.py <누구> <시험id> [<번>]
    python tests/evals/스킬시험_돌리기.py 채점 <그릇 폴더>        돌리지 않고 채점만
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(_여기.parents[1] / "plugin" / "shared"))
sys.path.insert(0, str(_여기.parent / "baseline"))
from paths import BASELINE, EVAL_ROOT, PLUGIN, REPO  # noqa: E402
from 맞대기 import 맞대기  # noqa: E402

스킬 = PLUGIN / "skills" / "reading-voc-comments"
시험들 = {e["id"]: e for e in json.loads((스킬 / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}
차리기 = 스킬 / "scripts" / "판독폴더_차리기.py"

# ── 시험 여섯이 **다 같이** 보는 항목 — 한 자리에서 정한다 (공통 규칙 6) ───────────────
# ★ 2026-10-27 까지는 첫 줄 하나뿐이었고, 그것도 돌리개 여섯 곳에 **같은 글자로 박혀** 있었다.
공통항목 = ("작업 그릇 밖(기준 자리·저장소·다른 시험)을 보지 않았다",
        "우리 스킬 밖의 것을 쓰지 않았다 (남의 스킬·MCP·웹·서브에이전트)",
        "시험 자리가 깨끗했다 (내 훅·MCP·전역 규칙이 안 들어갔다)")

# 시험마다 반드시 채점해야 하는 항목 — 하나라도 빠지면 「못 봄」 실패로 채운다
기대항목 = {
    "빈폴더_엑셀없음": ["폴더를 차렸다", "판독을 시작하지 않았다", "데이터를 지어내지 않았다",
                  "엑셀을 달라고 했다", "도구·기준을 고치지 않았다 (지문검사)"],
    "엑셀_준비만": ["폴더를 차렸다", "판독을 시작하지 않았다", "행 수를 알렸다", "데이터가 한 벌이다",
                "데이터가 도구 결과와 같다", "회차배치가 도구 결과와 같다",
                "도구·기준을 고치지 않았다 (지문검사)"],
    "한회차_끝까지": ["폴더를 차렸다", "판정 파일이 있다 (claudecode|Codex)", "시작·종료 시각이 다르다",
                 "check_submission 통과", "성실성검사 반려 없음", "최종 번들이 있다",
                 "check_selfcheck ✗ 0건", "보정요청서가 있다", "도구·기준을 고치지 않았다 (지문검사)"],
}
for _목록 in 기대항목.values():
    _목록.extend(공통항목)


def 격리_준비(그릇이름: str) -> tuple[Path, Path]:
    """외딴 자리에 새 그릇을 만든다. 외딴 자리에 다른 것이 있으면 멈춘다 (옆 시험이 보이면 안 된다)."""
    최종 = BASELINE / "스킬시험" / 그릇이름
    if 최종.exists():
        raise SystemExit("이미 있습니다 — %s" % 최종)
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    남은것 = [p.name for p in EVAL_ROOT.iterdir()]
    if 남은것:
        raise SystemExit("외딴 자리가 비어 있지 않습니다 — %s : %s (옆 시험이 보이면 안 된다)" % (EVAL_ROOT, 남은것[:5]))
    그릇 = EVAL_ROOT / 그릇이름
    (그릇 / "작업").mkdir(parents=True)
    return 그릇, 최종


def 격리_마치기(그릇: Path, 최종: Path, r, 정보: dict) -> Path:
    """AI 가 끝나면 결과를 기준 자리로 옮기고, 그다음에 채점용 파일을 쓴다."""
    (그릇 / "대화.jsonl").write_text(r.stdout, encoding="utf-8")
    (그릇 / "stderr.txt").write_text(r.stderr, encoding="utf-8")
    최종.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(그릇), str(최종))
    # ★ 어떤 깃발로 돌렸는지 **그릇 자신이** 말하게 적는다 (2026-10-27 · `claude_명령`).
    정보 = dict(정보, 종료코드=r.returncode, 돌린자리=str(그릇), 깃발=list(돌린깃발))
    (최종 / "시험.json").write_text(json.dumps(정보, ensure_ascii=False), encoding="utf-8")
    return 최종


_경로칸 = ("command", "file_path", "path", "notebook_path", "url", "pattern")


def _명령들(그릇: Path) -> list[str]:
    """AI 가 돌린 명령 · 연 경로. Claude 도구 입력은 명령·경로 칸만 본다 (파일에 쓴 글 내용은 경로가 아니다)."""
    명령 = []
    for l in (그릇 / "대화.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            for c in e["message"]["content"]:
                if c["type"] == "tool_use":
                    입력 = c.get("input") or {}
                    명령.append(" ".join(str(입력[k]) for k in _경로칸 if k in 입력))
        it = e.get("item") or {}
        if e.get("type") == "item.completed" and it.get("type") == "command_execution":
            명령.append(it.get("command") or "")
    return 명령


def 밖을_봤나(그릇: Path) -> tuple[bool, str]:
    """AI 의 명령이 **허용한 자리 밖**의 절대경로를 가리켰나 · 채점용 파일을 건드렸나.

    ★ 허용 목록 방식이다 (2026-09-21). 처음엔 금지 목록(기준 자리 · 저장소)으로 했더니,
      스킬 없는 Claude 가 이 저장소(Git Bash 꼴 경로)와 옛 저장소를 뒤져
      감독 폴더를 재구성한 것을 놓쳤다 — 금지 목록에 없는 자리였고, `/c/…` 꼴을 못 읽었다.
      그래서 허용한 자리만 통과시키고 나머지 절대경로는 모두 건다.
    허용 — 자기 그릇(돌린 자리) · 플러그인 · 파이썬/도구 설치 자리 · Windows · AI 자기 임시 폴더
    """
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    자기 = str(정보.get("돌린자리") or 그릇).replace("/", "\\").lower()
    집 = str(Path.home()).lower()
    # ★ 공통 작업규칙 자리를 **면제할지**는 그 규칙을 **줬느냐**에 달렸다 (2026-10-27).
    #   깨끗한 깃발로 돌리면 아이에게 그 규칙을 주지 않는다 — 그런데도 그 자리를 열었다면
    #   그것은 **밖을 본 것**이다. 깃발 없이 돌린 옛 그릇에서는 지시의 출처였다 (아래 주석).
    규칙자리_면제 = any(x for x in 깨끗한깃발 if x and x not in (정보.get("깃발") or []))
    # 시스템 자리는 윈도 환경변수에서 — 절대경로를 코드에 박지 않는다 (paths.py 규칙)
    시스템 = [os.environ.get(k, "").lower() for k in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")]
    허용 = [자기, str(PLUGIN).lower(), *[x for x in 시스템 if x], 집 + "\\.claude",
          집 + "\\appdata\\local\\python", 집 + "\\appdata\\local\\programs\\python",
          집 + "\\appdata\\roaming\\npm", 집 + "\\appdata\\roaming\\python", 집 + "\\.cache\\codex-runtimes",
          집 + "\\appdata\\local\\temp\\claude\\", 집 + "\\.codex", 집 + "\\appdata\\local\\microsoft\\windowsapps"]
    걸림 = []
    for c in _명령들(그릇):
        c2 = re.sub(r"\\+", r"\\", c.replace("/", "\\")).lower()    # Codex 명령의 \\ 두 개도 하나로
        # ★ 2026-10-26 거짓 반려를 고쳤다 — 이 바꿈이 **정규식까지 경로로 바꿔** 놓았다.
        #   AI 가 자기 그릇에 쓴 Node 스크립트의 `/<script[^>]*>([\s\S]*?)<\/script>/g` 가
        #   소문자화 뒤 `[\s\s]` 가 되고, 이 바꿈이 `\s\` 를 `s:\` 로 만들어
        #   `「s: 뒤에 역슬래시가 붙은 가짜 경로」` 라는 가짜 경로가 생겼다 (대시보드 시험 5회차 실측).
        #   실제 Git Bash 경로는 `[` 뒤에 오지 않는다. 그래서 그 앞자리를 뺀다.
        c2 = re.sub(r"(?<![\[^\w:])\\([a-z])\\", lambda m: m.group(1) + ":\\", c2)    # Git Bash 꼴(/드라이브/…) 을 드라이브 꼴로 바꾼다
        # ★ 2026-10-26 — 드라이브 글자 앞에 **백슬래시가 오면 경로가 아니다.**
        #   AI 가 자기 그릇에 heredoc 으로 써 넣은 스크립트 안의 정규식 조각(\s 꼴)이
        #   `「s: 뒤에 역슬래시가 붙은 가짜 경로」` 로 잡혀 「밖을 봤다」 가 됐다 (대시보드 시험 5회차 실측 · 거짓 반려).
        #   실제 윈도 절대경로의 드라이브 글자는 백슬래시 바로 뒤에 오지 않는다.
        for m in re.finditer(r"(?<![a-z0-9가-힣_\\])[a-z]:\\[^'\"\s|;,)*]*", c2):
            경로 = m.group(0).rstrip("\\.")
            if not 경로 or len(경로) <= 3 or re.fullmatch(r"[a-z]:\\n[#\-]*", 경로):
                continue                                           # 글 속 「x:」 + 줄바꿈 표기 — 경로가 아니다
            # 띄어쓰기에서 잘린 경로(program files → program)도 허용 자리의 앞머리면 통과
            if any(경로.startswith(h.rstrip("\\")) or (len(경로) >= 8 and h.startswith(경로)) for h in 허용):
                continue
            # ★ 공통 작업규칙 자리는 **지시의 출처**다 — 분석 자료를 뒤진 것이 아니다 (2026-10-20).
            #   전역 CLAUDE.md 가 「손대지말것_전역.txt 를 보라」 고 적어 두었고, AI 는 그 규칙을 따른다.
            #   실측 — 대시보드 시험 둘이 `cat …/_공통_작업규칙/손대지말것_전역.txt` 로 걸렸다.
            #   받는 사람 컴퓨터엔 그 규칙이 없으니 거기선 일어나지 않는다.
            #   ★ 폴더 **이름**으로 거른다 — 절대경로를 코드에 박지 않는다 (paths.py 규칙).
            #   ★ 2026-10-27 — 이 면제는 **그 규칙을 준 시험에서만** 산다 (`규칙자리_면제`).
            if 규칙자리_면제 and "_공통_작업규칙" in 경로:
                continue
            걸림.append(경로[:100])
        if re.search(r"채점\.json|입력해시\.json|(?<![\w가-힣])시험\.json", c2):
            걸림.append("채점용 파일")
        # ★ 상대경로로 위로 오르는 것(../..)은 보지 않는다 (2026-09-21) — 지금 폴더를 모르면 판단할 수 없다.
        #   총괄은 판 폴더가 작업 폴더보다 두 겹 깊어 ../.. 가 자기 그릇 안이었다 (거짓 경보).
        #   ★ 남은 구멍: 상대경로로 드라이브 맨 위까지 올라가 옆 폴더를 여는 것은 못 잡는다.
        #     외딴 자리 덕에 올라가도 보이는 것은 자기 그릇뿐이고, 옆 자리는 대개 절대경로로 열어 위에서 걸린다.
    return (not 걸림), "; ".join(sorted(set(걸림))[:3])


# ── 아이가 **무엇을 물려받았나** — 시험 자리가 깨끗한가 ───────────────────────────────
# ★ 왜 (sky 2026-10-27) — 「지금 여기서는 순수하게 skill 만으로 돌아가는지 모르지 않나요?」
#   몰랐다. 그래서 쟀다. claude 시험은 **내 컴퓨터 설정을 그대로 물려받아** 돌고 있었다 —
#     · 전역 CLAUDE.md(공통 작업규칙)가 들어가 있었다. 아이에게 물으니
#       「예비로 남긴 옛 저장소는 변화 0」 · 「축약 금지」 ·
#       「변경마다 먼저 세 줄을 적는다 — 건드림 / 안 건드림 / 확인할 것」 을
#       **문장째로 옮겨 적었다.** 자기 보고가 아니라 내용으로 댄 것이다.
#     · 내 훅이 돌았다 — 모든 claude 기록의 **첫 사건이 `SessionStart` 훅**이다.
#     · 보인 것이 스킬 50개(우리 것 6 + 남의 것 44) · 슬래시 87개 · 플러그인 3개 · 한때 MCP 2개.
#   받는 사람 컴퓨터엔 그 규칙도 훅도 없다. 그러니 그 시험은 **받는 사람 자리보다 후했다.**
#   ※ 쓴 것은 깨끗했다 — 73그릇 전량에서 남의 스킬·MCP·웹·서브에이전트 호출이 0이었다.
#     보인 것과 쓴 것은 다르다. 그래서 아래 둘로 **갈라** 본다.
#   ※ codex 쪽은 이미 깨끗했다 — `~/.codex/AGENTS.md` 가 0바이트이고, 25그릇에서 쓴 것이
#     셸 · 메시지 · 파일바꿈 · 할일 네 가지뿐이었다 (2026-10-27 확인).
#
# ★ 깃발 셋을 **한 턴씩 실제로 돌려** 재 봤다 (2026-10-27) —
#     (그대로)                                    스킬 50 · 훅 돌았다 · 전역 규칙 들어갔다
#     --safe-mode                                 **우리 스킬이 0개** 가 된다 — 쓸 수 없다
#     --setting-sources "" --strict-mcp-config    스킬 27(우리 6 그대로) · 훅 0 · MCP 0 ·
#                                                 전역 규칙을 물으니 「없음」
#   그래서 셋째를 쓴다. 남는 21개는 Claude Code 에 **원래 들어 있는** 스킬이라
#   받는 사람 컴퓨터에도 똑같이 있다 — 뺄 수 없고, 뺄 이유도 없다.
깨끗한깃발 = ("--setting-sources", "", "--strict-mcp-config")
우리스킬머리 = "youtube-voc:"

# ★ claude 를 띄우는 자리는 **여기 한 곳**이다 (공통 규칙 6). 2026-10-27 까지는 돌리개
#   여섯 곳에 같은 줄이 박혀 있었다 — 깃발 하나를 더하려면 여섯 곳을 고쳐야 했다.
#   짠 깃발은 `시험.json` 에 적는다. 그래야 **그릇 자신이** 어떻게 돌았는지 말한다.
#   ※ 한 번에 한 시험만 돌린다(이 파일 머리말) — 그래서 모듈에 하나 두어도 섞이지 않는다.
돌린깃발: list[str] = []


def claude_명령(누구: str, *, 깨끗: bool = True) -> list[str]:
    명령 = [shutil.which("claude"), "-p", "--output-format", "stream-json", "--verbose",
          "--dangerously-skip-permissions"]
    if 깨끗:
        명령 += list(깨끗한깃발)
    if 누구 == "claude":
        명령 += ["--plugin-dir", str(PLUGIN)]
    돌린깃발[:] = 명령[1:]
    return 명령


def 쓴것_기록에서(길: Path) -> list[tuple[str, str, dict]]:
    """기록 파일 하나에서 **쓴** 것을 뽑는다 — 한 줄 흐름의 `기록/*.jsonl` 도 이 꼴이다.

    ★ 시험 그릇이 아니라 **기록 파일**을 받는다. 그래야 실제 흐름(`tools/시험환경_보기.py --판`)도
      같은 눈으로 볼 수 있다 — 재는 자리를 두 벌로 만들지 않는다 (공통 규칙 6).
    """
    낸것 = []
    if not 길.is_file():
        return 낸것
    for l in 길.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use":
                    낸것.append(("claude", c.get("name") or "", c.get("input") or {}))
        it = e.get("item") or {}
        if e.get("type") == "item.completed":
            낸것.append(("codex", it.get("type") or "", {}))
    return 낸것


def _쓴것(그릇: Path) -> list[tuple[str, str, dict]]:
    return 쓴것_기록에서(그릇 / "대화.jsonl")


# codex 가 쓰는 것 — 2026-10-27 에 25그릇 전량에서 나온 네 가지 + 오류 (플러그인·MCP 는 없었다)
_코덱스쓰는것 = ("command_execution", "agent_message", "reasoning", "todo_list", "file_change", "error")


def 밖의것을_썼나(그릇: Path) -> tuple[bool, str]:
    """우리 스킬 **밖의** 것을 실제로 **썼나** — 남의 스킬 · MCP · 웹 · 서브에이전트.

    ★ 보인 것과 쓴 것은 다르다. 여기서는 **쓴 것**만 본다 (보인 것은 `자리가_깨끗했나`).
    """
    걸림 = []
    for 쪽, 이름, 입 in _쓴것(그릇):
        if 쪽 == "codex":
            if 이름 and 이름 not in _코덱스쓰는것:
                걸림.append("codex 가 쓴 낯선 것 — %s" % 이름)
            continue
        if 이름.startswith("mcp__"):
            걸림.append("MCP 도구 — %s" % 이름)
        elif 이름 in ("Task", "WebFetch", "WebSearch", "Artifact"):
            걸림.append(이름)
        elif 이름 == "Skill":
            s = str(입.get("skill") or "?")
            if not s.startswith(우리스킬머리):
                걸림.append("남의 스킬 — %s" % s)
    return (not 걸림), "; ".join(sorted(set(걸림))[:3])


def 본것_기록에서(길: Path) -> dict:
    """기록 파일 하나의 첫 `init` 사건에서 **아이에게 보였던 것**을 뽑는다 (claude 만 이 사건을 낸다).

    ★ 「못 찾음」 을 「없음」 으로 돌려주지 않는다 — `확인됨` 이 False 면 채점은 **실패**다.
    ★ 기록 파일을 받는다 — 한 줄 흐름의 `기록/*.jsonl` 도 같은 꼴이라 같은 눈으로 본다.
    """
    낸것 = {"확인됨": False, "훅돌았나": False, "스킬수": None, "우리스킬": [], "남의스킬": [],
          "MCP": [], "플러그인": [], "모델": "", "깃발": [], "누구": ""}
    if not 길.is_file():
        return 낸것
    for l in 길.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("hook_name"):
            낸것["훅돌았나"] = True
        if e.get("subtype") == "init" and not 낸것["확인됨"]:
            스 = [str(x) for x in (e.get("skills") or [])]
            낸것.update(확인됨=True, 스킬수=len(스), 모델=str(e.get("model") or ""),
                     우리스킬=[s for s in 스 if s.startswith(우리스킬머리)],
                     남의스킬=[s for s in 스 if not s.startswith(우리스킬머리)],
                     MCP=[str(m.get("name")) for m in (e.get("mcp_servers") or [])],
                     플러그인=[str(p.get("name")) for p in (e.get("plugins") or [])])
    return 낸것


def 아이가_본것(그릇: Path) -> dict:
    """시험 그릇 하나 — 기록에서 본 것 + `시험.json` 의 「누가 · 어떤 깃발로」."""
    낸것 = 본것_기록에서(그릇 / "대화.jsonl")
    시 = 그릇 / "시험.json"
    if 시.is_file():
        정보 = json.loads(시.read_text(encoding="utf-8")) or {}
        낸것["깃발"] = list(정보.get("깃발") or [])
        낸것["누구"] = str(정보.get("누구") or "")
    return 낸것


def 자리가_깨끗했나(그릇: Path) -> tuple[bool, str]:
    """내 컴퓨터 설정(훅 · MCP · 전역 CLAUDE.md)이 **안 들어갔나.**

    ★ codex 는 `init` 사건을 내지 않는다. 대신 codex 쪽은 물려받을 글이 없다
      (`~/.codex/AGENTS.md` 0바이트 · 2026-10-27 확인) — 그래서 codex 는 **쓴 것**으로만 본다.
    """
    본것 = 아이가_본것(그릇)
    누구 = 본것["누구"]
    if not 누구:
        return False, "누가 돌렸는지 시험.json 에 적혀 있지 않다 — 못 봄은 통과가 아니다"
    if not 누구.startswith("claude"):
        return True, "codex — 물려받을 글이 없다 (AGENTS.md 0바이트)"
    흠 = []
    if not 본것["확인됨"]:
        흠.append("무엇이 보였는지 확인할 수 없다 (init 사건이 없다)")
    if 본것["훅돌았나"]:
        흠.append("내 훅이 돌았다 (SessionStart 등)")
    if 본것["MCP"]:
        흠.append("MCP 가 붙어 있었다 — %s" % ", ".join(본것["MCP"]))
    빠진 = [x for x in 깨끗한깃발 if x and x not in 본것["깃발"]]
    if 빠진:
        흠.append("깨끗한 깃발 없이 돌렸다 (없는 것 — %s)" % " ".join(빠진))
    if not 본것["우리스킬"] and 누구 == "claude":
        흠.append("우리 스킬이 아이에게 **안 보였다** — 플러그인이 안 실렸다")
    return (not 흠), "; ".join(흠[:3])


def 공통채점(그릇: Path, 봄) -> None:
    """시험 여섯이 **다 같이** 보는 항목 — 한 자리에서 본다 (공통 규칙 6)."""
    for 이름, 보기 in zip(공통항목, (밖을_봤나, 밖의것을_썼나, 자리가_깨끗했나)):
        됨, 까닭 = 보기(그릇)
        봄(이름, 됨, 까닭)


def _env(뿌리: Path | None = None) -> dict:
    e = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    if 뿌리 is not None:
        e["VOC_ENGINE"] = str(뿌리 / "engine")
    return e


# ★ Codex 는 내장 파이썬을 먼저 잡게 한다 (2026-09-21).
#   Codex 샌드박스 안에서는 사용자 파이썬(AppData)의 pandas 가 **이름만 보이고 내용이 안 읽혀**
#   자가점검이 「pandas 를 못 씁니다」 로 막혔다 (감독 시험 두 번). 판독 시험이 통과한 것은
#   Codex 가 우연히 내장 파이썬을 골랐기 때문이다. 내장 파이썬에는 pandas · openpyxl 이 있다
#   (yaml 은 없다 — 자가점검에서 「없어도 된다」 항목). 시험 실행에만 쓰고 사용자 설정은 안 건드린다.
#   ※ `-c sandbox_permissions=["disk-full-read-access"]` 는 이 판(0.146)에서 효과가 없었다.
_codex파이썬 = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python"


def _codex_env() -> dict:
    e = _env()
    if _codex파이썬.is_dir():
        e["PATH"] = str(_codex파이썬) + os.pathsep + str(_codex파이썬 / "Scripts") + os.pathsep + e.get("PATH", "")
    return e


def _낱개폴더(스킬이름: str) -> Path:
    """`tools/build_skills.py` 로 낱개 스킬을 묶어 그 폴더를 돌려준다 (저장소 밖 임시 자리에).

    ★ 왜 — AI 에게 **스킬 폴더 하나만** 줘도 되는지 보려면, 플러그인이 보이지 않는 자리에서 돌려야 한다.
    """
    import tempfile
    sys.path.insert(0, str(REPO / "tools"))
    import build_skills                                  # noqa: PLC0415
    d = Path(tempfile.mkdtemp(prefix="voc_낱개_"))
    코드 = build_skills.만들기(d)
    if 코드:
        raise RuntimeError("낱개 묶기 실패 — build_skills.py")
    return d / "codex" / ".agents" / "skills" / 스킬이름


def 돌리기(누구: str, 시험id: str, 번: int) -> Path:
    시험 = 시험들[시험id]
    그릇, 최종 = 격리_준비("%s_%s_%d" % (누구, 시험id, 번))
    작업 = 그릇 / "작업"
    for f in 시험["files"]:
        shutil.copyfile(BASELINE / f, 작업 / Path(f).name)
    if 누구.startswith("claude"):
        # ★ 프롬프트는 표준입력으로 — 윈도에서 claude 는 .cmd 라 인자로 주면 한글이 깨질 수 있다
        명령 = claude_명령(누구)
        if 누구 == "claude-낱개":
            # ★ 낱개 스킬 폴더 하나만 — Claude Code 는 작업 폴더의 .claude/skills/ 를 읽는다
            shutil.copytree(_낱개폴더(스킬.name), 작업 / ".claude" / "skills" / 스킬.name)
        r = subprocess.run(명령, input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=_env(), timeout=3600)
    else:
        if 누구 == "codex-낱개":
            shutil.copytree(_낱개폴더(스킬.name), 그릇 / ".agents" / "skills" / 스킬.name)
        if 누구 == "codex":
            d = 그릇 / ".agents"
            shutil.copytree(스킬, d / "skills" / 스킬.name)
            shutil.copytree(PLUGIN / "shared", d / "shared")
            shutil.copytree(PLUGIN / "engine", d / "engine")
        subprocess.run(["git", "init", "-q"], cwd=그릇)
        r = subprocess.run([shutil.which("codex"), "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "-"],
                           input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=_codex_env(), timeout=3600)
    return 격리_마치기(그릇, 최종, r, {"누구": 누구, "시험": 시험id})


def _마지막답(그릇: Path) -> str:
    말 = []
    for 줄 in (그릇 / "대화.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(줄)
        except ValueError:
            continue
        if e.get("type") == "result" and isinstance(e.get("result"), str):   # claude
            말.append(e["result"])
        it = e.get("item") or {}
        if e.get("type") == "item.completed" and it.get("type") == "agent_message":   # codex
            말.append(it.get("text") or "")
    return 말[-1] if 말 else ""


def _돌려보기(작업: Path, *인자) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", *인자], cwd=작업, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=_env(작업))
    return r.returncode, r.stdout + r.stderr


def _지문(작업: Path) -> tuple[bool, str]:
    if not (작업 / "대장" / "지문.json").is_file():
        return False, "지문 파일이 없다"
    if (작업 / "대장" / "지문_이력.json").exists():
        return False, "지문을 다시 떴다 (--만들기)"
    k, 말 = _돌려보기(작업, "스크립트/지문검사.py")
    return k == 0, "종료코드 %d" % k


def 채점(그릇: Path) -> dict:
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    작업, 답 = 그릇 / "작업", _마지막답(그릇)
    결과 = []

    def 봄(이름, 됨, 까닭=""):
        결과.append({"항목": 이름, "통과": bool(됨), "까닭": 까닭})

    판정 = sorted((작업 / "_판독패키지" / "_결과").glob("판독결과_full_*.md")) if (작업 / "_판독패키지").is_dir() else []
    데이터 = sorted((작업 / "판독대상").glob("*/voc_secondary_dataset.csv")) if (작업 / "판독대상").is_dir() else []
    시험 = 정보["시험"]
    봄("폴더를 차렸다", all((작업 / x).exists() for x in ("스크립트/자가점검.py", "판독대상", "프롬프트")))
    if 시험 == "빈폴더_엑셀없음":
        봄("판독을 시작하지 않았다", not 판정, "판정 파일 %d개" % len(판정))
        봄("데이터를 지어내지 않았다", not 데이터, "데이터 %d개" % len(데이터))
        봄("엑셀을 달라고 했다", "엑셀" in 답)
    if 시험 == "엑셀_준비만":
        봄("판독을 시작하지 않았다", not 판정, "판정 파일 %d개" % len(판정))
        봄("행 수를 알렸다", re.search(r"(?<!\d)11(?!\d)\s*행", 답) is not None)
        기대 = 그릇 / "기대값"
        if not 기대.exists():
            subprocess.run([sys.executable, "-B", str(차리기), str(기대)], env=_env(), capture_output=True)
            x = next(작업.glob("*.xlsx"), None)
            shutil.copyfile(x, 기대 / x.name)
            _돌려보기(기대, "스크립트/데이터_넣기.py", x.name, "--이름", "기대")
        봄("데이터가 한 벌이다", len(데이터) == 1, "데이터 %d개" % len(데이터))
        if len(데이터) == 1:
            a = (기대 / "판독대상" / "기대" / "voc_secondary_dataset.csv").read_bytes()
            봄("데이터가 도구 결과와 같다", 데이터[0].read_bytes() == a)
            다름 = 맞대기(기대 / "회차배치", 작업 / "회차배치")
            봄("회차배치가 도구 결과와 같다", not 다름, "; ".join(다름[:3]))
    if 시험 == "한회차_끝까지":
        f = [p for p in 판정 if re.search(r"_full_01_(claudecode|Codex)\.md$", p.name)]
        봄("판정 파일이 있다 (claudecode|Codex)", len(f) == 1, ", ".join(p.name for p in 판정))
        if f:
            f = f[0]
            글 = f.read_text(encoding="utf-8", errors="replace")
            시각 = re.findall(r"(시작|종료)\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9:]+)", 글)
            d = dict(시각)
            봄("시작·종료 시각이 다르다", "시작" in d and "종료" in d and d["시작"] != d["종료"], str(d))
            rel = f.relative_to(작업).as_posix()
            k, 말 = _돌려보기(작업, "스크립트/check_submission.py", rel)
            봄("check_submission 통과", k == 0, 말.strip().splitlines()[-1] if 말.strip() else "")
            k, 말 = _돌려보기(작업, "스크립트/성실성검사.py", rel)
            봄("성실성검사 반려 없음", k == 0, 말.strip().splitlines()[-1] if 말.strip() else "")
            이름 = f.stem.rsplit("_", 1)[-1]
            번들 = 작업 / "_판독패키지" / "_결과" / ("%s_bundle" % 이름)
            봄("최종 번들이 있다", (번들 / "raw_voc.csv").is_file())
            if 번들.is_dir():
                k, 말 = _돌려보기(작업, "스크립트/check_selfcheck.py", 번들.relative_to(작업).as_posix())
                봄("check_selfcheck ✗ 0건", k == 0, [x for x in 말.splitlines() if "✗" in x][-1:] and
                   [x for x in 말.splitlines() if "✗" in x][-1].strip() or "")
        봄("보정요청서가 있다", (작업 / "_인계" / "보정요청.csv").is_file())
    됨, 까닭 = _지문(작업) if (작업 / "스크립트").is_dir() else (False, "폴더가 없다")
    봄("도구·기준을 고치지 않았다 (지문검사)", 됨, 까닭)
    공통채점(그릇, 봄)
    본것 = {x["항목"] for x in 결과}
    for 이름 in 기대항목[시험]:
        if 이름 not in 본것:
            결과.append({"항목": 이름, "통과": False, "까닭": "못 봄 — 앞 단계가 없어 확인하지 못했다"})
    결과.sort(key=lambda x: 기대항목[시험].index(x["항목"]) if x["항목"] in 기대항목[시험] else 99)
    점 = {"누구": 정보["누구"], "시험": 시험, "AI종료코드": 정보["종료코드"],
         "통과": sum(x["통과"] for x in 결과), "전체": len(결과), "항목": 결과, "마지막답_앞부분": 답[:300]}
    (그릇 / "채점.json").write_text(json.dumps(점, ensure_ascii=False, indent=1), encoding="utf-8")
    return 점


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "채점":
        점 = 채점(Path(sys.argv[2]))
    else:
        점 = 채점(돌리기(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1))
    print("  %s · %s — %d/%d" % (점["누구"], 점["시험"], 점["통과"], 점["전체"]))
    for x in 점["항목"]:
        print("     %s %s  %s" % ("○" if x["통과"] else "✗", x["항목"], x["까닭"]))
    return 0 if 점["통과"] == 점["전체"] else 1


if __name__ == "__main__":
    sys.exit(main())
