# -*- coding: utf-8 -*-
"""우리가 가져온 것이 **옛 저장소의 마지막 상태**와 같은가 — 결정 0004 를 지킨다.

★ 왜 (sky 2026-10-23) — 「지금 skill 화 하고 있는 게 첨부한 배포 패키지랑 동일한 것이 맞는지?」
  답할 근거가 어디에도 없었다. 재 보니 그 꾸러미(2026-08-26)는 그 폴더에서 **가장 오래된 것**이었고,
  우리는 그보다 새 판(옛 저장소 마지막 상태 · 2026-09-18)을 가져왔다.
  ★ 적어만 두면 또 어긋난다. 그래서 숫자를 여기서 지킨다.

★ 옛 저장소는 **읽기만** 한다 (결정 0001 · 변화 0) — 고치지 않고 돌리지 않고 zip 도 풀지 않는다.
★ 옛 저장소가 없는 컴퓨터(받는 사람 · CI)에서는 **건너뛴다** — 거기선 확인할 것이 없다.
  다만 **문서와 코드의 숫자가 어긋나는 것**은 옛 저장소 없이도 잡는다.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
from paths import REPO, SHARED  # noqa: E402
from paths import 옛저장소 as _옛저장소  # noqa: E402

# ★ 옛 저장소 자리는 **paths.py 한 곳에서만** 정한다 (공통 규칙 6 · 2026-10-23 검사가 잡았다)
옛저장소 = _옛저장소
결정 = REPO / "docs" / "decisions" / "0004-어느-판을-기준으로-삼았나.md"
# ★ 결정 0004 에 적은 숫자. 여기와 문서가 어긋나면 실패한다
적은것 = {"기준서": (8, 8), "도구": (72, 73)}


def _지문(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _옛저장소_파일들() -> dict:
    자리: dict[str, list[Path]] = {}
    for p in 옛저장소.rglob("*"):
        if p.is_file():
            자리.setdefault(p.name, []).append(p)
    return 자리


def test_결정_0004_가_있다():
    assert 결정.is_file(), "결정 0004 가 없다 — 어느 판을 기준으로 삼았는지 적은 문서다"
    글 = 결정.read_text(encoding="utf-8")
    for 말 in ("2026-09-18", "2026-08-26", "최신판이 정본"):
        assert 말 in 글, "결정 0004 에 「%s」 가 없다" % 말


def test_문서의_숫자와_코드의_숫자가_같다():
    """★ 문서에 적은 「8/8」 · 「72/73」 이 실제 기록 파일 수와 맞는가.

    옛 저장소가 없어도 **이것은 잡는다** — 기록 파일만 보면 되기 때문이다.
    """
    글 = 결정.read_text(encoding="utf-8")
    기준서 = json.loads((SHARED / "standards" / "출처.json").read_text(encoding="utf-8"))["파일"]
    옛기준서 = sum(1 for v in 기준서.values() if v.get("원본_sha256"))
    꾸러미 = json.loads((SHARED / "출처_꾸러미.json").read_text(encoding="utf-8"))["파일"]
    옛도구 = sum(1 for v in 꾸러미.values() if v.get("원본") and v.get("원본_sha256"))
    assert 옛기준서 == 적은것["기준서"][1], (
        "옛 저장소에서 온 기준서가 %d개인데 결정 0004 는 %d개로 적었다" % (옛기준서, 적은것["기준서"][1]))
    assert 옛도구 == 적은것["도구"][1], (
        "옛 저장소에서 온 도구·안내서가 %d개인데 결정 0004 는 %d개로 적었다" % (옛도구, 적은것["도구"][1]))
    assert re.search(r"\*\*%d / %d\*\*" % 적은것["기준서"], 글), "결정 0004 의 기준서 숫자가 바뀌었다"
    assert re.search(r"\*\*%d / %d\*\*" % 적은것["도구"], 글), "결정 0004 의 도구 숫자가 바뀌었다"


@pytest.mark.skipif(not 옛저장소.is_dir(), reason="이 컴퓨터에 옛 저장소가 없다 — 확인할 것이 없다")
def test_기준서가_옛저장소_마지막_상태와_같다():
    """★ 지문으로 본다 — 「비슷하다」 가 아니라 **한 글자도 다르지 않다**."""
    판독패키지 = 옛저장소 / "_2판" / "_판독패키지"
    출처 = json.loads((SHARED / "standards" / "출처.json").read_text(encoding="utf-8"))["파일"]
    본것, 어긋남 = 0, []
    for 이름, v in 출처.items():
        if not v.get("원본_sha256"):
            continue                     # 새 판 — 옛 저장소에 없다
        원 = 판독패키지 / 이름
        assert 원.is_file(), "옛 저장소에서 %s 를 못 찾았다 — 「못 찾음」 은 통과가 아니다" % 이름
        본것 += 1
        if _지문(원) != v["원본_sha256"]:
            어긋남.append(이름)
    assert 본것 == 적은것["기준서"][1], "본 기준서가 %d개다 (적어 둔 것 %d)" % (본것, 적은것["기준서"][1])
    assert not 어긋남, ("옛 저장소의 지금 기준서와 다른 것 %d개 — %s\n"
                      "  옛 저장소가 또 바뀌었거나, 우리가 옛 판을 들고 있다. 결정 0004 를 다시 본다."
                      % (len(어긋남), 어긋남))


@pytest.mark.skipif(not 옛저장소.is_dir(), reason="이 컴퓨터에 옛 저장소가 없다 — 확인할 것이 없다")
def test_도구와_안내서가_옛저장소_마지막_상태와_같다():
    자리 = _옛저장소_파일들()
    assert 자리, "옛 저장소에서 파일을 하나도 못 읽었다 — 「못 찾음」 은 통과가 아니다"
    출처 = json.loads((SHARED / "출처_꾸러미.json").read_text(encoding="utf-8"))["파일"]
    옛것 = {k: v for k, v in 출처.items() if v.get("원본") and v.get("원본_sha256")}
    같, 어긋남, 못찾음 = 0, [], []
    for k, v in 옛것.items():
        # ★ `원본` 칸이 **파일 이름이 아닌 것**이 하나 있다 — 엔진 코드에서 뽑아 만든 문서라
        #   「…analysis_runner.py 의 해당 줄을 옮긴 것」 처럼 설명 문장이 들어 있다 (2026-10-23 실측).
        #   그래서 우리 쪽 경로(키)의 이름으로 찾는다. 설명 문장을 파일 이름으로 보면 엉뚱한 것이 걸린다.
        이름 = Path(k).name
        것 = 자리.get(이름) or []
        if not 것:
            못찾음.append(이름)
            continue
        if v["원본_sha256"] in {_지문(p) for p in 것}:
            같 += 1
        else:
            어긋남.append(이름)
    assert not 어긋남, ("옛 저장소의 지금 파일과 다른 것 %d개 — %s\n"
                      "  우리가 옛 판을 들고 있거나 옛 저장소가 또 바뀌었다." % (len(어긋남), 어긋남[:8]))
    # ★ 못 찾는 1건은 **옛 저장소 파일이 아니다** — 엔진 코드에서 뽑아 만든 문서다.
    #   그보다 많아지면 「어디서 온 것인지 모르는 파일」 이 늘었다는 뜻이다.
    assert len(못찾음) <= 1, "옛 저장소에서 못 찾는 것이 %d개로 늘었다 — %s" % (len(못찾음), 못찾음[:5])
    if 못찾음:
        assert 못찾음 == ["99_1차_실행조건_원문.md"], "못 찾는 것이 바뀌었다 — %s" % 못찾음
    assert 같 == 적은것["도구"][0], (
        "옛 저장소와 같은 것이 %d개다 (결정 0004 는 %d개로 적었다)" % (같, 적은것["도구"][0]))


@pytest.mark.skipif(not 옛저장소.is_dir(), reason="이 컴퓨터에 옛 저장소가 없다")
def test_배포_꾸러미가_그_폴더에서_가장_오래됐다():
    """★ 결정 0004 의 뿌리 — 꾸러미가 최신이 아니라는 사실.

    꾸러미보다 새 파일이 **하나라도** 있으면 「꾸러미 = 최신」 이 아니다.
    """
    배포 = 옛저장소 / "_2판" / "_배포"
    zip들 = sorted(배포.glob("VoC_*.zip"))
    assert zip들, "옛 저장소에서 배포 꾸러미를 못 찾았다"
    꾸러미때 = max(p.stat().st_mtime for p in zip들)
    더새것 = [p for p in (옛저장소 / "_2판").rglob("*")
            if p.is_file() and p.stat().st_mtime > 꾸러미때]
    assert 더새것, ("꾸러미보다 새 파일이 하나도 없다 — 결정 0004 의 전제가 깨졌다. "
                  "꾸러미가 정말 마지막 상태라면 결정 0004 를 다시 쓴다.")
