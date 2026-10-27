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

import json
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

    ★ 2026-10-28 — 담는 목록이 **둘**이 됐다. `감독_분리제안.csv` 는 감독이 낸 것이
      있을 때만 만들어지므로(`build_master.py` 575줄) 필수 목록에 넣으면 정상인 판이
      멈춘다. 그래서 「있으면 담을 것」 을 따로 뒀다 — 이 시험은 **두 목록을 합쳐** 본다.
      합쳐 보는 것은 느슨해지는 것이 아니다. 승인 칸이 있는 파일이 두 목록 **어디에도**
      없으면 여전히 걸린다 (⑭ 절에서 그 파일이 실제로 담기는지도 따로 돌려 본다).
    """
    담을것 = set(총괄.아웃풋1에담을것) | set(총괄.아웃풋1에있으면담을것)
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
    for 조각 in ("--조건", "--확인만", "--승인", "--4차반영", "--되감기", "상태.json"):
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


# ── ⑧ 미리보기가 **말과 같은가** (2026-10-22 Codex 교차점검) ──────────────────────
#   ★ 찾은 것 둘 —
#     ① 「아무것도 돌리지 않았고 돈도 쓰지 않았습니다」 라고 말하면서 판자리와
#        `상태.json` 을 **만들었다.** 말과 행동이 달랐다.
#     ② 미리보기가 **비용 숫자를 말하지 않았다.** 돌리개는 1차에 `--승인` 을 붙여
#        넘기므로 사람이 어림을 보는 자리는 미리보기 한 곳뿐이다. 숫자가 없으면
#        묻지 않고 돈이 나가는 셈이 된다.
def _미리보기_돌리기(monkeypatch, 판자리, 조건="검색어=시험; 영상=5; 댓글=50") -> str:
    import io as _io
    import contextlib
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(판자리), "--확인만", "--조건", 조건])
    통 = _io.StringIO()
    with contextlib.redirect_stdout(통):
        코드 = 총괄.main()
    assert 코드 == 0, 통.getvalue()[-800:]
    return 통.getvalue()


def test_미리보기는_아무것도_쓰지_않는다(monkeypatch, tmp_path):
    판자리 = tmp_path / "아직_없는_자리"
    _미리보기_돌리기(monkeypatch, 판자리)
    assert not 판자리.exists(), "미리보기가 판자리를 만들었다 — 말과 다르다"


def test_미리보기가_어림을_말한다(monkeypatch, tmp_path):
    글 = _미리보기_돌리기(monkeypatch, tmp_path / "자리")
    for 말 in ("어림", "조각", "분", "$", "할당량"):
        assert 말 in 글, "미리보기가 「%s」 를 말하지 않았다 — 묻지 않고 돈이 나간다" % 말
    assert "판독자 둘" in 글 and "따로" in 글, \
        "1차 어림만 말하고 판독·감독 값을 안 말했다 — 사람이 전체 비용을 모른다"


def test_어림은_1차돌리개에서_온다():
    """두 벌로 세지 않는다 — 잰 숫자는 `1차_돌리기.py` 의 `잰것` 한 곳에 있다."""
    모 = 총괄._일차돌리개()
    assert 모 is not None, "1차 돌리개를 못 봤다 — 못 찾음은 통과가 아니다"
    assert hasattr(모, "어림") and hasattr(모, "잰것"), "어림·잰것이 1차 돌리개에 없다"
    e = 모.어림(5, 50)
    for 칸 in ("모은댓글", "조각", "분", "달러", "할당량"):
        assert 칸 in e, "어림에 %s 가 없다" % 칸
    글 = Path(총괄.__file__).read_text(encoding="utf-8")
    assert "잰것 =" not in 글, "총괄이 잰 숫자를 또 적었다 (두 벌)"


def test_1차돌리개를_못_보면_크게_실패한다(monkeypatch, tmp_path):
    """「못 찾음」 은 「없음」 이 아니다 — 1차 돌리개를 못 보면 키 이름도 어림도 못 낸다.

    ★ 처음 이 시험을 「어림만 못 낸다」 로 적었다가 틀렸다. 실제로는 갖춤새 점검이
      **먼저** 「키 이름 목록을 못 봤습니다」 로 잡고 종료코드 2 로 멈춘다. 그게 맞다 —
      조용히 넘어가는 것보다 크게 실패하는 쪽이다.
    """
    import io as _io
    import contextlib
    monkeypatch.setattr(총괄, "_일차돌리개", lambda: None)
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(tmp_path / "자리"), "--확인만",
                         "--조건", "검색어=시험; 영상=5; 댓글=50"])
    통 = _io.StringIO()
    with contextlib.redirect_stdout(통):
        코드 = 총괄.main()
    글 = 통.getvalue()
    assert 코드 == 2, "못 봤는데 통과했다"
    assert "키 이름 목록을 못 봤습니다" in 글, 글[-600:]
    assert "못 찾음은 통과가 아닙니다" in 글, 글[-600:]


def test_어림만_못_낼_때는_그렇게_말하고_계속한다(monkeypatch, tmp_path):
    """키 이름은 보이지만 `어림()` 이 없는 경우 — 조용히 넘어가지 않는다."""
    import io as _io
    import contextlib

    class _반쪽:
        키들 = 총괄._키이름들()

    monkeypatch.setattr(총괄, "_일차돌리개", lambda: _반쪽())
    for k in _반쪽.키들:
        monkeypatch.setenv(k, "시험용-값-아님")
    monkeypatch.setattr(총괄.shutil, "which", lambda x: "/시험/" + x)
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(tmp_path / "자리"), "--확인만",
                         "--조건", "검색어=시험; 영상=5; 댓글=50"])
    통 = _io.StringIO()
    with contextlib.redirect_stdout(통):
        코드 = 총괄.main()
    글 = 통.getvalue()
    assert 코드 == 0, 글[-600:]
    assert "어림을 내지 못했습니다" in 글, 글[-800:]


# ── ⑨ 돈 관문 — 승인 없이는 돌지 않는다 (2026-10-22) ────────────────────────────
#   ★ 왜 생겼나. 돌리개는 1차에 `--승인` 을 **자동으로** 붙여 넘겼다. 그래서 사람이
#     어림을 보는 자리도, 승인하는 자리도 없었다. 그날 내가 코드를 잘못 고쳐
#     미리보기가 실제 실행으로 흘렀고, **묻지 않은 1차가 돌아** 유튜브 할당량 108 과
#     OpenAI 호출 44 번을 썼다. 관문이 있으면 그렇게 흐르지 못한다.
#   ★ 이 시험들은 **아무것도 돌리지 않는다** — `단계들` 을 빈 목록으로 바꿔 둔다.
def _돌려보기(monkeypatch, 판자리, *덧붙임, 단계비우기=True) -> tuple:
    import io as _io
    import contextlib
    if 단계비우기:
        monkeypatch.setattr(총괄, "단계들", [])
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(판자리),
                         "--조건", "검색어=시험; 영상=5; 댓글=50", *덧붙임])
    통 = _io.StringIO()
    with contextlib.redirect_stdout(통):
        코드 = 총괄.main()
    return 코드, 통.getvalue()


def test_승인_없이는_돌지_않는다(monkeypatch, tmp_path):
    코드, 글 = _돌려보기(monkeypatch, tmp_path / "자리")
    assert 코드 == 2, "승인 없이 돌았다 — 묻지 않고 돈이 나간다" + 글[-600:]
    assert "돌리지 않았습니다" in 글, 글[-600:]
    assert "--승인" in 글, "무엇을 붙이라는지 말하지 않았다"


def test_승인_관문이_어림을_같이_말한다(monkeypatch, tmp_path):
    """숫자를 안 보여 주고 승인을 받는 것은 승인이 아니다."""
    _, 글 = _돌려보기(monkeypatch, tmp_path / "자리")
    for 말 in ("어림", "조각", "$", "할당량", "판독자 둘"):
        assert 말 in 글, "관문이 「%s」 를 말하지 않았다" % 말


def test_승인을_붙이면_지나간다(monkeypatch, tmp_path):
    판자리 = tmp_path / "자리"
    코드, 글 = _돌려보기(monkeypatch, 판자리, "--승인")
    assert 코드 == 0, 글[-800:]
    상태 = json.loads((판자리 / "상태.json").read_text(encoding="utf-8"))
    assert 상태.get("승인") is True, "승인을 적어 두지 않았다 — 이어갈 때 또 묻는다"


def test_한_번_승인하면_이어갈_때_또_묻지_않는다(monkeypatch, tmp_path):
    """「멈춰도 같은 명령을 그대로 다시 넣으면 이어진다」 가 살아 있어야 한다."""
    판자리 = tmp_path / "자리"
    판자리.mkdir()
    (판자리 / "상태.json").write_text(
        json.dumps({"끝난단계": [], "소견": [], "기록": {}, "승인": True}, ensure_ascii=False),
        encoding="utf-8")
    코드, 글 = _돌려보기(monkeypatch, 판자리)          # `--승인` 없이
    assert 코드 == 0, "이미 승인한 판인데 또 막았다" + 글[-600:]


def test_미리보기는_승인을_요구하지_않는다(monkeypatch, tmp_path):
    """미리보기는 돈이 안 든다 — 관문이 걸리면 안 된다."""
    코드, 글 = _돌려보기(monkeypatch, tmp_path / "자리", "--확인만", 단계비우기=False)
    assert 코드 == 0, 글[-600:]
    assert "돌리지 않았습니다" not in 글, "미리보기를 승인 관문이 막았다"


# ── ⑩ 실행조건 — 적은 칸이 **엔진까지 가는가** (2026-10-22 재점검) ────────────────
#   ★ 찾은 것 — 전에는 네 칸(검색어 · 영상 · 댓글 · 이름)만 넘겼다. 원문에는 스물두 칸이
#     있는데 나머지는 엔진 기본값으로 **조용히** 떨어졌다. 국가·언어·게시일·대댓글을
#     바꿔 돌릴 길이 아예 없었고, 적어도 사라졌다 (`_조건풀기` 가 버렸다).
def test_조건칸이_1차돌리개_한_곳에_있다():
    모 = 총괄._일차돌리개()
    assert 모 is not None, "1차 돌리개를 못 봤다 — 못 찾음은 통과가 아니다"
    assert hasattr(모, "조건칸") and hasattr(모, "꼭묻는칸"), "조건칸·꼭묻는칸이 없다"
    이름들 = [c[0] for c in 모.조건칸]
    # sky 2026-10-22 가 「그 외에는 필수」 라고 가른 열 칸
    for 칸 in ("검색어", "키워드들", "결합", "시작일", "종료일", "국가", "언어",
              "영상", "댓글", "대댓글"):
        assert 칸 in 모.꼭묻는칸, "반드시 묻는 칸에서 빠졌다 — %s" % 칸
    # sky 가 「필수가 아닐 수도」 라고 한 것들
    for 칸 in ("채널", "최대행", "묶음", "대기초", "모델"):
        assert 칸 in 이름들, "칸이 아예 없다 — %s" % 칸
        assert 칸 not in 모.꼭묻는칸, "묻지 않기로 한 칸을 필수로 적었다 — %s" % 칸


def test_모든_조건칸이_엔진_옵션에_이어진다():
    """칸마다 엔진이 **실제로 받는** 옵션이 있어야 한다. 없는 옵션을 넘기면 엔진이 죽는다."""
    모 = 총괄._일차돌리개()
    엔진돌리개 = _뿌리 / "plugin" / "engine" / "scripts" / \
        "run_dashboard60_youtube_collect_and_analyze.py"
    assert 엔진돌리개.is_file(), "엔진 돌리개를 못 찾았다 — 못 찾음은 통과가 아니다"
    글 = 엔진돌리개.read_text(encoding="utf-8")
    for 칸, 옵션, _기, _꼭, _설 in 모.조건칸:
        assert ('"%s"' % 옵션) in 글, "엔진이 받지 않는 옵션이다 — %s → %s" % (칸, 옵션)


def test_조건을_적으면_버리지_않는다():
    """`_조건풀기` 가 네 칸만 남기고 버리던 자리."""
    조건 = 총괄._조건풀기(
        "검색어=LG 로봇청소기; 국가=US; 언어=en; 대댓글=false; 최대행=100", Path("."))
    for 칸, 값 in (("국가", "US"), ("언어", "en"), ("대댓글", "false"), ("최대행", "100")):
        assert 조건.get(칸) == 값, "적은 칸이 사라졌다 — %s (받은 것: %r)" % (칸, 조건)


def test_모르는_칸은_잡는다():
    조건 = 총괄._조건풀기("검색어=x; 국가코드=US; 언어코드=en", Path("."))
    모름 = 총괄.모르는조건(조건)
    assert "국가코드" in 모름 and "언어코드" in 모름, "오타를 못 잡았다 — %r" % (모름,)
    assert "검색어" not in 모름 and "이름" not in 모름, "쓰는 칸을 모른다고 했다 — %r" % (모름,)


def test_모르는_칸이_있으면_돌지_않는다(monkeypatch, tmp_path):
    import io as _io
    import contextlib
    monkeypatch.setattr(총괄, "단계들", [])
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(tmp_path / "자리"), "--확인만",
                         "--조건", "검색어=x; 국가코드=US; 영상=5; 댓글=50"])
    통 = _io.StringIO()
    with contextlib.redirect_stdout(통):
        코드 = 총괄.main()
    assert 코드 == 2, "모르는 칸이 있는데 지나갔다"
    assert "모르는 조건 칸입니다" in 통.getvalue()


def test_댓글_0이면_어림을_내지_않고_멈춘다(monkeypatch, tmp_path):
    """★ 「가능한 모두」 는 양을 모른다. 모르는 것을 숫자로 말하면 승인이 거짓이 된다."""
    import io as _io
    import contextlib
    monkeypatch.setattr(총괄, "단계들", [])
    monkeypatch.setattr(총괄.sys, "argv",
                        ["한줄_돌리기.py", str(tmp_path / "자리"),
                         "--조건", "검색어=x; 영상=5; 댓글=0"])
    통 = _io.StringIO()
    with contextlib.redirect_stdout(통):
        코드 = 총괄.main()
    글 = 통.getvalue()
    assert 코드 == 2, "양을 모르는데 승인 관문을 지나갔다"
    assert "어림을 낼 수 없습니다" in 글, 글[-700:]
    assert "최대행" in 글, "묶는 길을 알려 주지 않았다"


def test_최대행을_걸면_어림이_줄어든다():
    모 = 총괄._일차돌리개()
    다 = 모.어림(5, 50)
    끊은것 = 모.어림(5, 50, 100)
    assert 끊은것["분석조각"] == 100 < 다["조각"], 끊은것
    assert 끊은것["달러"] < 다["달러"], "분석을 줄였는데 돈이 그대로다"
    assert 끊은것["할당량"] == 다["할당량"], "수집은 안 줄었는데 할당량이 줄었다"


def test_최댓값을_넘기면_돌리개가_멈춘다():
    """엔진이 조용히 깎는 것보다 여기서 말하는 쪽이 낫다."""
    모 = 총괄._일차돌리개()
    assert 모.최댓값["영상"] == 500 and 모.최댓값["댓글"] == 2000, 모.최댓값
    assert 모.최댓값["최대행"] == 10000, 모.최댓값


def test_스킬_문서가_묻는_칸을_적는다():
    """AI 가 무엇을 물어야 하는지 **문서에서** 알 수 있어야 한다."""
    일차 = (_뿌리 / "plugin" / "skills" / "running-voc-engine" / "SKILL.md") \
        .read_text(encoding="utf-8")
    for 칸 in ("키워드들", "결합", "시작일", "종료일", "국가", "언어", "대댓글"):
        assert ("`%s`" % 칸) in 일차, "1차 스킬 문서에 칸이 없다 — %s" % 칸
    for 말 in ("최대행", "묶음", "대기초", "중간 저장"):
        assert 말 in 일차, "끊길 때 묶는 법에서 빠졌다 — %s" % 말
    총괄글 = _스킬글()
    for 칸 in ("키워드들", "대댓글", "최대행"):
        assert 칸 in 총괄글, "총괄 문서에 칸이 없다 — %s" % 칸
    assert "국가코드=US" in 총괄글, "오타가 멈춘다는 말이 없다"


# ── ⑪ 키워드 결합 OR · AND 기준 (2026-10-22 · sky 「명확히 기록해주세요」) ──────────
#   ★ 왜 — 2026-08-20 에 대시보드 안내문이 **코드와 달랐다.** 「키워드별 개별 검색 후 공통」
#     이라 적혀 있었으나 실제로는 맨 윗줄로만 검색하고 아랫줄은 영상 메타데이터에서 글자로
#     걸러낸다. 안내문은 사람이 쓰므로 또 어긋날 수 있다. 그래서 **기준서가 엔진 코드와
#     같은 말을 하는지** 여기서 대본다.
_결합기준 = _뿌리 / "plugin" / "shared" / "common" / "키워드결합_OR_AND_기준.md"
_인제스트 = _뿌리 / "plugin" / "engine" / "src" / "pipelines" / "ingest_pipeline.py"


def test_결합기준서가_있다():
    assert _결합기준.is_file(), "OR·AND 기준서를 못 찾았다 — 못 찾음은 통과가 아니다"
    assert _인제스트.is_file(), "엔진 인제스트를 못 찾았다"


def test_결합기준서가_엔진_상수와_같은_숫자를_적는다():
    """후보를 몇 개까지 넓히는지 — 기준서의 숫자가 엔진과 어긋나면 사람이 잘못 안다."""
    엔진 = _인제스트.read_text(encoding="utf-8")
    기준 = _결합기준.read_text(encoding="utf-8")
    for 이름, 값 in (("AND_CANDIDATE_MULTIPLIER", "5"),
                   ("AND_CANDIDATE_MIN", "200"),
                   ("AND_CANDIDATE_CAP", "300")):
        쪽 = "%s = %s" % (이름, 값)
        assert 쪽 in 엔진, "엔진 상수가 바뀌었다 — %s" % 이름
        # ★ 처음에는 `이름 in 기준 and 값 in 기준` 으로 적었다 — **헛통과했다.**
        #   「200~300개」 같은 글에도 300 이 있어서, 상수를 999 로 틀리게 적어도 지나갔다.
        #   그래서 **상수 줄 그대로**를 찾는다 (기준서가 코드를 그대로 인용한다).
        assert 쪽 in 기준, "기준서의 상수가 엔진과 다르다 — %s 가 없다" % 쪽


def test_결합기준서가_걸러내는_자리_넷을_적는다():
    """제목 · 설명 · 채널명 둘 · 태그 — 엔진이 보는 자리와 같아야 한다."""
    엔진 = _인제스트.read_text(encoding="utf-8")
    기준 = _결합기준.read_text(encoding="utf-8")
    assert '("title", "description", "channel_title", "channel_name")' in 엔진, \
        "엔진이 보는 자리가 바뀌었다 — 기준서를 다시 맞춰야 한다"
    for 말 in ("title", "description", "channel_title", "channel_name", "tags"):
        assert 말 in 기준, "기준서에 걸러내는 자리가 없다 — %s" % 말
    assert "댓글 본문은 보지 않는다" in 기준, "댓글을 보지 않는다는 말이 없다 (헷갈리는 자리다)"


def test_결합기준서가_AND는_교집합이_아니라고_못박는다():
    기준 = _결합기준.read_text(encoding="utf-8")
    assert "교집합" in 기준 and "아니다" in 기준, "2026-08-20 에 틀렸던 그 말을 못박지 않았다"
    assert "맨 윗줄이 모수를 정한다" in 기준, "무엇이 모수를 정하는지 적지 않았다"
    # 최소매칭이 비면 전체 수라는 것 — 셈이 달라지는 자리다
    assert "비우면 = 키워드 전체 수" in 기준 or "비우면 **= 키워드 전체 수**" in 기준, \
        "최소매칭 기본값(= 전체 포함)을 적지 않았다"


def test_AND는_키워드가_하나면_OR와_같다():
    """엔진이 `len(search_keywords) > 1` 로 가른다 — 기준서도 그렇게 적어야 한다."""
    엔진 = _인제스트.read_text(encoding="utf-8")
    assert 'if keyword_mode == "AND" and len(search_keywords) > 1:' in 엔진, \
        "엔진의 갈림 조건이 바뀌었다"
    assert "AND 인데 키워드가 하나면 OR 와 똑같이 돈다" in _결합기준.read_text(encoding="utf-8")


def test_스킬_문서들이_결합기준서를_가리킨다():
    """AI 가 묻기 전에 읽어야 한다 — 문서가 가리키지 않으면 안 읽는다."""
    일차 = (_뿌리 / "plugin" / "skills" / "running-voc-engine" / "SKILL.md") \
        .read_text(encoding="utf-8")
    assert "키워드결합_OR_AND_기준.md" in 일차, "1차 스킬이 기준서를 가리키지 않는다"
    assert "키워드결합_OR_AND_기준.md" in _스킬글(), "총괄 스킬이 기준서를 가리키지 않는다"
    # 1차 작업 폴더에도 같이 놓이는가
    자리글 = (_뿌리 / "plugin" / "shared" / "lib" / "일차자리.py").read_text(encoding="utf-8")
    assert "키워드결합_OR_AND_기준.md" in 자리글, "1차 자리에 기준서를 놓지 않는다"


# ── ⑫ yaml 이 없는 파이썬 (2026-10-27 · 깨끗한 판 1 실측) ──────────────────────
#   ★ 찾은 구멍 둘 — 2026-10-09 에 pandas 때문에 **Codex 내장 파이썬**을 PATH 앞에 놓았다.
#     그 파이썬에는 pandas 3.0.1 · openpyxl 3.1.5 는 있고 **yaml 이 없다.**
#     ① `check_selfcheck._일차가_내놓는가()` 가 `from src.voc_rebuild import schema` 로
#        꾸러미를 불러왔고, 그 `__init__.py` → `.engine` → `config.py` → `yaml` 로 내려가
#        import 가 터졌다. 그래서 눈먼 길(`return True`)로 떨어져, 1차가 애초에 안 내놓는
#        `video_tags`·`video_description` 을 「번들에서 빠진 칸 ✗」 으로 **잘못 반려**했다.
#        VOC_ENGINE 을 줘도 막히지 않는다 — 가리키는 것과 **불러오는 것**이 다른 일이다.
#     ② 갖춤새 점검은 **총괄 파이썬**만 봤다. 돌리는 자리의 파이썬을 안 봐서
#        판독B 가 XLSX 번들과 계약·제출 검사를 못 만든 것을 미리 알릴 길이 없었다.
def _yaml_가리고(일하기):
    """yaml import 를 막은 채로 일을 시킨다 — Codex 내장 파이썬 흉내."""
    import builtins
    참 = builtins.__import__

    def 가짜(name, *a, **k):
        if name == "yaml" or name.startswith("yaml."):
            raise ImportError("No module named 'yaml'")
        return 참(name, *a, **k)

    지운것 = {k: v for k, v in sys.modules.items() if k == "yaml" or k.startswith("yaml.")}
    for k in 지운것:
        del sys.modules[k]
    builtins.__import__ = 가짜
    try:
        return 일하기()
    finally:
        builtins.__import__ = 참
        sys.modules.update(지운것)


def test_yaml_이_없어도_칸을_가른다():
    """★ ① 의 진짜 값 — yaml 없는 파이썬에서도 「1차가 안 내놓는 칸」 을 안다."""
    import check_selfcheck
    총괄._엔진_가리키기()

    def 보기():
        return [check_selfcheck._일차가_내놓는가(c)
                for c in ("video_tags", "video_description", "atomic_id")]

    assert _yaml_가리고(보기) == [False, False, True],         "yaml 이 없으면 칸을 가르지 못한다 — 안 깨진 번들을 깨졌다고 반려한다"


def test_엔진_schema_는_꾸러미를_안_불러온다():
    """`schema.py` **하나만** 읽는다 — 꾸러미를 불러오면 yaml 까지 끌려 온다."""
    import check_selfcheck
    총괄._엔진_가리키기()
    모 = _yaml_가리고(check_selfcheck._엔진_schema)
    assert 모 is not None, "yaml 없이 schema 를 못 읽었다"
    assert len(getattr(모, "TARGET_COLUMNS", [])) == 66,         "66칸 계약이 아니다 — %r" % (len(getattr(모, "TARGET_COLUMNS", [])),)


def test_엔진을_못_보면_눈먼길이라고_적는다(monkeypatch, tmp_path):
    """★ 일부러 엔진을 치운다 — 「못 봤다」 를 **조용히** 넘기지 않는지 본다 (공통 규칙 4)."""
    import check_selfcheck
    monkeypatch.delenv("VOC_ENGINE", raising=False)
    monkeypatch.setattr(check_selfcheck, "BASE", str(tmp_path))
    monkeypatch.setattr(check_selfcheck, "_HERE", str(tmp_path))
    가짜 = dict(sys.modules)
    sys.modules["src"] = None
    sys.modules["src.voc_rebuild"] = None
    sys.modules["src.voc_rebuild.schema"] = None
    check_selfcheck.눈먼길[:] = []
    try:
        assert check_selfcheck._일차가_내놓는가("video_tags") is True,             "엔진을 못 보는데도 가른다 — 이 시험이 지키는 것이 없다"
        assert check_selfcheck.눈먼길, "엔진을 못 봤는데 아무 말도 안 남겼다"
    finally:
        sys.modules.clear()
        sys.modules.update(가짜)


def test_갖춤새가_yaml_을_본다(monkeypatch):
    """번들 엑셀·계약 검사가 yaml 로 돌아간다 — 꾸러미 목록에 들어 있어야 한다."""
    assert "yaml" in 총괄._필요꾸러미, "yaml 을 안 본다 — XLSX 번들이 조용히 안 나온다"
    assert 총괄._핍이름들.get("yaml") == "pyyaml", "pip 이름이 pyyaml 이 아니다"


def test_갖춤새가_돌리는_자리의_파이썬을_본다(monkeypatch):
    """★ ② — **총괄 파이썬이 아니라** codex 쪽 파이썬에 없는 것을 말한다."""
    monkeypatch.setattr(총괄.shutil, "which", lambda n: "/시험/" + n)
    for k in 총괄._키이름들():
        monkeypatch.setenv(k, "시험용-값-아님")
    monkeypatch.setattr(총괄, "_없는꾸러미", lambda _: ["yaml"])
    monkeypatch.setattr(총괄.Path, "is_file", lambda self: True)
    안된것 = 총괄.갖춤새_점검([])
    붙은 = chr(10).join(총괄.귀띔)
    assert "yaml" in 붙은, "codex 파이썬에 yaml 이 없는데 말하지 않았다 — %r" % (총괄.귀띔,)
    assert "pip install pyyaml" in 붙은, "넣는 명령을 주지 않았다 — %r" % (총괄.귀띔,)
    for 자리 in ("판독B", "감독1"):
        assert 자리 in 붙은, "어느 자리가 막히는지 말하지 않았다 (%s)" % 자리
    # ★ **멈추지는 않는다** — yaml 이 없어도 CSV 번들은 나왔다 (2026-10-27 실측)
    assert not [x for x in 안된것 if "yaml" in x],         "yaml 없음으로 흐름을 막았다 — 되는 흐름을 0단계에서 세운다: %r" % (안된것,)


def test_코덱스_파이썬에_무엇이_있는지_못_물어보면_그렇다고_한다(monkeypatch):
    """「못 찾음」 을 「없음」 으로 돌려주지 않는다 (공통 규칙 4)."""
    monkeypatch.setattr(총괄.shutil, "which", lambda n: "/시험/" + n)
    for k in 총괄._키이름들():
        monkeypatch.setenv(k, "시험용-값-아님")
    monkeypatch.setattr(총괄, "_없는꾸러미", lambda _: None)
    monkeypatch.setattr(총괄.Path, "is_file", lambda self: True)
    총괄.갖춤새_점검([])
    assert [x for x in 총괄.귀띔 if "못 물어봤습니다" in x],         "못 물어봤는데 조용히 넘어갔다 — %r" % (총괄.귀띔,)


def test_없는꾸러미는_불러오지_않고_본다():
    """`find_spec` 으로 본다 — 불러오면 yaml 없는 자리에서 줄줄이 터져 가려진다."""
    글 = Path(총괄.__file__).read_text(encoding="utf-8")
    몸 = 글.split("def _없는꾸러미", 1)[1].split(chr(10) + "def ", 1)[0]
    assert "find_spec" in 몸, "find_spec 으로 보지 않는다"
    assert "__import__" not in 몸 and "importlib.import_module" not in 몸,         "꾸러미를 실제로 불러온다 — 없는 것이 가려진다"


# ── ⑬ 3차 감독을 **이어** 돌릴 때 (2026-10-27 · Codex 한도로 반쪽이 됐다) ──────────
#   ★ 찾은 구멍 — 건너뛰기 검사가 `감독결과_*.md` 가 **하나라도** 있으면 「이미 끝났다」 였다.
#     감독자는 회차마다 하나씩 낸다 (`s13_judge/judge_NN_ids.txt` 수만큼). 깨끗한 판 1 에서
#     감독1 이 judge_01(145행)만 내고 judge_02 중간에 멈췄다. 그대로 이어 돌리면
#     **남은 145행을 건너뛴 채** 3차마무리로 가서 반쪽 감독으로 최종 데이터가 만들어진다.
def _감독판(tmp_path, 낸수: dict, 회차: int = 2):
    """감독 폴더 둘을 차려 둔다 — `낸수` 는 폴더별로 이미 낸 감독결과 수."""
    판 = tmp_path / "판"
    조건 = {"이름": "판_시험"}
    (판 / "기록").mkdir(parents=True)
    for 번, (이름, _누구) in enumerate(총괄.감독자, start=1):
        자리 = 판 / "총괄" / 조건["이름"] / "_감독폴더" / ("3차 감독%d" % 번)
        (자리 / "s13_judge").mkdir(parents=True)
        for r in range(1, 회차 + 1):
            (자리 / "s13_judge" / ("judge_%02d_ids.txt" % r)).write_text("x", encoding="utf-8")
        결과 = 자리 / "_판독패키지" / "_결과"
        결과.mkdir(parents=True)
        (자리 / ".agents").mkdir()          # copytree 로 안 가게
        for r in range(1, 낸수.get(이름, 0) + 1):
            (결과 / ("감독결과_%02d_시험.md" % r)).write_text("판정", encoding="utf-8")
    return 판, 조건


def _감독_가로채기(monkeypatch, 낸것을_더함: int = 0):
    """AI돌리기 를 가로채 **누구를 어떤 말로 띄웠나**를 적어 둔다."""
    불린것 = []

    def 가짜(누구, 자리, 말, 기록):
        불린것.append((Path(자리).name, 누구, 말))
        결과 = Path(자리) / "_판독패키지" / "_결과"
        있는수 = len(list(결과.glob("감독결과_*.md")))
        for r in range(있는수 + 1, 있는수 + 1 + 낸것을_더함):
            (결과 / ("감독결과_%02d_시험.md" % r)).write_text("판정", encoding="utf-8")
        return 0, "했습니다"

    monkeypatch.setattr(총괄, "AI돌리기", 가짜)
    monkeypatch.setattr(총괄.subprocess, "run", lambda *a, **k: None)
    return 불린것


def test_반쪽만_낸_감독은_건너뛰지_않는다(monkeypatch, tmp_path):
    """★ 이 시험이 지키는 것 — 145행이 조용히 사라지지 않는다."""
    판, 조건 = _감독판(tmp_path, {"감독1": 1})
    불린것 = _감독_가로채기(monkeypatch, 낸것을_더함=2)
    총괄.단계_3차감독(판, {}, 조건, False)
    불린자리 = [x[0] for x in 불린것]
    assert "3차 감독1" in 불린자리, "회차 2 가운데 1 만 낸 감독을 건너뛰었다 — %r" % (불린것,)
    말 = [x[2] for x in 불린것 if x[0] == "3차 감독1"][0]
    assert "다시 하지 마시고" in 말, "이미 낸 회차를 또 하라고 보냈다 — %r" % 말
    assert "감독결과_01_시험.md" in 말, "어느 회차가 끝났는지 알려주지 않았다 — %r" % 말


def test_회차를_다_낸_감독은_건너뛴다(monkeypatch, tmp_path):
    """돈을 두 번 쓰지 않는다 (sky 「토큰을 최소화하며」) — 2026-10-09 고침을 지킨다."""
    판, 조건 = _감독판(tmp_path, {"감독1": 2, "감독2": 2})
    불린것 = _감독_가로채기(monkeypatch)
    총괄.단계_3차감독(판, {}, 조건, False)
    assert 불린것 == [], "다 끝난 감독을 또 띄웠다 — %r" % (불린것,)


def test_회차를_덜_내고_끝나면_멈춘다(monkeypatch, tmp_path):
    """★ 일부러 모자라게 낸다 — 반쪽으로 3차마무리에 넘기지 않는다."""
    판, 조건 = _감독판(tmp_path, {})
    _감독_가로채기(monkeypatch, 낸것을_더함=1)      # 회차 2 인데 1 만 낸다
    with pytest.raises(총괄.멈춤) as 터짐:
        총괄.단계_3차감독(판, {}, 조건, False)
    assert "1/2" in str(터짐.value), "몇 개 가운데 몇 개인지 말하지 않았다 — %s" % 터짐.value


def test_실제_멈춘_판에서도_회차가_모자라면_이어_돌린다():
    """★ 만든 표가 아니라 **실제 판**을 본다 (공통 규칙 4 — 안 돌려 본 자리부터).

    판 자리는 사람마다 다르므로 **환경변수 `VOC_REAL_RUN`** 으로 준다. 코드에 절대경로를
    박으면 `tests/test_no_old_paths.py` 가 막는다 (그 자리는 `paths.py` 한 곳이다).

        VOC_REAL_RUN=<판자리> python -m pytest tests/test_총괄환경.py -k 실제_멈춘

    ★ 2026-10-27 에 그날의 깨끗한 판으로 손으로 돌려 **회차 2 가운데 1** 인 것을 봤다
      (결정 0007 §8). 그래서 이어 돌리면 감독1 을 건너뛰지 않는다.

    ★ 2026-10-28 — 그 판이 **다 끝났다** (감독 둘 다 2/2). 그래서 전에 쓴 「반쪽이 하나는
      있어야 한다」 는 단정은 이제 **반드시 실패한다.** 반쪽을 요구하는 대신,
      ① 실제 판의 폴더마다 회차와 낸 수를 읽어 **코드의 판단이 그 수와 맞는지** 묻고,
      ② 실제 판에서 읽은 회차 수로 **반쪽을 만들어** 다시 묻는다. 판이 끝난 뒤에도
      이 시험이 지키는 것이 남아야 한다. 실제 판은 **읽기만** 한다.
    """
    자리글 = os.environ.get("VOC_REAL_RUN")
    if not 자리글:
        pytest.skip("VOC_REAL_RUN 이 없다 — 실제 판을 가리키면 그 자리를 본다")
    판 = Path(자리글)
    폴더들 = sorted(판.glob("총괄/*/_감독폴더/*"))
    if not 폴더들:
        pytest.fail("VOC_REAL_RUN(%s) 에 감독 폴더가 없다 — 못 찾음은 통과가 아니다" % 자리글)
    셈 = []
    for 자리 in 폴더들:
        회차수, 낸수 = 총괄.감독_회차셈(자리)
        셈.append((자리.name, 회차수, 낸수))
        # ★ 같은 말을 다시 적지 않고 **코드에 묻는다** (헛통과를 막는다)
        건너뛸까 = 총괄.감독을_건너뛸까(자리)
        if 낸수 < 회차수:
            assert 건너뛸까 is False, (
                "%s 를 「이미 끝났다」 로 본다 — 남은 회차가 사라진다 (회차/낸것 %r)"
                % (자리.name, 셈))
        else:
            assert 건너뛸까 is True, (
                "%s 는 회차를 다 냈는데 또 돌리려 한다 — 돈이 두 번 나간다 (회차/낸것 %r)"
                % (자리.name, 셈))


def test_실제_판의_회차수로_반쪽을_만들면_건너뛰지_않는다(tmp_path):
    """★ 판이 다 끝난 뒤에도 재는 것 — 실제 판에서 **회차 수만 읽어** 반쪽을 만든다.

    원본은 건드리지 않는다 (읽기만). 만든 자리에서 코드에 묻는다.
    """
    자리글 = os.environ.get("VOC_REAL_RUN")
    if not 자리글:
        pytest.skip("VOC_REAL_RUN 이 없다 — 실제 판을 가리키면 그 자리를 본다")
    폴더들 = sorted(Path(자리글).glob("총괄/*/_감독폴더/*"))
    if not 폴더들:
        pytest.fail("VOC_REAL_RUN(%s) 에 감독 폴더가 없다 — 못 찾음은 통과가 아니다" % 자리글)
    회차수, _낸수 = 총괄.감독_회차셈(폴더들[0])
    assert 회차수 >= 2, ("실제 판의 회차가 %d 다 — 1 회차면 반쪽이 있을 수 없어 "
                      "이 시험이 지키는 것이 없다" % 회차수)
    판, _조건 = _감독판(tmp_path, {"감독1": 회차수 - 1, "감독2": 회차수}, 회차=회차수)
    자리들 = {q.name: q for q in sorted(판.glob("총괄/*/_감독폴더/*"))}
    assert 총괄.감독을_건너뛸까(자리들["3차 감독1"]) is False, (
        "회차 %d 가운데 %d 만 냈는데 건너뛴다" % (회차수, 회차수 - 1))
    assert 총괄.감독을_건너뛸까(자리들["3차 감독2"]) is True, (
        "회차 %d 를 다 냈는데 또 돌리려 한다" % 회차수)


# ── ⑭ 감독이 낸 분리가 **사람에게 가는가** (2026-10-28 · 깨끗한 판 1 재점검) ─────────
#   ★ 찾은 구멍 — `build_master.py` 는 3차 감독이 「나눠야 한다」 로 낸 행을
#     `s15_master/감독_분리제안.csv` 로 쓰고 `승인상태` 칸까지 만들어 둔다.
#     그런데 그 파일을 읽는 코드는 `총괄검수.py` 하나(화면에 숫자만 찍는다)뿐이었고,
#     아웃풋 1 에도 `3차_최종데이터.xlsx` 에도 담기지 않았다. 사람이 받는 `분리제안.csv` 는
#     **판독자 2 의 번들을 이은 것**이라 깨끗한 판 1 에서는 0행이었다 —
#     회의 자료에는 「분리할 것 없음」 으로 보이고 감독이 낸 6건은 아무 데도 안 보였다.
def _아웃풋1판(tmp_path, 감독분리행: int = 0, 분리재지정: bool = False):
    """아웃풋 1 이 멈추지 않을 만큼만 차린 판 — `s15_master` 에 최종 파일들을 둔다."""
    판 = tmp_path / "판"
    조건 = {"이름": "판_시험"}
    (판 / "기록").mkdir(parents=True)
    자리 = 판 / "총괄" / 조건["이름"] / "s15_master"
    자리.mkdir(parents=True)
    for 이름 in 총괄.아웃풋1에담을것:
        (자리 / 이름).write_text("atomic_id,승인상태\n", encoding="utf-8")
    if 감독분리행:
        줄 = ["origin_atomic_id,승인상태"]
        for i in range(감독분리행):
            줄.append("a%d,한쪽 감독만 냈습니다 — 사람 확인" % i)
        (자리 / "감독_분리제안.csv").write_text("\n".join(줄) + "\n", encoding="utf-8")
    if 분리재지정:
        (판 / "총괄" / 조건["이름"] / "분리재지정_01.md").write_text("{}", encoding="utf-8")
    return 판, 조건


def test_감독_분리제안은_있으면담을것에_있다():
    """필수 목록에 넣으면 **감독이 분리를 안 낸 정상인 판이 멈춘다**."""
    assert "감독_분리제안.csv" in 총괄.아웃풋1에있으면담을것
    assert "감독_분리제안.csv" not in 총괄.아웃풋1에담을것, (
        "필수 목록에 있다 — `build_master.py` 는 낸 것이 없으면 이 파일을 안 만든다")


def test_감독이_분리를_안_내면_아웃풋1이_멈추지_않는다(tmp_path):
    판, 조건 = _아웃풋1판(tmp_path, 감독분리행=0)
    총괄.단계_아웃풋1(판, {}, 조건, False)
    모을곳 = 판 / "아웃풋1_회의에서_정할것"
    assert (모을곳 / "사람이볼목록.csv").is_file()
    assert not (모을곳 / "감독_분리제안.csv").exists(), "없는 것을 만들어 냈다"


def test_감독이_분리를_내면_아웃풋1에_담긴다(tmp_path):
    """★ 이 시험이 지키는 것 — 감독이 낸 6건이 회의 자료에서 사라지지 않는다."""
    판, 조건 = _아웃풋1판(tmp_path, 감독분리행=6)
    총괄.단계_아웃풋1(판, {}, 조건, False)
    담긴것 = 판 / "아웃풋1_회의에서_정할것" / "감독_분리제안.csv"
    assert 담긴것.is_file(), "감독이 낸 분리가 아웃풋 1 에 안 담겼다"
    assert 담긴것.read_text(encoding="utf-8").count(chr(10)) == 7, "행이 모자라다"


def test_담기면_4차가_안_읽는다는_말이_소견에_간다(tmp_path):
    """승인해도 데이터에 안 들어가는 것을 **조용히** 두지 않는다."""
    판, 조건 = _아웃풋1판(tmp_path, 감독분리행=6)
    상태 = {}
    총괄.단계_아웃풋1(판, 상태, 조건, False)
    말들 = " / ".join(s["말"] for s in 상태.get("소견", []))
    assert "감독_분리제안" in 말들, "감독 분리가 들어온 것을 안 알렸다 — %s" % 말들
    assert "자동으로 반영하지 않습니다" in 말들, (
        "4차가 안 읽는다는 말이 없다 — 사람이 승인하고 반영됐다고 믿는다. %s" % 말들)


def test_분리재지정이_있으면_4차경고를_내지_않는다(tmp_path):
    """★ 겁주기가 아니라 **재는 것**이다 — 4차가 읽을 파일이 있으면 경고하지 않는다."""
    판, 조건 = _아웃풋1판(tmp_path, 감독분리행=6, 분리재지정=True)
    판자리 = 판 / "총괄" / 조건["이름"]
    말들 = 총괄.감독분리_알릴말(판자리, 판자리 / "s15_master" / "감독_분리제안.csv")
    assert 말들, "들어온 것 자체는 알려야 한다"
    assert not any("자동으로 반영하지 않습니다" in m for m in 말들), (
        "4차가 읽을 `분리재지정_*.md` 가 있는데도 경고했다 — %r" % (말들,))


def test_못_읽으면_알릴것_없음으로_돌려주지_않는다(tmp_path):
    """「못 찾음」 은 통과가 아니다 (공통 규칙 4)."""
    판, 조건 = _아웃풋1판(tmp_path, 감독분리행=6)
    판자리 = 판 / "총괄" / 조건["이름"]
    말들 = 총괄.감독분리_알릴말(판자리, 판자리 / "s15_master" / "없는파일.csv")
    assert any("다시 읽지 못했습니다" in m for m in 말들), (
        "못 읽었는데 조용히 빈 목록을 돌려줬다 — %r" % (말들,))


def test_인풋2칸에_감독_분리제안이_있다():
    칸들 = {이름: (칸, 안정함) for 이름, 칸, _, 안정함 in 총괄.인풋2칸}
    assert "감독_분리제안.csv" in 칸들, "사람이 적을 자리로 세지 않는다"
    칸, 안정함 = 칸들["감독_분리제안.csv"]
    assert 칸 == "승인상태"
    assert 안정함 is None, (
        "안 정한 표시를 목록으로 적어 뒀다 — `build_master.py` 의 안내 문구가 바뀌면 "
        "**안 정한 것을 정했다고** 센다 (2026-10-28 에 0칸으로 찍혔다)")


def test_안내문구를_안_정한_것으로_센다():
    """★ 일부러 틀린 값을 준다 — 승인·반려가 아니면 전부 「안 정함」 이다."""
    assert 총괄._안정했나("한쪽 감독만 냈습니다 — 사람 확인", None) is True
    assert 총괄._안정했나("", None) is True
    assert 총괄._안정했나("무슨 말이든", None) is True
    assert 총괄._안정했나("승인", None) is False
    assert 총괄._안정했나("반려", None) is False
    # 목록을 준 자리는 전처럼 그 목록으로만 본다
    assert 총괄._안정했나("대기", ("", "대기")) is True
    assert 총괄._안정했나("승인", ("", "대기")) is False


def test_담긴_감독분리_6행이_적을자리_6칸으로_센다(tmp_path):
    """세는 자리와 담는 자리가 **같은 수**를 말해야 한다."""
    판, 조건 = _아웃풋1판(tmp_path, 감독분리행=6)
    총괄.단계_아웃풋1(판, {}, 조건, False)
    남은 = 총괄.인풋2_센다(판 / "아웃풋1_회의에서_정할것")
    assert 남은.get("감독_분리제안.csv") == 6, (
        "6행이 들어왔는데 적을 자리를 %r 로 센다" % (남은.get("감독_분리제안.csv"),))


# ── ⑭-2 소견이 되감기마다 쌓이지 않는가 (2026-10-28) ──────────────────────────
def test_같은_소견은_두_번_쌓이지_않는다(tmp_path):
    """`--되감기` 로 한 단계를 다시 돌리면 같은 줄이 또 쌓였다 — 세 번 읽게 됐다."""
    판 = tmp_path / "판"
    (판 / "기록").mkdir(parents=True)
    상태 = {}
    for _ in range(3):
        총괄.소견더하기(판, 상태, "아웃풋1", "같은 말")
    assert len(상태["소견"]) == 1, "같은 말이 %d벌 쌓였다" % len(상태["소견"])


def test_소견md가_상태json과_같은_수를_적는다(tmp_path):
    """★ 숫자가 둘이 되지 않게 — 안 넣을 때도 md 는 다시 쓴다."""
    판 = tmp_path / "판"
    (판 / "기록").mkdir(parents=True)
    상태 = {}
    총괄.소견더하기(판, 상태, "아웃풋1", "첫 말")
    총괄.소견더하기(판, 상태, "아웃풋1", "둘째 말")
    상태["소견"] = 상태["소견"][:1]            # 바깥에서 줄였다 (내가 손으로 중복을 지운 일)
    총괄.소견더하기(판, 상태, "아웃풋1", "첫 말")    # 같은 말 — 안 넣는다
    줄수 = sum(1 for x in (판 / 총괄.소견이름).read_text(encoding="utf-8").splitlines()
             if x.startswith("- **["))
    assert 줄수 == len(상태["소견"]) == 1, (
        "상태.json 은 %d개인데 소견.md 는 %d줄이다 — 한 꾸러미에서 숫자가 둘"
        % (len(상태["소견"]), 줄수))


def test_실제_판의_아웃풋1에_감독분리가_담겨_있다():
    """★ 만든 표가 아니라 **실제 판**을 본다 (공통 규칙 4).

        VOC_REAL_RUN=<판자리> python -m pytest tests/test_총괄환경.py -k 실제_판의_아웃풋1
    """
    자리글 = os.environ.get("VOC_REAL_RUN")
    if not 자리글:
        pytest.skip("VOC_REAL_RUN 이 없다 — 실제 판을 가리키면 그 자리를 본다")
    판 = Path(자리글)
    원본들 = sorted(판.glob("총괄/*/s15_master/감독_분리제안.csv"))
    if not 원본들:
        pytest.skip("이 판에는 감독이 낸 분리가 없다 — `build_master.py` 가 파일을 안 만든다")
    모을곳 = 판 / "아웃풋1_회의에서_정할것"
    if not 모을곳.is_dir():
        pytest.fail("VOC_REAL_RUN(%s) 에 아웃풋1 이 없다 — 못 찾음은 통과가 아니다" % 자리글)
    담긴것 = 모을곳 / "감독_분리제안.csv"
    assert 담긴것.is_file(), (
        "%s 에 감독이 낸 분리가 있는데 아웃풋 1 에는 없다 — 회의에서 못 본다" % 원본들[0])
    assert 담긴것.read_bytes() == 원본들[0].read_bytes(), "담긴 것이 최종 자리와 다르다"
    남은 = 총괄.인풋2_센다(모을곳)
    assert 남은.get("감독_분리제안.csv"), (
        "담겨 있는데 적을 자리를 %r 로 센다 — 사람이 정할 것이 없다고 보인다"
        % (남은.get("감독_분리제안.csv"),))
