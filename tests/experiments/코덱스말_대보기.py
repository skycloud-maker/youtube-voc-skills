# -*- coding: utf-8 -*-
"""Codex 가 ② 에서 한 말을 **실제 번들에 대고** 맞는지 본다 — Ver3 ③.

★ 왜 — ② 에서 받은 것은 **Codex 의 자기 설명**이다. 말과 실제가 다를 수 있다.
  ② 를 물을 때 「우리는 당신 답을 다시 그 번들에 대고 맞춰 볼 것입니다」 라고 미리 알렸다.

★ 자료 — 2026-09-21 판독 번들 (`기준데이터/스킬시험/실험_claudeA` · `실험_codexC`).
  claudeA 를 맞은편에 둔다(②의 근거묶음이 그 짝이었다). 대조군으로 claudeB 도 같이 잰다 —
  **「Codex 라서」 인지 「판독이 매번 흔들려서」 인지** 가르려면 같은 모델 둘이 필요하다.

★ 규율 — 「못 찾음」 은 「맞다」 가 아니다. 볼 거리가 없으면 **못 봄**으로 적는다.
  그리고 Codex 가 스스로 「글로 적기 어렵다」 고 한 것은 **대지 않는다** (brand 경계 · 분절 수 ·
  channel_feedback 경계 · out-of-scope 35건 · need_signal 임계값).

쓰기
    python tests/experiments/코덱스말_대보기.py
"""
from __future__ import annotations

