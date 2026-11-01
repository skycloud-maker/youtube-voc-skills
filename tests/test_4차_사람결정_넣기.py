# -*- coding: utf-8 -*-
"""사람 4차 결정을 넣는 도구가 **짐작으로 채우지 않는가** (2026-11-01).

★ 왜 이 시험이 있나 — sky 2026-11-01 —
  「뭐 **매번 4차는 사람이 한 게 없어서 임의로 테스트로 넣습니다** 이런 것만 하고」

  그래서 재는 것은 하나다 — **사람이 정하지 않은 행을 이 도구가 건드리는가.**
  건드리면 최종 데이터에 **AI 가 지어낸 결정**이 들어간다. 그것이 가장 나쁜 고장이다.
"""
from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
sys.path.insert(0, str(REPO / "tools"))


@pytest.fixture()
def 도구():
    m = importlib.import_module("4차_사람결정_넣기")
    return importlib.reload(m)


def _쓰기(쪽: Path, 칸들, 줄들):
    쪽.parent.mkdir(parents=True, exist_ok=True)
    with io.open(쪽, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=칸들)
        w.writeheader()
        for r in 줄들:
            w.writerow(r)


def _읽기(쪽: Path):
    with io.open(쪽, encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


@pytest.fixture()
def 자리(도구, tmp_path, monkeypatch):
    """옛 결정 셋 · 우리 행 넷을 둔 가짜 판을 차린다."""
    옛 = tmp_path / "옛"
    _쓰기(옛 / "감독_분리제안.csv",
         ["origin_atomic_id", "승인상태"],
         [{"origin_atomic_id": "AAA-01", "승인상태": "✅ 총괄 확정 — 나눈다"},
          {"origin_atomic_id": "BBB-01", "승인상태": "✅ 총괄 확정 — 과분리를 합친다"},
          {"origin_atomic_id": "DDD-01", "승인상태": "사람 최종 승인 대기"}])
    _쓰기(옛 / "수정로그_4차규칙_2판.csv",
         ["atomic_id", "field", "옛값", "새값", "규칙", "승인상태"],
         [{"atomic_id": "R-01", "field": "status/topic", "옛값": "x", "새값": "위생/냄새",
           "규칙": "§9", "승인상태": "총괄 적용 (sky 확정)"}])
    monkeypatch.setattr(도구, "옛자리", 옛)

    판 = tmp_path / "판"
    회의 = 판 / "아웃풋1_회의에서_정할것"
    조각 = json.dumps([{"atomic_voc": "가", "topic": "디자인"},
                      {"atomic_voc": "나", "topic": "소음"}], ensure_ascii=False)
    _쓰기(회의 / "감독_분리제안.csv",
         ["origin_atomic_id", "segments", "why", "승인상태"],
         [{"origin_atomic_id": "AAA-01", "segments": 조각, "why": "대상이 다르다",
           "승인상태": "★ 감독 둘이 다르게 나눴습니다 — 사람이 정하십시오"},
          {"origin_atomic_id": "BBB-01", "segments": 조각, "why": "",
           "승인상태": "한쪽 감독만 냈습니다 — 사람 확인"},
          {"origin_atomic_id": "CCC-01", "segments": 조각, "why": "",
           "승인상태": "사람 최종 승인 대기"}])
    _쓰기(회의 / "수정로그_오류확정.csv",
         ["atomic_id", "field", "제안값", "승인상태"],
         [{"atomic_id": "R-01", "field": "topic", "제안값": "위생/냄새", "승인상태": ""},
          {"atomic_id": "R-01", "field": "topic", "제안값": "위생/냄새", "승인상태": ""},
          {"atomic_id": "R-01", "field": "topic", "제안값": "다른값", "승인상태": ""},
          {"atomic_id": "Z-99", "field": "topic", "제안값": "아무거나", "승인상태": ""}])
    (판 / "총괄" / "2판통째" / "_판독패키지" / "_결과").mkdir(parents=True)
    return {"판": 판, "회의": 회의, "옛": 옛, "도구": 도구}


def _돌리기(도구, 판: Path, *더):
    import sys as _s
    옛argv = _s.argv
    _s.argv = ["x", str(판)] + list(더)
    try:
        return 도구.main()
    finally:
        _s.argv = 옛argv


def test_사람이_정하지_않은_행은_건드리지_않는다(자리):
    """★ 알맹이. CCC-01 은 옛 결정에 없다 — 손대면 AI 가 지어낸 결정이 된다."""
    _돌리기(자리["도구"], 자리["판"])
    줄들 = {r["origin_atomic_id"]: r for r in _읽기(자리["회의"] / "감독_분리제안.csv")}
    assert 줄들["CCC-01"]["승인상태"] == "사람 최종 승인 대기", (
        "사람이 정하지 않은 행의 승인상태를 **바꿨다** — %r. "
        "이것이 「임의로 테스트로 넣는 것」 이다." % 줄들["CCC-01"]["승인상태"])
    줄들2 = _읽기(자리["회의"] / "수정로그_오류확정.csv")
    Z = [r for r in 줄들2 if r["atomic_id"] == "Z-99"][0]
    assert Z["승인상태"] == "", "사람 결정에 없는 수정을 %r 로 바꿨다" % Z["승인상태"]


def test_나누라고_정한_것은_승인_합치라는_것은_반려(자리):
    _돌리기(자리["도구"], 자리["판"])
    줄들 = {r["origin_atomic_id"]: r for r in _읽기(자리["회의"] / "감독_분리제안.csv")}
    assert 줄들["AAA-01"]["승인상태"] == "승인", 줄들["AAA-01"]["승인상태"]
    assert 줄들["BBB-01"]["승인상태"] == "반려", (
        "「과분리를 합친다」 는 **나누지 말라**는 뜻이다 — %r" % 줄들["BBB-01"]["승인상태"])


def test_같은_칸에_승인이_둘_되지_않는다(자리):
    """돌리개가 「어느 쪽이 들어갔는지 알 수 없다」 며 멈추는 자리다."""
    _돌리기(자리["도구"], 자리["판"])
    줄들 = [r for r in _읽기(자리["회의"] / "수정로그_오류확정.csv")
           if r["atomic_id"] == "R-01"]
    승인 = [r for r in 줄들 if r["승인상태"] == "승인"]
    assert len(승인) == 1, "같은 (atomic_id, field) 에 승인이 %d개다 — 하나여야 한다" % len(승인)
    assert 승인[0]["제안값"] == "위생/냄새"
    다른값 = [r for r in 줄들 if r["제안값"] == "다른값"][0]
    assert 다른값["승인상태"] == "반려", "사람이 정한 값과 다른데 %r" % 다른값["승인상태"]


def test_field가_붙어_있어도_가른다(자리):
    """옛 `field` 는 `status/topic` 처럼 둘이 붙어 온다. 못 가르면 승인이 0이 된다."""
    _돌리기(자리["도구"], 자리["판"])
    승인 = [r for r in _읽기(자리["회의"] / "수정로그_오류확정.csv")
           if r["승인상태"] == "승인"]
    assert 승인, "`status/topic` 을 가르지 못해 승인이 하나도 없다"


def test_분리재지정_파일에_우리_조각이_들어간다(자리):
    _돌리기(자리["도구"], 자리["판"])
    쪽 = (자리["판"] / "총괄" / "2판통째" / "_판독패키지" / "_결과"
          / "분리재지정_01_사람결정.md")
    assert 쪽.is_file(), "apply_split 이 읽을 파일을 안 만들었다"
    글 = 쪽.read_text(encoding="utf-8")
    assert "자동 생성" in 글 and "손으로 고치지 마십시오" in 글, 글[:300]
    담긴 = [json.loads(s) for s in 글.splitlines() if s.startswith('{"atomic_id"')]
    ids = {o["atomic_id"] for o in 담긴}
    assert ids == {"AAA-01"}, (
        "승인된 것만 들어가야 한다 — 들어간 것 %s "
        "(BBB-01 은 반려 · CCC-01 은 사람이 안 정했다)" % sorted(ids))
    assert len(담긴[0]["split"]) == 2, "우리 감독이 낸 조각 둘이 그대로 들어가야 한다"


def test_확인만은_아무것도_쓰지_않는다(자리):
    앞 = (자리["회의"] / "감독_분리제안.csv").read_bytes()
    앞2 = (자리["회의"] / "수정로그_오류확정.csv").read_bytes()
    코드 = _돌리기(자리["도구"], 자리["판"], "--확인만")
    assert 코드 == 0
    assert (자리["회의"] / "감독_분리제안.csv").read_bytes() == 앞, "--확인만 인데 고쳤다"
    assert (자리["회의"] / "수정로그_오류확정.csv").read_bytes() == 앞2, "--확인만 인데 고쳤다"
    assert not list((자리["판"] / "총괄").rglob("분리재지정_*.md")), "--확인만 인데 파일을 만들었다"


def test_옛_결정이_없으면_멈춘다(자리):
    """★ 「못 찾음」 은 통과가 아니다. 조용히 0건 승인으로 끝나면 사람은
    「사람 결정을 넣었다」 고 믿는다."""
    (자리["옛"] / "수정로그_4차규칙_2판.csv").unlink()
    with pytest.raises(SystemExit) as e:
        _돌리기(자리["도구"], 자리["판"])
    assert "못 찾았습니다" in str(e.value) and "통과가 아닙니다" in str(e.value), str(e.value)


def test_회의_자리가_없으면_멈춘다(자리, tmp_path):
    with pytest.raises(SystemExit) as e:
        _돌리기(자리["도구"], tmp_path / "빈판")
    assert "회의 자리가 없습니다" in str(e.value)


def test_감독의_병합판정을_조용히_넘기지_않는다(자리, capsys):
    """★ 2026-11-01 — 3차 감독이 「합쳐야 한다」 로 낸 것은 `segments` 가 `"MERGE"` 다.

    `apply_split.py` 에는 **병합 코드가 없다** (`grep merge` 0건). 그래서 승인해도
    사슬이 아무것도 못 한다. 조용히 넘기면 감독의 판정이 사라진 것을 아무도 모른다.
    """
    쪽 = 자리["회의"] / "감독_분리제안.csv"
    줄들 = _읽기(쪽)
    줄들.append({"origin_atomic_id": "AAA-01", "segments": '"MERGE"',
                "why": "과분리다 — 합쳐야 한다", "승인상태": "한쪽 감독만 냈습니다 — 사람 확인"})
    # AAA-01 은 옛 결정이 「나눈다」 다. 그래도 segments 가 MERGE 면 승인해선 안 된다.
    _쓰기(쪽, ["origin_atomic_id", "segments", "why", "승인상태"], 줄들)

    _돌리기(자리["도구"], 자리["판"])
    병합행 = [r for r in _읽기(쪽) if (r.get("segments") or "") == '"MERGE"']
    assert 병합행, "시험 자료가 잘못됐다"
    for r in 병합행:
        assert r["승인상태"] == "반려", (
            "병합 판정을 %r 로 뒀다 — 승인하면 사슬이 아무것도 못 하는데 "
            "「반영됐다」 로 보인다" % r["승인상태"])
    말 = capsys.readouterr().out
    assert "사슬의 구멍" in 말 and "병합" in 말, (
        "병합을 못 받는다는 것을 **안 말했다** — 조용히 사라진다\n%s" % 말)


def test_옛_표기를_제대로_푼다(도구):
    """★ 2026-11-01 — 내가 틀렸던 자리.

    옛 수정로그는 `field` 에 `status/topic` 쌍을 적고 `새값` 에 **한 값을 이 표기로**
    적는다. `제외(X)` 는 status=scope_excluded · 사유=X · topic=N/A 를 뜻한다.
    처음에는 같은 `새값` 을 두 칸에 다 대서, 사람이 「제외」 로 정한 **18행을
    반려로 떨어뜨렸다.**
    """
    풀기 = 도구.표기_풀기
    r = dict(풀기("status/topic", "제외(operator_notice)"))
    assert r.get("status") == "scope_excluded", r
    assert r.get("scope_exclusion_reason") == "operator_notice", r
    assert r.get("topic") == "N/A", r

    r = dict(풀기("status/topic", "제품 전반"))
    assert r.get("topic") == "제품 전반", r
    assert r.get("status") == "normal", r

    r = dict(풀기("topic/status", "시장 점유·경쟁 구도"))
    assert r.get("topic") == "시장 점유·경쟁 구도" and r.get("status") == "normal", r

    assert dict(풀기("topic", "위생/냄새")).get("topic") == "위생/냄새", "단일 topic"
    assert dict(풀기("entity_role", "product_brand")).get("entity_role") == "product_brand"


def test_제외로_정한_행을_승인한다(자리):
    """★ 사람이 「제외」 로 정했고 우리 판독자가 scope_excluded 를 제안했으면 승인해야 한다."""
    _쓰기(자리["옛"] / "수정로그_4차규칙_2판.csv",
         ["atomic_id", "field", "옛값", "새값", "규칙", "승인상태"],
         [{"atomic_id": "S-01", "field": "status/topic", "옛값": "제품 전반",
           "새값": "제외(operator_notice)", "규칙": "정본③", "승인상태": "총괄 적용 (sky 확정)"}])
    _쓰기(자리["회의"] / "수정로그_오류확정.csv",
         ["atomic_id", "field", "제안값", "승인상태"],
         [{"atomic_id": "S-01", "field": "status", "제안값": "scope_excluded", "승인상태": ""},
          {"atomic_id": "S-01", "field": "scope_exclusion_reason",
           "제안값": "operator_notice", "승인상태": ""},
          {"atomic_id": "S-01", "field": "topic", "제안값": "N/A", "승인상태": ""}])
    _돌리기(자리["도구"], 자리["판"])
    줄들 = _읽기(자리["회의"] / "수정로그_오류확정.csv")
    for r in 줄들:
        assert r["승인상태"] == "승인", (
            "「제외」 로 정한 것의 %s 를 %r 로 뒀다 — 사람 결정이 데이터에 안 들어간다"
            % (r["field"], r["승인상태"]))
