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
    scripts/ 두 개 (2026-10-07 더함) — run_dashboard60_youtube_collect_and_analyze.py(1차 수집·분석) ·
        run_voc_rebuild_dashboard.py. 이 둘은 import 가 아니라 글자 경로로 subprocess 로 불려(analysis_runner.py:683 · 727)
        import 를 따라가는 방식으로는 안 잡혔다. 옛 scripts/ 의 나머지 79개는 아무도 부르지 않아 가져오지 않는다.

남기는 것 (옛 판독 꾸러미 엔진에만 있던 것 — 옛 저장소 90078f1 의 outputs/voc_secondary/engine)
    src/voc_secondary/ (2차 계약 · N/A 규칙 — 번들 · 3차 도구가 부른다) · src/voc_rebuild/config/__init__.py ·
    「0_이 폴더는 무엇입니까.md」 (판독 · 감독 폴더의 engine/ 안내문)

고치는 것 (결정 0001 — 코드에 옛 경로가 남으면 결함)
    src/dashboard60/app_operating.py 의 옛 저장소 경로 대비책 한 줄

쓰기
    python tools/엔진_가져오기.py <옛 live_merge 작업 폴더> <nlp_analyzer 저장소>
        plugin/engine/ 을 새로 만든다 (지금 것은 지운다). 출처 둘 다 **읽기만** 한다.
        둘 다 자리를 명령 인자로 받는다 — 코드에 박지 않는다 (결정 0001).
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
         ".env.example", "streamlit_app.py",
         # ★ 2026-10-07 더함 — 이 둘은 import 가 아니라 **글자 경로로 subprocess** 로 불린다
         #   (src/dashboard60/analysis_runner.py:683 · 727 의 `ROOT / "scripts" / ...`).
         #   그래서 import 를 따라가는 방식으로는 안 잡혀 1차 실행 경로가 빠져 있었다.
         #   둘이 부르는 src.* 는 모두 이미 들어와 있다 (src.api.quota · src.cli · src.voc_rebuild.engine ·
         #   src.dashboard60.export_bundle). 시험 `test_글자경로로_부르는_파일이_다_있다` 가 다시 빠지면 잡는다.
         "scripts/run_dashboard60_youtube_collect_and_analyze.py",   # 1차 — 유튜브 수집 + 분석
         "scripts/run_voc_rebuild_dashboard.py"]                     # 이미 모은 자료로 다시 분석
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
# ★ 두 번째 출처 — nlp_analyzer (2026-10-07 sky 결정 「엔진처럼 동결 사본으로 들여온다」)
#   왜 — 1차가 `from nlp_analyzer import ...` 로 쓰는데(src/analytics/sentiment.py:18~21) 그 꾸러미는 이 저장소가 아니라
#   **다른 저장소**에 있고 requirements.txt 에도 없었다. `try/except ImportError` 라 없어도 돌지만 enrichment 칸이 비어
#   **다른 PC 에서 조용히 다른 결과**가 난다. 엔진 안(plugin/engine/nlp_analyzer/)에 두면 `import nlp_analyzer` 가
#   엔진 자리에서 먼저 잡힌다 (1차 스크립트가 ROOT 를 sys.path 맨 앞에 넣는다).
#   가져오는 것은 1차가 실제로 닿는 파일만 — import 를 코드로 따라가 뽑은 8개 + 꾸러미 입구 providers/__init__.py.
nlp커밋 = "ab8ea8c"
nlp자리 = "nlp_analyzer"                       # 엔진 안에 놓는 자리
nlp가져올것 = ["__init__.py", "analyzer.py", "models.py", "prompts.py", "router.py",
           "providers/__init__.py", "providers/base.py", "providers/claude.py", "providers/openai.py",
           # ★ 처음에 「시험용 가짜 provider」 라고 뺐다가 되돌렸다 (2026-10-07) — providers/__init__.py 가
           #   `from .mock import ...` 로 부른다. 빠지면 analyzer.py 의 `from .models import ...` 가 ImportError 로
           #   떨어져 대비 가지(`from models import ...`)로 갔다가 거기서 터진다. 「안 부른다」 는 내 짐작이었다.
           "providers/mock.py"]
