# -*- coding: utf-8 -*-
"""최신결정_검사 — `판독패키지/0_최신결정_먼저.md` 의 규칙 가운데 기계로 볼 수 있는 것을 본다 (섹션 5b · 2026-09-22).

★ 왜 — 판독은 매번 흔들린다. 같은 기준서로도 판독자에 따라 「대상 제품 아님」 을 16행에서 57행까지 놓쳤다.
  규칙을 글로만 두면 같이 틀린 행이 감독에게 가지 않는다. 그래서 판독자가 내기 전에 기계가 한 번 본다.

쓰기 (판독 폴더에서)
    python 스크립트/최신결정_검사.py 영상            판독 **전에** — 제품군이 어긋나 보이는 영상 (라1 · [가2])
    python 스크립트/최신결정_검사.py 번들 [번들]     판독 **뒤에** — 번들 raw_voc 를 본다 (라2~라8)
        [번들] 을 안 주면 `_판독패키지/_결과/*_bundle/raw_voc.csv` 에서 찾는다 (하나여야 한다)
        1차 값(라8)은 `판독대상/*/voc_secondary_dataset.csv` 에서 찾는다

종료코드   0 = 걸린 것 없음 · 1 = ✗ 가 있다 · 2 = 볼 것을 못 찾았다 (★ 못 찾음은 통과가 아니다)
「영상」 은 판단을 사람에게 넘기는 알림이라 ✗ 대신 「!」 로 알리고 0 으로 끝난다 — 보정요청서에 옮겨 적는다.
"""
from __future__ import annotations

import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── 라1 · 제품군마다 「그 제품을 말한다」 로 보는 말 (2판 실제 데이터로 맞췄다 — 2026-09-22)
어휘 = {
    "로봇청소기": r"로봇\s*청소기|로청|롯청|로보락|로봇|청소기|스테이션|물걸레|걸레|흡입|먼지|드리미|에코백스|로니|RONi|로보킹|히든|제트봇|모바|나르왈",
    "세탁기": r"세탁|워시|트롬|드럼|빨래|탈수|헹굼",
    "식기세척기": r"식기\s*세척기|식세기|설거지|식기",
    "냉장고": r"냉장고|냉동|얼음|김치",
    "건조기": r"건조",
}
최소행 = 5          # 이보다 적은 영상은 비율이 흔들려 보지 않는다
댓글비율 = 0.2       # 그 제품군을 말하는 댓글이 이보다 적으면

# ── 라2 · 라4 · 라7
자사 = re.compile(r"^\s*(LG|엘지|LG전자|엘지전자|자사)\s*$", re.I)
역할값 = {"creator_channel", "unknown", "product_brand", "competitor_brand"}
폐기라벨 = {"구매의사/이탈", "위생/살균", "위생/냄새(곰팡이)", "배수·부품", "주거 수납/공간"}
뭉뚱 = {"", "N/A", "미분류"}
시각 = re.compile(r"^\s*\(?\d{1,2}:\d{2}(:\d{2})?")
TEE = ("time", "effort", "emotion", "success")


