# -*- coding: utf-8 -*-
"""다음 차수로 넘어가도 되는지 **사람 대신 판단한다.**

★ 왜 (sky 2026-08-23)
  「2차 후 3차로 넘어갈때 오늘은 당신이 직접 2차의 상태를 보고
    3차로 넘겨도 됩니다 라는 판단을 해서 넘겼고 … 실제 실무자들 단계에서는
    그 중간 결과 점검자가 없는 상태인거 같은데」

  ★ 맞습니다. 없었습니다. 오늘 그 자리를 사람(나)이 메웠습니다.
    실무자만 있으면 아무도 「넘어가도 되나」 를 묻지 않고 그냥 넘어갑니다.

  ★★ 그러면 이런 일이 조용히 지나갑니다 — 오늘 실제로 다 겪은 것들입니다.
      · 최종 번들이 안 만들어졌는데 끝난 줄 안다 (08-22 B)
      · 한쪽 감독자만으로 통합해 감독자를 통째로 무시한다
      · 앞 차수 보정요청을 안 이어받아 3건이 사라진다
      · judge_10 이후 회차를 안 읽고도 에러 없이 끝난다

  이 도구는 **차수를 넘기기 전에 돌립니다.** 넘어가도 되면 그렇게 말하고,
  아니면 무엇이 모자란지 말합니다. 짐작하지 않고 파일을 셉니다.

쓰기
    python 스크립트/넘어가도_되나.py            이 폴더가 어느 차수인지 스스로 봅니다
"""
from __future__ import annotations

import csv
import glob
import io
import json
import re
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

막힘: list[str] = []
알림: list[str] = []


def 줄(표: str, 말: str) -> None:
    print("  %-3s %s" % (표, 말))


def _번들들(뿌리: Path) -> list[Path]:
    """회차 번들이 아닌 최종 번들만."""
    if not 뿌리.is_dir():
        return []
    return [d for d in sorted(뿌리.iterdir())
            if d.is_dir() and not d.name.startswith("bundle_")
            and "옛판" not in d.name and (d / "raw_voc.csv").exists()]


def 이차(뿌리: Path) -> None:
    """2차 판독 — 3차로 넘어가도 되나."""
    배치 = sorted((뿌리 / "회차배치").glob("full_*_ids.txt"))
    결과 = sorted((뿌리 / "_판독패키지" / "_결과").glob("판독결과_full_*.md"))
    줄("·", "회차배치 %d · 판정 %d" % (len(배치), len(결과)))
    if not 배치:
        막힘.append("회차배치가 없습니다 — 데이터를 먼저 앉히십시오")
        return
    if len(결과) < len(배치):
        막힘.append("판정이 %d회차 모자랍니다 (%d/%d)"
                    % (len(배치) - len(결과), len(결과), len(배치)))

    번들 = _번들들(뿌리 / "_판독패키지" / "_결과")
    if not 번들:
        막힘.append("최종 번들이 없습니다 — 마무리를 안 했습니다")
    else:
        줄("·", "최종 번들 %s" % " · ".join(d.name for d in 번들))
        # ★ 번들이 판정보다 오래됐으면 옛것이다 (08-22 에 실제로 그랬다)
        if 결과:
            늦은판정 = max(p.stat().st_mtime for p in 결과)
            for d in 번들:
                # ★ 폴더 시각은 못 믿는다 (2026-08-23) — 안의 파일이 나중에 바뀌어도
                #   폴더 시각은 그대로다. A 폴더에서 폴더 01:53 · 파일 02:06 이었다.
                _안 = [p.stat().st_mtime for p in d.iterdir() if p.is_file()]
                if (max(_안) if _안 else 0) < 늦은판정:
                    막힘.append("번들 %s 이 판정보다 오래됐습니다 — 다시 만드십시오"
                                % d.name)
        if len(번들) > 1:
            알림.append("번들이 %d개입니다 — 판독자 폴더가 섞였는지 보십시오"
                        % len(번들))

    req = 뿌리 / "_인계" / "보정요청.csv"
    if req.exists():
        with io.open(req, encoding="utf-8-sig", newline="") as h:
            n = len(list(csv.DictReader(h)))
        줄("·", "보정요청 %d건" % n)
    else:
        알림.append("보정요청서가 없습니다 — 낼 것이 없었다면 그대로 두십시오")


