# -*- coding: utf-8 -*-
"""1차 분석 엔진을 옛 live_merge 동결본에서 한 번 들여온다 (섹션 7 ① · sky 2026-09-22 「옛 live_merge 동결본」).

★ 한 번만 쓴다 — 다른 가져오기 도구(옛꾸러미_가져오기*.py)와 같다. 들여온 뒤 원본 한 벌은 `plugin/engine/` 이다.
★ 옛 저장소는 **읽기만** 한다 — `git archive` 는 옛 저장소에 아무것도 쓰지 않는다 (섹션 2 에서도 이렇게 했다).

원본
    옛 live_merge 작업 폴더 (명령 인자로 받는다)  갈래 codex/voc-engine-rebuild  커밋 a94e731 (2026-09-18)
    = 엔진 동결 d78dc8c (2026-08-13) 과 엔진 코드가 같다 + 대시보드 09-07 최신판(72ed050) + logger · secret_filter
    얼린 기준(섹션 2 · 3차)도 이 커밋의 src/ 로 만들었다 (기준 자리 engine/).

들여오는 것
    src/ 전부 — 단 옛 대시보드 판 · 쓰지 않는 텍스트마이닝은 뺀다(아래 「뺀다」). 1차 입구(src.cli)와 대시보드 입구
        (src.dashboard60.app_operating)에서 실제로 불러 쓰는 파일을 코드로 따라가 확인했다 — 빼는 것은 어느 입구에서도 안 닿는다.
    voc-classifier/src/classifier.py — comment_truth 가 파일 이름으로 불러 쓴다 (없으면 건너뛰어 결과가 달라진다)
    config/ · fonts/ · requirements.txt · pyproject.toml · .env.example · streamlit_app.py

남기는 것 (옛 판독 꾸러미 엔진에만 있던 것 — 옛 저장소 90078f1 의 outputs/voc_secondary/engine)
    src/voc_secondary/ (2차 계약 · N/A 규칙 — 번들 · 3차 도구가 부른다) · src/voc_rebuild/config/__init__.py ·
    「0_이 폴더는 무엇입니까.md」 (판독 · 감독 폴더의 engine/ 안내문)

고치는 것 (결정 0001 — 코드에 옛 경로가 남으면 결함)
    src/dashboard60/app_operating.py 의 옛 저장소 경로 대비책 한 줄

쓰기
    python tools/엔진_가져오기.py <옛 live_merge 작업 폴더>     plugin/engine/ 을 새로 만든다 (지금 것은 지운다)
"""
from __future__ import annotations

import hashlib
import io
import re
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
엔진 = REPO / "plugin" / "engine"
커밋 = "a94e731"
가져올것 = ["src", "voc-classifier/src/classifier.py", "config", "fonts", "requirements.txt", "pyproject.toml",
         ".env.example", "streamlit_app.py"]
