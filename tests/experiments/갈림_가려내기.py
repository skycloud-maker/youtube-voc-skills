# -*- coding: utf-8 -*-
"""Claude 와 Codex 가 **어디서 갈렸나** 를 패턴으로 가려낸다 (검토 2026-10-07 ①).

★ 왜 — sky 물음 「모델의 차이를 어떻게 지시문으로 발라내나」. 먼저 **갈림 가운데 몇 %가 글로 적을 수 있는
  종류인가** 를 숫자로 내야 지시문에 무엇을 적을지 정해진다. 글로 적을 수 있는 것은 절차와 경계이고,
  모델 바탕 차이는 적을 수 없다.

★ 자료 — 2026-09-21/22 판독자 조합 실험의 **살아 있는 번들** 다섯 벌 (기준데이터/스킬시험/실험_*).
  짝: Claude↔Codex 세 쌍(A·C / B·C / D·E) 과 **대조군** Claude↔Claude 한 쌍(A·B).
  대조군이 있어야 「모델이 달라서 갈린 것」 과 「판독이 매번 흔들려서 갈린 것」 을 가를 수 있다.

★ 눈금 — 정본(2판 최종 산출물)은 채점용 눈금이지 정답률이 아니다. 그리고 [가1] 뒤로 제품군이 어긋난
  영상의 행은 정본이 더는 답이 아니라 따로 센다 (판독자조합_정본에_대기.py 와 같은 기준).

쓰기
    python tests/experiments/갈림_가려내기.py       화면에 표 · 기준데이터/검토1007/ 에 갈림 목록
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(뿌리 / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

실행자리 = BASELINE / "스킬시험"
낼자리 = BASELINE / "검토1007"
번들 = {
    "claudeA": "실험_claudeA/작업/_판독패키지/_결과/claudecode_bundle/raw_voc.csv",
    "claudeB": "실험_claudeB/작업/_판독패키지/_결과/claudecode_bundle/raw_voc.csv",
    "claudeD": "실험_claudeD/작업/_판독패키지/_결과/claudecode_bundle/raw_voc.csv",
    "codexC": "실험_codexC/작업/_판독패키지/_결과/Codex_bundle/raw_voc.csv",
    "codexE": "실험_codexE/작업/_판독패키지/_결과/Codex_bundle/raw_voc.csv",
}
짝들 = [("claudeA", "codexC", "다른 모델"), ("claudeB", "codexC", "다른 모델"),
        ("claudeD", "codexE", "다른 모델 · 5b 뒤"), ("claudeA", "claudeB", "같은 모델(대조군)")]
# 판정 대상 칸 (원본사본/2판/25_판정대상_컬럼분류.md D절) 가운데 라벨 갈림 뒤에 더 볼 칸
볼칸 = ["status", "scope_exclusion_reason", "topic", "topic_evidence", "entity_role", "brand",
        "product_category", "inquiry_flag", "inquiry_type", "need_signal_flag", "need_signal_type",
        "cej", "rootcause_problem", "rootcause_cause", "rootcause_target",
        "tee_time_score", "tee_effort_score", "tee_emotion_score", "tee_success_score", "review_required"]


def _읽기(p: Path) -> list[dict]:
    if not p.is_file():
        raise SystemExit("못 찾음: %s" % p)      # ★ 「못 찾음」 은 「없음」 이 아니다
    return list(csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig"))))


def _그룹표() -> dict:
    d = json.loads((뿌리 / "plugin" / "shared" / "registry" / "topic_group_map.json").read_text(encoding="utf-8"))
    표 = d.get("topic_to_group")
    if not isinstance(표, dict) or len(표) < 30:
        raise SystemExit("못 찾음: topic_group_map.json 의 topic_to_group")   # 「못 찾음」 은 「없음」 이 아니다
    return 표


def _어긋난영상집합(정: list[dict]) -> set[str]:
    """제품군이 어긋난 영상 — 같은 기준을 두 벌 적지 않고 기존 도구에서 불러온다"""
    p = 뿌리 / "tests" / "experiments" / "판독자조합_정본에_대기.py"
    사양 = importlib.util.spec_from_file_location("정본에_대기", p)
    m = importlib.util.module_from_spec(사양)
    sys.modules["정본에_대기"] = m
    사양.loader.exec_module(m)
    return m._어긋난영상({r["atomic_id"]: r for r in 정})


def _판정(r: dict) -> tuple[str, str]:
    """한 조각의 판정 — (제외/라벨, 값)"""
    if (r.get("status") or "") == "scope_excluded" or (r.get("scope_excluded") or "").lower() in ("true", "1", "y"):
        return ("제외", r.get("scope_exclusion_reason") or "(빈칸)")
    return ("라벨", r.get("topic") or "(빈칸)")


def _원본별(xs: list[dict]) -> dict:
    d = defaultdict(list)
    for r in xs:
        d[r.get("source_id") or r["atomic_id"].rsplit("-", 1)[0]].append(r)
    for v in d.values():
        v.sort(key=lambda r: r.get("atomic_index") or r["atomic_id"])
    return d


def 가름(가: list[dict], 나: list[dict], 그룹: dict) -> tuple[Counter, list[dict]]:
    """원문 하나씩 대고 갈림을 종류로 나눈다. 조각 수가 다르면 라벨을 맞댈 수 없다."""
    ㄱ, ㄴ = _원본별(가), _원본별(나)
    셈, 목록 = Counter(), []
    for sid in sorted(set(ㄱ) & set(ㄴ)):
        a, b = ㄱ[sid], ㄴ[sid]
        셈["원문"] += 1
        if len(a) != len(b):
            셈["조각수 다름"] += 1
            목록.append({"source_id": sid, "종류": "조각수 다름", "가": "조각 %d" % len(a), "나": "조각 %d" % len(b),
                         "원문": (a[0].get("original_voc") or "")[:120]})
            continue
        for x, y in zip(a, b):
            셈["조각"] += 1
            ㄱ판, ㄴ판 = _판정(x), _판정(y)
            if ㄱ판 == ㄴ판:
                셈["같음"] += 1
                continue
            if ㄱ판[0] != ㄴ판[0]:
                종류 = "제외↔라벨"
            elif ㄱ판[0] == "제외":
                종류 = "제외 사유만 다름"
            elif 그룹.get(ㄱ판[1]) and 그룹.get(ㄱ판[1]) == 그룹.get(ㄴ판[1]):
                종류 = "라벨 — 같은 그룹 안"
            else:
                종류 = "라벨 — 다른 그룹"
            셈[종류] += 1
            목록.append({"source_id": sid, "atomic_id": x["atomic_id"], "종류": 종류,
                         "가": "%s:%s" % ㄱ판, "나": "%s:%s" % ㄴ판,
                         "조각": (x.get("atomic_voc") or "")[:80], "원문": (x.get("original_voc") or "")[:120]})
    return 셈, 목록


def 칸별(가: list[dict], 나: list[dict]) -> Counter:
    """같은 atomic_id 가 양쪽에 있는 조각만 — 칸마다 몇 조각이 다른가"""
    ㄱ = {r["atomic_id"]: r for r in 가}
    ㄴ = {r["atomic_id"]: r for r in 나}
    같은 = sorted(set(ㄱ) & set(ㄴ))
    셈 = Counter({"맞댄 조각": len(같은)})
    for i in 같은:
        for c in 볼칸:
            if c in ㄱ[i] and c in ㄴ[i] and (ㄱ[i][c] or "") != (ㄴ[i][c] or ""):
                셈[c] += 1
    return 셈


def 누가맞나(목록: list[dict], 정: dict, 뺄영상: set) -> Counter:
    """갈린 조각마다 정본과 같은 쪽 — 제품군 어긋난 영상은 따로"""
    셈 = Counter()
    for 줄 in 목록:
        if 줄["종류"] == "조각수 다름":
            continue
        r = 정.get(줄.get("atomic_id", ""))
        if r is None:
            셈[줄["종류"] + " / 정본에 그 조각 없음"] += 1
            continue
        if r.get("video_id") in 뺄영상:
            셈[줄["종류"] + " / 어긋난 영상(채점 안 함)"] += 1
            continue
        답 = "%s:%s" % _판정(r)
        셈[줄["종류"] + " / " + ("가 맞음" if 줄["가"] == 답 else "나 맞음" if 줄["나"] == 답 else "둘 다 아님")] += 1
    return 셈


def 모델몫(쌓은: dict) -> dict:
    """★ 모델 차이 = 다른 모델 쌍의 갈림 − 같은 모델 쌍(대조군)의 갈림.

    까닭 — 판독은 같은 모델로 두 번 돌려도 갈린다. 그 흔들림을 빼지 않으면 모델 차이를 셀 수 없다.
    5b 전 세 쌍만 같은 자리에서 대고(A·C · B·C vs 대조군 A·B), 5b 뒤(D·E)는 규칙이 달라 따로 적는다.
    """
    대조 = 쌓은["claudeA·claudeB"]
    print("\n── 모델 몫 (5b 전 · 같은 240행) — 「다른 모델 쌍 평균 − 대조군」, 맞댄 조각 대비 %")
    print("   %-24s %9s %9s %9s %9s" % ("", "A·C", "B·C", "대조 A·B", "모델 몫"))
    줄들 = [("조각수 다름(원문 대비)", "조각수 다름", "원문"), ("제외↔라벨", "제외↔라벨", "조각"),
            ("제외 사유만 다름", "제외 사유만 다름", "조각"), ("라벨 — 같은 그룹 안", "라벨 — 같은 그룹 안", "조각"),
            ("라벨 — 다른 그룹", "라벨 — 다른 그룹", "조각")]
    out = {}
    for 이름, 열쇠, 밑 in 줄들 + [(c, c, "맞댄 조각") for c in 볼칸]:
        값 = []
        for 짝 in ("claudeA·codexC", "claudeB·codexC", "claudeA·claudeB"):
            셈 = 쌓은[짝]
            값.append(100.0 * 셈[열쇠] / 셈[밑] if 셈[밑] else 0.0)
        몫 = (값[0] + 값[1]) / 2 - 값[2]
        if max(값) < 1.0 and abs(몫) < 1.0:
            continue
        out[이름] = 몫
        print("   %-24s %8.1f%% %8.1f%% %8.1f%% %+8.1f%%p" % (이름, 값[0], 값[1], 값[2], 몫))
    return out


def 쏠림(자료: dict, 칸: str, 짝: tuple[str, str], 몇개: int = 5) -> tuple[float, list]:
    """★ 「글로 적을 수 있나」 를 가르는 자리 — 갈림이 **한쪽으로 쏠렸나**.

    같은 바뀜(Claude 값 → Codex 값)이 되풀이되면 그것은 규칙이다 — 지시문에 적을 수 있다.
    갈림이 제각각이면 쏠림이 낮고, 그것은 모델이 읽는 결의 차이라 글로 옮기기 어렵다.
    돌려주는 것 — (상위 3가지가 덮는 비율, 상위 목록).
    """
    ㄱ = {r["atomic_id"]: r for r in 자료[짝[0]]}
    ㄴ = {r["atomic_id"]: r for r in 자료[짝[1]]}
    바뀜 = Counter()
    for i in set(ㄱ) & set(ㄴ):
        a, b = (ㄱ[i].get(칸) or "(빈칸)"), (ㄴ[i].get(칸) or "(빈칸)")
        if 칸 == "topic_evidence":                       # 근거는 글자가 길다 — 길이와 포함 관계로만 본다
            a2, b2 = (ㄱ[i].get(칸) or ""), (ㄴ[i].get(칸) or "")
            if a2 == b2:
                continue
            바뀜["나가 더 짧다" if len(b2) < len(a2) else "나가 더 길다"] += 1
            continue
        if a != b:
            바뀜["%s → %s" % (a[:22], b[:22])] += 1
    모두 = sum(바뀜.values())
    상위 = 바뀜.most_common(몇개)
    덮음 = 100.0 * sum(n for _, n in 상위[:3]) / 모두 if 모두 else 0.0
    return 덮음, 상위


def main() -> int:
    그룹 = _그룹표()
    자료 = {n: _읽기(실행자리 / r) for n, r in 번들.items()}
    정줄 = _읽기(BASELINE / "원본사본" / "2판" / "s15_master" / "raw_voc.csv")
    정 = {r["atomic_id"]: r for r in 정줄}
    뺄영상 = _어긋난영상집합(정줄)
    낼자리.mkdir(parents=True, exist_ok=True)
    print("정본 %d 조각 · 제품군 어긋난 영상 %d개 · topic 그룹표 %d개" % (len(정), len(뺄영상), len(그룹)))
    print("판독 번들 — " + " · ".join("%s %d조각" % (n, len(x)) for n, x in 자료.items()))
    모은목록, 쌓은 = [], {}
    for 가, 나, 꼬리 in 짝들:
        셈, 목록 = 가름(자료[가], 자료[나], 그룹)
        쌓은["%s·%s" % (가, 나)] = 셈 + 칸별(자료[가], 자료[나])
        print("\n── %s · %s  (%s)" % (가, 나, 꼬리))
        print("   맞댄 원문 %d · 맞댄 조각 %d · 같음 %d" % (셈["원문"], 셈["조각"], 셈["같음"]))
        for k in ("조각수 다름", "제외↔라벨", "제외 사유만 다름", "라벨 — 같은 그룹 안", "라벨 — 다른 그룹"):
            print("   %-16s %4d" % (k, 셈[k]))
        ㅋ = 칸별(자료[가], 자료[나])
        print("   칸별 갈림 (맞댄 조각 %d): " % ㅋ["맞댄 조각"]
              + " · ".join("%s %d" % (c, ㅋ[c]) for c in 볼칸 if ㅋ[c]))
        맞 = 누가맞나(목록, 정, 뺄영상)
        for k in sorted(맞):
            print("      %-44s %3d" % (k, 맞[k]))
        for 줄 in 목록:
            줄["짝"] = "%s·%s" % (가, 나)
        모은목록 += 목록
    몫 = 모델몫(쌓은)
    볼것 =["topic_evidence", "brand", "entity_role", "cej", "need_signal_flag", "need_signal_type",
            "tee_emotion_score", "rootcause_cause", "topic", "scope_exclusion_reason", "rootcause_target"]
    for 짝 in (("claudeA", "codexC"), ("claudeD", "codexE")):
        print("\n── 쏠렸나 (%s·%s) — 상위 3가지가 갈림의 몇 %%를 덮나. 높으면 규칙으로 적을 수 있다" % 짝)
        for c in 볼것:
            덮음, 상위 = 쏠림(자료, c, 짝)
            if not 상위:
                print("   %-22s 갈림 없음" % c)
                continue
            print("   %-22s 덮음 %5.1f%%  | %s" % (c, 덮음, " · ".join("%s ×%d" % (k, n) for k, n in 상위[:4])))
    # ★ sky 물음에 대한 한 숫자 — 모델 몫 가운데 「쏠려서 글로 적을 수 있는」 몫
    #   눈금: 상위 3가지가 갈림의 60% 이상을 덮으면 「쏠림」 (내가 정한 눈금이다 — 50·70 으로도 같이 적는다)
    for 눈금 in (50, 60, 70):
        적을수있음 = 못적음 = 0.0
        for c in 볼칸:
            if c not in 몫 or 몫[c] <= 0:
                continue
            덮음, _ = 쏠림(자료, c, ("claudeA", "codexC"))
            if 덮음 >= 눈금:
                적을수있음 += 몫[c]
            else:
                못적음 += 몫[c]
        모두 = 적을수있음 + 못적음
        print("   쏠림 눈금 %d%% → 글로 적을 수 있는 몫 %.0f / 못 적는 몫 %.0f  = **%.0f%%**"
              % (눈금, 적을수있음, 못적음, 100.0 * 적을수있음 / 모두 if 모두 else 0))
    칸 = ["짝", "종류", "source_id", "atomic_id", "가", "나", "조각", "원문"]
    낼 = 낼자리 / "갈림_목록.csv"
    with io.open(낼, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, 칸, extrasaction="ignore")
        w.writeheader()
        w.writerows(모은목록)
    print("\n갈림 %d줄 → %s" % (len(모은목록), 낼))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
