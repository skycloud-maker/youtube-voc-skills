# -*- coding: utf-8 -*-
"""총괄(한 줄 흐름)이 **시험 하네스와 같은 환경**을 주는가 · 최종 산출물을 제대로 집는가 (Ver2).

★ 왜 — 2026-10-09 한 번의 실행에서 **같은 모양의 결함이 다섯** 나왔다.
  하나하나는 달라 보이지만 뿌리가 같다 — 「시험·도구에는 적혀 있는데 실제 흐름(총괄)에 없던 것」.

  ① `VOC_ENGINE` 을 안 줘서 칸 검수가 눈먼 길로 갔다.
     `check_selfcheck._일차가_내놓는가()` 는 엔진을 못 보면 `return True` (「예전대로 반려」)
     로 떨어진다. 그래서 1차가 애초에 안 내놓는 `video_tags`·`video_description` 을
     「번들에서 빠진 칸」 으로 보고 **안 깨진 번들을 깨졌다고** 멈췄다.
     기준 만들개와 스킬 시험은 이미 주고 있었다. 총괄만 빠져 있었다.
  ② Codex 내장 파이썬을 PATH 앞에 안 놔서 3차 감독이 「pandas 를 못 씁니다」 로 멈췄다.
     2026-09-21 에 두 번 겪고 `스킬시험_돌리기._codex_env` 에는 고쳐 둔 것이다.
  ③ 자가점검 맨 끝 **합계 줄**(`✗ 0건 · ! 2건`)을 지적으로 세어 깨끗한 번들에도 소견이 붙었다.
  ④ 아웃풋 1 이 `sorted(rglob(이름))[0]` — **글자 순 첫 번째**를 담아,
     최종(`master_final`) 대신 판독A 의 중간 번들을 담았다. 사람이 받은 분리제안은 4행인데
     같은 꾸러미 안의 최종 엑셀 시트는 2행 — 한 꾸러미에서 숫자가 둘.
  ⑤ 아웃풋 2 가 `3차_최종데이터.xlsx` 를 담았다. 그것은 **4차 반영 전** 엑셀이다.
     4차_반영 이 스스로 「받을 것」 으로 적는 것은 `voc_dashboard_export_bundle*.xlsx` 다.

  그래서 사람 기억이 아니라 여기서 잡는다. 하네스가 주는 것을 총괄도 주는지 **대본다**.

★ 「못 찾음」 은 통과가 아니다 — 총괄 스크립트나 하네스를 못 읽으면 실패한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared" / "tools"))
sys.path.insert(0, str(_뿌리 / "tests" / "evals"))
sys.path.insert(0, str(_뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))

총괄 = pytest.importorskip("한줄_돌리기", reason="총괄 스크립트를 못 읽었다")
하네스 = pytest.importorskip("스킬시험_돌리기", reason="스킬 시험 하네스를 못 읽었다")


# ── ① 엔진을 가리키는가 ──────────────────────────────────────────────────
def test_총괄이_엔진을_가리킨다(monkeypatch):
    monkeypatch.delenv("VOC_ENGINE", raising=False)
    총괄._엔진_가리키기()
    자리 = os.environ.get("VOC_ENGINE", "")
    assert 자리, "총괄이 VOC_ENGINE 을 안 줬다 — 칸 검수가 눈먼 길로 간다"
    assert (Path(자리) / "src" / "voc_rebuild" / "schema.py").is_file(), \
        "VOC_ENGINE 이 엔진이 아닌 자리를 가리킨다: %s" % 자리


def test_엔진을_가리키면_안내놓는칸을_가른다():
    """★ ① 의 진짜 값 — 「1차가 안 내놓는 칸」 과 「번들에서 잃은 칸」 이 갈리는가.

    원문 `25_판정대상_컬럼분류.md` — video_tags · video_description 은 66컬럼에 없다.
    1차가 LLM 입력으로만 쓰고 출력에서 뺐다 (D-30). 판독자는 이 두 값을 볼 수 없다.
    """
    import check_selfcheck
    총괄._엔진_가리키기()
    for 칸 in ("video_tags", "video_description"):
        assert check_selfcheck._일차가_내놓는가(칸) is False, \
            "%s 을 「1차가 내놓는 칸」 으로 본다 — 판독자를 잘못 반려한다" % 칸
    for 칸 in ("video_title", "atomic_id", "topic"):
        assert check_selfcheck._일차가_내놓는가(칸) is True, \
            "%s 을 「1차가 안 내놓는 칸」 으로 본다 — 진짜 잃은 칸을 놓친다" % 칸


def test_엔진을_못_보면_반려로_떨어진다(monkeypatch):
    """★ 일부러 눈을 가려 본다 — 엔진을 못 보면 **가르지 못한다**(그래서 가리켜야 한다).

    이 시험이 없으면 위 시험이 「엔진을 가리켜서」 통과한 것인지
    「원래 늘 통과하는 것」 인지 알 수 없다.
    """
    import check_selfcheck
    monkeypatch.delenv("VOC_ENGINE", raising=False)
    monkeypatch.setattr(check_selfcheck, "_일차가_내놓는가",
                        check_selfcheck._일차가_내놓는가, raising=True)
    가짜 = {k: v for k, v in sys.modules.items()}
    sys.modules["src.voc_rebuild.schema"] = None        # import 가 실패하게
    sys.modules["src.voc_rebuild"] = None
    sys.modules["src"] = None
    깨끗한길 = [p for p in sys.path if "engine" not in p.replace("\\", "/")]
    monkeypatch.setattr(sys, "path", 깨끗한길)
    try:
        assert check_selfcheck._일차가_내놓는가("video_tags") is True, \
            "엔진을 못 보는데도 가른다 — 그러면 이 시험이 지키는 것이 없다"
    finally:
        sys.modules.clear()
        sys.modules.update(가짜)


# ── ② Codex 내장 파이썬 ────────────────────────────────────────────────
def test_총괄과_하네스가_같은_파이썬을_가리킨다():
    assert 총괄._코덱스파이썬 == 하네스._codex파이썬, \
        "총괄과 시험 하네스가 다른 파이썬을 가리킨다 — 시험만 통과하고 실제로 막힌다"


def test_코덱스는_내장파이썬을_PATH_앞에_놓는다():
    if not 총괄._코덱스파이썬.is_dir():
        pytest.skip("이 컴퓨터에 Codex 내장 파이썬이 없다")
    앞 = 총괄._코덱스파이썬_먼저({"PATH": "/아무거나"})["PATH"].split(os.pathsep)
    assert 앞[0] == str(총괄._코덱스파이썬), \
        "내장 파이썬이 PATH 맨 앞이 아니다 — 자가점검이 pandas 로 막힌다"
    assert "/아무거나" in 앞, "원래 PATH 를 지웠다"


def test_띄울_때_실제로_그_환경을_준다(monkeypatch, tmp_path):
    """★ 말이 아니라 **실제로 띄우는 환경**을 본다 — subprocess 를 가로채 env 를 꺼낸다."""
    if not 총괄._코덱스파이썬.is_dir():
        pytest.skip("이 컴퓨터에 Codex 내장 파이썬이 없다")
    총괄._엔진_가리키기()
    담은것: dict[str, str] = {}

    class _답:
        returncode, stdout, stderr = 0, "", ""

    def _가짜(명령, **ㅋ):
        담은것.clear()
        담은것.update(ㅋ.get("env") or {})
        return _답()

    monkeypatch.setattr(총괄.subprocess, "run", _가짜)
    monkeypatch.setattr(총괄.shutil, "which", lambda x: "/가짜/%s.exe" % x)
    총괄.AI돌리기("codex", tmp_path, "아무 말", tmp_path / "기록.jsonl")
    assert 담은것.get("PATH", "").split(os.pathsep)[0] == str(총괄._코덱스파이썬), \
        "codex 를 띄울 때 내장 파이썬을 앞에 안 놨다"
    assert 담은것.get("VOC_ENGINE"), "codex 를 띄울 때 VOC_ENGINE 을 안 줬다"
    for 칸 in ("PYTHONIOENCODING", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE"):
        assert 담은것.get(칸), "%s 를 안 줬다 — 한글이 깨지거나 캐시가 쌓인다" % 칸

    총괄.AI돌리기("claude", tmp_path, "아무 말", tmp_path / "기록2.jsonl")
    assert 담은것.get("VOC_ENGINE"), "claude 를 띄울 때 VOC_ENGINE 을 안 줬다"


# ── ③ 합계 줄은 지적이 아니다 ─────────────────────────────────────────────
def test_자가점검_합계줄은_지적이_아니다():
    assert 총괄._합계줄.match("✗ 0건 · ! 2건"), "합계 줄을 못 알아본다 — 늘 소견이 하나 붙는다"
    assert 총괄._합계줄.match("✗ 3건 · ! 1건")
    assert not 총괄._합계줄.match("✗ 번들에서 빠진 칸 1 — video_title"), \
        "진짜 지적을 합계 줄로 본다 — 깨진 번들이 그냥 지나간다"
    assert not 총괄._합계줄.match("✗ 2건의 라벨이 폐기 라벨이다"), \
        "「N건」 으로 시작하는 진짜 지적까지 빼면 안 된다"


# ── ④⑤ 최종 산출물을 집는가 ──────────────────────────────────────────────
def test_최종자리가_중간번들보다_먼저다():
    """★ 글자 순으로는 `claudecode_bundle` 이 `master_final` 보다 앞선다.

    그래서 순서를 **이름 순이 아니라 적어 둔 순서**로 정해야 한다.
    """
    assert 총괄.최종자리[0] == "_최종결과"
    assert "_판독패키지/_결과/master_final" in 총괄.최종자리
    assert not any("bundle" in x for x in 총괄.최종자리), \
        "최종 자리에 판독자 번들이 들어 있다 — 중간 사본을 최종이라 부른다"
    assert "claudecode_bundle" < "master_final", \
        "이 시험의 전제가 깨졌다 — 글자 순 문제가 아니면 주석을 고쳐야 한다"


def test_최종사본은_최종자리에서_집고_다른_사본을_알려준다(tmp_path):
    판자리 = tmp_path / "판"
    번들 = 판자리 / "_판독패키지" / "_결과"
    (판자리 / "_최종결과").mkdir(parents=True)
    (번들 / "claudecode_bundle").mkdir(parents=True)
    (번들 / "master_final").mkdir(parents=True)
    (판자리 / "_최종결과" / "사람이볼목록.csv").write_text("최종", encoding="utf-8")
    (번들 / "claudecode_bundle" / "사람이볼목록.csv").write_text("중간", encoding="utf-8")
    고른것, 다름 = 총괄._최종사본(판자리, "사람이볼목록.csv")
    assert 고른것 is not None and 고른것.parent.name == "_최종결과", "중간 번들을 집었다"
    assert [p.parent.name for p in 다름] == ["claudecode_bundle"], \
        "다른 내용의 중간 사본을 알려주지 않았다 — 사람이 모른 채 넘어간다"

    # 같은 내용이면 알릴 것이 없다
    (번들 / "claudecode_bundle" / "사람이볼목록.csv").write_text("최종", encoding="utf-8")
    _, 다름2 = 총괄._최종사본(판자리, "사람이볼목록.csv")
    assert 다름2 == [], "내용이 같은 사본을 「다르다」 고 한다 — 쓸데없는 소견이 쌓인다"

    # ★ 2026-10-09 에 실제로 틀린 것 — 분리제안은 최종 자리에 master_final 에만 있다
    (번들 / "master_final" / "분리제안.csv").write_text("2행", encoding="utf-8")
    (번들 / "claudecode_bundle" / "분리제안.csv").write_text("4행", encoding="utf-8")
    고른것2, _ = 총괄._최종사본(판자리, "분리제안.csv")
    assert 고른것2 is not None and 고른것2.parent.name == "master_final", \
        "분리제안을 판독자 번들에서 집었다 (2026-10-09 에 실제로 그랬다)"

    # 없으면 **못 찾음**이다 — 중간 것으로 때우지 않는다
    assert 총괄._최종사본(판자리, "없는것.csv") == (None, []), "없는 것을 있다고 한다"


def test_가장새것은_시간순으로_집는다(tmp_path):
    import time
    먼저 = tmp_path / "z_bundle.xlsx"
    나중 = tmp_path / "a_bundle.xlsx"
    먼저.write_text("먼저", encoding="utf-8")
    time.sleep(0.05)
    나중.write_text("나중", encoding="utf-8")       # 글자 순으로는 a 가 앞, 시간 순으로는 나중
    assert 총괄._가장새것(tmp_path.glob("*_bundle.xlsx")) == 나중, \
        "글자 순으로 집는다 — 낡은 산출물을 최종이라 부를 수 있다"
    assert 총괄._가장새것([]) is None, "빈 것에 None 을 안 돌려준다"


# ── 되감기 ──────────────────────────────────────────────────────────────
def test_되감기_이름은_단계_목록과_같다():
    """`--되감기` 에 쓰는 이름이 실제 단계 이름인가.

    ★ `4차반영` 은 단계 목록에 없는데 `끝난단계` 에는 들어온다(사차반영이 적는다).
      그래서 되감을 때 `.index()` 가 ValueError 로 터졌다 (2026-10-09).
    """
    이름들 = [n for n, _ in 총괄.단계들]
    assert 이름들[0] == "1차" and 이름들[-1] == "아웃풋1"
    assert "4차반영" not in 이름들, \
        "4차반영이 단계 목록에 들어왔다 — 되감기 쪽 처리를 다시 보아야 한다"


# ── 인풋 2 — 사람이 정한 것을 정말 읽는가 ──────────────────────────────────
# ★ 2026-10-09 — `--4차반영` 이 사람이 정한 것을 **아무도 읽지 않고** 최종 엑셀을 냈다.
#   원문 `98_전체흐름_1차부터_4차까지.md` 의 「정한 뒤 — 총괄」 ①②③ 이 빠져 있었다.
#   또 아웃풋 1 에 **승인 칸이 든 파일**(수정로그 둘)이 안 담겨서, 사람이 정한 것을
#   적을 자리 자체가 없었다. 그래서 「정한 것이 하나도 없는 최종본」 이 나올 수 있었다.
def test_아웃풋1이_승인칸이_든_파일을_담는다():
    """★ 인풋 2 칸이 있는 파일은 **전부** 아웃풋 1 에 들어가야 한다.

    글자 검색이 아니라 **값**을 본다 (`아웃풋1에담을것` 과 `인풋2칸` 을 맞댄다) —
    모듈 어딘가에 그 이름이 있기만 해도 통과하면 지키는 것이 없다.
    """
    담을것 = set(총괄.아웃풋1에담을것)
    칸있는것 = {이름 for 이름, _, _, _ in 총괄.인풋2칸}
    빠진것 = 칸있는것 - 담을것
    assert not 빠진것, (
        "승인 칸이 있는데 아웃풋 1 에 안 담는다 — 사람이 정한 것을 적을 자리가 없다: %s"
        % sorted(빠진것))
    assert "사람이볼목록.csv" in 담을것, "읽는 표(사람이볼목록)도 같이 줘야 한다"


def test_인풋2칸이_실제_파일의_칸_이름과_같다():
    """칸 이름을 코드에 적었으니, 도구들이 쓰는 이름과 **같아야** 한다.

    `apply_approved.py` 가 읽는 이름은 `승인상태` 다 — 그 도구에서 직접 확인한다.
    """
    import apply_approved
    assert "승인상태" in inspect_소스(apply_approved), \
        "apply_approved 가 「승인상태」 를 안 읽는다 — 칸 이름이 바뀌었다"
    칸들 = {칸 for _, 칸, _, _ in 총괄.인풋2칸}
    assert 칸들 == {"승인상태", "처리상태"}, "인풋 2 칸 이름이 바뀌었다 — %s" % sorted(칸들)
    assert 총괄._승인말 >= {"승인"} and 총괄._반려말 >= {"반려"}
    # ★ apply_approved 와 **같은 말**을 승인으로 봐야 한다. 다르면 사람이 적은 「Y」 가 한쪽에서만 통한다
    assert 총괄._승인말 == apply_approved.APPROVED, \
        "승인으로 보는 말이 apply_approved 와 다르다 — %s vs %s" % (
            sorted(총괄._승인말), sorted(apply_approved.APPROVED))


def inspect_소스(모듈) -> str:
    import inspect
    return inspect.getsource(모듈)


def test_아무것도_안정하면_센다(tmp_path):
    """`인풋2_센다` 가 「아직 안 정한 칸」 을 센다 — 0 이면 사차반영이 멈춘다."""
    import csv as _csv
    모을곳 = tmp_path / "아웃풋1_회의에서_정할것"
    모을곳.mkdir()
    길 = 모을곳 / "수정로그_재검토필요.csv"
    with open(길, "w", encoding="utf-8-sig", newline="") as h:
        w = _csv.DictWriter(h, fieldnames=["atomic_id", "field", "제안값", "승인상태"])
        w.writeheader()
        w.writerow({"atomic_id": "a", "field": "topic", "제안값": "", "승인상태": "대기"})
        w.writerow({"atomic_id": "b", "field": "topic", "제안값": "", "승인상태": ""})
        w.writerow({"atomic_id": "c", "field": "topic", "제안값": "x", "승인상태": "승인"})
    남은 = 총괄.인풋2_센다(모을곳)
    assert 남은["수정로그_재검토필요.csv"] == 2, \
        "안 정한 칸을 잘못 센다 (「대기」 와 빈칸이 둘) — %s" % 남은


def test_승인했는데_데이터에_없으면_잡는다(tmp_path):
    """★ 「총괄이 돌았다」 와 「반영됐다」 는 다르다 — 값을 하나씩 대본다."""
    import csv as _csv
    판자리 = tmp_path / "총괄판"
    번들 = 판자리 / "_판독패키지" / "_결과" / "master_final"
    번들.mkdir(parents=True)
    (판자리 / "_최종결과").mkdir()

    def 쓰기(길, 머리, 줄들):
        with open(길, "w", encoding="utf-8-sig", newline="") as h:
            w = _csv.DictWriter(h, fieldnames=머리)
            w.writeheader()
            w.writerows(줄들)

    쓰기(번들 / "raw_voc.csv", ["atomic_id", "topic"],
       [{"atomic_id": "a", "topic": "옛라벨"}, {"atomic_id": "b", "topic": "새라벨"}])
    쓰기(번들 / "수정로그_재검토필요.csv", ["atomic_id", "field", "제안값", "승인상태"],
       [{"atomic_id": "a", "field": "topic", "제안값": "새라벨", "승인상태": "승인"},
        {"atomic_id": "b", "field": "topic", "제안값": "새라벨", "승인상태": "승인"},
        {"atomic_id": "a", "field": "topic", "제안값": "딴것", "승인상태": "반려"}])
    안된것 = 총괄.인풋2_확인(판자리)
    assert len(안된것) == 1 and "a" in 안된것[0], \
        "승인했는데 안 들어간 것을 못 잡거나, 반려를 잡는다 — %s" % 안된것

    # 제안값이 비었는데 승인한 것도 잡는다
    쓰기(번들 / "수정로그_재검토필요.csv", ["atomic_id", "field", "제안값", "승인상태"],
       [{"atomic_id": "b", "field": "topic", "제안값": "", "승인상태": "승인"}])
    안된것2 = 총괄.인풋2_확인(판자리)
    assert 안된것2 and "제안값이 비었" in 안된것2[0],안된것2

    # ★ 「못 찾음」 은 통과가 아니다 — raw_voc 가 없으면 그것을 말한다
    (번들 / "raw_voc.csv").unlink()
    안된것3 = 총괄.인풋2_확인(판자리)
    assert 안된것3 and "못 찾았습니다" in 안된것3[0], \
        "raw_voc 가 없는데 「문제 없음」 으로 돌려준다 — 검사 안 한 것을 숨긴다"


# ── ⑥ 갖춤새를 **돌리기 전에** 보는가 (2026-10-22) ────────────────────────────
#   ★ 찾은 구멍 — `--확인만` 이 「누가 무엇을 한다」 만 보여 주고 **갖춤새를 안 봤다.**
#     키가 없어도 · `claude`·`codex` 가 없어도 미리보기는 종료코드 0 으로 통과했고,
#     실제로 돌려 1차에 들어가서야 멈췄다. 받은 사람에게는 「미리보기가 됐는데 왜 멈추나」 다.
#     「못 찾음」 을 「없음」 으로 돌려주던 것과 같은 모양의 결함이다.
def test_갖춤새가_없는_키를_잡는다(monkeypatch):
    for k in 총괄._키이름들():
        monkeypatch.delenv(k, raising=False)
    말들 = 총괄.갖춤새_점검([])
    키말 = [x for x in 말들 if "키가 없습니다" in x]
    assert 키말, "키가 없는데 못 잡았다 — %r" % (말들,)
    for k in 총괄._키이름들():
        assert k in 키말[0], "어느 키가 없는지 말하지 않았다 — %s" % 키말[0]


def test_1차가_끝났으면_키를_보지_않는다(monkeypatch):
    """차수마다 필요한 것이 다르다 — 이미 모은 뒤에는 키가 없어도 이어갈 수 있다."""
    for k in 총괄._키이름들():
        monkeypatch.delenv(k, raising=False)
    말들 = 총괄.갖춤새_점검(["1차", "2차준비", "2차판독", "총괄검수1", "3차준비", "3차감독"])
    assert not [x for x in 말들 if "키가 없습니다" in x], "끝난 1차에 키를 요구했다 — %r" % (말들,)


def test_갖춤새가_없는_AI명령을_잡는다(monkeypatch):
    monkeypatch.setattr(총괄.shutil, "which", lambda _: None)
    말들 = 총괄.갖춤새_점검([])
    for 명령 in ("claude", "codex"):
        assert [x for x in 말들 if ("`%s`" % 명령) in x], \
            "%s 가 없는데 못 잡았다 — %r" % (명령, 말들)
    # 어느 자리를 못 띄우는지까지 말해야 한다 (사람이 바로 알 수 있게)
    붙은 = " ".join(말들)
    for 자리, _ in list(총괄.판독자) + list(총괄.감독자):
        assert 자리 in 붙은, "%s 자리를 말하지 않았다 — %r" % (자리, 말들)


def test_판독이_끝났으면_그_명령은_보지_않는다(monkeypatch):
    monkeypatch.setattr(총괄.shutil, "which", lambda _: None)
    말들 = 총괄.갖춤새_점검(["1차", "2차준비", "2차판독", "총괄검수1", "3차준비", "3차감독"])
    붙은 = " ".join(말들)
    for 자리, _ in list(총괄.판독자) + list(총괄.감독자):
        assert 자리 not in 붙은, "끝난 자리를 요구했다 (%s) — %r" % (자리, 말들)


def test_4차반영은_총괄_명령만_본다(monkeypatch):
    for k in 총괄._키이름들():
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(총괄.shutil, "which", lambda _: None)
    말들 = 총괄.갖춤새_점검(["1차"], 사차=True)
    assert not [x for x in 말들 if "키가 없습니다" in x], "4차 반영에 키를 요구했다 — %r" % (말들,)
    assert [x for x in 말들 if "총괄" in x], "총괄 명령이 없는데 못 잡았다 — %r" % (말들,)


def test_갖추면_아무것도_안_나온다(monkeypatch):
    for k in 총괄._키이름들():
        monkeypatch.setenv(k, "시험용-값-아님")
    monkeypatch.setattr(총괄.shutil, "which", lambda n: "/시험/" + n)
    assert 총괄.갖춤새_점검([]) == [], "다 갖췄는데 모자란다고 했다"


def test_키_이름은_1차돌리개_한_곳에서_온다():
    """두 벌로 적지 않는다 — 1차 돌리개의 `키들` 이 원본이다 (공통 규칙 6)."""
    이름들 = 총괄._키이름들()
    assert 이름들, "키 이름 목록을 못 봤다 — 못 찾음은 통과가 아니다"
    글 = Path(총괄.__file__).read_text(encoding="utf-8")
    for k in 이름들:
        # 총괄 스크립트 안에 키 이름이 **박혀 있으면** 두 벌이 된다
        assert k not in 글, "키 이름을 총괄에도 박았다 (두 벌) — %s" % k


def test_미리보기가_못_갖춘_것을_보면_멈춘다(monkeypatch, tmp_path):
    """★ 이것이 구멍 그 자체였다 — 미리보기가 **통과**했다. 이제 종료코드 2 로 멈춘다."""
    for k in 총괄._키이름들():
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(총괄.shutil, "which", lambda _: None)
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(tmp_path), "--확인만",
                         "--조건", "검색어=시험; 영상=1; 댓글=1"])
    assert 총괄.main() == 2, "못 갖췄는데 미리보기가 통과했다"


# ── ⑦ 돌리개가 **스킬 문서에 있는가** (2026-10-22) ──────────────────────────────
#   ★ 찾은 구멍 — 한 줄 돌리개는 `.py` 파일 **안에만** 적혀 있었다. 여섯 SKILL.md 어디에도
#     이름이 없었다. 그래서 채팅창에 「유튜브 댓글 분석 해 줘」 라고 넣으면 AI 가 돌리개의
#     존재를 모르고 1차 스킬만 띄운 뒤 멈춘다 — Ver1 방식(차수마다 사람이 말 걸기)이 된다.
#     코드가 되는 것과 **AI 가 그것을 아는 것**은 다르다.
_총괄스킬 = _뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "SKILL.md"


def _스킬글() -> str:
    assert _총괄스킬.is_file(), "총괄 SKILL.md 를 못 찾았다 — 못 찾음은 통과가 아니다"
    return _총괄스킬.read_text(encoding="utf-8")


def test_돌리개가_스킬_설명에_있다():
    """`description` 은 AI 가 **이 스킬을 띄울지** 고르는 자리다. 여기에 없으면 안 띄운다."""
    글 = _스킬글()
    설명 = [s for s in 글.split(chr(10)) if s.startswith("description:")]
    assert 설명, "description 줄을 못 찾았다"
    assert "한줄_돌리기" in 설명[0], "설명에 돌리개 이름이 없다 — AI 가 이 스킬을 안 띄운다"


def test_전부_맡길_때의_부름말이_설명에_있다():
    """사용자가 실제로 쓸 말로 걸려야 한다 — 「총괄」 「3차 준비」 만으로는 안 걸린다."""
    설명 = [s for s in _스킬글().split(chr(10)) if s.startswith("description:")][0]
    for 말 in ("처음부터 끝까지", "한 번에 돌려", "전체 분석", "한 줄로"):
        assert 말 in 설명, "부름말이 없다 — 「%s」" % 말


def test_스킬_문서가_돌리개_쓰는_법_넷을_적는다():
    """쓰는 법이 넷이다 — 처음 돌리기 · 미리보기 · 이어가기(같은 명령 다시) · 4차 반영."""
    글 = _스킬글()
    for 조각 in ("--조건", "--확인만", "--4차반영", "--되감기", "상태.json"):
        assert 조각 in 글, "돌리개 쓰는 법에서 빠졌다 — %s" % 조각


def test_스킬_문서가_인풋_두_번을_적는다():
    글 = _스킬글()
    for 조각 in ("인풋 1", "인풋 2", "아웃풋 1", "아웃풋 2"):
        assert 조각 in 글, "두 단계 설명에서 빠졌다 — %s" % 조각


def test_스킬_문서가_돈_쓰기_전에_묻게_한다():
    """돈이 드는 일이다. 묻지 않고 돌리면 안 된다 (sky 2026-10-09)."""
    글 = _스킬글()
    assert "승인" in 글, "승인을 받으라는 말이 없다"
    assert "실행조건" in 글 and "99_1차_실행조건_원문" in 글, \
        "실행조건을 어디서 보고 묻는지 적지 않았다 (지어내게 된다)"


def test_스킬_문서가_저장소_밖에_차리게_한다():
    assert "저장소 밖" in _스킬글(), "판자리를 저장소 밖에 차리라는 말이 없다"


def test_한_차수만_맡길_때는_돌리개를_안_쓴다고_적는다():
    """돌리개는 **전부를 맡길 때**만 쓴다 — 아니면 끝난 차수를 다시 돌려 돈이 두 번 나간다."""
    글 = _스킬글()
    assert "전부를 맡길 때" in 글, "돌리개를 언제 안 쓰는지 적지 않았다"
