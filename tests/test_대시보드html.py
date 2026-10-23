# -*- coding: utf-8 -*-
r"""대시보드 HTML 한 장이 **엔진과 같은 숫자**를 담는가 (여섯 번째 스킬 · 2026-10-22).

★ 왜 이 파일이 생겼나
  2026-10-21 Codex 교차점검이 숫자 어긋남 17건을 짚었다. 내 자기검사는 그때 **초록불**이었다 —
  담아 둔 정답이 적어서 틀린 화면을 통과시켰다. 그래서 정답을 늘렸고, 이 시험은 그 정답이
  **실제로 담기는지**와 「값을 치우다 자료가 깨지지 않는지」 를 기계로 지킨다.

★ 가장 크게 물렸던 자리 — 개인정보를 치우는 무늬를 **다 만들어진 JSON 글자**에 댔더니
  링크 무늬 `https?://\S+` 가 공백까지 JSON 문법을 먹어 **행이 120개 사라졌다**
  (2판 6,846행 → 6,726행). 화면의 자기검사가 126건으로 잡았지만, 50행짜리 작은 번들에서는
  먹힌 자리가 행 경계를 안 넘어 **우연히 통과**했다. 작은 자료로만 봤으면 못 찾았다.
  그래서 이 시험은 **URL 뒤에 공백과 한글이 오는 행**을 일부러 만든다.

★ 엔진이 없으면 건너뛰지 않고 **실패**한다 — 「못 찾음」 은 「없음」 이 아니다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
_스킬 = _뿌리 / "plugin" / "skills" / "showing-voc-dashboard"
_엔진 = _뿌리 / "plugin" / "engine"
_만들개 = _스킬 / "scripts" / "대시보드_HTML_만들기.py"

pytest.importorskip("pandas", reason="pandas 가 없으면 대시보드 자체가 못 돈다")

_자료 = re.compile(r"window\.__VOC__=(\{.*?\});</script>", re.S)


def _칸들() -> list[str]:
    sys.path.insert(0, str(_스킬 / "scripts"))
    import 자료_담기                                           # noqa: PLC0415
    return list(자료_담기.담을칸)


def _밑id(i: int) -> str:
    """유튜브 댓글 id 와 **같은 꼴**. 7행은 6행과 같은 댓글의 둘째 조각이다."""
    return "Ugz6w2UmZgOaWpFs1qN%03dAaABAg" % (6 if i == 7 else i)


def _시험표(자리: Path, 행수: int = 12) -> Path:
    """작은 CSV 하나 — ★ URL 뒤에 **공백과 한글**이 오는 칸을 일부러 둔다."""
    칸 = _칸들()
    길 = 자리 / "raw_voc.csv"
    머리 = ",".join(칸)
    줄들 = [머리]
    for i in range(행수):
        값 = []
        for c in 칸:
            if c == "status":
                값.append("normal")
            elif c == "confidence_rating":
                값.append("Very High" if i % 2 == 0 else "Medium")
            elif c == "confidence_gate":
                값.append("True" if i % 2 == 0 else "False")
            elif c in ("review_required", "review_queue"):
                값.append("Y" if i % 5 == 0 else "N")
            elif c == "validity":
                # ★ 적어도 엔진이 다시 만든다 (`data_contract._validity`) — 적는 뜻이 없다.
                #   무효행은 아래 topic 을 "N/A" 로 두어 만든다.
                값.append("")
            elif c == "product_category":
                값.append("로봇청소기")
            elif c == "topic":
                # ★ 엔진 규칙 — topic 이 "N/A" 면 **무효행**이다 (`_validity`).
                #   i % 6 == 0 을 "N/A" 로 둬서 영상 집계의 「유효행만」 규칙을 시험한다.
                #   빈 topic 도 섞는다 — 분포에서 "N/A" 로 모이는지 보는 자리다.
                값.append("N/A" if i % 6 == 0 else ("소음" if i % 3 else ""))
            elif c == "topic_group":
                값.append("성능" if i % 4 else "")
            elif c == "sentiment_dir":
                값.append(["긍정", "부정", "중립"][i % 3])
            elif c == "inquiry_flag":
                값.append("y" if i % 3 == 0 else "")
            elif c == "brand":
                값.append("LG")
            elif c == "brand_display":
                값.append("LG" if i % 2 == 0 else "")
            elif c == "entity_role":
                값.append("product_brand" if i % 2 == 0 else "competitor_brand")
            elif c == "competitor_brand_tags":
                값.append("Roborock")
            elif c == "competitor_brand_display_tags":
                값.append("로보락")
            elif c == "video_id":
                값.append("vid%d" % (i % 3))
            elif c == "video_title":
                값.append("영상제목%d" % (i % 3))
            elif c == "video_url":
                # ★ 사고를 **실제 꼴로** 만든다 (2026-10-22 에 시험을 두 번 고쳤다).
                #   처음에는 "…abc0 스테이션" 처럼 **같은 값 안에 공백**을 뒀더니
                #   링크 무늬가 그 공백에서 멈춰 아무 일도 안 났다 — 시험이 무력했다.
                #   실제 자료의 `video_url` 은 **URL 하나뿐**이어서, 무늬가 값의 닫는
                #   따옴표를 넘어 다음 칸·다음 행까지 먹었다. 그 꼴로 둔다.
                값.append("https://www.youtube.com/watch?v=abc%d" % i)
            elif c == "source_id":
                # ★ **실제 꼴로** 둔다 (2026-10-23). 전에는 "src3" 이라 공유용 가명화를
                #   시험해도 「유튜브 id 가 새지 않았다」 가 **그냥 참**이었다 — 무력한 시험이다.
                값.append(_밑id(i))
            elif c == "atomic_id":
                값.append(_밑id(i) + ("-02" if i == 7 else "-01"))
            elif c == "split_origin_atomic_id":
                # ★ 2차 분리 짝 하나 — 6행과 7행이 같은 댓글에서 나뉜 것으로 둔다.
                #   가명으로 바꿔도 **형제 관계가 살아 있는지** 보는 자리다.
                값.append(_밑id(6) + "-01" if i in (6, 7) else "")
            elif c in ("tee_emotion_score", "tee_success_score", "topic_score",
                       "voc_total_score", "tee_time_score", "tee_effort_score"):
                값.append("-2" if i % 3 == 1 else "1")
            elif c == "atomic_voc":
                # ★ 공백을 **드물게** 둔다. 링크 무늬는 공백에서야 멈추므로, 공백이 멀면
                #   그 사이의 칸과 **행 경계(`}},{{`)** 까지 먹힌다 — 실제로 행 120개가
                #   사라진 그 자리다. 여기서는 다섯 행마다 하나만 공백을 둔다.
                값.append("원문 %d 입니다" % i if i % 5 == 0 else "원문%d입니다" % i)
            elif c == "atomic_voc_summary":
                값.append("요약%d" % i)
            else:
                값.append("")
        줄들.append(",".join(값))
    길.write_text("\n".join(줄들) + "\n", encoding="utf-8", newline="\n")
    return 길


@pytest.fixture(scope="module")
def 만든것(tmp_path_factory):
    자리 = tmp_path_factory.mktemp("대시보드")
    표 = _시험표(자리)
    받을곳 = 자리 / "낸것"
    환경 = {"VOC_ENGINE": str(_엔진)}
    import os
    r = subprocess.run([sys.executable, "-X", "utf8", str(_만들개), str(표), str(받을곳)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, **환경))
    assert r.returncode == 0, r.stdout + r.stderr
    것 = {}
    for p in 받을곳.glob("*.html"):
        쪽 = "공유용" if "공유용" in p.name else "살펴보기"
        글 = p.read_text(encoding="utf-8")
        m = _자료.search(글)
        assert m, "%s 에서 자료를 못 찾았다" % p.name
        것[쪽] = (p, json.loads(m.group(1).replace("<" + chr(92) + "/", "</")), 글)
    assert set(것) == {"살펴보기", "공유용"}, sorted(것)
    return 것


def test_두_장이_같은_행수를_담는다(만든것):
    """★ 공유용은 **칸만** 뺀다. 행이 줄면 치우다 자료를 깬 것이다."""
    보기 = 만든것["살펴보기"][1]
    공유 = 만든것["공유용"][1]
    assert len(공유["행"]) == len(보기["행"]), (
        "공유용 행이 %d 로 줄었다 (살펴보기 %d) — 치우는 무늬가 JSON 문법을 먹었다"
        % (len(공유["행"]), len(보기["행"])))


def test_링크를_치워도_옆_칸이_살아_있다(만든것):
    """URL 뒤에 공백·한글이 와도 **그 칸만** 치워져야 한다."""
    공유 = 만든것["공유용"][1]
    첫줄 = 공유["행"][0]
    assert "[링크 치움]" in str(첫줄.get("video_url", "")), 첫줄.get("video_url")
    # 옆 칸들이 먹히지 않았는가 — 칸 수와 값이 그대로여야 한다
    보기첫줄 = 만든것["살펴보기"][1]["행"][0]
    남아야할칸 = [c for c in 공유["칸"] if c != "video_url"]
    없어진것 = [c for c in 남아야할칸 if c not in 첫줄]
    assert not 없어진것, "치우다 칸이 사라졌다 — %s" % 없어진것[:5]
    assert 첫줄.get("atomic_voc_summary") == 보기첫줄.get("atomic_voc_summary"), (
        "옆 칸 값이 먹혔다 — %r" % 첫줄.get("atomic_voc_summary"))


def test_공유용은_원문칸을_빼고_살펴보기는_넣는다(만든것):
    보기 = 만든것["살펴보기"][1]
    공유 = 만든것["공유용"][1]
    assert "atomic_voc" in 보기["칸"], "살펴보기에 원문이 없다"
    for c in ("original_voc", "atomic_voc", "parent_voc", "video_description"):
        assert c not in 공유["칸"], "공유용에 원문칸이 남았다 — %s" % c
    assert 공유["뺀칸"], "뺀 칸을 적지 않았다"


def test_맞춤값이_고친_것들을_다_담는다(만든것):
    """★ 정답이 없으면 자기검사가 **틀린 화면을 통과시킨다** (2026-10-21 에 그랬다)."""
    맞 = 만든것["살펴보기"][1]["맞춤값"]
    for 이름 in ("기본행수", "개선과제수", "개선상위", "판정충족도별", "판정충족도_빈목록행수",
              "차원통과행수", "사람검토행수_기본충족도", "사람검토행수_전체충족도",
              "브랜드선택지", "브랜드별", "문의행수", "문의유형분포", "니즈신호분포",
              "영상수", "영상집계"):
        assert 이름 in 맞, "맞춤값에 %s 가 없다 — 그만큼 자기검사가 눈을 감는다" % 이름


def test_엔진_상수를_실어_보낸다(만든것):
    """브랜드 표준화 표·판정 충족도·문의 표시값은 **엔진에서** 와야 한다 (두 벌 금지)."""
    상수 = 만든것["살펴보기"][1]["상수"]
    assert 상수["브랜드동의어"], "브랜드 동의어 표가 비었다"
    assert "중국 브랜드" in 상수["중국묶음"], 상수["중국묶음"]
    assert 상수["판정충족도"] == ["Very High", "High", "Medium", "Low"], 상수["판정충족도"]
    assert 상수["기본판정충족도"] == ["Very High", "High"], 상수["기본판정충족도"]
    assert 상수["문의유형이름"] and 상수["니즈신호이름"], "문의 표시값 사전이 비었다"


def test_판정충족도별_합이_차원통과와_맞는다(만든것):
    """레벨별 행수를 다 더하면 「무엇을 볼까」 통과 행수가 되어야 한다."""
    맞 = 만든것["살펴보기"][1]["맞춤값"]
    합 = sum(맞["판정충족도별"].values())
    assert 합 == 맞["차원통과행수"], (
        "레벨별 합 %d 과 차원통과 %d 가 다르다 — 거르는 조건이 어긋났다"
        % (합, 맞["차원통과행수"]))
    assert 맞["판정충족도_빈목록행수"] == 0, "하나도 안 고르면 0행이어야 한다"


def test_영상집계가_유효행만_쓴다(만든것):
    """무효행이 섞이면 댓글 수와 비율이 달라진다 (원본 video_summary)."""
    맞 = 만든것["살펴보기"][1]["맞춤값"]
    행 = 만든것["살펴보기"][1]["행"]
    기본 = [r for r in 행 if r.get("status") == "normal" and r.get("confidence_gate") is True]
    유효 = [r for r in 기본 if r.get("validity") == "유효"]
    assert len(유효) < len(기본), "시험 자료에 무효행이 없다 — 이 시험이 무력하다"
    합 = sum(v["comment_count"] for v in 맞["영상집계"])
    assert 합 == len(유효), "영상 댓글 수 합 %d 이 유효행 %d 과 다르다" % (합, len(유효))


def test_자기검사_글이_들어_있다(만든것):
    """화면이 스스로 대보지 않으면 「돌아간다」 와 「맞다」 를 구분할 수 없다."""
    for 쪽 in ("살펴보기", "공유용"):
        글 = 만든것[쪽][2]
        assert "selfCheck" in 글 and "selfcheck" in 글, "%s 에 자기검사가 없다" % 쪽
        assert "이 화면을 믿지 마십시오" in 글, "%s 에 어긋날 때의 말이 없다" % 쪽


# ─────────────────────────────────────────────────────────────────────────────
# 원본 상수 대조 — 화면의 고르개가 **엔진 원본과 같은 이름·같은 정렬 칸**인가
#   ★ 왜 (2026-10-23) — ④ 개선 방향성과 ③ 문의 속 니즈를 옮길 때 내가 정렬 축 이름과
#     기준을 **지어냈다가** 원본과 달라졌다. 눈으로 대 보고 고쳤지만, 눈은 다음에 또 놓친다.
#   ★ 우리 JS 에 베껴 적은 것이 아니라 **엔진 원본 파일을 그때그때 읽어** 댄다.
#     그래서 원본이 바뀌어도, 우리가 빼먹어도 **둘 다** 잡힌다.
# ─────────────────────────────────────────────────────────────────────────────
_화면 = _스킬 / "scripts" / "화면_js.py"


def _원본상수(파일: str, 이름: str):
    """엔진 views/*.py 에서 상수 하나를 꺼낸다 (import 하지 않는다 — streamlit 이 필요하다)."""
    import ast                                                 # noqa: PLC0415

    길 = _엔진 / "src" / "dashboard60" / "views" / 파일
    assert 길.is_file(), "엔진 원본 %s 가 없다 — 「못 찾음」 은 통과가 아니다" % 길
    나무 = ast.parse(길.read_text(encoding="utf-8"))
    for 가지 in 나무.body:
        대상 = (가지.targets[0] if isinstance(가지, ast.Assign)
              else 가지.target if isinstance(가지, ast.AnnAssign) else None)
        if isinstance(대상, ast.Name) and 대상.id == 이름:
            return ast.literal_eval(가지.value)
    raise AssertionError("엔진 %s 에서 %s 를 못 찾았다" % (파일, 이름))


def test_정렬축_넷이_원본_이름과_정렬칸까지_같다():
    """④ 개선 방향성 — SORT_AXES 의 이름·정렬 칸·설명 글귀가 화면에 그대로 있나."""
    축 = _원본상수("improvement.py", "SORT_AXES")
    글 = _화면.read_text(encoding="utf-8")
    assert len(축) == 4, "원본 정렬 축이 %d개로 바뀌었다 — 화면도 같이 고친다" % len(축)
    for 이름, (칸들, 오름, 설명) in 축.items():
        assert '"%s"' % 이름 in 글, "정렬 축 이름 「%s」 가 화면에 없다" % 이름
        assert 설명 in 글, "정렬 축 「%s」 의 설명 글귀가 화면과 다르다" % 이름
        for c in 칸들:
            assert '"%s"' % c in 글, "정렬 축 「%s」 의 정렬 칸 %s 가 화면에 없다" % (이름, c)
    # 오름/내림을 뒤집으면 순서가 거꾸로 된다 — 축마다 몇 개인지까지 센다
    for 이름, (칸들, 오름, _설명) in 축.items():
        assert len(칸들) == len(오름), "원본 %s 의 칸 수와 오름차순 수가 어긋났다" % 이름


def test_문의_카드_정렬_셋이_원본과_같다():
    """③ 문의 속 니즈 — INQUIRY_CARD_SORTS 의 이름·정렬 칸이 화면에 그대로 있나."""
    정렬 = _원본상수("inquiry.py", "INQUIRY_CARD_SORTS")
    글 = _화면.read_text(encoding="utf-8")
    assert len(정렬) == 3, "원본 카드 정렬 기준이 %d개로 바뀌었다" % len(정렬)
    for 이름, 칸들 in 정렬.items():
        assert '"%s"' % 이름 in 글, "카드 정렬 기준 「%s」 가 화면에 없다" % 이름
        for c in 칸들:
            assert '"%s"' % c in 글, "「%s」 의 정렬 칸 %s 가 화면에 없다" % (이름, c)


def test_문의_표의_열한_칸이_원본_순서까지_같다():
    """★ 원본 주석 — 「주제를 왼쪽으로 올리고 식별자는 맨 뒤로 보낸다」. 순서가 뜻이다."""
    칸들 = _원본상수("inquiry.py", "INQUIRY_TABLE_COLUMNS")
    머리 = _원본상수("inquiry.py", "INQUIRY_TABLE_HEADERS")
    글 = _화면.read_text(encoding="utf-8")
    덩이 = 글.split("var INQUIRY_TABLE = [", 1)
    assert len(덩이) == 2, "화면에 INQUIRY_TABLE 이 없다 — 문의 표를 누가 지웠다"
    우리 = 덩이[1].split("];", 1)[0]
    자리 = []
    for c in 칸들:
        이름 = 머리[c]
        assert '"%s"' % 이름 in 우리, "문의 표에 「%s」 칸이 없다" % 이름
        자리.append(우리.index('"%s"' % 이름))
    assert 자리 == sorted(자리), ("문의 표 칸 순서가 원본과 다르다 — 원본 순서는 %s"
                               % [머리[c] for c in 칸들])
    assert len(칸들) == 11, "원본 문의 표가 %d칸으로 바뀌었다 — 화면도 같이 고친다" % len(칸들)


def test_영상_카드_정렬_셋이_원본과_같다():
    """② 분석 영상 정보 — VIDEO_CARD_SORTS 의 이름·정렬 칸이 화면에 그대로 있나."""
    정렬 = _원본상수("video.py", "VIDEO_CARD_SORTS")
    글 = _화면.read_text(encoding="utf-8")
    assert len(정렬) == 3, "원본 영상 카드 정렬이 %d개로 바뀌었다" % len(정렬)
    for 이름, 칸들 in 정렬.items():
        assert '"%s"' % 이름 in 글, "영상 카드 정렬 「%s」 가 화면에 없다" % 이름
        for c in 칸들:
            assert '"%s"' % c in 글, "「%s」 의 정렬 칸 %s 가 화면에 없다" % (이름, c)


def test_영상_표의_열다섯_칸이_원본_순서까지_같다():
    """★ 원본 주석 — 「봐야 할 칸을 왼쪽으로 … video_id 는 맨 뒤로 보낸다」. 순서가 뜻이다.

    ★ 원본은 칸 목록을 `render()` 안에서 짓는다(`video_columns`). 그래서 모듈 상수가 아니라
      함수 안의 대입을 찾는다 — 「못 찾음」 이면 실패한다.
    """
    import ast                                                 # noqa: PLC0415

    머리 = _원본상수("video.py", "VIDEO_TABLE_HEADERS")
    원본길 = _엔진 / "src" / "dashboard60" / "views" / "video.py"
    나무 = ast.parse(원본길.read_text(encoding="utf-8"))
    칸들 = None
    for 가지 in ast.walk(나무):
        if (isinstance(가지, ast.Assign) and isinstance(가지.targets[0], ast.Name)
                and 가지.targets[0].id == "video_columns"):
            칸들 = ast.literal_eval(가지.value)
    assert 칸들, "원본 video.py 에서 video_columns 를 못 찾았다"
    assert len(칸들) == 15, "원본 영상 표가 %d칸으로 바뀌었다 — 화면도 같이 고친다" % len(칸들)
    글 = _화면.read_text(encoding="utf-8")
    덩이 = 글.split("var VIDEO_TABLE = [", 1)
    assert len(덩이) == 2, "화면에 VIDEO_TABLE 이 없다 — 영상 표를 누가 지웠다"
    우리 = 덩이[1].split(chr(10) + "];", 1)[0]
    자리 = []
    for c in 칸들:
        이름 = 머리[c]
        assert '"%s"' % 이름 in 우리, "영상 표에 「%s」 칸이 없다" % 이름
        자리.append(우리.index('"%s"' % 이름))
    assert 자리 == sorted(자리), ("영상 표 칸 순서가 원본과 다르다 — 원본 순서는 %s"
                               % [머리[c] for c in 칸들])


def _원본_함수안_상수(파일: str, 이름: str):
    """원본이 `render()` 안에서 짓는 칸 목록을 꺼낸다 (모듈 상수가 아니다)."""
    import ast                                                 # noqa: PLC0415

    길 = _엔진 / "src" / "dashboard60" / "views" / 파일
    assert 길.is_file(), "엔진 원본 %s 가 없다" % 길
    나무 = ast.parse(길.read_text(encoding="utf-8"))
    것 = None
    for 가지 in ast.walk(나무):
        if (isinstance(가지, ast.Assign) and isinstance(가지.targets[0], ast.Name)
                and 가지.targets[0].id == 이름):
            것 = ast.literal_eval(가지.value)
    assert 것, "원본 %s 에서 %s 를 못 찾았다 — 「못 찾음」 은 통과가 아니다" % (파일, 이름)
    return 것


def test_현황표의_열아홉_칸이_원본_순서까지_같다():
    """① VoC 현황 — `display_columns` 그대로. ★ 원본은 칸이름을 **바꾸지 않는다**.

    원본은 source_run 을 2번, 2차분리를 4번 자리에 끼운다. 끼우는 자리가 바뀌면 순서가 깨진다.
    """
    칸들 = _원본_함수안_상수("overview.py", "display_columns")
    assert len(칸들) == 18, "원본 현황 표 기본 칸이 %d개로 바뀌었다" % len(칸들)
    글 = _화면.read_text(encoding="utf-8")
    덩이 = 글.split("function 현황표칸() {", 1)
    assert len(덩이) == 2, "화면에 현황표칸() 이 없다 — ① 표를 누가 지웠다"
    우리 = 덩이[1].split(chr(10) + "}", 1)[0]
    자리 = []
    for c in 칸들:
        assert '"%s"' % c in 우리, "현황 표에 %s 칸이 없다" % c
        자리.append(우리.index('"%s"' % c))
    assert 자리 == sorted(자리), "현황 표 칸 순서가 원본과 다르다 — 원본 순서는 %s" % 칸들
    # 끼워 넣는 두 칸과 그 자리까지 본다
    for 말 in ('splice(2, 0, "source_run")', 'splice(4, 0, "2차분리")'):
        assert 말 in 우리, "원본이 끼우는 자리(%s)가 화면과 다르다" % 말
    원본글 = (_엔진 / "src" / "dashboard60" / "views" / "overview.py").read_text(encoding="utf-8")
    for 말 in ('insert(2, "source_run")', 'insert(4, "2차분리")'):
        assert 말 in 원본글, "원본이 끼우는 자리가 바뀌었다(%s) — 화면도 같이 고친다" % 말


def test_제외사유_일곱이_건수0까지_다_나온다():
    """★ 원본 주석 — 「빠진 분류가 보이도록 건수 0 이어도 다 낸다」.

    사유 이름은 **엔진에서 실어** 쓴다. 화면 코드에 베껴 적으면 두 벌이 된다.
    """
    import ast                                                 # noqa: PLC0415

    길 = _엔진 / "src" / "dashboard60" / "data_contract.py"
    나무 = ast.parse(길.read_text(encoding="utf-8"))
    꺼낸것 = {}
    for 가지 in 나무.body:
        대상 = (가지.targets[0] if isinstance(가지, ast.Assign) else None)
        if isinstance(대상, ast.Name) and 대상.id in (
                "SCOPE_EXCLUSION_REASONS", "SCOPE_EXCLUSION_REASON_LABELS"):
            꺼낸것[대상.id] = ast.literal_eval(가지.value)
    사유 = 꺼낸것.get("SCOPE_EXCLUSION_REASONS")
    이름 = 꺼낸것.get("SCOPE_EXCLUSION_REASON_LABELS")
    assert 사유 and 이름, "엔진에서 제외 사유 상수를 못 꺼냈다"
    assert len(사유) == 7, "원본 제외 사유가 %d가지로 바뀌었다" % len(사유)
    # ① 화면이 그 사유를 **엔진에서 실어** 쓰는가 (화면 코드에 이름을 베끼지 않았는가)
    글 = _화면.read_text(encoding="utf-8")
    assert "K.제외사유" in 글 and "K.제외사유이름" in 글, "제외 사유를 엔진에서 싣지 않는다"
    for v in 이름.values():
        assert v not in 글, "제외 사유 이름 「%s」 를 화면 코드에 베껴 적었다 — 두 벌이 된다" % v
    담기 = (_스킬 / "scripts" / "자료_담기.py").read_text(encoding="utf-8")
    assert "SCOPE_EXCLUSION_REASONS" in 담기 and "scope_exclusion_reason" in 담기, (
        "자료_담기 가 제외 사유 칸·상수를 싣지 않는다 — ① 의 그 섹션이 빈다")


def test_RootCause_세_칸의_이름과_순서가_원본과_같다():
    """★ 원본 주석 — 「데이터사전 정의 그대로 쓴다. 내가 지어낸 『무엇이/어디가/왜』 는
    실제 내용과 어긋났다」 (sky 2026-08-19). **이름과 순서가 뜻이다.**
    """
    원본글 = (_엔진 / "src" / "dashboard60" / "views" / "overview.py").read_text(encoding="utf-8")
    짝 = '(("문제 현상", problem), ("개선 대상", target), ("근본 원인", cause))'
    assert 짝 in 원본글, "원본의 RootCause 세 칸이 바뀌었다 — 화면도 같이 고친다"
    글 = _화면.read_text(encoding="utf-8")
    자리 = [글.index('"문제 현상"'), 글.index('"개선 대상"'), 글.index('"근본 원인"')]
    assert 자리 == sorted(자리), "화면의 RootCause 세 칸 순서가 원본과 다르다"
    for 틀린것 in ('"무엇이"', '"어디가"', '"왜"'):
        assert 틀린것 not in 글, "지어낸 라벨 %s 이 화면에 남아 있다" % 틀린것


def test_화면_틀이_원본_머리와_같다():
    """★ 원본 주석 — 「『VoC 65』 는 개발 중 컬럼 수를 딴 이름이었다. 실무자에게는 뜻이 없다」.

    큰 제목·설명 글귀는 원본 app_operating.main() 에 있는 그대로여야 한다.
    schema 는 최종본_앉히기 가 metadata.json 에 적는 값과 **같아야** 한다 — 두 벌이 어긋나면
    대시보드는 「다른 자료」 로 읽는다.
    """
    만들개글 = _만들개.read_text(encoding="utf-8")
    원본글 = (_엔진 / "src" / "dashboard60" / "app_operating.py").read_text(encoding="utf-8")
    assert 'st.title("YouTube VoC 분석 대시보드")' in 원본글, "원본의 큰 제목이 바뀌었다"
    assert '큰제목 = "YouTube VoC 분석 대시보드"' in 만들개글, "HTML 의 큰 제목이 원본과 다르다"
    for 조각 in ("YouTube 영상 댓글을 분석해 개선 포인트를 찾는 화면입니다. ",
                "제품군 · 이유 topic · 감성을 나누어 보고, RootCause 까지 이어 봅니다."):
        assert 조각 in 원본글, "원본의 설명 글귀가 바뀌었다 — %s" % 조각
        assert 조각 in 만들개글, "HTML 의 설명 글귀가 원본과 다르다 — %s" % 조각
    assert "배포 커밋" in 만들개글, "원본에 있는 「배포 커밋」 줄이 HTML 에 없다"
    앉히기 = (_스킬 / "scripts" / "최종본_앉히기.py").read_text(encoding="utf-8")
    표시 = '"schema_version": "'
    스키마 = 앉히기.split(표시, 1)[1].split('"', 1)[0]
    assert '스키마판 = "%s"' % 스키마 in 만들개글, (
        "HTML 의 schema 가 최종본_앉히기(%s)와 다르다" % 스키마)


def test_탭_다섯이_원본_순서와_같다():
    """원본 OPERATING_TABS 의 **순서**가 화면 탭과 같은가."""
    import ast                                                 # noqa: PLC0415

    길 = _엔진 / "src" / "dashboard60" / "app_operating.py"
    글 = 길.read_text(encoding="utf-8")
    나무 = ast.parse(글)
    이름값 = {}
    for 가지 in 나무.body:
        대상 = (가지.targets[0] if isinstance(가지, ast.Assign) else None)
        if isinstance(대상, ast.Name) and 대상.id.startswith("TAB_"):
            이름값[대상.id] = ast.literal_eval(가지.value)
    차례 = 글.split("OPERATING_TABS = [", 1)[1].split("]", 1)[0]
    탭들 = [이름값[n.strip()] for n in 차례.split(",") if n.strip()]
    assert len(탭들) == 5, "원본 탭이 %d개로 바뀌었다" % len(탭들)
    우리 = _화면.read_text(encoding="utf-8").split("var TABS = [", 1)[1].split("];", 1)[0]
    자리 = []
    for t in 탭들:
        assert '"%s"' % t in 우리, "탭 「%s」 가 화면에 없다" % t
        자리.append(우리.index('"%s"' % t))
    assert 자리 == sorted(자리), "탭 순서가 원본과 다르다 — 원본 순서는 %s" % 탭들


# ─────────────────────────────────────────────────────────────────────────────
# 공유용의 식별자 — **가명**이어야 하고, 셈은 그대로여야 한다
#   sky 2026-10-23 「공유용은 가명으로 바꿔주세요」
#   ★ 지우지 않는 까닭 — source_id 는 영상별 댓글 수의 분모이고,
#     atomic_id·split_origin_atomic_id 는 2차 분리 관계를 셈한다. 지우면 그 셈이 깨진다.
#     그래서 한 대 한으로 바꾼다. 이 시험이 **둘 다** 지킨다.
# ─────────────────────────────────────────────────────────────────────────────
_유튜브id = re.compile(r"Ug[A-Za-z0-9_.-]{15,}")
_가명 = re.compile(r"^댓글#\d+(-\d+)?$")


def test_공유용에는_유튜브_댓글id가_없다(만든것):
    살글 = 만든것["살펴보기"][2]
    공글 = 만든것["공유용"][2]
    # ★ 먼저 **시험이 무력하지 않은지** 본다 — 살펴보기에는 있어야 한다
    assert _유튜브id.search(살글), (
        "시험 자료에 유튜브 id 꼴이 없다 — 이 시험이 무력하다 (_밑id 를 확인한다)")
    남음 = _유튜브id.findall(공글)
    assert not 남음, "공유용에 유튜브 댓글 id 가 %d번 남았다 — %s" % (len(남음), 남음[:3])


def test_공유용_식별자가_가명_꼴이다(만든것):
    행 = 만든것["공유용"][1]["행"]
    for c in ("source_id", "atomic_id", "split_origin_atomic_id"):
        값들 = [str(r.get(c) or "").strip() for r in 행]
        있는것 = [v for v in 값들 if v]
        assert 있는것, "공유용에 %s 값이 하나도 없다 — 셈이 깨진다" % c
        틀린것 = [v for v in 있는것 if not _가명.match(v)]
        assert not 틀린것, "공유용 %s 에 가명이 아닌 값 %d개 — %s" % (c, len(틀린것), 틀린것[:3])


def test_가명으로_바꿔도_셈이_그대로다(만든것):
    """★ 가명화가 지켜야 하는 것 — 같은 id 는 같은 가명, 다른 id 는 다른 가명.

    그래야 영상별 댓글 수(source_id 가 있는 행)와 2차 분리 형제 수가 바뀌지 않는다.
    """
    def 셈(자료):
        행 = 자료["행"]
        있는source = [str(r.get("source_id") or "").strip() for r in 행]
        있는source = [v for v in 있는source if v]
        묶 = {}
        for r in 행:
            v = str(r.get("split_origin_atomic_id") or "").strip()
            if v:
                묶[v] = 묶.get(v, 0) + 1
        return {"행수": len(행), "source있는행": len(있는source),
                "source고유": len(set(있는source)), "형제묶음": sorted(묶.values())}

    살 = 셈(만든것["살펴보기"][1])
    공 = 셈(만든것["공유용"][1])
    assert 살["형제묶음"], "시험 자료에 2차 분리 행이 없다 — 형제 셈을 못 본다"
    assert 살 == 공, "가명으로 바꾸자 셈이 달라졌다 — 살 %s / 공 %s" % (살, 공)


def test_영상집계_숫자가_두_장에서_같다(만든것):
    """댓글 수는 source_id 가 있는 행을 센다 — 가명화가 이것을 깨면 ② 화면이 틀린다."""
    살 = {v["video_id"]: v["comment_count"] for v in 만든것["살펴보기"][1]["맞춤값"]["영상집계"]}
    공 = {v["video_id"]: v["comment_count"] for v in 만든것["공유용"][1]["맞춤값"]["영상집계"]}
    assert 살 and 살 == 공, "영상별 댓글 수가 두 장에서 다르다 — 살 %s / 공 %s" % (살, 공)
