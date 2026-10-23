# -*- coding: utf-8 -*-
"""최종 산출물로 **대시보드 화면을 HTML 한 장**으로 만든다 — 서버 없이 어디서든 열린다.

★ 무엇을 하나 (sky 2026-10-20)
  「여섯번째 스킬이 최종 분석 아웃풋을 바탕으로 스트림릿에 있는 대시보드를 그대로 구현한 걸
   html 파일로 누구나 어디 컴퓨터에서든 열 수 있도록 만들고 싶은거죠」
  「거기서 구현되는 동작들까지 다 그대로 백프로 따라서 그냥 그대로 가져오면 되는 거 알죠?」
  「어차피 서버로 부르는 분석은 스킬로 미리 다 하고, 최종 결과물을 반영한 대시보드만
   보기 쉽게 html 로 만드는 게 6번 skill 의 역할」

  → **보는 쪽은 100% 그대로** 옮긴다. 서버가 필요한 쪽(새로 분석 · 다시 분석 · 결과 올리기 ·
    챗봇)은 **넣지 않는다** — 그것은 1~5번 스킬이 이미 한 일이다.

★ 어떻게 (2026-10-20 에 방식을 바꿨다)
  전에는 **집계를 미리 계산해 그림으로 박아** 넣었다. 그래서 필터를 바꿔도 다시 계산되지 않았다 —
  보이는 것만 흉내 낸 것이다. 지금은 **행 자료를 통째로 넣고** 화면 로직을 JS 로 옮겨,
  필터를 바꿀 때마다 카드·그림·표가 **다시 계산**된다.

    `자료_담기.py`   최종 엑셀 → 행 자료 · 고를 것 · 엔진이 낸 맞춤값
    `화면_js.py`     필터와 다섯 화면을 JS 로 옮긴 것 (원본 views/ 를 하나씩 대조)
    이 파일          둘을 묶어 HTML 한 장으로 낸다

★ 꾸밈은 **원본 CSS 를 그대로 꺼내 쓴다** (`ui_cards.inject_card_css` 의 style 덩이 · 약 15,600자).
  내가 다시 쓰면 영원히 조금씩 다르다.

★ 인터넷 없이 열려야 한다 — CDN 을 쓰지 않는다. 그림은 인라인 SVG, 동작은 순수 JS.

★ 숫자가 엔진과 어긋나면 안 된다 — HTML 이 열릴 때 **엔진이 낸 값과 스스로 대본다.**
  어긋나면 화면 맨 위에 빨갛게 알린다. 「돌아간다」 와 「맞다」 는 다르다.

★ 두 벌을 낸다 (sky 「둘 다 필요하다」)
    <이름>_살펴보기.html   원문을 담는다. 사내에서 본다
    <이름>_공유용.html     원문 전량·식별자를 빼고 링크·이메일·사용자명을 치운다.
                           치운 건수를 적고 **다시 훑어 0건**임을 확인한다

쓰기
    python <이 스킬>/scripts/대시보드_HTML_만들기.py <최종엑셀> [<받을곳>]

종료코드
    0  둘 다 만들었다     1  막혔다     2  치울 것이 남았다 (공유용을 믿을 수 없다)
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path

여기 = Path(__file__).resolve().parent
스킬 = 여기.parent
sys.path.insert(0, str(여기))
import 자료_담기 as 담기          # noqa: E402
from 화면_js import JS            # noqa: E402

# ── 치우는 것 — 보고서 스킬(`building-voc-report`)과 같은 무늬를 쓴다 ──────────────
링크 = re.compile(r"https?://\S+|www\.\S+")
이메일 = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
사용자명 = re.compile(r"@[\w가-힣._-]{2,}")
# ★ 내가 쓴 <style>·<script> 는 자료가 아니라서 다시훑기에서 뺀다 (CSS 의 @media 가 걸렸다)
꾸밈덩어리 = re.compile(r"<(style|script)\b.*?</\1>", re.S | re.I)


def _h(x) -> str:
    return html.escape("" if x is None else str(x))


def _치우기(글: str, 셈: dict) -> str:
    글 = 링크.sub(lambda m: (셈.__setitem__("링크", 셈["링크"] + 1), "[링크 치움]")[1], 글)
    글 = 이메일.sub(lambda m: (셈.__setitem__("이메일", 셈["이메일"] + 1), "[이메일 치움]")[1], 글)
    글 = 사용자명.sub(lambda m: (셈.__setitem__("사용자명", 셈["사용자명"] + 1), "[사용자명 치움]")[1], 글)
    return 글


def 행값_치우기(행들: list, 셈: dict) -> list:
    r"""★ **값 하나하나에** 적용한다 — JSON 글자에 대고 하면 안 된다 (2026-10-22).

    전에는 다 만들어진 JSON **글자**에 무늬를 댔다. 그래서 링크 무늬 `https?://\S+` 가
    「공백이 아닌 글자」 를 따라가며 **JSON 문법을 통째로 먹었다.** `json글` 이 공백 없이
    (`separators=(",", ":")`) 찍으므로, 값 뒤의 `","다음칸":"…` 가 전부 링크의 일부로
    빨려 들어갔다. 실제로 이렇게 됐다 —

        "video_url":"[링크 치움] 스테이션","atomic_voc_summary":"설치/설치 편의성: 설치"
                           ↑ 칸 여러 개가 사라지고, 행 경계(`}},{{`)를 넘으면 **행이 합쳐졌다**

    2판 6,846행에서 **행이 120개 줄었고**(6,846 → 6,726) 집계가 다 어긋났다.
    화면의 자기검사가 126건으로 잡아 빨간 띠를 띄웠다 — 조용히 틀리지는 않았다.
    (작은 번들 50행에서는 먹힌 자리가 행 경계를 안 넘어 우연히 통과했다.)

    그래서 **값에만** 댄다. 값 안에서는 `\S+` 가 그 값을 넘어갈 수 없다.
    """
    치운것 = []
    for 줄 in 행들:
        새줄 = {}
        for k, v in 줄.items():
            새줄[k] = _치우기(v, 셈) if isinstance(v, str) else v
        치운것.append(새줄)
    return 치운것


def _남았나(글: str) -> dict:
    자료 = 꾸밈덩어리.sub(" ", 글)
    return {"링크": len(링크.findall(자료)), "이메일": len(이메일.findall(자료)),
            "사용자명": len(사용자명.findall(자료))}


def _원본꾸밈() -> str:
    """★ 대시보드의 **진짜 CSS** 를 엔진 소스에서 꺼낸다.

    `ui_cards.inject_card_css()` 가 `st.markdown` 으로 넣는 `<style>` 덩이다.
    부르면 streamlit 이 필요하므로 소스에서 뽑는다. 내가 다시 쓰면 모양이 달라진다.
    """
    길 = 담기._찾기("engine") / "src" / "dashboard60" / "ui_cards.py"
    if not 길.is_file():
        return ""
    m = re.search(r"def inject_card_css.*?<style>(.*?)</style>", 길.read_text(encoding="utf-8"), re.S)
    return m.group(1) if m else ""


# ── 뼈대 꾸밈 — 원본에 없는 것만 (사이드바 · 탭 · 표 · 접이식) ──────────────────
뼈대꾸밈 = """
/* ★ 개선 방향성 — 정렬 축 줄과 Top 3 배치 (2026-10-23 · 원본 st.radio + st.columns(3)) */
.d60-axis{margin:10px 0 4px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}
.d60-axis label{display:inline-flex;gap:5px;align-items:center;cursor:pointer;font-size:14px}
.d60-top3{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:8px 0 18px}
.d60-mini-card details{margin-top:8px}
.d60-mini-card details>summary{cursor:pointer;color:var(--sub,#6b7280);font-size:13px;padding:4px 0}
/* ★ 대표 문의 카드 — 원본은 행마다 st.columns(2) 를 새로 만든다 (두 칸 격자가 같은 모양) */
.d60-card2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:8px 0 18px}
.d60-axis select{font:inherit;padding:3px 6px;border:1px solid var(--line,#e5e7eb);border-radius:6px}
/* ★ ② 영상 — 고르개 줄과 「영상 열기」 (원본 st.columns + st.link_button) */
.vopt{margin:10px 0 4px;display:flex;flex-wrap:wrap;gap:14px;align-items:center}
.vopt label{display:inline-flex;gap:5px;align-items:center;font-size:14px}
.vopt select,.vopt input[type=number]{font:inherit;padding:3px 6px;
  border:1px solid var(--line,#e5e7eb);border-radius:6px}
.vopt input[type=number]{width:84px}
.vopt>p{flex:1 0 100%;margin:2px 0 0}
.d60-link{display:inline-block;margin:6px 0;padding:5px 12px;border-radius:8px;
  border:1px solid var(--line,#e5e7eb);text-decoration:none;color:inherit;font-size:14px}
.d60-link:hover{background:#f8fafc}
@media(max-width:700px){.d60-top3,.d60-card2{grid-template-columns:1fr}}

*{box-sizing:border-box}
body{margin:0;background:var(--bg,#fff);color:var(--fg,#111827);
  font:15px/1.6 -apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
.wrap{display:grid;grid-template-columns:260px 1fr;min-height:100vh}
#side{border-right:1px solid var(--line,#e5e7eb);padding:18px 14px;background:var(--card,#f9fafb);
  position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto}
#side h3{margin:16px 0 6px;font-size:14px}
.side-box{border:1px solid var(--line,#e5e7eb);border-radius:8px;padding:9px 11px;background:var(--bg,#fff)}
.fgroup{margin:8px 0 12px}
.flabel{font-size:12px;font-weight:700;margin-bottom:3px}
label.chk{display:block;font-size:13px;padding:1px 0;cursor:pointer}
#side button,.pickhead button{font:inherit;font-size:13px;padding:6px 11px;margin-top:6px;
  border:1px solid var(--line,#e5e7eb);border-radius:8px;background:var(--bg,#fff);cursor:pointer}
#side button:hover:not(:disabled){border-color:var(--lg-red,#A50034);color:var(--lg-red,#A50034)}
button:disabled{opacity:.45;cursor:default}
main{padding:18px 20px 60px;max-width:1180px}
h1{margin:0 0 4px;font-size:22px}h2{margin:22px 0 6px;font-size:18px}
.sub{color:var(--sub,#6b7280);font-size:13px;margin:2px 0 10px}
.empty{color:var(--sub,#6b7280);padding:12px;background:var(--card,#f9fafb);border-radius:8px}
#tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
#tabs button{font:inherit;padding:7px 15px;border:1px solid var(--line,#e5e7eb);border-radius:999px;
  background:transparent;color:inherit;cursor:pointer}
#tabs button[aria-selected="true"]{background:var(--lg-red,#A50034);color:#fff;border-color:var(--lg-red,#A50034)}
#seen{font-size:13px;color:var(--sub,#6b7280);margin:4px 0 10px}
#selfcheck{font-size:13px;border-radius:8px;padding:8px 11px;margin:8px 0}
#selfcheck.ok{background:#ecfdf5;color:#065f46}
#selfcheck.bad{background:#fef2f2;color:#991b1b;font-weight:700}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.pickhead{display:flex;align-items:center;justify-content:space-between;gap:10px}
.bl{font-size:11px;fill:var(--sub,#6b7280)}.bv{font-size:11px;fill:var(--fg,#111827)}
details.d60-ratio{margin-top:8px}
details.d60-ratio>summary{cursor:pointer;color:var(--sub,#6b7280);font-size:13px;padding:4px 0}
.tw{overflow:auto;max-height:62vh;border:1px solid var(--line,#e5e7eb);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line,#e5e7eb);padding:6px 9px;text-align:left;
  vertical-align:top;max-width:440px;overflow-wrap:anywhere}
th{position:sticky;top:0;background:var(--card,#f9fafb);cursor:pointer;white-space:nowrap}
tr.pickable{cursor:pointer}tr.pickable:hover{background:rgba(165,0,52,.06)}
tr.on{background:rgba(165,0,52,.12)}
.find{width:100%;padding:8px 10px;margin:6px 0;font:inherit;
  border:1px solid var(--line,#e5e7eb);border-radius:8px}
.detail{margin-top:14px;border:1px solid var(--line,#e5e7eb);border-radius:10px;padding:12px 14px}
footer{border-top:1px solid var(--line,#e5e7eb);margin-top:30px;padding:16px 0;
  color:var(--sub,#6b7280);font-size:13px}
@media(max-width:860px){.wrap{grid-template-columns:1fr}#side{position:static;max-height:none}}
"""


# ★ 화면 틀 — 원본 app_operating.main() 의 머리와 같게 (2026-10-23).
#   원본 주석 — 「『VoC 65』 는 개발 중 컬럼 수를 딴 이름이었다. 실무자에게는 뜻이 없다」
#   (sky 2026-08-20). 그래서 큰 제목은 **파일 이름이 아니라** 늘 이 이름이다.
큰제목 = "YouTube VoC 분석 대시보드"
설명줄 = ("YouTube 영상 댓글을 분석해 개선 포인트를 찾는 화면입니다. "
       "제품군 · 이유 topic · 감성을 나누어 보고, RootCause 까지 이어 봅니다.")
# ★ 최종본_앉히기 가 metadata.json 에 적는 것과 **같은 값**이어야 한다
#   (어긋나면 tests/test_대시보드html.py 가 잡는다)
스키마판 = "voc-final-after-4th"
읽개판 = "showing-voc-dashboard/대시보드_HTML_만들기"


def _만든판() -> str:
    """이 HTML 을 만든 코드의 판 — 원본의 「배포 커밋」 과 같은 자리.

    ★ git 이 없거나 저장소가 아니면 「unknown」 이다. 원본도 그렇게 적는다.
    """
    import subprocess                                                  # noqa: PLC0415

    try:
        것 = subprocess.run(["git", "--no-optional-locks", "rev-parse", "--short", "HEAD"],
                           cwd=str(Path(__file__).resolve().parents[3]),
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    값 = (것.stdout or "").strip()
    return 값 if 것.returncode == 0 and 값 else "unknown"


def 한장만들기(자료글: str, *, 제목: str, 머리말: str, 꼬리말: str) -> str:
    return ("<!doctype html>" + chr(10)
            + '<html lang="ko"><head><meta charset="utf-8">'
            + '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + "<title>%s</title>" % _h(제목)
            # ★ 원본 CSS 를 먼저, 그 위에 뼈대 꾸밈
            + "<style>%s</style><style>%s</style></head><body>" % (_원본꾸밈(), 뼈대꾸밈)
            + '<div class="wrap"><aside id="side"></aside><main>'
            # ★ 원본과 같은 머리 넷 — 큰 제목 · 배포 커밋 · 설명 · schema/parser
            + "<h1>%s</h1>" % _h(큰제목)
            + '<p class="sub">배포 커밋: <code>%s</code></p>' % _h(_만든판())
            + '<p class="sub">%s</p>' % _h(설명줄)
            + '<p class="sub">schema=%s · parser=%s</p>' % (_h(스키마판), _h(읽개판))
            + '<p class="sub">%s · %s</p>' % (_h(제목), 머리말)
            + '<div id="tabs"></div><div id="seen"></div><div id="selfcheck"></div>'
            + '<div id="body"></div>'
            + "<footer>%s</footer></main></div>" % 꼬리말
            + "<script>window.__VOC__=%s;</script>" % 자료글
            + "<script>%s</script></body></html>" % JS + chr(10))


def 만들기(최종: Path, 받을곳: Path) -> int:
    것 = 담기.엔진_불러오기()
    if 것 is None:
        return 1
    pd, 칸맞추기, apply_filters, 점수, 계약 = 것
    if not 최종.is_file():
        print("  ✗ 최종 산출물을 못 찾았습니다 — %s" % 최종)
        print("     (「못 찾음」 은 통과가 아닙니다 — 빈 화면을 만들지 않습니다)")
        return 1
    try:
        책 = 담기.책읽기(pd, 최종)
    except Exception as e:                                    # noqa: BLE001
        print("  ✗ 최종 산출물을 못 읽었습니다 — %s: %s" % (type(e).__name__, e))
        return 1
    생 = next((n for n in 책 if n.lower() == "raw_voc"), None)
    if 생 is None:
        print("  ✗ raw_voc 시트가 없습니다 — 최종 산출물이 아닌 것 같습니다.")
        print("     있는 시트: %s" % " · ".join(list(책)[:10]))
        return 1
    표틀 = 칸맞추기(책[생])
    맞춤 = 담기.맞춤값(표틀, pd, apply_filters, 점수, 계약)
    print("  · 읽었습니다 — %s · raw_voc %d행 · 시트 %d개" % (최종.name, len(표틀), len(책)))
    print("    엔진 기준 기본 필터 통과 %d행 (status=normal · confidence_gate)" % 맞춤["기본행수"])

    받을곳.mkdir(parents=True, exist_ok=True)
    밑이름 = 최종.stem
    낸것 = []
    for 쪽이름, 공유용 in (("살펴보기", False), ("공유용", True)):
        자료 = 담기.자료만들기(표틀, pd, 계약, 공유용=공유용)
        자료["맞춤값"] = 맞춤
        자료["정보"] = {"파일": 최종.name, "전체행": int(len(표틀)),
                     "만든날": datetime.now().strftime("%Y-%m-%d %H:%M")}
        제목 = "YouTube VoC 분석 대시보드 — %s (%s)" % (밑이름, 쪽이름)
        머리말 = ("4차까지 거친 <b>최종 데이터</b>로 만든 화면입니다 · "
               "서버 없이 열립니다 · 인터넷도 필요 없습니다")
        꼬리 = ["<p><b>무엇으로 만들었나</b> — %s · 숫자는 대시보드와 같은 계산"
              "(<code>data_contract.apply_filters</code> · <code>scoring</code>)을 썼고, "
              "열릴 때 엔진이 낸 값과 <b>스스로 대봅니다</b>.</p>" % _h(최종.name),
              "<p><b>여기 없는 것</b> — 새로 분석 돌리기 · 같은 원문으로 다시 분석 · "
              "결과 파일 올려서 보기 · 챗봇. 유튜브·OpenAI 를 불러야 해서 서버가 필요하고, "
              "그 일은 <b>1~5번 스킬이 이미 했습니다</b>.</p>"]
        셈 = {"링크": 0, "이메일": 0, "사용자명": 0}
        if 공유용:
            # ★ JSON 으로 찍기 **전에** 값마다 치운다 (아래 `행값_치우기` 주석의 사고)
            자료 = dict(자료, 행=행값_치우기(자료["행"], 셈))
        자료글 = 담기.json글(자료)
        if 공유용:
            뺀 = " · ".join(자료["뺀칸"]) or "뺀 칸 없음"
            꼬리.append("<p><b>공유용입니다</b> — 원문 전량과 식별자를 뺐습니다(%s). "
                      "치운 것 — 링크 %d · 이메일 %d · 사용자명 %d.</p>"
                      % (_h(뺀), 셈["링크"], 셈["이메일"], 셈["사용자명"]))
        else:
            꼬리.append("<p><b>살펴보기용입니다</b> — 원문이 들어 있습니다. 사내에서만 봅니다. "
                      "밖으로 보낼 때는 같은 이름의 <code>_공유용.html</code> 을 쓰십시오.</p>")
        길 = 받을곳 / ("%s_%s.html" % (밑이름, 쪽이름))
        길.write_text(한장만들기(자료글, 제목=제목, 머리말=머리말, 꼬리말="".join(꼬리)),
                     encoding="utf-8", newline="\n")
        낸것.append((길, 셈, 공유용))
        print("  · %s — %s (%.1f MB · 행 %d · 칸 %d)"
              % (쪽이름, 길.name, 길.stat().st_size / 1048576, len(자료["행"]), len(자료["칸"])))

    for 길, 셈, 공유용 in 낸것:
        if not 공유용:
            continue
        남음 = _남았나(길.read_text(encoding="utf-8"))
        print("    치운 것 — 링크 %d · 이메일 %d · 사용자명 %d" % (셈["링크"], 셈["이메일"], 셈["사용자명"]))
        print("    다시 훑은 결과 — 링크 %d · 이메일 %d · 사용자명 %d"
              % (남음["링크"], 남음["이메일"], 남음["사용자명"]))
        if any(남음.values()):
            print("  ✗ 공유용에 치울 것이 남았습니다 — 밖으로 보내지 마십시오: %s" % 길)
            return 2
    print("  ★ 끝났습니다 — 서버 없이 열립니다. 필터를 바꾸면 화면이 **다시 계산**됩니다.")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    인자 = sys.argv[1:]
    # ★ 2026-10-08 — `--help` 를 자리 이름으로 보고 폴더를 만든 일이 있었다. 먼저 가린다.
    if not 인자 or 인자[0] in ("-h", "--help", "/?"):
        print(__doc__)
        return 0 if 인자 else 1
    최종 = Path(인자[0]).resolve()
    받을곳 = Path(인자[1]).resolve() if len(인자) > 1 else 최종.parent / "대시보드_HTML"
    return 만들기(최종, 받을곳)


if __name__ == "__main__":
    sys.exit(main())
