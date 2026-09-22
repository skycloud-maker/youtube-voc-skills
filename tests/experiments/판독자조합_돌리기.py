# -*- coding: utf-8 -*-
"""판독자 조합 실험 — Claude 창 둘(같은 모델) vs Claude + Codex(다른 모델) (sky 2026-09-21 요청).

★ 물음 — 원문 98 「같은 것을 둘 쓰면 같은 실수를 같이 한다」 는 검증한 적이 없다. 재 본다.
★ 방법
  ① 2판 10회차 · 40회차(240행)를 **지금** 세 번 판독한다 — Claude A · Claude B (서로 모르는 새 창) · Codex C.
     2판 판독은 8월 판 모델이 한 것이라 섞지 않는다.
  ② 행마다 라벨(topic, 제외면 「제외:사유」)을 견준다 — 같은 모델 쌍(A·B) · 다른 모델 쌍(A·C) 의 갈림 비율.
  ③ ★ 셋 중 둘은 같고 하나만 다른 행을 **전부** 뽑아, 누가 냈는지 가린 채 sky 가 「둘이 낸 답이 맞는가」 를 채점한다.
     → 같은 모델 쌍 · 다른 모델 쌍이 **같이 틀린** 비율 (일치율은 정확도가 아니다 — 정답이 있어야 잰다).
★ 판독은 판독 스킬 그대로 — 스킬 시험과 같은 외딴 자리 · 같은 방식으로 돌린다.

쓰기
    python tests/experiments/판독자조합_돌리기.py 돌리기            A · B · C 를 차례로 (없는 것만)
    python tests/experiments/판독자조합_돌리기.py 돌리기 claudeD:claude codexE:codex
                                                               섹션 5b 뒤 다시 재기 — 이름:누구 (sky 2026-09-22 「Claude 1 + Codex 1」)
    python tests/experiments/판독자조합_돌리기.py 견주기            ② 와 ③ 의 채점지를 만든다
"""
from __future__ import annotations

import csv
import io
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(_여기.parent / "evals"))
import 스킬시험_돌리기 as 공통  # noqa: E402
from paths import BASELINE, PLUGIN  # noqa: E402

재료 = BASELINE / "시험재료" / "실험_판독자조합_2회차.xlsx"
결과자리 = BASELINE / "실험" / "판독자조합"
프롬프트 = "이 폴더에 있는 1차 분석 결과로 2차 판독을 해 주세요."
판독자 = {"claudeA": "claude", "claudeB": "claude", "codexC": "codex"}


