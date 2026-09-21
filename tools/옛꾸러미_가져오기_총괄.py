# -*- coding: utf-8 -*-
"""총괄 재료를 최신판으로 한 번 복사해 온다 — 섹션 5 (2026-09-21).

★ 무엇을 — 매 판 총괄 입구(3차_준비 · 감독쪽지_만들기 · 3차_마무리 · 번들_마무리꾸미기 · 4차_반영)에서
  닿는 도구 가운데 plugin/shared/tools/ 에 아직 없는 18개 + 공통/어휘.json.
★ 옛 저장소 관리 도구 5개(마무리_이력정리 · 정본_맞추기 · make_zip · 박힌말_검사 · 5차기준_검사)는
  sky 결정(2026-09-21 「새 방식으로 대신한다」)대로 **도구로는 넣지 않고** 원문을 docs/sources/옛관리도구/ 에
  기록으로만 둔다. 그 일은 새 저장소가 맡는다 (쌍둥이 → tests/test_shared.py · 꾸러미 → 스킬 차리기 · 섹션 6 조립 ·
  커밋·진행 기록 → 저장소 절차 · 박힌말/5차기준 검사 → tests/ 로 옮길 것).
★ 옛 자리를 **읽기만** 한다. 원본은 모두 커밋된 상태(90078f1)이고 원본 자리와 2판 사본이 같은 내용이다.
★ 고친 것 두 곳 — 까닭은 `고친_이력` 에 적는다
  ① 그룹_맞추기.py — 옛 저장소 대장을 대비책으로 읽던 경로 한 줄을 지웠다 (결정 0001)
  ② 4차_반영.py — 마지막 「이력」 단계가 옛 관리 도구 4개를 불렀다. 새 저장소에는 없어 늘 「막혔습니다」 로 끝나므로,
     그 단계는 「새 저장소가 맡는다」 는 안내만 내고 통과하게 했다 (sky 결정)

쓰기
    python tools/옛꾸러미_가져오기_총괄.py <옛 voc_secondary 자리>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import PLUGIN, REPO, SHARED  # noqa: E402

새도구 = ["3차_준비.py", "감독쪽지_만들기.py", "3차_마무리.py", "build_master.py", "make_judge_input.py",
        "총괄검수.py", "PL이슈_뽑기.py", "차례_만들기.py", "사람이볼목록_채우기.py", "번들_마무리꾸미기.py",
        "번들_색칠하기.py", "데이터안내_만들기.py", "4차_반영.py", "그룹_맞추기.py", "폐기라벨_정리.py",
        "아무도_안채우는칸_검사.py", "apply_sky.py", "apply_split.py"]
옛관리도구 = ["마무리_이력정리.py", "정본_맞추기.py", "make_zip.py", "박힌말_검사.py", "5차기준_검사.py"]

고침 = {
    # 그룹_맞추기.py 는 줄 모양으로 고친다 (아래 _그룹_고치기) — 옛 경로 글자를 이 도구에 적지 않으려고
    "4차_반영.py": (
        '''def _이력() -> tuple[int, str]:
    말 = []
    나쁨 = 0''',
        '''def _이력() -> tuple[int, str]:
    # ★ 새 저장소에서는 이 단계를 저장소가 맡는다 (sky 2026-09-21 「새 방식으로 대신한다」).
    #   옛 관리 도구 4개(정본_맞추기 · 박힌말_검사 · 5차기준_검사 · make_zip)는 옛 저장소 구조를 전제로 해서
    #   여기 없다. 부르면 늘 「못 찾았습니다」 로 막혀, 반영을 다 해 놓고도 「막혔습니다」 로 끝났다.
    #   원문은 저장소 docs/sources/옛관리도구/ 에 기록으로 있다.
    return 0, ("     이력 맞추기는 새 저장소가 맡습니다 — 쌍둥이 문서는 저장소 시험(test_shared),\\n"
               "     꾸러미는 스킬의 폴더 차리기, 커밋·진행 기록은 저장소 절차가 합니다.")
    말 = []
    나쁨 = 0''',
        "2026-09-21 섹션 5 — 마지막 「이력」 단계가 옛 관리 도구 4개를 불렀다. 새 저장소에는 없어 늘 막혔으므로 "
        "「새 저장소가 맡는다」 안내만 내고 통과하게 했다 (sky 결정 「새 방식으로 대신한다」). 뒤의 옛 코드는 지우지 않고 남겼다."),
}


def _그룹_고치기(t: str) -> str:
    """_매핑() 의 찾는 차례에서 세 번째 자리(옛 저장소의 s9_group)를 뺀다.

    원문은 `ROOT / s9_group` · `ROOT.parent / s9_group` 다음에 옛 저장소 절대경로 두 줄이 이어진다.
    그 두 줄을 줄 모양(`Path(r"` 로 시작 · `topic_group_map.json"))` 로 끝)으로 찾아 지우고,
    앞 줄의 끝을 `):` 로 닫는다.
    """
    줄 = t.split("\n")
    i = next(k for k, x in enumerate(줄) if x.strip().startswith('ROOT.parent / "s9_group" / "topic_group_map.json"'))
    assert 줄[i + 1].strip().startswith('Path(r"') and 줄[i + 2].strip().endswith('topic_group_map.json")):'), "모양이 다르다"
    줄[i] = 줄[i].rstrip().rstrip(",") + "):"
    del 줄[i + 1:i + 3]
    return "\n".join(줄)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    옛 = Path(sys.argv[1])
    기록p = SHARED / "출처_꾸러미.json"
    기록 = json.loads(기록p.read_text(encoding="utf-8"))
    for 이름, 새, 원 in ([(n, SHARED / "tools" / n, n) for n in 새도구]
                        + [("어휘.json", SHARED / "common" / "어휘.json", "공통/어휘.json")]):
        자리 = 새.relative_to(REPO).as_posix()
        if 자리 in 기록["파일"]:
            print("  이미 있어 건너뜀 — %s" % 자리)
            continue
        raw = (옛 / 원).read_bytes()
        body = raw.replace(b"\r\n", b"\n")
        이력 = []
        if 이름 in 고침:
            a, b, 까닭 = 고침[이름]
            t = body.decode("utf-8")
            assert t.count(a) == 1, (이름, "고칠 자리를 못 찾았다")
            body = t.replace(a, b).encode("utf-8")
            이력.append(까닭)
        if 이름 == "그룹_맞추기.py":
            body = _그룹_고치기(body.decode("utf-8")).encode("utf-8")
            이력.append("2026-09-21 섹션 5 — 옛 저장소 대장을 대비책으로 읽던 경로 한 줄을 지웠다 (결정 0001). "
                      "이 판 안 · 위 폴더만 본다.")
        새.parent.mkdir(parents=True, exist_ok=True)
        새.write_bytes(body)
        기록["파일"][자리] = {"원본": 원, "원본_sha256": hashlib.sha256(raw).hexdigest(),
                            "지금_sha256": hashlib.sha256(body).hexdigest(), "고친_이력": 이력,
                            "복사한_날": "2026-09-21"}
        print("  옮김 — %s%s" % (자리, "  (고침)" if 이력 else ""))
    기록p.write_text(json.dumps(기록, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    # 옛 관리 도구 — 기록으로만 (원문 그대로 · 줄바꿈만 LF)
    기록자리 = REPO / "docs" / "sources" / "옛관리도구"
    기록자리.mkdir(parents=True, exist_ok=True)
    출처 = {"설명": "옛 저장소 관리 도구 5개의 원문 — 기록이다. 새 저장소에서 돌리지 않는다 (sky 2026-09-21 「새 방식으로 대신한다」).",
            "원본_자리": "옛 저장소 github.com/skycloud-maker/youtube-comment-analyzer 의 outputs/voc_secondary (90078f1)",
            "파일": {}}
    for n in 옛관리도구:
        raw = (옛 / n).read_bytes()
        (기록자리 / n).write_bytes(raw.replace(b"\r\n", b"\n"))
        출처["파일"][n] = hashlib.sha256(raw).hexdigest()
        print("  기록 — docs/sources/옛관리도구/%s" % n)
    (기록자리 / "출처.json").write_text(json.dumps(출처, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