nlp뺀다 = {
    "app.py": "streamlit 데모 — 1차가 부르지 않는다", "debug_api.py": "손시험용",
    "run_golden.py": "그 저장소의 시험 돌리개", "run_test.py": "그 저장소의 시험 돌리개",
    "tests/": "그 저장소의 시험",
    ".env": "★ 키가 든 파일 — 저장소에 넣지 않는다 (게다가 ANTHROPIC_API_KEY 값이 한글 자리표시자다)",
    "env.example": "키 보기 — 이 저장소는 Windows 사용자 환경변수를 쓴다",
    "pyproject.toml": "그 저장소의 꾸러미 설정", "README.md": "그 저장소의 안내",
}
고칠것 = {
    "src/dashboard60/app_operating.py": (
        r'Path\(r"[A-Za-z]:/.*master_final/편향검사\.csv',   # 드라이브 글자로 시작하는 절대경로 줄 하나 (옛 저장소 폴더 대비책)
        "옛 저장소 경로 대비책 한 줄을 지웠다 (결정 0001). 편향검사.csv 를 찾는 다른 후보는 그대로다.",
    ),
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _tar읽기(자리: Path, 커밋: str, 가져올것: list[str]) -> dict[str, bytes]:
    """옛 자리에서 `git archive` 로 **읽기만** 한다 (그 저장소는 고치지 않는다)."""
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(자리), "archive", "--format=tar", 커밋, *가져올것],
                       capture_output=True)
    if r.returncode:
        raise SystemExit(r.stderr.decode("utf-8", "replace"))
    out = {}
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        for m in tf.getmembers():
            if m.isfile():
                out[m.name] = tf.extractfile(m).read()
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    옛자리 = Path(sys.argv[1])
    nlp옛자리 = Path(sys.argv[2])
    for 자리 in (옛자리, nlp옛자리):
        if not (자리 / ".git").exists():
            print("  ✗ 옛 자리를 못 찾았습니다 — %s" % 자리)
            return 2
    # ★ nlp_analyzer 도 먼저 읽어 둔다 — 지우기 전에 다 읽는다 (2026-09-22 에 반쯤 지워진 적이 있다)
    nlp쓸것 = _tar읽기(nlp옛자리, nlp커밋, nlp가져올것)
    없음 = [n for n in nlp가져올것 if n not in nlp쓸것]
    if 없음:
        print("  ✗ nlp_analyzer 에서 못 찾은 파일 — %s" % 없음)
        return 2
    # 「남길 것」 은 지금 엔진 폴더에서 읽는다. 다만 앞선 실행이 중간에 터져 폴더가 비어 있을 수 있으니
    # 그때는 **이 저장소의 커밋**에서 읽는다 (2026-10-07 에 실제로 그 상태가 됐다).
    옛남길것 = {}
    for n in 남길것:
        p = 엔진 / n
        if p.is_file():
            옛남길것[n] = p.read_bytes()
            continue
        r = subprocess.run(["git", "--no-optional-locks", "-C", str(REPO), "show",
                            "HEAD:plugin/engine/" + n], capture_output=True)
        if r.returncode:
            print("  ✗ 남길 것을 못 찾았습니다 (폴더에도, 커밋에도) — %s" % n)
            return 2
        옛남길것[n] = r.stdout
    옛출처 = json.loads((REPO / "plugin" / "shared" / "출처_꾸러미.json").read_text(encoding="utf-8"))["파일"]
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(옛자리), "archive", "--format=tar", 커밋, *가져올것],
                       capture_output=True)
    if r.returncode:
        print(r.stderr.decode("utf-8", "replace"))
        return 1
    기록: dict = {"설명": "plugin/engine/ 의 출처 — 1차 분석 엔진 한 벌 (섹션 7 ①). tools/엔진_가져오기.py 가 만들었다.",
          "원본_자리": "옛 저장소 github.com/skycloud-maker/youtube-comment-analyzer 의 live_merge 작업 폴더 "
                     "(갈래 codex/voc-engine-rebuild @ %s — 엔진 코드는 동결 d78dc8c 와 같다 · 대시보드 09-07)" % 커밋,
          "들여온_날": "2026-09-22", "sky 결정": "2026-09-22 「옛 live_merge 동결본」 을 엔진 정본으로",
          "두_번째_원본": "nlp_analyzer (github.com/skycloud-maker 의 별도 저장소 @ %s) → %s/ · "
                      "1차가 import 로 닿는 파일만. sky 2026-10-07 「엔진처럼 동결 사본으로 들여온다」" % (nlp커밋, nlp자리),
          "뺀_것": {**뺀다, **{k + "/": v for k, v in 뺀다_폴더.items()},
                  **{nlp자리 + "/" + k: v for k, v in nlp뺀다.items()}},
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
    # nlp_analyzer — 글 파일이므로 줄바꿈만 LF 로 (글자는 그대로)
    for n, b in nlp쓸것.items():
        원본해시 = _sha(b)
        b2 = b.replace(b"\r\n", b"\n")
        자리이름 = nlp자리 + "/" + n
        쓸것[자리이름] = b2
        기록["파일"][자리이름] = {"원본": "nlp_analyzer %s:%s" % (nlp커밋, n), "원본_sha256": 원본해시,
                             "지금_sha256": _sha(b2), "고친_이력": [],
                             "까닭": "1차가 import 로 쓴다 (src/analytics/sentiment.py) — 다른 저장소에 있던 것을 들여왔다"}
    # ★ 여기까지 다 읽고 확인했다 — 이제야 지우고 쓴다
    # ★ 폴더는 지우지 않고 **파일만** 지운다 (2026-10-07) — 어떤 프로세스의 현재 폴더면 Windows 가 rmdir 을 거부한다.
    #   `shutil.rmtree(엔진)` 은 「안은 다 지우고 뿌리에서」 터져 엔진을 빈 폴더로 남겼다(커밋이 있어 git restore 로 되살렸다).
    #   빈 폴더가 남는 것은 해롭지 않다 — 곧 그 자리에 다시 쓰고, 출처 기록은 파일만 센다.
    for p in sorted(엔진.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_file():
            p.unlink()
    for p in sorted(엔진.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass            # 누군가의 현재 폴더 — 비었으면 그대로 두고 다시 쓴다
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
    print("  · 엔진 %d개 (옛 꾸러미에서 남긴 것 %d개 · nlp_analyzer %d개 포함) · 뺀 것 %d개 + 폴더 %d" % (
        len(기록["파일"]), len(옛남길것), len(nlp쓸것), len(뺀다), len(뺀다_폴더)))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
