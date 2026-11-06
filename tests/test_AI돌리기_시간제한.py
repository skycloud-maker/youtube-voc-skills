# -*- coding: utf-8 -*-
"""판독자·감독자 한 창이 시간 제한을 넘겼을 때 **터지지 않고, 기록을 잃지 않고, 끝까지 끄는가** (2026-11-07).

★ 왜 이 시험이 있나 — 2026-10-30 큰 판 다섯째 바퀴에서 실제로 일어났다.
  `AI돌리기` 는 `subprocess.run(..., capture_output=True, timeout=240분)` 이었다.
  ① 240분을 넘기면 `TimeoutExpired` 가 **그대로 터져** 실무자에게 traceback 이 보였다.
  ② 기록은 다 끝난 **뒤에** 한꺼번에 썼으므로, 터진 바퀴의 AI 기록(비용)이 **아예 안 남았다.**
  ③ 터진 것은 240분이 아니라 **332분**이었다. Windows 에서 `claude` 는 `.cmd` 라서
     파이썬이 죽이는 것은 `cmd.exe` 하나뿐이고, 그 밑에서 도는 진짜 프로그램은 살아남아
     출력 관을 쥔 채 제 일이 끝날 때까지 갔다 — 제한이 **사실상 없었다.**

★ 그래서 재는 것은 셋이다 — 가짜 판독자(`.cmd` 밑에서 도는 파이썬)가 한 줄 쓰고 오래 잔다.
  · 제한을 넘기면 **예외 없이** 종료코드 `시간넘김` 과 알림말을 돌려주는가
  · 넘기기 **전에 쓴 줄이 기록 파일에 남아 있는가**
  · `.cmd` 밑의 **손자 프로세스까지 꺼졌는가** (그래서 제한 가까이에서 돌아오는가)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared" / "tools"))
sys.path.insert(0, str(_뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))
총괄 = pytest.importorskip("한줄_돌리기", reason="총괄 스크립트를 못 읽었다")

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="가짜 명령을 .cmd 로 만든다")

_가짜 = r'''
import json, os, sys, time
from pathlib import Path
잠 = float(sys.argv[1])
받은말 = sys.stdin.read()
여기 = Path(os.environ["FAKE_DIR"])
(여기 / "pid.txt").write_text(str(os.getpid()), encoding="utf-8")
(여기 / "받은말.txt").write_text(받은말, encoding="utf-8")
print(json.dumps({"type": "result", "result": "첫 회차 했습니다"}, ensure_ascii=False), flush=True)
print("잘 갑니다", file=sys.stderr, flush=True)
time.sleep(잠)
print(json.dumps({"type": "result", "result": "다 했습니다"}, ensure_ascii=False), flush=True)
(여기 / "끝까지_갔다.txt").write_text("x", encoding="utf-8")
'''


def _가짜차리기(자리: Path, monkeypatch, 잠: float) -> Path:
    (자리 / "fake.py").write_text(_가짜, encoding="utf-8")
    (자리 / "claude.cmd").write_text(
        '@"%s" "%s" %s\r\n' % (sys.executable, 자리 / "fake.py", 잠), encoding="ascii")
    monkeypatch.setenv("PATH", str(자리) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FAKE_DIR", str(자리))
    return 자리


def _살아있나(pid: int) -> bool:
    r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
                       capture_output=True, text=True, errors="replace")
    return str(pid) in r.stdout


def test_제때_끝나면_전처럼_답과_기록을_돌려준다(tmp_path_factory, monkeypatch):
    자리 = _가짜차리기(tmp_path_factory.mktemp("fakebin"), monkeypatch, 잠=0)
    작업 = tmp_path_factory.mktemp("work")
    기록 = tmp_path_factory.mktemp("log") / "판독A.jsonl"

    코드, 답 = 총괄.AI돌리기("claude", 작업, "판독해 주세요 한글", 기록, 분=1)

    assert 코드 == 0, 코드
    assert 답 == "다 했습니다", 답
    assert (자리 / "받은말.txt").read_text(encoding="utf-8") == "판독해 주세요 한글", "프롬프트가 안 갔다"
    글 = 기록.read_text(encoding="utf-8")
    assert "첫 회차 했습니다" in 글 and "다 했습니다" in 글, 글
    assert "잘 갑니다" in 기록.with_suffix(".stderr.txt").read_text(encoding="utf-8")


def test_제한을_넘기면_터지지_않고_기록을_남기고_손자까지_끈다(tmp_path_factory, monkeypatch):
    자리 = _가짜차리기(tmp_path_factory.mktemp("fakebin"), monkeypatch, 잠=60)
    작업 = tmp_path_factory.mktemp("work")
    기록 = tmp_path_factory.mktemp("log") / "판독A.jsonl"

    처음 = time.monotonic()
    코드, 답 = 총괄.AI돌리기("claude", 작업, "판독해 주세요", 기록, 분=0.05)   # 3초
    걸린 = time.monotonic() - 처음

    assert 코드 == 총괄.시간넘김, "제한을 넘겼는데 종료코드가 %r 이다" % 코드
    assert "시간 제한" in 답, "알림말에 무슨 일인지가 없다 — %r" % 답
    assert 걸린 < 30, ("제한(3초)을 넘기고도 %.0f초 걸렸다 — .cmd 밑의 진짜 프로그램이 "
                     "안 꺼져서 끝날 때까지 기다린 것이다 (2026-10-30 의 332분)" % 걸린)
    글 = 기록.read_text(encoding="utf-8")
    assert "첫 회차 했습니다" in 글, "넘기기 전에 쓴 줄이 기록에 없다 — 비용 기록을 잃는다:\n%r" % 글
    pid = int((자리 / "pid.txt").read_text(encoding="utf-8"))
    assert not _살아있나(pid), "손자 프로세스(pid %d)가 아직 돈다 — 돈을 계속 쓴다" % pid
    assert not (자리 / "끝까지_갔다.txt").exists()


def test_돌리개_한줄로_타면_traceback_대신_멈춤으로_알리고_상태를_지킨다(tmp_path_factory, monkeypatch, capsys):
    """판독 단계에서 제한을 넘기면 — 사람에게 보이는 것은 「여기서 멈췄습니다」 와 까닭이다."""
    import json
    _가짜차리기(tmp_path_factory.mktemp("fakebin"), monkeypatch, 잠=60)
    monkeypatch.setattr(총괄.AI돌리기, "__defaults__", (0.05,))          # 240분 → 3초
    판 = tmp_path_factory.mktemp("pan")
    (판 / "상태.json").write_text(json.dumps(
        {"끝난단계": ["1차", "2차준비"], "소견": [], "승인": True,
         "조건": {"검색어": "시험", "영상": "1", "댓글": "5", "이름": "시험판"}},
        ensure_ascii=False), encoding="utf-8")
    (판 / "판독A").mkdir()
    (판 / "판독B").mkdir()
    monkeypatch.setattr(sys, "argv", ["한줄_돌리기.py", str(판)])

    코드 = 총괄.main()                     # 예외가 새면 여기서 시험이 터진다
    말 = capsys.readouterr().out

    assert 코드 == 1, 코드
    assert "여기서 멈췄습니다" in 말 and "시간 제한" in 말, 말[-1500:]
    assert "Traceback" not in 말
    상태 = json.loads((판 / "상태.json").read_text(encoding="utf-8"))
    assert "2차판독" not in 상태["끝난단계"] and 상태.get("승인") is True, 상태
    assert "첫 회차 했습니다" in (판 / "기록" / "판독A.jsonl").read_text(encoding="utf-8")