def 돌리기(누구들: dict[str, str] | None = None) -> None:
    결과자리.mkdir(parents=True, exist_ok=True)
    for 이름, 누구 in (누구들 or 판독자).items():
        최종 = BASELINE / "스킬시험" / ("실험_%s" % 이름)
        if 최종.exists():
            print("  · %s — 이미 있어 건너뜀" % 이름)
            continue
        그릇, 최종 = 공통.격리_준비("실험_%s" % 이름)
        작업 = 그릇 / "작업"
        shutil.copyfile(재료, 작업 / 재료.name)
        if 누구 == "claude":
            명령 = [shutil.which("claude"), "-p", "--output-format", "stream-json", "--verbose",
                  "--dangerously-skip-permissions", "--plugin-dir", str(PLUGIN)]
            환경 = 공통._env()
        else:
            d = 그릇 / ".agents"
            shutil.copytree(PLUGIN / "skills" / "reading-voc-comments", d / "skills" / "reading-voc-comments")
            shutil.copytree(PLUGIN / "shared", d / "shared")
            shutil.copytree(PLUGIN / "engine", d / "engine")
            subprocess.run(["git", "init", "-q"], cwd=그릇)
            명령 = [shutil.which("codex"), "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "-"]
            환경 = 공통._codex_env()
        r = subprocess.run(명령, input=프롬프트, cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=환경, timeout=4 * 3600)
        공통.격리_마치기(그릇, 최종, r, {"누구": 누구, "시험": "실험_" + 이름})
        print("  · %s — AI 종료코드 %d" % (이름, r.returncode))


def _라벨(r: dict) -> str:
    if (r.get("status") or "") == "scope_excluded":
        return "제외:" + (r.get("scope_exclusion_reason") or "?")
    return r.get("topic") or "(빈칸)"


def _번들(이름: str) -> dict:
    작업 = BASELINE / "스킬시험" / ("실험_%s" % 이름) / "작업"
    후보 = sorted((작업 / "_판독패키지" / "_결과").glob("*_bundle/raw_voc.csv"))
    if len(후보) != 1:
        raise SystemExit("%s 의 최종 번들을 하나로 못 찾았다 — %s" % (이름, [str(p) for p in 후보]))
    rows = list(csv.DictReader(io.StringIO(후보[0].read_bytes().decode("utf-8-sig"))))
    return {r["atomic_id"]: r for r in rows}


def 견주기() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    A, B, C = _번들("claudeA"), _번들("claudeB"), _번들("codexC")
    공통행 = sorted(set(A) & set(B) & set(C))          # 분리로 새로 생긴 조각은 빼고 셋 다 있는 원래 행만
    라 = {k: (_라벨(A[k]), _라벨(B[k]), _라벨(C[k])) for k in 공통행}
    갈림AB = sum(a != b for a, b, c in 라.values())
    갈림AC = sum(a != c for a, b, c in 라.values())
    갈림BC = sum(b != c for a, b, c in 라.values())
    print("셋 다 있는 행 %d" % len(공통행))
    print("  같은 모델 A·B 갈림 %d (%.1f%%)" % (갈림AB, 100 * 갈림AB / len(라)))
    print("  다른 모델 A·C 갈림 %d (%.1f%%) · B·C %d (%.1f%%)" % (갈림AC, 100 * 갈림AC / len(라), 갈림BC, 100 * 갈림BC / len(라)))
    # ③ 둘은 같고 하나만 다른 행 — 누가 냈는지 가린다 (쌍 이름은 채점지에 넣지 않는다)
    채점, 열쇠 = [], {}
    for k, (a, b, c) in 라.items():
        if a == b != c:
            쌍 = "같은모델(A·B)"; 둘, 하나 = a, c
        elif a == c != b:
            쌍 = "다른모델(A·C)"; 둘, 하나 = a, b
        elif b == c != a:
            쌍 = "다른모델(B·C)"; 둘, 하나 = b, a
        else:
            continue
        채점.append({"atomic_id": k, "원문": A[k].get("original_voc", ""), "조각": A[k].get("atomic_voc", ""),
                   "답1": 둘, "답2": 하나})
        열쇠[k] = 쌍
    random.Random(20260921).shuffle(채점)
    for i, x in enumerate(채점, 1):
        x["번호"] = i
        # 답1·답2 의 자리도 섞는다 — 「답1 이 늘 둘이 낸 답」 이면 채점자가 눈치챈다
        if random.Random(i).random() < 0.5:
            x["답1"], x["답2"] = x["답2"], x["답1"]
            열쇠[x["atomic_id"]] = (열쇠[x["atomic_id"]], "둘이낸답=답2")
        else:
            열쇠[x["atomic_id"]] = (열쇠[x["atomic_id"]], "둘이낸답=답1")
    결과자리.mkdir(parents=True, exist_ok=True)
    with open(결과자리 / "채점지.csv", "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=["번호", "atomic_id", "원문", "조각", "답1", "답2", "맞는 답(1/2/둘다/둘다아님)", "메모"])
        w.writeheader()
        for x in 채점:
            w.writerow({k: x.get(k, "") for k in w.fieldnames})
    (결과자리 / "_열쇠_채점뒤에만.json").write_text(json.dumps(열쇠, ensure_ascii=False, indent=1), encoding="utf-8")
    (결과자리 / "갈림.json").write_text(json.dumps({"셋다있는행": len(공통행), "AB": 갈림AB, "AC": 갈림AC, "BC": 갈림BC},
                                               ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("채점할 행 %d — %s" % (len(채점), dict(Counter(v[0] for v in 열쇠.values()))))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")     # 윈도 콘솔(cp949)에서 — 따위 글자로 죽지 않게 (2026-09-21 A 뒤에 멈췄다)
    if sys.argv[1] == "돌리기" and len(sys.argv) > 2:
        돌리기(dict(x.split(":", 1) for x in sys.argv[2:]))
    else:
        {"돌리기": 돌리기, "견주기": 견주기}[sys.argv[1]]()