뺀다 = {  # 어느 입구에서도 안 닿는다 (2026-09-22 정적 추적) — 옛 대시보드 판 · 텍스트마이닝
    "src/dashboard_app.py": "옛 대시보드 (1만 5천 줄 · 옛 사용자 폴더 경로가 박혀 있다)",
    "src/dashboard_v2.py": "옛 대시보드 판", "src/dashboard_v3.py": "옛 대시보드 판",
    "src/dashboard_v5_page.py": "옛 대시보드 판", "src/dashboard_strategy_page.py": "옛 대시보드 판",
    "src/dashboard_text_mining.py": "옛 대시보드 판", "src/dashboard_text_mining_page.py": "옛 대시보드 판",
    "src/dashboard_rules.py": "옛 대시보드 판", "src/dashboard_ui_contracts.py": "옛 대시보드 판",
}
뺀다_폴더 = {"src/text_mining": "쓰지 않는 텍스트마이닝 (옛 대시보드만 불렀다)"}
바이트그대로 = {".ttf", ".otf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".xlsx", ".docx", ".zip", ".pdf", ".pkl"}
남길것 = ["0_이 폴더는 무엇입니까.md", "src/voc_secondary/__init__.py", "src/voc_secondary/contracts.py",
        "src/voc_secondary/na_rules.py", "src/voc_rebuild/config/__init__.py"]
고칠것 = {
    "src/dashboard60/app_operating.py": (
        r'Path\(r"[A-Za-z]:/.*master_final/편향검사\.csv',   # 드라이브 글자로 시작하는 절대경로 줄 하나 (옛 저장소 폴더 대비책)
        "옛 저장소 경로 대비책 한 줄을 지웠다 (결정 0001). 편향검사.csv 를 찾는 다른 후보는 그대로다.",
    ),
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    옛자리 = Path(sys.argv[1])
    if not (옛자리 / ".git").exists():
        print("  ✗ 옛 자리를 못 찾았습니다 — %s" % 옛자리)
        return 2
    옛남길것 = {n: (엔진 / n).read_bytes() for n in 남길것}
    옛출처 = json.loads((REPO / "plugin" / "shared" / "출처_꾸러미.json").read_text(encoding="utf-8"))["파일"]
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(옛자리), "archive", "--format=tar", 커밋, *가져올것],
                       capture_output=True)
    if r.returncode:
        print(r.stderr.decode("utf-8", "replace"))
        return 1
    기록 = {"설명": "plugin/engine/ 의 출처 — 1차 분석 엔진 한 벌 (섹션 7 ①). tools/엔진_가져오기.py 가 만들었다.",
          "원본_자리": "옛 저장소 github.com/skycloud-maker/youtube-comment-analyzer 의 live_merge 작업 폴더 "
                     "(갈래 codex/voc-engine-rebuild @ %s — 엔진 코드는 동결 d78dc8c 와 같다 · 대시보드 09-07)" % 커밋,
          "들여온_날": "2026-09-22", "sky 결정": "2026-09-22 「옛 live_merge 동결본」 을 엔진 정본으로",
          "뺀_것": {**뺀다, **{k + "/": v for k, v in 뺀다_폴더.items()}},
          "고칠_때": "고치면 tests/test_engine.py 가 실패한다 — 이유를 `고친_이력` 에 적고 `지금_sha256` 을 갱신한다.",
          "파일": {}}
    쓸것: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            if m.name in 뺀다 or any(m.name.startswith(d + "/") for d in 뺀다_폴더):
                continue
            b = tf.extractfile(m).read()
            원본해시 = _sha(b)
            이력 = []
            # 글 파일은 줄바꿈만 LF 로 (저장소 .gitattributes · 다른 출처 기록과 같은 방식) — 글자는 그대로
            if Path(m.name).suffix.lower() not in 바이트그대로:
                b = b.replace(b"\r\n", b"\n")
            if m.name in 고칠것:
                무늬, 왜 = 고칠것[m.name]
                줄들 = b.decode("utf-8").splitlines(keepends=True)
                걸린 = [x for x in 줄들 if re.search(무늬, x)]
                assert len(걸린) == 1, "고칠 줄을 하나로 못 찾았다 — %s" % m.name
                b = "".join(x for x in 줄들 if x not in 걸린).encode("utf-8")
                이력.append("2026-09-22 " + 왜)
            쓸것[m.name] = b
            기록["파일"][m.name] = {"원본": "%s:%s" % (커밋, m.name), "원본_sha256": 원본해시,
                                  "지금_sha256": _sha(b), "고친_이력": 이력}
    # ★ 여기까지 다 읽고 확인했다 — 이제야 지우고 쓴다
    shutil.rmtree(엔진)
    for n, b in list(쓸것.items()) + list(옛남길것.items()):
        p = 엔진 / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    for n, b in 옛남길것.items():
        옛 = 옛출처.get("plugin/engine/" + n, {})
        기록["파일"][n] = {"원본": "90078f1:outputs/voc_secondary/engine/" + n, "원본_sha256": 옛.get("원본_sha256"),
                         "지금_sha256": _sha(b), "고친_이력": 옛.get("고친_이력", []),
                         "까닭": "옛 판독 꾸러미 엔진에만 있던 것 — 2차 도구가 부른다 (live_merge 에는 없다)"}
    (엔진 / "출처_엔진.json").write_text(json.dumps(기록, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                    newline="\n")
    print("  · 엔진 %d개 (옛 꾸러미에서 남긴 것 %d개 포함) · 뺀 것 %d개 + 폴더 %d" % (
        len(기록["파일"]), len(옛남길것), len(뺀다), len(뺀다_폴더)))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
