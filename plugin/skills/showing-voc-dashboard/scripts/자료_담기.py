# -*- coding: utf-8 -*-
"""최종 산출물에서 **대시보드가 쓰는 칸만** 골라 HTML 안에 넣을 자료로 만든다 (2026-10-20).

★ 왜 이 파일이 따로 있나 (sky 2026-10-20)
  「거기서 구현되는 동작들까지 다 그대로 백프로 따라서 그냥 그대로 가져오면 되는 거 알죠?」

  전에는 **집계를 미리 계산해 그림으로 박아** 넣었다. 그래서 필터를 바꿔도 다시 계산되지 않았다 —
  보이는 것만 흉내 낸 것이다. 제대로 하려면 **행 단위 자료를 통째로 넣고** 화면 로직을 JS 로 옮겨
  필터를 바꿀 때마다 카드·그림·표가 **다시 계산**되어야 한다.

  이 파일은 그 「자료를 담는 일」 만 한다. 그리는 일은 JS 가 한다.

★ 칸은 **세어서** 골랐다 — 다섯 화면(`views/`)과 필터(`data_contract.apply_filters`) ·
  점수(`scoring`) 가 실제로 읽는 칸을 코드에서 전수로 뽑았다 (42개). 지어내지 않았다.

★ 서버가 필요한 것(새로 분석 · 다시 분석 · 결과 올리기 · 챗봇)은 **담지 않는다.**
  그것은 1~5번 스킬이 이미 한 일이다 (sky 2026-10-20 — 「어차피 서버로 부르는 분석은 스킬로
  미리 다 하고, 최종 결과물을 반영한 대시보드만 보기 쉽게 html 로 만드는 게 6번의 역할」).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]

# ── HTML 에 담을 칸 — 코드에서 전수로 뽑았다 (views/ · data_contract · scoring) ──────────
#   ★ 늘릴 때는 「어느 화면이 읽는가」 를 확인하고 늘린다. 줄이면 그 화면이 빈다.
필터칸 = ("status", "confidence_gate", "confidence_rating", "review_queue", "review_required",
       "product_category", "topic_group", "brand_display", "brand",
       "competitor_brand_display_tags", "competitor_brand_tags",
       "market_display", "market", "sentiment_dir", "cej", "cej_group")
화면칸 = ("atomic_id", "topic", "inquiry_flag", "validity", "video_id", "video_title",
       # ★ 2026-10-23 — 「Scope 제외 사유」 그림이 이 칸을 센다. 없어서 그 섹션이 아예 없었다.
       #   제외행(status=scope_excluded)만 쓰는 칸이라 다른 화면은 보지 않는다.
       "scope_exclusion_reason",
       "inquiry_type", "inquiry_type_display", "need_signal_type", "need_signal_type_display",
       "rootcause_summary", "source_run", "split_origin_atomic_id", "atomic_index",
       # ★ 2026-10-21 Codex 교차점검에서 「자료 자체가 없다」 고 짚힌 칸들을 더했다.
       #   없으면 원본 계산을 아예 흉내 낼 수 없다 (개선과제 대상·부정 강도·영상 분모·링크).
       "entity_role",                 # 개선과제 대상 행 (product_brand · unknown 만)
       "tee_emotion_score",           # 부정 강도 = min(감정, 성공, 0) · PL 정렬
       "tee_success_score",           # 같음 — 이것이 없어 감성 라벨로 대신 셌다
       "tee_time_score", "tee_effort_score", "topic_score", "voc_total_score",
       "source_id", "raw_row_index",  # 영상 댓글 수 분모 (source_id 가 있는 행만)
       "video_url", "video_tags", "product_tags")
원문칸 = ("atomic_voc", "atomic_voc_summary", "original_voc", "parent_voc",
       "rootcause_problem", "rootcause_cause", "rootcause_target",
       "decided_by", "video_description", "topic_evidence")
담을칸 = 필터칸 + 화면칸 + 원문칸

# 공유용에서 **빼는** 칸 — 원문 전량과 식별자
공유용_빼는칸 = ("original_voc", "parent_voc", "atomic_voc", "video_description",
            "topic_evidence", "rootcause_problem", "rootcause_cause", "rootcause_target")


def _찾기(이름: str) -> Path:
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


def 엔진_불러오기():
    """엔진의 칸 맞추기·점수 계산을 그대로 쓴다. 못 부르면 **왜** 못 불렀는지 말한다."""
    엔진 = _찾기("engine")
    if str(엔진) not in sys.path:
        sys.path.insert(0, str(엔진))
    try:
        import pandas as pd                                            # noqa: PLC0415
        # ★ 2026-10-21 Codex 교차점검 — 전에는 `ensure_dashboard_columns` 만 썼다. 틀렸다.
        #   그것은 **없는 칸을 기본값으로 채우기만** 한다. 원본 화면은
        #   `materialize_dashboard_columns` 로 점수 칸을 숫자로 바꾸고 sentiment_dir ·
        #   시장 · 브랜드 · CEJ 그룹 · validity · confidence/review gate 를 **매번 다시 만든다**
        #   (`app_operating.py:319`). 안 그러면 칸이 없거나 낡은 번들에서 confidence 가 전부
        #   False · validity 가 전부 무효가 되어 기본 화면부터 달라진다.
        from src.dashboard60.data_contract import (                    # noqa: PLC0415
            apply_filters, materialize_dashboard_columns)
        from src.dashboard60.scoring import score_improvement_tasks    # noqa: PLC0415
        # ★ 2026-10-22 Codex 교차점검 — 브랜드 선택지·표준화 표·판정 충족도 목록을
        #   손으로 베껴 적지 않는다 (두 벌이 된다). **엔진에서 꺼내 HTML 에 실어** JS 가 쓴다.
        from src.dashboard60 import data_contract as _계약               # noqa: PLC0415
    except ImportError as e:
        print("  ✗ 엔진의 계산 모듈을 못 불렀습니다 — %s" % e)
        print("     이 도구는 대시보드와 **같은 계산**을 씁니다 (따로 세지 않습니다).")
        # ★ 2026-10-26 빈 환경 시험이 잡았다 — `pyyaml` 이 빠져 있었다. 엔진의 계산 모듈이
        #   설정 yaml 을 읽어서 필요하다. 셋을 다 적지 않으면 받는 사람이 빈 컴퓨터에서 막힌다.
        print("     필요한 것: pandas · openpyxl · pyyaml")
        print("       python -m pip install pandas openpyxl pyyaml")
        return None
    return pd, materialize_dashboard_columns, apply_filters, score_improvement_tasks, _계약


def 책읽기(pd, 최종: Path) -> dict:
    """최종 엑셀의 시트를 전부 읽는다. CSV 면 raw_voc 한 장으로 본다."""
    if 최종.suffix.lower() == ".csv":
        return {"raw_voc": pd.read_csv(최종, keep_default_na=False)}
    return pd.read_excel(최종, sheet_name=None, keep_default_na=False)


def _참으로(v) -> bool:
    s = str(v).strip().lower()
    return s in ("true", "1", "y", "yes", "t")


def 자료만들기(표틀, pd, 계약=None, *, 공유용: bool = False) -> dict:
    """행 자료 + 고를 수 있는 값 목록. **JS 가 이것으로 전부 다시 계산한다.**

    ★ 참/거짓 칸(`confidence_gate` · `review_queue`)은 **진짜 참거짓**으로 바꿔 넣는다 —
      JS 에서 문자열 "False" 가 참이 되는 사고를 막는다.
    """
    있는칸 = [c for c in 담을칸 if c in 표틀.columns]
    뺀칸 = []
    if 공유용:
        뺀칸 = [c for c in 공유용_빼는칸 if c in 있는칸]
        있는칸 = [c for c in 있는칸 if c not in 뺀칸]
    줄들 = []
    for _, r in 표틀[있는칸].iterrows():
        줄 = {}
        for c in 있는칸:
            v = r[c]
            if c in ("confidence_gate", "review_queue"):
                줄[c] = _참으로(v)
            else:
                줄[c] = "" if pd.isna(v) else str(v)
        줄들.append(줄)

    def 값들(칸: str) -> list:
        if 칸 not in 표틀.columns:
            return []
        s = 표틀[칸].fillna("").astype(str).str.strip()
        return sorted({x for x in s if x})

    # ★ 2026-10-22 Codex 교차점검 — 브랜드 선택지를 `brand_display` 한 칸에서만 뽑았다. 틀렸다.
    #   원본은 자사 브랜드와 **경쟁사 태그를 합쳐 표준화**하고, 중국계 태그가 있으면
    #   「중국 브랜드」·「중국 제품」 묶음도 선택지에 넣는다 (`brand_filter_options`).
    #   그래서 삼성·로보락·드리미가 데이터에 있는데도 선택지가 `LG` 하나뿐이었다.
    #   **엔진 함수를 그대로 부른다** — 손으로 베끼지 않는다.
    브랜드선택지 = None
    if 계약 is not None:
        try:
            브랜드선택지 = list(계약.brand_filter_options(표틀))
        except Exception as 왜:                                         # noqa: BLE001
            print("  ! 브랜드 선택지를 엔진에서 못 냈습니다 — %s" % 왜)
    if 브랜드선택지 is None:
        브랜드선택지 = 값들("brand_display" if "brand_display" in 표틀.columns else "brand")
    return {
        "칸": 있는칸,
        "뺀칸": 뺀칸,
        "행": 줄들,
        "상수": 상수담기(계약),
        "고를것": {
            "product_category": 값들("product_category"),
            "topic_group": 값들("topic_group"),
            "brand": 브랜드선택지,
            "market": 값들("market_display" if "market_display" in 표틀.columns else "market"),
            "cej": 값들("cej"),
            "sentiment_dir": 값들("sentiment_dir"),
        },
    }


def 상수담기(계약) -> dict:
    """★ 엔진의 **상수를 그대로 실어** JS 가 쓴다 (2026-10-22).

    손으로 베껴 적으면 두 벌이 되고, 엔진이 바뀌어도 화면은 모른다 (공통 규칙 6).
    못 꺼내면 빈 것을 돌려주고, 화면의 자기검사가 그때 숫자로 어긋남을 잡는다.
    """
    것 = {"브랜드동의어": {}, "중국묶음": [], "판정충족도": [], "기본판정충족도": []}
    if 계약 is None:
        return 것
    것["브랜드동의어"] = {str(k): str(v) for k, v in
                    getattr(계약, "BRAND_SYNONYM_MAP", {}).items()}
    것["중국묶음"] = sorted(str(x) for x in getattr(계약, "CHINA_BRAND_GROUP_MEMBERS", ()))
    것["판정충족도"] = [str(x) for x in getattr(계약, "CONFIDENCE_LEVELS", ())]
    것["기본판정충족도"] = [str(x) for x in getattr(계약, "DEFAULT_CONFIDENCE_LEVELS", ())]
    # ★ 문의 화면의 한국어 표시값 — 원본은 사전을 `inquiry_labels.py` **한 곳**에만 둔다
    #   (그 파일 주석: 「여기 있던 사전 복사본을 지웠다 — 두 벌이 따로 놀며 둘 다 허용값의
    #   3분의 1만 담고 있었다」). 그러니 여기서도 베끼지 않고 그 파일에서 꺼낸다.
    것["문의유형이름"], 것["니즈신호이름"] = {}, {}
    try:
        from src.dashboard60.inquiry_labels import (                   # noqa: PLC0415
            INQUIRY_TYPE_LABELS, NEED_SIGNAL_TYPE_LABELS)
        것["문의유형이름"] = {str(k): str(v) for k, v in INQUIRY_TYPE_LABELS.items()}
        것["니즈신호이름"] = {str(k): str(v) for k, v in NEED_SIGNAL_TYPE_LABELS.items()}
    except ImportError as 왜:
        print("  ! 문의 표시값 사전을 못 불렀습니다 — %s" % 왜)
    # ★ Scope 제외 사유 — 일곱 가지를 **건수 0 이어도 다 낸다** (원본 주석: 「빠진 분류가
    #   보이도록」). 순서와 한국어 이름을 엔진에서 그대로 꺼낸다.
    것["제외사유"] = [str(x) for x in getattr(계약, "SCOPE_EXCLUSION_REASONS", ())]
    것["제외사유이름"] = {str(k): str(v) for k, v in
                    getattr(계약, "SCOPE_EXCLUSION_REASON_LABELS", {}).items()}
    # ★ RootCause 등급 풀이 — 원본은 views/overview.py 에 둔다 (계약 파일이 아니다).
    #   그 파일은 streamlit 을 불러오므로 **import 하지 않고 글자만 읽어** 꺼낸다.
    것["등급풀이"] = _원본상수("views/overview.py", "ROOTCAUSE_GRADE_NOTE")
    return 것


def _원본상수(어디: str, 이름: str) -> dict:
    """엔진 파일 하나에서 상수를 **읽어서** 꺼낸다 (import 하지 않는다).

    ★ 손으로 베껴 적으면 두 벌이 되고, 엔진이 바뀌어도 화면은 모른다 (공통 규칙 6).
      못 꺼내면 빈 것을 돌려주고 그 자리를 쓰는 화면이 비게 된다 — 조용히 틀린 값을
      쓰지 않는다.
    """
    import ast                                                        # noqa: PLC0415

    길 = _찾기("engine") / "src" / "dashboard60" / 어디
    if not 길.is_file():
        print("  ! 엔진 원본을 못 찾았습니다 — %s" % 길)
        return {}
    try:
        나무 = ast.parse(길.read_text(encoding="utf-8"))
    except SyntaxError as 왜:
        print("  ! 엔진 원본을 못 읽었습니다 — %s" % 왜)
        return {}
    for 가지 in 나무.body:
        대상 = (가지.targets[0] if isinstance(가지, ast.Assign)
              else getattr(가지, "target", None) if isinstance(가지, ast.AnnAssign) else None)
        if isinstance(대상, ast.Name) and 대상.id == 이름:
            것 = ast.literal_eval(가지.value)
            return {str(k): str(v) for k, v in 것.items()}
    print("  ! %s 에서 %s 를 못 찾았습니다" % (어디, 이름))
    return {}


def 맞춤값(표틀, pd, apply_filters, score_improvement_tasks, 계약=None) -> dict:
    """★ **JS 가 맞는지 대볼 값**을 파이썬 엔진으로 미리 낸다 (2026-10-20).

    JS 로 다시 계산하면 숫자가 엔진과 어긋날 위험이 있다. 그래서 엔진이 낸 값을 함께 담고,
    HTML 이 열릴 때 JS 가 같은 값을 내는지 **스스로 대본다.** 어긋나면 화면에 알린다.
    「돌아간다」 와 「맞다」 는 다르다.
    """
    기본 = apply_filters(표틀)
    것 = {"기본행수": int(len(기본))}
    try:
        순위 = score_improvement_tasks(기본)
        것["개선과제수"] = int(len(순위))
        # ★ 2026-10-21 — 여기서 `combined_rank` 로 **다시 정렬**해 담았다. 틀렸다.
        #   `score_improvement_tasks` 가 돌려주는 차례가 이미 원본 정렬이다
        #   (priority_score ↓ · rc_coverage ↓ · n ↓ — scoring.py:156-160).
        #   맞춤값이 틀리면 **맞는 화면을 틀렸다고** 잡는다. 실제로 그랬다.
        것["개선상위"] = [[str(r.get("topic", "")), int(r.get("n", 0))]
                     for _, r in 순위.head(5).iterrows()]
    except Exception:                                                  # noqa: BLE001
        것["개선과제수"] = -1
        것["개선상위"] = []
    # 필터를 하나 걸었을 때도 맞는지 — 가장 흔한 제품군 하나로 대본다
    제품 = 기본["product_category"].fillna("").astype(str)
    흔한 = 제품[제품 != ""].mode()
    if len(흔한):
        것["맞댈제품군"] = str(흔한.iloc[0])
        것["맞댈제품군행수"] = int(len(apply_filters(표틀, products=[것["맞댈제품군"]])))

    # ★ 2026-10-22 Codex 교차점검 — 새로 살린 것들도 **대볼 값을 같이 담는다.**
    #   담지 않으면 「돌아간다」 만 보고 「맞다」 를 못 본다. 고친 것마다 정답을 둔다.
    if 계약 is not None:
        try:
            # ① 판정 충족도 — 레벨마다 몇 행인가 (전에는 Very High+High 만 보였다)
            것["판정충족도별"] = {
                str(값): int(len(apply_filters(표틀, confidence_levels=[str(값)])))
                for 값 in getattr(계약, "CONFIDENCE_LEVELS", ())}
            # 빈 목록은 0행이어야 한다 — 감성과 같은 뜻
            것["판정충족도_빈목록행수"] = int(len(apply_filters(표틀, confidence_levels=[])))
            # ★ 상단 분모 — 「무엇을 볼까」 만 통과한 집합 (판정 충족도·사람검토 끄기)
            것["차원통과행수"] = int(len(apply_filters(
                표틀, high_confidence_only=False, review_required_only=False)))
            # ② 사람 검토가 필요한 행만
            # ★ 2026-10-22 — 처음에는 이름을 「사람검토행수」 하나로 두고 `apply_filters(
            #   review_required_only=True)` 를 담았다. 그것은 **기본 충족도(Very High+High)
            #   까지 걸린 값**인데, 화면 쪽 시험은 네 레벨을 다 켜고 재서 61 대 185 로
            #   어긋났다. 2판 6,846행으로 돌려 보고 알았다 — 작은 자료에서는 둘 다 0 이었다.
            #   어느 쪽이 틀린 게 아니라 **서로 다른 것을 재고 있었다.** 이름으로 가른다.
            기본충족도 = list(getattr(계약, "DEFAULT_CONFIDENCE_LEVELS", ()))
            것["사람검토행수_기본충족도"] = int(len(apply_filters(
                표틀, confidence_levels=기본충족도, review_required_only=True)))
            것["사람검토행수_전체충족도"] = int(len(apply_filters(
                표틀, confidence_levels=list(getattr(계약, "CONFIDENCE_LEVELS", ())),
                review_required_only=True)))
            # ③ 브랜드 선택지 — 자사 + 경쟁사 태그 + 중국 묶음
            것["브랜드선택지"] = list(계약.brand_filter_options(표틀))
            # ④ 브랜드를 골랐을 때 — 선택지의 앞 셋과 「중국 브랜드」 묶음으로 대본다
            대볼브랜드 = [b for b in 것["브랜드선택지"][:3]]
            if "중국 브랜드" in 것["브랜드선택지"] and "중국 브랜드" not in 대볼브랜드:
                대볼브랜드.append("중국 브랜드")
            것["브랜드별"] = {str(b): int(len(apply_filters(표틀, brands=[str(b)])))
                          for b in 대볼브랜드}
            # ⑤ 문의 두 분포 — 원본 사전으로 한국어 표시값을 만든 뒤 센다
            from src.dashboard60.data_contract import inquiry_rows      # noqa: PLC0415
            from src.dashboard60.inquiry_labels import (                # noqa: PLC0415
                INQUIRY_TYPE_LABELS, NEED_SIGNAL_TYPE_LABELS)
            문의 = inquiry_rows(기본)
            것["문의행수"] = int(len(문의))

            def _분포(칸, 이름표):
                if 칸 not in 문의.columns or 문의.empty:
                    return {}
                s = 문의[칸].fillna("").astype(str).str.strip()
                s = s.map(lambda v: 이름표.get(v, v or "해당없음"))
                return {str(k): int(v) for k, v in s.value_counts().items()}

            것["문의유형분포"] = _분포("inquiry_type", INQUIRY_TYPE_LABELS)
            것["니즈신호분포"] = _분포("need_signal_type", NEED_SIGNAL_TYPE_LABELS)
            # ⑥ 영상 집계 — **엔진 함수를 그대로 부른다** (대상 행 · 묶음 키 · 분모가 까다롭다)
            from src.dashboard60.data_contract import video_summary     # noqa: PLC0415
            영상 = video_summary(기본)
            것["영상수"] = int(len(영상))
            것["영상집계"] = [
                {"video_id": str(r.get("video_id", "")),
                 "video_title": str(r.get("video_title", "")),
                 "comment_count": int(r.get("comment_count", 0)),
                 "negative_rate": round(float(r.get("negative_rate", 0) or 0), 6),
                 "positive_rate": round(float(r.get("positive_rate", 0) or 0), 6),
                 "inquiry_rate": round(float(r.get("inquiry_rate", 0) or 0), 6)}
                for _, r in 영상.iterrows()]
        except Exception as 왜:                                         # noqa: BLE001
            print("  ! 맞춤값 일부를 못 냈습니다 — %s: %s" % (type(왜).__name__, 왜))
    return 것


def json글(것) -> str:
    """HTML 안에 넣을 JSON. `</script>` 로 깨지지 않게 막는다."""
    return (json.dumps(것, ensure_ascii=False, separators=(",", ":"))
            .replace("</", "<\\/"))