def _읽기(p: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig"))))


def _v(r: dict, c: str) -> str:
    return str(r.get(c) or "").strip()


def _하나(후보: list[Path], 무엇: str) -> Path | None:
    if len(후보) != 1:
        print("  ✗ %s 을(를) 하나로 못 찾았습니다 — %d개: %s" % (무엇, len(후보), [str(p) for p in 후보][:5]))
        return None
    return 후보[0]


def 영상(자료: Path) -> int:
    print("[라1] 제품군이 어긋나 보이는 영상 — 0_최신결정_먼저 [가2]")
    rows = _읽기(자료)
    if not rows:
        print("  ✗ 1차 자료에 행이 없습니다 — %s" % 자료)
        return 2
    묶음 = defaultdict(list)
    for r in rows:
        묶음[(_v(r, "video_id"), _v(r, "video_title"), _v(r, "product_category"))].append(r)
    걸림 = []
    for (vid, 제목, 군), xs in 묶음.items():
        pat = 어휘.get(군)
        if not pat or len(xs) < 최소행 or re.search(pat, 제목, re.I):
            continue
        비율 = sum(bool(re.search(pat, _v(x, "original_voc"), re.I)) for x in xs) / len(xs)
        if 비율 < 댓글비율:
            걸림.append((vid, 제목, 군, len(xs), 비율))
    print("  · 영상 %d개 · 제품군 %s 를 봤습니다" % (len({k[0] for k in 묶음}), sorted({k[2] for k in 묶음})))
    for vid, 제목, 군, n, 비율 in sorted(걸림, key=lambda x: -x[3]):
        print("  ! %s  「%s」 — product_category=%s 인데 제목에 그 말이 없고, 그 제품을 말하는 댓글이 %d%% (%d행)"
              % (vid, 제목[:40], 군, round(100 * 비율), n))
    if 걸림:
        print("  → 값은 바꾸지 않습니다. 보정요청서에 이 영상들을 적고, 댓글마다의 판정은 [가1](가전이면 살린다)로 합니다")
    else:
        print("  · 어긋나 보이는 영상 없음")
    return 0


def 번들(raw: Path, 일차: Path | None) -> int:
    rows = _읽기(raw)
    print("번들 %s — %d행" % (raw, len(rows)))
    if not rows:
        print("  ✗ 번들에 행이 없습니다")
        return 2
    걸림: dict[str, list[str]] = defaultdict(list)
    원문별 = defaultdict(list)
    for r in rows:
        k = _v(r, "atomic_id")
        for t in re.split(r"[|,;/]", _v(r, "competitor_brand_tags")):
            if 자사.match(t):
                걸림["라2 경쟁사 칸에 자사 (LG) — [다1]"].append(k)
        if _v(r, "brand") in 역할값:
            걸림["라4 brand 칸에 entity_role 값 — [다5]"].append(k)
        for a in TEE:
            if _v(r, "tee_%s_score" % a) in ("0", "0.0") and not _v(r, "tee_%s_evidence" % a):
                걸림["라5 점수 0 인데 근거 빈칸 (N/A 로 적는다) — [다4]"].append("%s:%s" % (k, a))
        if _v(r, "status") == "scope_excluded" and _v(r, "topic") != "N/A":
            걸림["라6 제외 행의 topic 이 N/A 가 아님 — [다15]"].append(k)
        t = _v(r, "topic")
        if t in 폐기라벨 or t.startswith("기타("):
            걸림["라7 쓰지 않는 라벨 이름 「%s」 — [나9]~[나15]" % t].append(k)
        원문별[_v(r, "source_id") or _v(r, "parent_voc_id")].append(r)
    for sid, xs in 원문별.items():
        if sum(bool(시각.match(_v(x, "atomic_voc"))) for x in xs) >= 2:
            걸림["라3 목차 댓글을 나눴다 (한 덩어리 · operator_notice) — [다3]"].append(sid)
    if 일차 is None:
        print("  ✗ 라8 을 못 봤습니다 — 1차 자료(판독대상/*/voc_secondary_dataset.csv)를 못 찾았습니다")
        못봄 = True
    else:
        못봄 = False
        첫 = {_v(r, "atomic_id"): r for r in _읽기(일차)}
        본것 = 0
        for r in rows:
            f = 첫.get(_v(r, "atomic_id"))
            if not f:
                continue                       # 판독자가 나눠서 새로 생긴 조각
            본것 += 1
            ev = _v(r, "topic_evidence")
            # 라벨 → 다른 라벨로 바꾼 normal 행만 본다 (2026-09-22 실제 데이터로 좁힘):
            #   제외 행은 근거문이 판정에 쓰이지 않고, 1차가 미분류 · N/A 였으면 1차 근거가 새 라벨을 뒷받침할 수 있다
            #   (「LG는 요새 너무 비쌈」 → 가격/가성비)
            if (_v(r, "status") == "normal" and _v(r, "topic") not in 뭉뚱 and _v(f, "topic") not in 뭉뚱
                    and _v(r, "topic") != _v(f, "topic") and ev and ev not in ("N/A", "-")
                    and ev == _v(f, "topic_evidence")):
                걸림["라8 라벨을 바꿨는데 근거문은 1차 그대로 — [다2]"].append(_v(r, "atomic_id"))
        print("  · 라8 — 1차와 같은 행 %d개를 봤습니다" % 본것)
        if not 본것:
            print("  ✗ 라8 — 1차 자료와 겹치는 행이 0개입니다. 다른 판의 자료가 아닌지 봅니다")
            못봄 = True
    for 규칙, ks in sorted(걸림.items()):
        print("  ✗ %s — %d건: %s" % (규칙, len(ks), ", ".join(ks[:5]) + (" …" if len(ks) > 5 else "")))
    if not 걸림:
        print("  · 라2~라8 걸린 것 없음")
    if 못봄:
        return 2
    return 1 if 걸림 else 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("영상", "번들"):
        print(__doc__)
        return 2
    여기 = Path.cwd()
    if argv[0] == "영상":
        p = Path(argv[1]) if len(argv) > 1 else _하나(sorted(여기.glob("판독대상/*/voc_secondary_dataset.csv")), "1차 자료")
        return 영상(p) if p else 2
    raw = Path(argv[1]) if len(argv) > 1 else _하나(sorted(여기.glob("_판독패키지/_결과/*_bundle/raw_voc.csv")), "최종 번들")
    if raw is None:
        return 2
    if raw.is_dir():
        raw = raw / "raw_voc.csv"
    if not raw.is_file():
        print("  ✗ 번들을 못 찾았습니다 — %s" % raw)
        return 2
    일차후보 = sorted(여기.glob("판독대상/*/voc_secondary_dataset.csv"))
    return 번들(raw, 일차후보[0] if len(일차후보) == 1 else None)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
