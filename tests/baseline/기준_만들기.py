# -*- coding: utf-8 -*-
"""기준 정답을 한 번 만든다 — 옛 2판 도구의 **사본**을 저장소 밖 기준 자리에서 돌린다.

★ 결정 0002 (sky 2026-09-18): 옛 결과 파일은 그 뒤 코드가 바뀌고 사람이 고쳐 써서
  기준으로 못 쓴다. 그래서 옛 도구(최신판)와 입력을 복사해 **사본을** 돌리고,
  그 결과를 기준 정답으로 얼린다. 옛 폴더는 복사만 했고 여기서는 읽지도 않는다.

★ 옛 폴더를 막는 것
  - 엔진은 VOC_ENGINE 으로 사본(기준자리/engine)을 가리킨다.
    옛 도구는 이것이 없을 때만 옛 엔진 자리로 간다.
  - PYTHONDONTWRITEBYTECODE=1 — 어디에도 캐시를 쓰지 않는다.
  - 돌리기 전·후 옛 폴더 상태 대조는 따로 한다 (진행 기록 참고).

★ 두 번씩 돌린다 — 두 번이 다른 자리는 기준에서 빼야 하므로 먼저 안다.

쓰기
    python tests/baseline/기준_만들기.py            없는 실행만 만든다
기준 자리의 `실행/` 아래에 이미 있는 것은 덮지 않는다 (얼린 기준을 지키려고).
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

원본 = BASELINE / "원본사본" / "2판"
엔진 = BASELINE / "engine"

# 도구가 **만들어 낼** 것 — 돌리기 전 상태로 되돌리려고 사본에서 뺀다 (2판 기준 상대경로)
_공통제외 = [
    "s15_master",
    "_판독패키지/_결과/master_final",
    "_판독패키지/_결과/분리재지정_01_총괄확정.md",   # 08-26 17:05 — 통합(09:47) 뒤에 생김
    "_최종결과",
    "_인계/편향검사.md",
    "_인계/보정요청_논의본.md",
    "0_결과는_어디_있나.md",
    "_라벨바꾸기전_*",       # 08-26 16:59 백업 — 두 실행 뒤에 생겼고 raw_voc.csv 가 있어 2차 번들로 잡힌다
    "__pycache__",
]
실행들 = {
    # 3차_준비 (원래 08-25 23:08) — 2차 번들 둘 → 갈린 행 · 익명화 · 회차 · 감독 폴더
    "3차준비": ("3차_준비.py", _공통제외 + [
        "s13_judge", "_총괄만", "_감독폴더",
        "_판독패키지/_결과/감독결과_*.md",
    ]),
    # 3차_마무리 (원래 08-26 09:47) — 감독결과 28개 + 매핑 → 통합 ~ _최종결과
    "3차마무리": ("3차_마무리.py", _공통제외),
    # 번들_마무리꾸미기 (섹션 7 · 2026-10-08) — 3차_마무리 가 낸 최종 번들을 사람이 보기 좋게 다듬는다.
    #   ★ 혼자 돌 수 없다 — 꾸밀 번들이 있어야 하므로 **3차_마무리 를 먼저 돌리고** 이어서 돌린다.
    #   그래서 도구 자리에 목록을 둘 수 있게 넓혔다.
    "번들꾸미기": (["3차_마무리.py", "번들_마무리꾸미기.py"], _공통제외),
    # 4차_반영 (섹션 7 · 2026-10-08) — 3차 결과에 4차 결정을 반영하고 최종 번들까지 다시 만든다.
    #   ★ 사본의 사람 결정(분리제안 승인 · 총괄검수 판정)은 **비어 있다** — 그래도 도구가 도는 길
    #   (분리 반영 · 묶음 맞추기 · xlsx 다시 · 우선순위 · PL 이슈 · 시트 붙이기)은 그대로 탄다.
    #   그 길이 바뀌면 드러나는 것이 이 기준의 쓸모다. 사람 결정이 든 판은 나중에 따로 얼린다.
    #   ★ `폐기라벨_정리` 를 **먼저** 돌린다 — 없이 돌리면 4차_반영 이 ⓪-2 묶음 맞추기 에서 멈춘다
    #     (매핑에 없는 라벨 `구매의사/이탈` 440행 · `위생/냄새(곰팡이)` 44행 · 2026-10-08 확인).
    #     2판 실제 흐름도 그 순서였다 (sky 2026-08-26 「구매의사/이탈 → 구매의사」).
    "4차반영": (["3차_마무리.py", "폐기라벨_정리.py", "4차_반영.py"], _공통제외),
}


def _뺄것(제외: list[str]):
    def ignore(dirpath: str, names: list[str]) -> set[str]:
        rel = Path(dirpath).relative_to(원본).as_posix()
        rel = "" if rel == "." else rel + "/"
        return {n for n in names
                if any(fnmatch.fnmatch(rel + n, pat) for pat in 제외)}
    return ignore


def 한번(이름: str, 번: int) -> int:
    그릇 = BASELINE / "실행" / ("%s_%d" % (이름, 번))
    if 그릇.exists():
        print("  · %s — 이미 있어 건너뜁니다 (얼린 기준은 덮지 않습니다)" % 그릇.name)
        return 0
    return 차려서_돌리기(이름, 그릇)


def 차려서_돌리기(이름: str, 그릇: Path) -> int:
    """`그릇/2판` 에 돌리기 전 상태를 차리고 도구를 돌린다. 시험도 이것을 쓴다.

    ★ 그릇의 부모에는 다른 2판이 없어야 한다 — 도구가 부모 폴더까지 뒤진다.
    """
    도구, 제외 = 실행들[이름]
    도구들 = [도구] if isinstance(도구, str) else list(도구)      # 차례로 둘 이상도 받는다
    뿌리 = 그릇 / "2판"
    shutil.copytree(원본, 뿌리, ignore=_뺄것(제외))
    env = dict(os.environ, VOC_ENGINE=str(엔진), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    적을것, 마지막코드 = [], 0
    for 도구이름 in 도구들:
        r = subprocess.run([sys.executable, "-B", str(뿌리 / 도구이름)], cwd=str(뿌리),
                           env=env, text=True, encoding="utf-8", errors="replace",
                           capture_output=True)
        적을것.append("도구: %s\n종료코드: %d\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
                    % (도구이름, r.returncode, r.stdout, r.stderr))
        마지막코드 = r.returncode
        if r.returncode:
            break                                            # 앞이 실패하면 뒤를 돌리지 않는다
    (그릇 / "실행기록.txt").write_text("\n".join(적을것), encoding="utf-8")
    print("  · %s — 종료코드 %d (도구 %d개)" % (그릇.name, 마지막코드, len(적을것)))
    return 마지막코드


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for 자리, 뜻 in ((원본, "옛 2판 사본"), (엔진 / "src" / "voc_rebuild", "엔진 사본")):
        if not 자리.is_dir():
            print("  ✗ %s 을 못 찾았습니다 — %s" % (뜻, 자리))
            return 1
    if "codex" in str(BASELINE).lower():
        print("  ✗ 기준 자리가 옛 폴더 안입니다 — %s" % BASELINE)
        return 1
    나쁨 = 0
    for 이름 in 실행들:
        for 번 in (1, 2):
            나쁨 |= 한번(이름, 번) != 0
    return 1 if 나쁨 else 0


if __name__ == "__main__":
    sys.exit(main())
