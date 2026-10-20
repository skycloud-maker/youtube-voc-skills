# -*- coding: utf-8 -*-
"""최종 산출물로 **대시보드 화면을 HTML 한 장**으로 만든다 — 서버 없이 어디서든 열린다 (2026-10-20).

★ 왜 (sky 2026-10-20)
  「여섯번째 스킬이 최종 분석 아웃풋을 바탕으로 스트림릿에 있는 대시보드를 그대로 구현한 걸
   html 파일로 누구나 어디 컴퓨터에서든 열 수 있도록 만들고 싶은거죠」

  그 대시보드(`src/dashboard60/`)는 화면 다섯이다 —
    VoC 현황(overview) · 개선 방향성(improvement) · 문의 속 니즈(inquiry) ·
    PL Issue(pl_issue) · 분석 영상 정보(video)
  이 도구는 그 다섯을 **같은 숫자로** HTML 에 담는다.

★ 숫자를 다시 계산하지 않는다 — **엔진의 계산 모듈을 그대로 부른다** (공통 규칙 6).
    data_contract.ensure_dashboard_columns · topic_distribution
    scoring.score_improvement_tasks        개선 방향성
    inquiry_labels                          문의 속 니즈
  우리가 따로 세면 대시보드와 숫자가 갈린다. 그리는 층만 Streamlit → HTML 로 바꾼다.

★ 인터넷 없이 열려야 한다 — CDN 을 쓰지 않는다. 그림은 **인라인 SVG**, 표 정렬·검색은 순수 JS.

★ 라이브만 안 된다 — 유튜브에서 새로 모으고 다시 분석하는 것(OpenAI 호출)은 서버가 있어야 한다.
  보는 것(표 · 그림 · 탭 · 필터 · 정렬 · 검색)은 HTML 로 된다. 그 차이를 HTML 맨 아래에 적어 둔다.

★ 두 벌을 낸다 (sky 「둘 다 필요하다」)
    <이름>_살펴보기.html   원문을 담는다. 사내에서 본다
    <이름>_공유용.html     원문 전량·식별자를 빼고 링크·이메일·사용자명을 치운다.
                           치운 건수를 적고 **다시 훑어 0건**임을 확인한다 (보고서 스킬과 같은 규율)

쓰기
    python <이 스킬>/scripts/대시보드_HTML_만들기.py <최종엑셀> [<받을곳>]

종료코드
    0  둘 다 만들었다     1  막혔다     2  치울 것이 남았다 (공유용을 믿을 수 없다)
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]

# ── 치우는 것 — 보고서 스킬(`building-voc-report`)과 같은 무늬를 쓴다 ──────────────
링크 = re.compile(r"https?://\S+|www\.\S+")
이메일 = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
사용자명 = re.compile(r"@[\w가-힣._-]{2,}")
# 공유용에서 통째로 빼는 칸 — 원문 전량과 식별자
공유용_빼는칸 = ("original_voc", "parent_voc", "voc_cleaned", "voc_residual",
            "source_id", "raw_row_index", "parent_voc_id", "video_url", "channel_id")


def _찾기(이름: str) -> Path:
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


def _엔진_불러오기():
    """엔진의 계산 모듈을 불러온다. 못 불러오면 **왜** 못 불렀는지 말하고 멈춘다."""
    엔진 = _찾기("engine")
    if str(엔진) not in sys.path:
        sys.path.insert(0, str(엔진))
    try:
        import pandas as pd                                            # noqa: PLC0415
        from src.dashboard60.data_contract import (                    # noqa: PLC0415
            ensure_dashboard_columns, topic_distribution)
        from src.dashboard60.scoring import score_improvement_tasks    # noqa: PLC0415
    except ImportError as e:
        print("  ✗ 엔진의 계산 모듈을 못 불렀습니다 — %s" % e)
        print("     이 도구는 대시보드와 **같은 계산**을 씁니다 (따로 세지 않습니다).")
        print("     필요한 것: pandas · openpyxl   (python -m pip install pandas openpyxl)")
        return None
    return pd, ensure_dashboard_columns, topic_distribution, score_improvement_tasks


def _h(x) -> str:
    return html.escape("" if x is None else str(x))


def _치우기(글: str, 셈: dict) -> str:
    """링크 · 이메일 · 사용자명을 치우고 **몇 건 치웠는지 센다.**"""
    글 = 링크.sub(lambda m: (셈.__setitem__("링크", 셈["링크"] + 1), "[링크 치움]")[1], 글)
    글 = 이메일.sub(lambda m: (셈.__setitem__("이메일", 셈["이메일"] + 1), "[이메일 치움]")[1], 글)
    글 = 사용자명.sub(lambda m: (셈.__setitem__("사용자명", 셈["사용자명"] + 1), "[사용자명 치움]")[1], 글)
    return 글


_꾸밈덩어리 = re.compile(r"<(style|script)\b.*?</\1>", re.S | re.I)


def _남았나(글: str) -> dict:
    """★ 「치웠다」 가 아니라 **다시 훑어** 0건임을 본다 (보고서 스킬과 같은 규율).

    ★ 내가 쓴 `<style>`·`<script>` 는 **자료가 아니라서 뺀다** (2026-10-20 실측).
      CSS 의 `@media(...)` 가 사용자명 무늬(`@이름`)에 걸려 공유용이 거짓으로 반려됐다.
      검사를 약하게 하는 것이 아니다 — **자료만** 본다. 자료 쪽은 그대로 전부 훑는다.
    """
    자료 = _꾸밈덩어리.sub(" ", 글)
    return {"링크": len(링크.findall(자료)), "이메일": len(이메일.findall(자료)),
            "사용자명": len(사용자명.findall(자료))}


# ── 그리기 — 인라인 SVG (CDN 을 쓰지 않는다) ─────────────────────────────────
색 = ["#A50034", "#6B7280", "#1D4ED8", "#047857", "#B45309", "#7C3AED",
     "#BE185D", "#0E7490", "#4D7C0F", "#9333EA"]
감성색 = {"긍정": "#047857", "부정": "#A50034", "중립": "#6B7280"}


def 막대그림(짝들, *, 제목: str, 밑말: str = "", 색표: dict | None = None,
          너비: int = 560, 줄높이: int = 26) -> str:
    """(이름, 수) 목록을 가로 막대로. 대시보드의 bar_chart 와 같은 자료를 받는다."""
    짝들 = [(str(a), int(b)) for a, b in 짝들 if str(a) != ""]
    if not 짝들:
        return ('<div class="chart"><h3>%s</h3><p class="empty">이 조건에서는 담을 것이 없습니다.</p></div>'
                % _h(제목))
    최대 = max(v for _, v in 짝들) or 1
    이름칸, 수칸 = 150, 60
    막대칸 = 너비 - 이름칸 - 수칸
    높이 = 줄높이 * len(짝들) + 8
    줄 = []
    for i, (이름, 수) in enumerate(짝들):
        y = i * 줄높이 + 4
        길이 = max(2, int(막대칸 * 수 / 최대))
        c = (색표 or {}).get(이름) or 색[i % len(색)]
        줄.append(
            '<text x="%d" y="%d" class="bl" text-anchor="end">%s</text>'
            '<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s"></rect>'
            '<text x="%d" y="%d" class="bv">%s</text>'
            % (이름칸 - 8, y + 15, _h(이름[:22]),
               이름칸, y + 4, 길이, 줄높이 - 10, c,
               이름칸 + 길이 + 6, y + 15, format(수, ",")))
    return ('<div class="chart"><h3>%s</h3>%s'
            '<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="%s">%s</svg></div>'
            % (_h(제목),
               ('<p class="sub">%s</p>' % _h(밑말)) if 밑말 else "",
               너비, 높이, _h(제목), "".join(줄)))


def 지표카드(것들) -> str:
    """(이름, 값, 밑말, 톤) — 대시보드의 metric_card 와 같은 자리."""
    칸 = ['<div class="cards">']
    for 이름, 값, 밑말, 톤 in 것들:
        칸.append('<div class="card t-%s"><div class="k">%s</div><div class="v">%s</div>'
                  '<div class="s">%s</div></div>' % (_h(톤), _h(이름), _h(값), _h(밑말)))
    칸.append("</div>")
    return "".join(칸)


def 표(머리, 줄들, *, 이름: str, 찾기: bool = True) -> str:
    """정렬 · 찾기가 되는 표 (순수 JS — 인터넷이 없어도 된다)."""
    if not 줄들:
        return '<p class="empty">이 조건에서는 담을 것이 없습니다.</p>'
    위 = []
    if 찾기:
        위.append('<input class="find" data-for="%s" placeholder="이 표에서 찾기 — 글자를 넣으면 걸러집니다">'
                  % _h(이름))
    위.append('<div class="tw"><table id="%s"><thead><tr>%s</tr></thead><tbody>'
              % (_h(이름),
                 "".join('<th data-i="%d">%s</th>' % (i, _h(c)) for i, c in enumerate(머리))))
    for r in 줄들:
        위.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _h(v) for v in r))
    위.append('</tbody></table></div><p class="sub">%s행 · 머리를 누르면 정렬됩니다</p>'
              % format(len(줄들), ","))
    return "".join(위)


# ── 다섯 화면 ───────────────────────────────────────────────────────────────
def 화면_VoC현황(표틀, pd, topic_distribution) -> str:
    """대시보드 `views/overview.py` — 지표 카드 7개 + 그림 4개."""
    총 = len(표틀)
    문의 = int((표틀["inquiry_flag"].fillna("").astype(str).str.upper() == "Y").sum()) if 총 else 0
    검토 = int(pd.to_numeric(표틀.get("review_queue", 0), errors="coerce").fillna(0).sum()) if 총 else 0
    유효 = int((표틀.get("validity", "") == "유효").sum()) if 총 else 0
    분리 = int((표틀.get("atomic_index", "").astype(str).str.strip().isin(["2", "3", "4", "5"])).sum()) if 총 else 0
    쪽 = ['<h2>VoC 현황</h2>',
         '<p class="sub">topic 은 제품군·감성과 분리된 <b>이유</b> 라벨이고, 감성은 TEE/S 기반 '
         'sentiment_dir 로 따로 봅니다.</p>',
         지표카드([
             ("VoC Rows", format(총, ","), "최종 데이터 기준", "blue"),
             ("유효 Row", format(유효, ","), ("%.1f%%" % (유효 / 총 * 100)) if 총 else "0.0%", "green"),
             ("문의 비율", ("%.1f%%" % (문의 / 총 * 100)) if 총 else "0.0%", "%s건" % format(문의, ","), "purple"),
             ("사람검토 큐", format(검토, ","), "review_required=Y", "orange"),
             ("제품군 수", format(표틀["product_category"].nunique() if 총 else 0, ","), "product_category", "blue"),
             ("Reason Topic 수", format(표틀["topic"].nunique() if 총 else 0, ","), "제품·감성 분리", "green"),
             ("2차 분리 행", format(분리, ","), "한 댓글에 주제가 여럿이라 나눈 것", "purple"),
         ])]
    분포 = topic_distribution(표틀).head(15)
    쪽.append('<div class="row">')
    쪽.append(막대그림(list(zip(분포["topic"], 분포["count"])),
                   제목="Reason Topic 분포", 밑말="상위 15개"))
    감성 = 표틀["sentiment_dir"].fillna("중립").replace("", "중립").value_counts()
    쪽.append(막대그림(list(zip(감성.index, 감성.values)),
                   제목="감성 분포", 밑말="TEE/S 기반 긍정·부정·중립", 색표=감성색))
    쪽.append("</div><div class=\"row\">")
    cej = 표틀["cej"].fillna("해당없음").replace("", "해당없음").value_counts()
    쪽.append(막대그림(list(zip(cej.index, cej.values)), 제목="CEJ 9단계", 밑말="데이터사전 v2.7 기준"))
    플래그 = 표틀["inquiry_flag"].fillna("N").replace("", "N").value_counts()
    쪽.append(막대그림(list(zip(플래그.index, 플래그.values)), 제목="문의 Flag", 밑말="질문형 VoC 비율"))
    쪽.append("</div>")
    return "".join(쪽)


def 화면_개선방향성(표틀, score_improvement_tasks) -> str:
    """대시보드 `views/improvement.py` — 엔진의 두 축 점수를 그대로 쓴다."""
    쪽 = ['<h2>개선 방향성</h2>',
         '<p class="sub">건수와 부정 강도 <b>두 축</b>으로 매긴 개선과제입니다. 점수는 엔진의 '
         '<code>scoring.score_improvement_tasks</code> 가 낸 값을 그대로 옮겼습니다.</p>']
    try:
        순위 = score_improvement_tasks(표틀)
    except Exception as e:                                    # noqa: BLE001
        return "".join(쪽) + ('<p class="empty">엔진 점수를 못 냈습니다 — %s: %s</p>'
                             % (_h(type(e).__name__), _h(e)))
    if 순위 is None or len(순위) == 0:
        return "".join(쪽) + '<p class="empty">이 조건에서 개선과제 후보 군집이 없습니다.</p>'
    # ★ 칸 이름은 엔진이 정한다 — 건수는 `n`, 부정 건수는 `neg_count` 다 (2026-10-20 실측).
    #   전에 `count` 로 짐작했다가 그림이 통째로 비었다. 짐작하지 않고 엔진이 낸 이름을 쓴다.
    이름칸 = next((c for c in ("topic", "label", "task", "name") if c in 순위.columns), 순위.columns[0])
    보기순 = 순위.sort_values("combined_rank") if "combined_rank" in 순위.columns else 순위
    for 수칸, 제목, 밑말 in (("n", "개선과제 — 건수", "건수 축"),
                        ("neg_count", "개선과제 — 부정 건수", "부정 강도 축")):
        if 수칸 not in 보기순.columns:
            continue
        쪽.append(막대그림(list(zip(보기순[이름칸].head(15), 보기순[수칸].head(15))),
                       제목=제목, 밑말=밑말 + " · 상위 15개 (combined_rank 순)"))
    순위 = 보기순
    머리 = list(순위.columns)
    쪽.append(표(머리, [[r[c] for c in 머리] for _, r in 순위.iterrows()], 이름="t-improve"))
    return "".join(쪽)


def 화면_문의속니즈(표틀, pd) -> str:
    """대시보드 `views/inquiry.py` — 문의형만 골라 본다."""
    총 = len(표틀)
    문의 = 표틀[표틀["inquiry_flag"].fillna("").astype(str).str.upper() == "Y"]
    n = len(문의)
    쪽 = ['<h2>문의 속 니즈</h2>',
         '<p class="sub">질문형 VoC 만 골라 봅니다. 문의율은 감성과 <b>별도 축</b>입니다 — '
         '부정적인 문의도 있습니다.</p>',
         지표카드([
             ("문의형 VoC", format(n, ","), ("%.1f%%" % (n / 총 * 100)) if 총 else "0.0%", "purple"),
             ("문의 제품군 수", format(문의["product_category"].nunique() if n else 0, ","), "product_category", "blue"),
             ("문의 Topic 수", format(문의["topic"].nunique() if n else 0, ","), "reason topic", "green"),
         ])]
    if not n:
        return "".join(쪽) + '<p class="empty">이 조건에서 문의형 VoC 가 없습니다.</p>'
    t = 문의["topic"].fillna("(빈칸)").replace("", "(빈칸)").value_counts().head(15)
    c = 문의["cej"].fillna("해당없음").replace("", "해당없음").value_counts()
    쪽.append('<div class="row">')
    쪽.append(막대그림(list(zip(t.index, t.values)), 제목="문의 Topic 분포", 밑말="상위 15개"))
    쪽.append(막대그림(list(zip(c.index, c.values)), 제목="문의의 CEJ 단계", 밑말=""))
    쪽.append("</div>")
    return "".join(쪽)


def 화면_PL이슈(책, pd) -> str:
    """대시보드 `views/pl_issue.py` — 안전·위생은 **건수로 거르지 않는다** (전량)."""
    쪽 = ['<h2>PL Issue</h2>',
         '<p class="sub">안전(화재·감전·누수)과 위생/냄새는 <b>건수로 거르지 않고 전량</b> 봅니다.</p>']
    시트 = next((n for n in 책 if "PL" in n), None)
    if 시트 is None or len(책[시트]) == 0:
        return "".join(쪽) + '<p class="empty">지금 조건에서 안전·위생으로 잡힌 행이 없습니다.</p>'
    표틀 = 책[시트]
    글 = 표틀.astype(str).apply(lambda s: " ".join(s), axis=1)
    안전 = int(글.str.contains("안전|화재|감전|누수|폭발").sum())
    위생 = int(글.str.contains("위생|냄새|곰팡이|악취|세균").sum())
    쪽.append(지표카드([("전체", format(len(표틀), ","), "건수로 거르지 않았습니다", "blue"),
                   ("안전(화재·감전·누수)", format(안전, ","), "화재 · 감전 · 누수 · 폭발", "orange"),
                   ("위생/냄새", format(위생, ","), "곰팡이 · 악취 · 세균", "purple")]))
    머리 = list(표틀.columns)
    쪽.append(표(머리, [[r[c] for c in 머리] for _, r in 표틀.iterrows()], 이름="t-pl"))
    return "".join(쪽)


def 화면_영상정보(표틀, pd) -> str:
    """대시보드 `views/video.py` — 영상별 댓글 수 · 긍정률 · 부정률 · 문의율."""
    총 = len(표틀)
    쪽 = ['<h2>분석 영상 정보</h2>',
         '<p class="sub">영상별 댓글 수, 긍정률, 부정률, 문의율을 최종 데이터에서 집계합니다. '
         '문의율은 감성과 별도 축이라 <b>합이 100%를 넘을 수 있습니다.</b></p>',
         지표카드([("집계 Row", format(총, ","), "최종 데이터 기준", "blue"),
                ("영상 수", format(표틀["video_id"].nunique() if 총 else 0, ","), "video_id 기준", "green")])]
    if not 총:
        return "".join(쪽) + '<p class="empty">이 조건에서 영상 집계가 없습니다.</p>'
    감성 = 표틀["sentiment_dir"].fillna("중립").replace("", "중립")
    문의 = 표틀["inquiry_flag"].fillna("N").astype(str).str.upper() == "Y"
    줄들 = []
    for vid, 묶 in 표틀.groupby(표틀["video_id"].fillna("(없음)")):
        n = len(묶)
        제목 = str(묶["video_title"].iloc[0] if "video_title" in 묶.columns else "")
        줄들.append([제목[:60] or str(vid), str(vid), format(n, ","),
                  "%.1f%%" % (float((감성.loc[묶.index] == "긍정").sum()) / n * 100),
                  "%.1f%%" % (float((감성.loc[묶.index] == "부정").sum()) / n * 100),
                  "%.1f%%" % (float(문의.loc[묶.index].sum()) / n * 100),
                  str(묶["product_category"].mode().iloc[0]) if 묶["product_category"].notna().any() else ""])
    줄들.sort(key=lambda r: int(r[2].replace(",", "")), reverse=True)
    쪽.append(막대그림([(r[0], int(r[2].replace(",", ""))) for r in 줄들[:15]],
                   제목="영상별 댓글 수", 밑말="상위 15개", 너비=640))
    쪽.append(표(["영상", "video_id", "댓글 수", "긍정률", "부정률", "문의율", "주요 제품군"],
                줄들, 이름="t-video"))
    return "".join(쪽)


# ── HTML 뼈대 — 인터넷 없이 열린다 (CDN 없음 · 모든 것을 안에 넣는다) ──────────────
_꾸밈 = """
:root{--bg:#fff;--fg:#111827;--sub:#6b7280;--line:#e5e7eb;--lg:#A50034;--card:#f9fafb}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0b0f14;--fg:#e5e7eb;--sub:#9ca3af;--line:#1f2937;--card:#111827}}
:root[data-theme="dark"]{--bg:#0b0f14;--fg:#e5e7eb;--sub:#9ca3af;--line:#1f2937;--card:#111827}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:15px/1.6 -apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
header{padding:20px 16px 12px;border-bottom:1px solid var(--line)}
h1{margin:0 0 4px;font-size:20px}
h2{margin:24px 0 6px;font-size:18px}
h3{margin:0 0 2px;font-size:14px}
main{padding:0 16px 48px;max-width:1180px;margin:0 auto}
.sub{color:var(--sub);font-size:13px;margin:2px 0 10px}
.empty{color:var(--sub);padding:12px;background:var(--card);border-radius:8px}
nav{display:flex;gap:6px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--line);
  position:sticky;top:0;background:var(--bg);z-index:5}
nav button{font:inherit;padding:7px 13px;border:1px solid var(--line);border-radius:999px;
  background:transparent;color:var(--fg);cursor:pointer}
nav button[aria-selected="true"]{background:var(--lg);color:#fff;border-color:var(--lg)}
section[hidden]{display:none}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.card .k{font-size:12px;color:var(--sub)}
.card .v{font-size:22px;font-weight:700;margin:2px 0}
.card .s{font-size:12px;color:var(--sub)}
.card.t-blue{border-left:3px solid #1D4ED8}.card.t-green{border-left:3px solid #047857}
.card.t-purple{border-left:3px solid #7C3AED}.card.t-orange{border-left:3px solid #B45309}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.chart{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:16px}
.bl{font-size:11px;fill:var(--sub)}.bv{font-size:11px;fill:var(--fg)}
.tw{overflow:auto;max-height:70vh;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:6px 9px;text-align:left;
  vertical-align:top;max-width:460px;overflow-wrap:anywhere}
th{position:sticky;top:0;background:var(--card);cursor:pointer;white-space:nowrap}
th:hover{color:var(--lg)}
.find{width:100%;padding:8px 10px;margin:6px 0;font:inherit;border:1px solid var(--line);
  border-radius:8px;background:var(--bg);color:var(--fg)}
footer{border-top:1px solid var(--line);margin-top:28px;padding:16px;color:var(--sub);font-size:13px}
footer b{color:var(--fg)}
@media(max-width:600px){main{padding:0 16px 48px}.row{grid-template-columns:1fr}}
"""

_스크립트 = r"""
document.querySelectorAll('nav button').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('nav button').forEach(function(x){x.setAttribute('aria-selected','false')});
    b.setAttribute('aria-selected','true');
    document.querySelectorAll('main section').forEach(function(s){s.hidden = s.id !== b.dataset.tab});
    window.scrollTo(0,0);
  });
});
document.querySelectorAll('input.find').forEach(function(inp){
  inp.addEventListener('input',function(){
    var q = inp.value.trim().toLowerCase();
    var t = document.getElementById(inp.dataset.for);
    if(!t) return;
    Array.prototype.forEach.call(t.tBodies[0].rows,function(r){
      r.hidden = q !== '' && r.innerText.toLowerCase().indexOf(q) === -1;
    });
  });
});
document.querySelectorAll('table th').forEach(function(th){
  th.addEventListener('click',function(){
    var t = th.closest('table'), i = +th.dataset.i;
    var up = th.dataset.up !== '1';
    Array.prototype.forEach.call(t.tHead.rows[0].cells,function(c){c.dataset.up=''});
    th.dataset.up = up ? '1' : '0';
    var rows = Array.prototype.slice.call(t.tBodies[0].rows);
    var num = function(s){ var v = parseFloat(String(s).replace(/[,%\s]/g,'')); return isNaN(v)?null:v; };
    rows.sort(function(a,b){
      var x = a.cells[i].innerText, y = b.cells[i].innerText;
      var nx = num(x), ny = num(y);
      var r = (nx !== null && ny !== null) ? nx - ny : x.localeCompare(y,'ko');
      return up ? r : -r;
    });
    rows.forEach(function(r){ t.tBodies[0].appendChild(r) });
  });
});
"""

_탭들 = [("voc", "VoC 현황"), ("improve", "개선 방향성"), ("inquiry", "문의 속 니즈"),
       ("pl", "PL Issue"), ("video", "분석 영상 정보")]


def 한장만들기(쪽들: dict, *, 제목: str, 머리말: str, 꼬리말: str) -> str:
    나브 = "".join('<button data-tab="%s" aria-selected="%s">%s</button>'
                 % (k, "true" if i == 0 else "false", _h(v))
                 for i, (k, v) in enumerate(_탭들))
    본문 = "".join('<section id="%s"%s>%s</section>'
                 % (k, "" if i == 0 else " hidden", 쪽들.get(k, ""))
                 for i, (k, _) in enumerate(_탭들))
    return ("<!doctype html>" + chr(10)
            + '<html lang="ko"><head><meta charset="utf-8">'
            + '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + "<title>%s</title><style>%s</style></head><body>" % (_h(제목), _꾸밈)
            + "<header><h1>%s</h1><p class=\"sub\">%s</p></header>" % (_h(제목), 머리말)
            + "<nav>%s</nav><main>%s</main>" % (나브, 본문)
            + "<footer>%s</footer>" % 꼬리말
            + "<script>%s</script></body></html>" % _스크립트 + chr(10))


# ── 만들기 ──────────────────────────────────────────────────────────────────
def _책읽기(pd, 최종: Path) -> dict:
    """최종 엑셀의 시트를 전부 읽는다. CSV 면 raw_voc 한 장으로 본다."""
    if 최종.suffix.lower() == ".csv":
        return {"raw_voc": pd.read_csv(최종, keep_default_na=False)}
    return pd.read_excel(최종, sheet_name=None, keep_default_na=False)


def 만들기(최종: Path, 받을곳: Path) -> int:
    것 = _엔진_불러오기()
    if 것 is None:
        return 1
    pd, 칸맞추기, topic_distribution, score_improvement_tasks = 것
    if not 최종.is_file():
        print("  ✗ 최종 산출물을 못 찾았습니다 — %s" % 최종)
        print("     (「못 찾음」 은 통과가 아닙니다 — 빈 화면을 만들지 않습니다)")
        return 1
    try:
        책 = _책읽기(pd, 최종)
    except Exception as e:                                    # noqa: BLE001
        print("  ✗ 최종 산출물을 못 읽었습니다 — %s: %s" % (type(e).__name__, e))
        return 1
    생 = next((n for n in 책 if n.lower() == "raw_voc"), None)
    if 생 is None:
        print("  ✗ raw_voc 시트가 없습니다 — 최종 산출물이 아닌 것 같습니다.")
        print("     있는 시트: %s" % " · ".join(list(책)[:10]))
        return 1
    표틀 = 칸맞추기(책[생])
    print("  · 읽었습니다 — %s · raw_voc %d행 · 시트 %d개" % (최종.name, len(표틀), len(책)))

    받을곳.mkdir(parents=True, exist_ok=True)
    밑이름 = 최종.stem
    낸것 = []
    for 쪽이름, 공유용 in (("살펴보기", False), ("공유용", True)):
        쓸표틀 = 표틀
        뺀칸 = []
        if 공유용:
            뺀칸 = [c for c in 공유용_빼는칸 if c in 쓸표틀.columns]
            쓸표틀 = 쓸표틀.drop(columns=뺀칸)
        쪽들 = {
            "voc": 화면_VoC현황(쓸표틀, pd, topic_distribution),
            "improve": 화면_개선방향성(쓸표틀, score_improvement_tasks),
            "inquiry": 화면_문의속니즈(쓸표틀, pd),
            "pl": 화면_PL이슈(책, pd),
            "video": 화면_영상정보(쓸표틀, pd),
        }
        본문 = "".join(쪽들.values())
        셈 = {"링크": 0, "이메일": 0, "사용자명": 0}
        if 공유용:
            # ★ 치우는 것은 **합친 뒤 한 번**에 한다 — 화면마다 따로 하면 센 숫자가 어긋난다
            본문 = _치우기(본문, 셈)
            쪽들 = {k: _치우기(v, {"링크": 0, "이메일": 0, "사용자명": 0}) for k, v in 쪽들.items()}
        제목 = "VoC 분석 대시보드 — %s (%s)" % (밑이름, 쪽이름)
        머리말 = ("4차까지 거친 <b>최종 데이터</b>로 만든 화면입니다 · "
               "raw_voc %s행 · 만든 날 %s" % (format(len(표틀), ","),
                                          datetime.now().strftime("%Y-%m-%d %H:%M")))
        꼬리 = ["<p><b>무엇으로 만들었나</b> — %s · 숫자는 대시보드와 같은 계산"
              "(<code>data_contract</code> · <code>scoring</code>)을 썼습니다.</p>" % _h(최종.name),
              "<p><b>라이브만 안 됩니다</b> — 유튜브에서 새로 모으고 다시 분석하는 것(OpenAI 호출)은 "
              "서버가 있어야 합니다. 보는 것(표 · 그림 · 탭 · 찾기 · 정렬)은 이 파일 안에서 다 됩니다. "
              "인터넷이 없어도 열립니다.</p>"]
        if 공유용:
            남음 = _남았나(본문)
            꼬리.append("<p><b>공유용입니다</b> — 원문 전량과 식별자를 뺐습니다(%s). "
                      "치운 것 — 링크 %d · 이메일 %d · 사용자명 %d. "
                      "다시 훑은 결과 — 링크 %d · 이메일 %d · 사용자명 %d.</p>"
                      % (" · ".join(뺀칸) or "뺀 칸 없음",
                         셈["링크"], 셈["이메일"], 셈["사용자명"],
                         남음["링크"], 남음["이메일"], 남음["사용자명"]))
        else:
            꼬리.append("<p><b>살펴보기용입니다</b> — 원문이 들어 있습니다. 사내에서만 봅니다. "
                      "밖으로 보낼 때는 같은 이름의 <code>_공유용.html</code> 을 쓰십시오.</p>")
        길 = 받을곳 / ("%s_%s.html" % (밑이름, 쪽이름))
        길.write_text(한장만들기(쪽들, 제목=제목, 머리말=머리말, 꼬리말="".join(꼬리)),
                     encoding="utf-8", newline="\n")
        낸것.append((길, 셈, _남았나(길.read_text(encoding="utf-8")) if 공유용 else None))
        print("  · %s — %s (%.1f MB)" % (쪽이름, 길.name, 길.stat().st_size / 1048576))
        if 공유용:
            print("    치운 것 — 링크 %d · 이메일 %d · 사용자명 %d" % (셈["링크"], 셈["이메일"], 셈["사용자명"]))

    # ★ 「치웠다」 가 아니라 **다시 훑어 0건**임을 본다. 남으면 공유용을 믿을 수 없다
    for 길, _셈, 남음 in 낸것:
        if 남음 is None:
            continue
        print("    다시 훑은 결과 — 링크 %d · 이메일 %d · 사용자명 %d"
              % (남음["링크"], 남음["이메일"], 남음["사용자명"]))
        if any(남음.values()):
            print("  ✗ 공유용에 치울 것이 남았습니다 — 밖으로 보내지 마십시오: %s" % 길)
            return 2
    print("  ★ 끝났습니다 — 이 HTML 은 **서버 없이** 열립니다 (인터넷도 필요 없습니다).")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    인자 = sys.argv[1:]
    # ★ 2026-10-08 — `--help` 를 **자리 이름으로 보고** 폴더를 만든 일이 있었다. 먼저 가린다.
    if not 인자 or 인자[0] in ("-h", "--help", "/?"):
        print(__doc__)
        return 0 if 인자 else 1
    최종 = Path(인자[0]).resolve()
    받을곳 = Path(인자[1]).resolve() if len(인자) > 1 else 최종.parent / "대시보드_HTML"
    return 만들기(최종, 받을곳)


if __name__ == "__main__":
    sys.exit(main())
