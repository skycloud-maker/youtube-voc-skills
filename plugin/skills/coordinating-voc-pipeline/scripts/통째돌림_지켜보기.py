# -*- coding: utf-8 -*-
"""오래 걸리는 판을 **지켜보며 이어 돌린다** — 진행이 멈추면 **멈춘다** (2026-10-30).

★ 왜 이 도구가 있나 — 2026-10-30 에 2판 통째 재현을 돌려 보고 알았다.

  판독자(claude)가 **스스로 넘긴다.** 53회차 중 **10회차**를 하고
  「full_10 까지 했습니다. 새 창에서 이어가 주십시오.」 로 끝냈다 (139분 · 종료 0).
  돌리개는 **최종 번들이 없으면** 그 단계에서 멈추므로(그게 맞다 — 반쪽을 3차로
  넘기지 않는다), 사람이 **같은 명령을 그대로 다시** 넣어야 이어간다.
  53회차 × 판독자 둘 + 감독 둘 = **열 번 넘게** 다시 넣어야 한다.

★ **진행이 없으면 멈춘다.** 이것이 이 도구의 알맹이다 —
  돌리개를 끝없이 다시 띄우면 **같은 자리에서 돈만 쓴다.** 한 바퀴를 돌고도
  늘어난 것이 하나도 없으면 바로 멈추고 사람에게 말한다.

★ 세는 것 — `상태.json` 의 끝난단계 수 · 판자리 안의 `판독결과_*` · `감독결과_*` 파일 수.
  이름을 박지 않고 **무늬로** 센다 (claude·codex 가 이름을 다르게 낸다).

★ 2026-11-06 — 저장소 `tools/` 에서 **꾸러미 안**(이 스킬의 `scripts/`)으로 옮겼다 (큰 판 길).
  sky 「정확도 채점과 큰 규모 실행은 … 여기서 그게 돌아가서 그런 결과는 나오는 skill 을
  만들어놔야」. 실무자 컴퓨터에는 저장소가 없고 꾸러미만 간다 — 도구가 꾸러미 밖에 있으면
  큰 판을 사람이 열 번 넘게 손으로 다시 넣어야 한다. 옮기면서 달라진 것 셋 —
  ① 돌리개를 **같은 폴더**에서 찾는다 (저장소 자리를 짐작하지 않는다).
  ② **`--승인` 을 스스로 붙이지 않는다.** 옮기기 전에는 붙였다 — 꾸러미에서 그대로 두면
     사람이 어림을 한 번도 안 보고 돈이 나갈 수 있다. 이제 `상태.json` 에 **사람이 승인한
     기록**(돌리개가 `--승인` 을 받으면 적는다)이 있는 판만 이어 돌리고, 없으면 거절한다.
  ③ 다 끝난 뒤 안내에서 저장소에만 있는 도구(`tools/옛판_결과대조.py`) 이름을 뺐다.

쓰기 —
    python 통째돌림_지켜보기.py <판자리>
    python 통째돌림_지켜보기.py <판자리> --최대 20 --깨끗

  ★ 먼저 돌리개로 **한 번** 시작해야 한다 — `python 한줄_돌리기.py <판자리> --조건 "…"` 로
    어림을 보고, 괜찮으면 `--승인` 을 붙여 다시 넣는다. 판독자가 스스로 넘겨 멈추면
    그때부터 이 도구가 이어 띄운다.
  멈추려면 — 판자리에 `멈춤` 이라는 빈 파일을 만든다 (돌던 한 바퀴는 끝까지 간다).
  2판 통째 재현에서 실제로 쓴 기록은 저장소의 `docs/진행_2판통째.md` 에 있다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

돌리개 = Path(__file__).resolve().parent / "한줄_돌리기.py"
끝단계 = "아웃풋1"
멈춤이름 = "멈춤"
기록보관 = "_바퀴별"


def 진행_세기(판: Path) -> dict:
    """지금까지 **쌓인 것**을 센다. 늘지 않으면 한 바퀴가 헛돌았다는 뜻이다."""
    상태 = {}
    p = 판 / "상태.json"
    if p.is_file():
        try:
            상태 = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            상태 = {}
    끝난 = list(상태.get("끝난단계", []))
    판독 = sorted(q.name for q in 판.rglob("판독결과_*") if q.is_file())
    감독 = sorted(q.name for q in 판.rglob("감독결과_*") if q.is_file())
    return {"끝난단계": 끝난, "판독": len(판독), "감독": len(감독),
            "소견": len(상태.get("소견", [])), "자": (tuple(끝난), len(판독), len(감독))}


def 승인했나(판: Path) -> bool:
    """`상태.json` 에 사람이 승인한 기록이 있나 — 돌리개가 `--승인` 을 받으면 `"승인": true` 를 적는다.
    읽을 수 없으면 **승인 안 한 것**으로 본다 (못 읽음은 통과가 아니다)."""
    try:
        return json.loads((판 / "상태.json").read_text(encoding="utf-8")).get("승인") is True
    except Exception:
        return False


def 기록_간수(판: Path) -> int:
    """AI 기록(`기록/*.jsonl`)은 **바퀴마다 덮인다** — 덮이기 전에 챙겨 둔다.

    ★ 2026-10-30 에 실제로 잃었다. 돌리개는 `기록자리.write_text(...)` 로 **덮으므로**
      바퀴를 다섯 번 돌고도 비용 기록이 **한 바퀴 분량만** 남아 있었다. 그래서
      「지금까지 얼마 썼나」 를 못 셌다. 게다가 240분 제한에 걸려 터진 바퀴는
      기록이 **아예 안 적힌다** (쓰기 전에 예외가 난다).
      (2026-11-07 뒤 이야기 — 돌리개가 이제 기록을 쓰는 대로 파일에 받고, 제한을 넘기면
      예외 대신 종료코드 124 로 멈춘다. 바퀴마다 덮이는 것은 그대로라 이 간수는 여전히 쓴다.)

    ★ 적힌 때를 이름에 붙여 `기록/_바퀴별/` 로 옮겨 둔다. 같은 것은 다시 안 챙긴다.
      돌려주는 것 — 이번에 새로 챙긴 개수.
    """
    기록 = 판 / "기록"
    if not 기록.is_dir():
        return 0
    보관 = 기록 / 기록보관
    보관.mkdir(exist_ok=True)
    챙김 = 0
    for q in sorted(기록.glob("*.jsonl")):
        때 = datetime.fromtimestamp(q.stat().st_mtime).strftime("%m%d_%H%M%S")
        쪽 = 보관 / ("%s_%s" % (때, q.name))
        if 쪽.exists():
            continue
        shutil.copy2(q, 쪽)
        챙김 += 1
    return 챙김


def 한바퀴(판: Path, 깨끗: bool, 기록: Path) -> int:
    """돌리개를 한 번 띄운다. 돌려주는 것 — **진짜 종료코드.**

    ★ 2026-10-30 — 처음에는 셸에서 `코드=$?` 로 적으려 했다. 셸 변수 이름에 한글을
      쓸 수 없어 `$코드` 가 **글자 그대로** 기록에 남았고, 진짜 종료코드를 잃었다.
      그래서 파이썬이 직접 받아 적는다.
    """
    # ★ `--승인` 을 붙이지 않는다 — 사람의 승인은 `상태.json` 에 이미 있어야 한다 (main 이 본다).
    명령 = [sys.executable, str(돌리개), str(판)]
    if 깨끗:
        명령.append("--깨끗")
    환경 = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    with open(기록, "a", encoding="utf-8", newline="\n") as f:
        f.write("\n" + "=" * 66 + "\n")
        f.write("  한 바퀴 시작 %s — %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        " ".join(명령[2:])))
        f.write("=" * 66 + "\n")
        f.flush()
        r = subprocess.run(명령, stdout=f, stderr=subprocess.STDOUT, cwd=str(판), env=환경)
        f.write("\n── 한 바퀴 끝 %s · ★ 진짜 종료코드 %d\n"
                % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r.returncode))
    return r.returncode


def 지켜보기(판: Path, 최대: int, 깨끗: bool) -> int:
    기록 = 판 / "돌린기록.txt"
    앞 = 진행_세기(판)
    print("  시작 진행 — 끝난단계 %s · 판독결과 %d · 감독결과 %d"
          % (" · ".join(앞["끝난단계"]) or "(없음)", 앞["판독"], 앞["감독"]))
    for 바퀴 in range(1, 최대 + 1):
        if (판 / 멈춤이름).exists():
            print("\n  ■ 판자리에 `%s` 파일이 있어 멈춥니다 (사람이 세웠습니다)." % 멈춤이름)
            return 0
        시작 = time.time()
        print("\n── 바퀴 %d/%d  %s" % (바퀴, 최대, datetime.now().strftime("%H:%M:%S")))
        코드 = 한바퀴(판, 깨끗, 기록)
        챙김 = 기록_간수(판)
        뒤 = 진행_세기(판)
        분 = (time.time() - 시작) / 60
        print("   종료코드 %d · %.1f분 · 끝난단계 %d · 판독결과 %d · 감독결과 %d · 소견 %d"
              % (코드, 분, len(뒤["끝난단계"]), 뒤["판독"], 뒤["감독"], 뒤["소견"]))
        if 챙김:
            print("   AI 기록 %d개를 `기록/%s/` 로 챙겼습니다 (덮이기 전에)" % (챙김, 기록보관))

        if 끝단계 in 뒤["끝난단계"]:
            print("\n  ✔ `%s` 까지 끝났습니다 — %d 바퀴 걸렸습니다." % (끝단계, 바퀴))
            print("    다음 — 회의에서 정한 뒤 `한줄_돌리기.py <판자리> --4차반영` 으로 사람 결정을 넣습니다.")
            return 0
        if 뒤["자"] == 앞["자"]:
            # ★ 알맹이 — 늘어난 것이 하나도 없다. 다시 띄우면 같은 자리에서 돈만 쓴다.
            print("\n  ✗ 한 바퀴를 돌았는데 **늘어난 것이 없습니다** — 여기서 멈춥니다.")
            print("    끝난단계 %s · 판독결과 %d · 감독결과 %d (바퀴 전과 같습니다)"
                  % (" · ".join(뒤["끝난단계"]) or "(없음)", 뒤["판독"], 뒤["감독"]))
            print("    기록의 마지막을 보십시오: %s" % 기록)
            print("    ★ 다시 띄우면 같은 자리에서 돈만 씁니다. 까닭을 먼저 고치십시오.")
            return 1
        앞 = 뒤
    print("\n  ■ 바퀴 %d 번을 다 썼습니다 — 아직 `%s` 가 아닙니다." % (최대, 끝단계))
    print("    진행은 늘고 있으니 같은 명령을 다시 넣으면 이어갑니다.")
    return 2


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("판자리")
    p.add_argument("--최대", type=int, default=40, help="다시 띄우는 횟수 한도 (기본 40)")
    p.add_argument("--깨끗", action="store_true", help="돌리개에 --깨끗 을 붙인다")
    a = p.parse_args()
    판 = Path(a.판자리).resolve()
    if not (판 / "상태.json").is_file():
        raise SystemExit("판자리에 상태.json 이 없습니다 (%s) — 먼저 `한줄_돌리기.py` 로 "
                         "어림을 보고 `--승인` 을 붙여 한 번 시작하십시오" % 판)
    if not 승인했나(판):
        raise SystemExit("이 판은 사람이 승인한 기록이 없습니다 (%s 의 상태.json) — "
                         "이 도구는 돈이 드는 것을 되풀이 띄우므로 스스로 승인하지 않습니다. "
                         "먼저 `한줄_돌리기.py` 로 어림을 보고 `--승인` 을 붙여 한 번 시작하십시오" % 판)
    if a.최대 < 1:
        raise SystemExit("--최대 는 1 이상이어야 합니다")
    print("=" * 66)
    print("  지켜보며 이어 돌립니다 — %s" % 판)
    print("  한도 %d 바퀴 · 깨끗 %s · 멈추려면 판자리에 `%s` 파일을 만드십시오"
          % (a.최대, "예" if a.깨끗 else "아니오", 멈춤이름))
    print("=" * 66)
    return 지켜보기(판, a.최대, a.깨끗)


if __name__ == "__main__":
    raise SystemExit(main())