def 삼차(뿌리: Path) -> None:
    """3차 감독 — 통합해도 되나."""
    배치 = sorted((뿌리 / "s13_judge").glob("judge_*_ids.txt"))
    결과 = sorted((뿌리 / "_판독패키지" / "_결과").glob("감독결과_*.md"))
    줄("·", "회차배치 %d · 판정 %d" % (len(배치), len(결과)))
    if not 배치:
        막힘.append("감독 회차가 없습니다")
        return
    if len(결과) < len(배치):
        막힘.append("판정이 %d회차 모자랍니다 (%d/%d)"
                    % (len(배치) - len(결과), len(결과), len(배치)))

    # 감독 입력의 모든 행에 답이 있는가
    입력 = 뿌리 / "s13_judge" / "judge_input.csv"
    if 입력.exists():
        with io.open(입력, encoding="utf-8-sig", newline="") as h:
            할것 = {r["atomic_id"] for r in csv.DictReader(h)}
        한것 = set()
        for p in 결과:
            for x in p.read_text(encoding="utf-8", errors="replace").splitlines():
                x = x.strip()
                if x.startswith("{") and '"verdict"' in x:
                    try:
                        j = json.loads(x)
                    except Exception:                        # noqa: BLE001
                        continue
                    if j.get("atomic_id"):
                        한것.add(j["atomic_id"])
        빠짐 = 할것 - 한것
        줄("·", "감독 입력 %d행 · 답 %d행" % (len(할것), len(한것 & 할것)))
        if 빠짐:
            막힘.append("답이 없는 행 %d개가 있습니다" % len(빠짐))


def 통합(뿌리: Path) -> None:
    """총괄 자리 — 4차로 넘어가도 되나."""
    R = 뿌리 / "_판독패키지" / "_결과"
    이름 = {}
    for p in R.glob("감독결과_*.md"):
        m = re.match(r"감독결과_[^_]+_(.+)$", p.stem)
        if m:
            이름[m.group(1)] = 이름.get(m.group(1), 0) + 1
    줄("·", "감독자 %s" % (" · ".join("%s %d회차" % x for x in 이름.items()) or "없음"))
    if len(이름) < 2:
        막힘.append("감독자가 둘이어야 합니다 — 한쪽만으로 통합하면 감독자가 무시됩니다")

    번들 = [d.name for d in _번들들(R) if d.name != "master_final"]
    줄("·", "판독 번들 %s" % (" · ".join(번들) or "없음"))
    if len(번들) < 2:
        막힘.append("2차 판독 번들 둘이 있어야 합니다")

    mf = R / "master_final"
    if not (mf / "raw_voc.csv").exists():
        알림.append("아직 통합 전입니다 — 총괄이 3차_마무리.py 를 돌립니다")
    elif not list(mf.glob("*.xlsx")):
        막힘.append("최종 xlsx 가 없습니다 — 1차 엔진(engine/)이 있는지 보십시오")

    # ★ 앞 차수 보정요청을 이어받았는가 (2026-08-23 에 3건이 사라졌다)
    req = 뿌리 / "_인계" / "보정요청.csv"
    if req.exists():
        with io.open(req, encoding="utf-8-sig", newline="") as h:
            행 = list(csv.DictReader(h))
        차수 = {re.sub(r"\s*\(.*", "", r.get("나온_회차") or "") for r in 행}
        줄("·", "보정요청 %d건 — %s" % (len(행), " · ".join(sorted(차수))))
        if not any("2차" in x for x in 차수):
            알림.append("보정요청에 2차에서 나온 것이 없습니다 — "
                        "앞 차수 파일을 _인계/ 에 놓고 다시 뽑으십시오")
    else:
        알림.append("보정요청서가 아직 없습니다 — handoff.py 를 돌리십시오")


def main() -> int:
    print("=" * 70)
    print("  넘어가도 되나 — %s" % ROOT)
    print("=" * 70)

    있음 = {
        "3차 감독": (ROOT / "s13_judge" / "judge_input.csv").exists()
                  and not list((ROOT / "_판독패키지" / "_결과")
                               .glob("감독결과_*_*.md"))[2:3],
        "통합": len(list((ROOT / "_판독패키지" / "_결과")
                       .glob("감독결과_*.md"))) > 0
                and len(_번들들(ROOT / "_판독패키지" / "_결과")) >= 2,
        "2차 판독": (ROOT / "회차배치").is_dir(),
    }
    if 있음["통합"]:
        차수, 할일 = "총괄 통합 → 4차", 통합
    elif (ROOT / "s13_judge" / "judge_input.csv").exists():
        차수, 할일 = "3차 감독 → 통합", 삼차
    elif 있음["2차 판독"]:
        차수, 할일 = "2차 판독 → 3차", 이차
    else:
        print("  이 폴더가 어느 차수인지 모르겠습니다.")
        print("  회차배치/ 또는 s13_judge/ 가 있어야 합니다.")
        return 1

    print("  이 자리 : %s" % 차수)
    print()
    할일(ROOT)
    print()

    print("=" * 70)
    if 막힘:
        print("  ★ 아직 넘어가면 안 됩니다 — %d건" % len(막힘))
        for x in 막힘:
            print("     · %s" % x)
    else:
        print("  넘어가도 됩니다.")
    if 알림:
        print()
        print("  참고 (막지는 않습니다)")
        for x in 알림:
            print("     · %s" % x)
    print("=" * 70)
    return 1 if 막힘 else 0


if __name__ == "__main__":
    sys.exit(main())