import csv
import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(뿌리 / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

번들 = {
    "claudeA": "실험_claudeA/작업/_판독패키지/_결과/claudecode_bundle/raw_voc.csv",
    "claudeB": "실험_claudeB/작업/_판독패키지/_결과/claudecode_bundle/raw_voc.csv",
    "codexC": "실험_codexC/작업/_판독패키지/_결과/Codex_bundle/raw_voc.csv",
}
_브랜드말 = re.compile(r"(LG|엘지|삼성|로보락|로보록|다이소|샤오미|드리미|에코백스|위닉스|쿠쿠|코웨이)", re.I)
_역할말 = re.compile(r"(채널|구독|영상|유튜브|형님|님|리뷰|업로드|편집)")
_긍정말 = re.compile(r"(좋|최고|대박|굿|만족|편하|예쁘|이쁘|괜찮|감사|기대)")
_사양말 = re.compile(r"(되나요|되나\?|안되|안 되|안돼|호환|동시|가능한가|되는건가|지원)")


def _읽기(이름: str) -> dict:
    p = BASELINE / "스킬시험" / 번들[이름]
    if not p.is_file():
        raise SystemExit("못 찾음: %s" % p)        # 「못 찾음」 은 「없음」 이 아니다
    return {r["atomic_id"]: r for r in csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig")))}


def _맞댈것(ㄱ: dict, ㄴ: dict) -> list[str]:
    return sorted(set(ㄱ) & set(ㄴ))


def 말1_근거를_짧게(ㄱ: dict, ㄴ: dict) -> str:
    """「라벨을 직접 입증하는 최소 어구만 남긴다」 — 짧은가, 그리고 **상대 근거 안에 들어가는가**."""
    짧, 긺, 안김, 밖 = 0, 0, 0, 0
    for i in _맞댈것(ㄱ, ㄴ):
        a, b = (ㄱ[i].get("topic_evidence") or "").strip(), (ㄴ[i].get("topic_evidence") or "").strip()
        if not a or not b or a == b:
            continue
        (짧 := 짧) if False else None
        if len(b) < len(a):
            짧 += 1
        else:
            긺 += 1
        if b and b in a:
            안김 += 1                      # 나(Codex)의 근거가 상대 근거 **안에** 들어간다 = 최소 핵심
        elif a and a in b:
            밖 += 1
    모두 = 짧 + 긺
    if not 모두:
        return "못 봄 — 맞댈 근거가 없다"
    return ("다른 %d건 중 더 짧음 %d(%.0f%%) · 더 긺 %d | 상대 근거 **안에 들어감** %d · 반대 %d"
            % (모두, 짧, 100 * 짧 / 모두, 긺, 안김, 밖))


def 말2_이름만으로_안채움(ㄱ: dict, ㄴ: dict) -> str:
    """「조각에 브랜드가 없으면 앞뒤 문맥에서 보충하지 않고 비운다」 — 조각에 브랜드말이 **없는** 행만 본다."""
    대상 = [i for i in _맞댈것(ㄱ, ㄴ) if not _브랜드말.search(ㄱ[i].get("atomic_voc") or "")]
    if not 대상:
        return "못 봄 — 조각에 브랜드말이 없는 행을 못 찾았다"
    def 채움(d):
        return sum(1 for i in 대상 if (d[i].get("brand") or "").strip() not in ("", "unknown", "N/A"))
    return ("조각에 브랜드말이 없는 %d행 — 그래도 brand 를 채운 비율: 상대 %.0f%% · 나 %.0f%%"
            % (len(대상), 100 * 채움(ㄱ) / len(대상), 100 * 채움(ㄴ) / len(대상)))


def 말3_역할은_보수적으로(ㄱ: dict, ㄴ: dict) -> str:
    """「역할이 드러나지 않으면 상식으로 메우지 않고 unknown」 — 조각에 역할 단서가 **없는** 행만 본다."""
    대상 = [i for i in _맞댈것(ㄱ, ㄴ) if not _역할말.search(ㄱ[i].get("atomic_voc") or "")]
    if not 대상:
        return "못 봄 — 역할 단서가 없는 행을 못 찾았다"
    def 몰라(d):
        return sum(1 for i in 대상 if (d[i].get("entity_role") or "") == "unknown")
    return ("역할 단서가 없는 %d행 — unknown 으로 둔 비율: 상대 %.0f%% · 나 %.0f%%"
            % (len(대상), 100 * 몰라(ㄱ) / len(대상), 100 * 몰라(ㄴ) / len(대상)))


def 말4_짧은_긍정도_살림(ㄱ: dict, ㄴ: dict) -> str:
    """「짧거나 일반적인 감탄형이어도 제품 평가면 N/A 로 빼지 않는다」 — 짧고 긍정인 조각만 본다."""
    대상 = [i for i in _맞댈것(ㄱ, ㄴ)
          if len((ㄱ[i].get("atomic_voc") or "")) <= 25 and _긍정말.search(ㄱ[i].get("atomic_voc") or "")]
    if not 대상:
        return "못 봄 — 짧고 긍정인 조각을 못 찾았다"
    def 살림(d):
        return sum(1 for i in 대상 if (d[i].get("topic") or "") not in ("", "N/A", "미분류")
                   and (d[i].get("status") or "") != "scope_excluded")
    def 신호(d):
        return sum(1 for i in 대상 if (d[i].get("need_signal_flag") or "").upper().startswith("Y"))
    return ("짧고 긍정인 %d행 — 라벨을 붙인 비율: 상대 %.0f%% · 나 %.0f%% | need_signal Y: 상대 %d · 나 %d"
            % (len(대상), 100 * 살림(ㄱ) / len(대상), 100 * 살림(ㄴ) / len(대상), 신호(ㄱ), 신호(ㄴ)))


def 말5_나눈것은_라벨이_다름(ㄱ: dict, ㄴ: dict) -> str:
    """「접속사 수가 아니라 **라벨의 독립성**을 기준으로 나눈다」 —
    더 잘게 나눈 원문에서 그 조각들의 라벨이 실제로 서로 다른가."""
    def 원본별(d):
        m = defaultdict(list)
        for i, r in d.items():
            m[r.get("source_id") or i.rsplit("-", 1)[0]].append(r)
        return m
    ㄱm, ㄴm = 원본별(ㄱ), 원본별(ㄴ)
    더잘게 = [s for s in set(ㄱm) & set(ㄴm) if len(ㄴm[s]) > len(ㄱm[s])]
    if not 더잘게:
        return "못 봄 — 내가 더 잘게 나눈 원문이 없다"
    def 고유비(묶음):
        라 = [r.get("topic") or "" for r in 묶음]
        return len(set(라)) / len(라) if 라 else 0
    내 = sum(고유비(ㄴm[s]) for s in 더잘게) / len(더잘게)
    상대 = sum(고유비(ㄱm[s]) for s in 더잘게) / len(더잘게)
    return ("내가 더 잘게 나눈 원문 %d개 — 조각 라벨의 **고유 비율**(1.0 이면 전부 다름): 나 %.2f · 상대 %.2f"
            % (len(더잘게), 내, 상대))


def 말7_가능여부는_사양(ㄱ: dict, ㄴ: dict) -> str:
    """「된다/안 된다 · 호환 · 동시 사용은 `제품 식별·사양`」 — 그런 말이 든 조각만 본다."""
    대상 = [i for i in _맞댈것(ㄱ, ㄴ) if _사양말.search(ㄱ[i].get("atomic_voc") or "")]
    if not 대상:
        return "못 봄 — 가능/호환 말이 든 조각을 못 찾았다"
    def 사양(d):
        return sum(1 for i in 대상 if (d[i].get("topic") or "") == "제품 식별·사양")
    return ("가능/호환 말이 든 %d행 — `제품 식별·사양` 으로 본 수: 상대 %d · 나 %d"
            % (len(대상), 사양(ㄱ), 사양(ㄴ)))


말들 = [("① 근거를 최소 충분 범위로", 말1_근거를_짧게),
      ("② 이름만으로 brand 를 채우지 않는다", 말2_이름만으로_안채움),
      ("③ 역할이 안 드러나면 unknown", 말3_역할은_보수적으로),
      ("④ 짧아도 분석 가능한 평가는 살린다", 말4_짧은_긍정도_살림),
      ("⑤ 나눈 조각은 라벨이 독립적이다", 말5_나눈것은_라벨이_다름),
      ("⑦ 가능/호환 사실은 제품 식별·사양", 말7_가능여부는_사양)]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    A, B, C = _읽기("claudeA"), _읽기("claudeB"), _읽기("codexC")
    print("자료 — claudeA %d · claudeB %d · codexC %d 조각" % (len(A), len(B), len(C)))
    print("\n각 말마다 두 줄을 본다 — **Codex vs Claude A**(①의 짝) 와 **대조군 Claude B vs Claude A**.")
    print("대조군에서도 같은 차이가 나면 그것은 「Codex 라서」 가 아니라 **판독이 매번 흔들려서**다.\n")
    for 이름, 재기 in 말들:
        print("── %s" % 이름)
        print("   Codex  : %s" % 재기(A, C))
        print("   대조군 B: %s" % 재기(A, B))
    print("\n★ Codex 가 스스로 「글로 적기 어렵다」 고 한 것은 대지 않았다 —")
    print("  brand 경계 · 정확한 분절 수 · channel_feedback↔no_analytic_value 경계 ·")
    print("  out-of-scope 35건 · need_signal 임계값.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
