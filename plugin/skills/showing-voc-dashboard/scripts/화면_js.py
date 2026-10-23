# -*- coding: utf-8 -*-
"""대시보드 화면 로직을 **JS 로 옮긴 것** — 필터를 바꾸면 전부 다시 계산한다 (2026-10-20).

★ 옮긴 원본 (하나하나 대조했다)
    `data_contract.apply_filters`        필터 — status · confidence_gate · 여섯 차원
    `views/overview.py`                  VoC 현황 — 카드 7 · 영역 고르개 · 그림 4 · 행 자세히
    `views/improvement.py`               개선 방향성 — 두 축 점수
    `views/inquiry.py`                   문의 속 니즈 — 카드 3 · 그림 2
    `views/pl_issue.py`                  PL Issue — 카드 3 · 표 (건수로 거르지 않는다)
    `views/video.py`                     분석 영상 정보 — 카드 2 · 그림 · 표

★ 서버가 필요한 것은 **담지 않는다** — 새로 분석 · 다시 분석 · 결과 올리기 · 챗봇.
  그것은 1~5번 스킬이 이미 한 일이다 (sky 2026-10-20).

★ 숫자가 엔진과 어긋나면 안 된다. 그래서 HTML 이 열릴 때 **엔진이 낸 맞춤값과 스스로 대본다**
  (`자료_담기.맞춤값`). 어긋나면 화면 맨 위에 빨갛게 알린다 — 조용히 틀린 숫자를 보여 주지 않는다.
"""

JS = r"""
// ─────────────────────────────────────────────────────────────────────────
// 필터 — 원본 data_contract.apply_filters 를 그대로 옮겼다
//   status == "normal" 인 행만 (scope_excluded 는 뺀다)
//   confidence_gate 통과한 행만 (기본 high_confidence_only = true)
//   제품군 · 영역 · 국가 · 감성 · CEJ 는 고른 것이 있으면 isin, 비었으면 전체 (AND)
//   브랜드만 OR — 자사(brand_display) 또는 경쟁사 태그 중 하나만 맞아도 통과
// ─────────────────────────────────────────────────────────────────────────
var D = window.__VOC__;          // {칸, 행, 고를것, 맞춤값, 정보}

// ── 엔진에서 실어 온 상수 — 손으로 베끼지 않는다 (2026-10-22 Codex 교차점검) ──────
//   브랜드 동의어 표 · 중국 브랜드 묶음 · 판정 충족도 목록은 `자료_담기.상수담기` 가
//   엔진(`data_contract`)에서 꺼내 HTML 에 실어 준다. 여기서 또 적으면 두 벌이 된다.
var K = D.상수 || {};
var SYN = K.브랜드동의어 || {};
var CHINA = K.중국묶음 || [];
var CONF_LEVELS = (K.판정충족도 && K.판정충족도.length) ? K.판정충족도
                  : ["Very High", "High", "Medium", "Low"];
var CONF_DEFAULT = (K.기본판정충족도 && K.기본판정충족도.length) ? K.기본판정충족도
                   : ["Very High", "High"];
// 원본은 **칸이 있는지**로 어느 칸을 볼지 정한다 (행마다 고르지 않는다) — data_contract:426-431
var OWN_COL = (D.칸 || []).indexOf("brand_display") >= 0 ? "brand_display" : "brand";
var COMP_COL = (D.칸 || []).indexOf("competitor_brand_display_tags") >= 0
               ? "competitor_brand_display_tags" : "competitor_brand_tags";

// 원본 `_normalize_brand_display` 그대로 — 공백을 하나로 고르고, 세 꼴로 동의어를 찾는다
function normBrand(v) {
  var s = txt(v);
  if (!s) return "";
  var sp = s.replace(/[\s ]+/g, " ").trim();
  var keys = [sp, sp.split(" ").join(""), sp.toLowerCase()];
  for (var i = 0; i < keys.length; i++) {
    if (Object.prototype.hasOwnProperty.call(SYN, keys[i])) return SYN[keys[i]];
  }
  return sp;
}

// 원본 `_expand_brand_filter_values` — 「중국」 이 들어가면 중국 브랜드 묶음을 전부 더한다
function expandBrands(vals) {
  var out = {};
  (vals || []).forEach(function (v) {
    var nv = normBrand(v);
    if (!nv) return;
    out[nv] = 1;
    if (nv.indexOf("중국") >= 0 || nv.split(" ").join("").indexOf("중국") >= 0) {
      CHINA.forEach(function (m) { out[m] = 1; });
    }
  });
  return Object.keys(out);
}

// 원본 `_brand_matches` — 공백을 없애고 소문자로 만든 뒤 **양쪽 부분일치**까지 본다
function brandMatches(v, selected) {
  var nv = normBrand(v);
  if (!nv) return false;
  var compact = nv.split(" ").join("").toLowerCase();
  for (var i = 0; i < selected.length; i++) {
    var cc = normBrand(selected[i]).split(" ").join("").toLowerCase();
    if (!cc) continue;
    if (compact === cc || cc.indexOf(compact) >= 0 || compact.indexOf(cc) >= 0) return true;
  }
  return false;
}
// ★ 2026-10-21 Codex 교차점검 — 감성만 뜻이 반대였다.
//   원본(app_operating.py:416-423 · data_contract.py:440-442)은 감성을 **처음에 셋 다 고른**
//   상태로 두고, `sentiments is not None` 이라 **빈 목록이면 0행**이다. 다른 축은 빈 목록이 전체다.
//   내 것은 빈 목록을 전체로 봤다 — 마지막 감성을 끄면 원본은 빈 화면인데 내 것은 전체로 돌아갔다.
// ★ 2026-10-22 Codex 교차점검 — 판정 충족도와 사람검토 **필터 자체가 없었다.**
//   원본은 둘을 사용자가 고르고 그 값으로 거른다 (app_operating.py:425-452 ·
//   gating.py:28-51). 내 것은 `confidence_gate === true` 를 박아 두어 **언제나
//   Very High+High** 만 보였다 — 그 상태에서만 우연히 맞고 다른 화면은 못 만들었다.
//   ★ 판정 충족도도 감성과 같다 — **빈 목록이면 0행**이다
//     (`confidence_levels` 가 `[]` 여도 `is not None` 이라 `isin(set())` 가 된다).
var S = {product_category: [], topic_group: [], brand: [], market: [],
         cej: [], sentiment_dir: null,
         confidence: CONF_DEFAULT.slice(), review_only: false,
         // 영상 화면 — 원본 기본값 그대로 (최소 5댓글 · 부정률 높은 순 · 4개)
         video_min: 5, video_thin_only: false,
         video_sort: "부정률 높은 순", video_count: 4,
         tab: "voc", detail: null};

function txt(v) { return v === undefined || v === null ? "" : String(v).trim(); }
function esc(v) {
  return txt(v).replace(/[&<>"']/g, function (c) {
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
  });
}
function num(n) { return Number(n).toLocaleString("ko-KR"); }
function pct(a, b) { return b ? (a / b * 100).toFixed(1) + "%" : "0.0%"; }

// 브랜드는 태그가 여럿일 수 있다 — 원본 _split_tag_values 와 같이 나눈다
function tagList(v) {
  return txt(v).split(/[|,;·]/).map(function (x) { return x.trim(); }).filter(Boolean);
}

function applyFilters(rows, opt) {
  opt = opt || {};
  var skip = opt.skip || "";
  var gate = opt.gate || "";
  // 「중국」 묶음 펼치기는 한 번만 한다 (행마다 하면 느리고 결과는 같다)
  var 고른브랜드 = expandBrands(S.brand);
  // ★ scope: 「제외 사유」 그림용 집합 — 원본 app_operating.py:543
  //   `apply_filters(products=·brands=·markets=, high_confidence_only=False,
  //     include_scope_excluded=True)`. 제외행은 신뢰도가 낮고 영역이 미판정이라
  //   그 조건을 걸면 다 사라진다. **제품군·브랜드·국가만** 건다.
  var scope = !!opt.scope;
  return rows.filter(function (r) {
    if (!scope && txt(r.status) !== "normal") return false;
    if (scope) {
      if (S.product_category.length &&
          S.product_category.indexOf(txt(r.product_category)) < 0) return false;
      if (S.market.length && S.market.indexOf(txt(r.market_display || r.market)) < 0) return false;
      if (고른브랜드.length) {
        var c2 = tagList(r[COMP_COL]);
        if (!(brandMatches(r[OWN_COL], 고른브랜드) ||
              c2.some(function (c) { return brandMatches(c, 고른브랜드); }))) return false;
      }
      return true;
    }
    // 판정 충족도 — 고른 목록으로 거른다 (빈 목록이면 0행 · 원본과 같다)
    // ★ gate: "none" 은 「무엇을 볼까」 만 통과한 집합(dimension_filtered) ·
    //   gate: "conf" 는 판정 충족도까지만(confidence_filtered). 원본 app_operating.py:430-467
    if (gate !== "none" && skip !== "confidence" &&
        S.confidence.indexOf(txt(r.confidence_rating)) < 0) return false;
    if (gate !== "none" && gate !== "conf" && S.review_only && r.review_queue !== true) return false;
    if (skip !== "product_category" && S.product_category.length &&
        S.product_category.indexOf(txt(r.product_category)) < 0) return false;
    if (skip !== "topic_group" && S.topic_group.length &&
        S.topic_group.indexOf(txt(r.topic_group)) < 0) return false;
    if (skip !== "market" && S.market.length &&
        S.market.indexOf(txt(r.market_display || r.market)) < 0) return false;
    if (skip !== "cej" && S.cej.length && S.cej.indexOf(txt(r.cej)) < 0) return false;
    // ★ 감성은 **빈 목록이면 0행**이다 (원본 sentiments is not None). 다른 축과 다르다
    if (skip !== "sentiment_dir" && S.sentiment_dir !== null &&
        S.sentiment_dir.indexOf(txt(r.sentiment_dir)) < 0) return false;
    if (skip !== "brand" && 고른브랜드.length) {
      // ★ 자사 OR 경쟁사 — 원본에서 이 축만 OR 다
      // ★ 2026-10-22 — 전에는 `r.brand_display || r.brand` 로 **빈 행에 원래 brand 를
      //   되살렸다.** 원본은 그러지 않는다 — `brand_display` 는 「자사 얘기일 때만」
      //   채워진 칸이라, 되살리면 LG 가 무관한 행까지 먹는다 (`_brand_display` 주석의
      //   실측: LG 필터가 6,392행 → 3,160행, 빠지는 행의 96% 는 원문에 LG 가 없다).
      var comp = tagList(r[COMP_COL]);
      var hit = brandMatches(r[OWN_COL], 고른브랜드) ||
                comp.some(function (c) { return brandMatches(c, 고른브랜드); });
      if (!hit) return false;
    }
    return true;
  });
}

// ── 집계 ──────────────────────────────────────────────────────────────────
// ★ 2026-10-22 Codex 교차점검 — 빈값 처리가 원본과 달랐다.
//   원본은 칸마다 **정해진 대체 라벨**로 모은다 (data_contract.py:461-496 · overview.py:300-345) —
//     topic       → "N/A"      (`topic_distribution`)
//     topic_group → "미판정"    (`topic_group_distribution`)
//     cej         → "해당없음"
//     inquiry_flag→ "N" · **대문자로 바꾼 뒤** Y/N 을 **항상 둘 다** 낸다
//     sentiment_dir → 대체 없음. `value_counts()` 그대로라 빈값도 한 칸으로 센다
//   내 것은 대체 라벨이 없으면 **빈값을 버렸다.** 그래서 막대 합계가 전체 행 수보다 작았다.
//   `blank` 를 주지 않으면 빈값을 「(빈칸)」 으로 **버리지 않고** 센다.
function countBy(rows, col, blank, opt) {
  opt = opt || {};
  var m = {};
  rows.forEach(function (r) {
    var k = txt(r[col]);
    if (opt.upper) k = k.toUpperCase();
    if (!k) k = (blank !== undefined && blank !== null) ? blank : "(빈칸)";
    m[k] = (m[k] || 0) + 1;
  });
  // 원본이 `reindex` 로 **없는 값도 0 으로** 내는 칸이 있다 (문의 Flag 의 Y·N)
  (opt.always || []).forEach(function (k) { if (m[k] === undefined) m[k] = 0; });
  var 것 = Object.keys(m).map(function (k) { return [k, m[k]]; });
  if (opt.order) {
    return opt.order.filter(function (k) { return m[k] !== undefined; })
      .map(function (k) { return [k, m[k]]; });
  }
  return 것.sort(function (a, b) { return b[1] - a[1] || a[0].localeCompare(b[0], "ko"); });
}
// 원본 `_display_label` + `_counts` — 코드값을 한국어로 바꾼 뒤 센다.
//   사전에 없으면 원문 그대로, 빈값은 「해당없음」 (원본 inquiry.py:32-34 · 158-166)
function countByLabel(rows, col, 이름표) {
  이름표 = 이름표 || {};
  var m = {};
  rows.forEach(function (r) {
    var 코드 = txt(r[col]);
    var k = Object.prototype.hasOwnProperty.call(이름표, 코드) ? 이름표[코드]
            : (코드 || "해당없음");
    m[k] = (m[k] || 0) + 1;
  });
  return Object.keys(m).map(function (k) { return [k, m[k]]; })
    .sort(function (a, b) { return b[1] - a[1] || a[0].localeCompare(b[0], "ko"); });
}

// ★ 2026-10-21 Codex 교차점검 — 원본은 pandas `nunique()` 라 **빈 문자열도 한 값으로** 센다.
//   내 것은 빈값을 버려서 카드 숫자가 원본보다 하나 작아졌다.
function uniq(rows, col) {
  var s = {};
  rows.forEach(function (r) { s[txt(r[col])] = 1; });
  return Object.keys(s).length;
}

// ── 그리기 조각 — 원본 ui_cards 의 클래스를 그대로 쓴다 (원본 CSS 가 먹는다) ─────────
function card(label, value, sub, tone) {
  return '<div class="d60-metric-card tone-' + (tone || "blue") + '">' +
    '<div class="d60-metric-label">' + esc(label) + '</div>' +
    '<div class="d60-metric-value">' + esc(value) + '</div>' +
    '<div class="d60-metric-sub">' + esc(sub) + '</div></div>';
}
function cardGrid(cards) { return '<div class="d60-card-grid">' + cards.join("") + "</div>"; }
function sectionTitle(t, note) {
  return '<div class="d60-section-title"><h4>' + esc(t) + "</h4>" +
    (note ? '<span class="d60-note">' + esc(note) + "</span>" : "") + "</div>";
}

var PALETTE = ["#A50034", "#6B7280", "#1D4ED8", "#047857", "#B45309", "#7C3AED",
               "#BE185D", "#0E7490", "#4D7C0F", "#9333EA"];
var SENTI = {"긍정": "#047857", "부정": "#A50034", "중립": "#6B7280"};
function colorOf(label, i, map) { return (map && map[label]) || PALETTE[i % PALETTE.length]; }

// 비율 줄 — 원본 ui_cards.ratio_rows 와 같은 클래스
function ratioRows(pairs, map) {
  var total = pairs.reduce(function (a, b) { return a + b[1]; }, 0) || 1;
  return pairs.map(function (p, i) {
    var w = (p[1] / total * 100).toFixed(1);
    return '<div class="d60-ratio-row"><div class="d60-ratio-head"><span>' + esc(p[0]) +
      "</span><span>" + num(p[1]) + " · " + w + '%</span></div>' +
      '<div class="d60-ratio-track"><div class="d60-ratio-fill" style="width:' + w +
      "%;background:" + colorOf(p[0], i, map) + '"></div></div></div>';
  }).join("");
}

// 가로 막대 그림 (인라인 SVG — 인터넷이 없어도 뜬다) + 비율 보기 접이식
function barChart(pairs, title, note, map, onclick) {
  if (!pairs.length) {
    return '<div class="d60-mini-card">' + sectionTitle(title, note) +
      '<p class="empty">이 조건에서는 담을 것이 없습니다.</p></div>';
  }
  var W = 560, NAME = 150, VAL = 60, LH = 26;
  var max = Math.max.apply(null, pairs.map(function (p) { return p[1]; })) || 1;
  var H = LH * pairs.length + 8, bars = "";
  pairs.forEach(function (p, i) {
    var y = i * LH + 4, len = Math.max(2, Math.round((W - NAME - VAL) * p[1] / max));
    var cursor = onclick ? ' style="cursor:pointer"' : "";
    var on = onclick ? ' data-pick="' + esc(p[0]) + '" data-pickkind="' + onclick + '"' : "";
    bars += '<g' + cursor + on + '>' +
      '<text x="' + (NAME - 8) + '" y="' + (y + 15) + '" class="bl" text-anchor="end">' +
        esc(p[0].length > 22 ? p[0].slice(0, 22) : p[0]) + "</text>" +
      '<rect x="' + NAME + '" y="' + (y + 4) + '" width="' + len + '" height="' + (LH - 10) +
        '" rx="3" fill="' + colorOf(p[0], i, map) + '"></rect>' +
      '<text x="' + (NAME + len + 6) + '" y="' + (y + 15) + '" class="bv">' + num(p[1]) +
      "</text></g>";
  });
  return '<div class="d60-mini-card">' + sectionTitle(title, note) +
    '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" role="img" aria-label="' + esc(title) +
    '">' + bars + "</svg>" +
    '<details class="d60-ratio"><summary>' + esc(title) + " — 비율 보기</summary>" +
    ratioRows(pairs, map) + "</details></div>";
}

// 표 — 정렬 · 찾기 · 행 고르기
function table(head, rows, id, pickable, detailId) {
  if (!rows.length) return '<p class="empty">이 조건에서는 담을 것이 없습니다.</p>';
  var th = head.map(function (c, i) { return '<th data-i="' + i + '">' + esc(c) + "</th>"; }).join("");
  var tb = rows.map(function (r, ri) {
    return '<tr' + (pickable ? ' data-row="' + ri + '"' +
      (detailId ? ' data-detail="' + detailId + '"' : "") + ' class="pickable"' : "") + ">" +
      r.map(function (v) { return "<td>" + esc(v) + "</td>"; }).join("") + "</tr>";
  }).join("");
  return '<input class="find" data-for="' + id + '" placeholder="이 표에서 찾기">' +
    '<div class="tw"><table id="' + id + '"><thead><tr>' + th + "</tr></thead><tbody>" + tb +
    "</tbody></table></div><p class=\"sub\">" + num(rows.length) +
    "행 · 머리를 누르면 정렬" + (pickable ? " · 행을 누르면 아래에 자세히" : "") + "</p>";
}


// ─────────────────────────────────────────────────────────────────────────
// 화면 ① VoC 현황 — 원본 views/overview.py:render
//   카드 7 · 개선/강화 영역 고르개(막대를 누르면 필터) · 그림 4 · 행 자세히
// ─────────────────────────────────────────────────────────────────────────
// ★ 원본 views/overview.py:175 ROOTCAUSE_GRADE_NOTE — 엔진에서 실어 온다 (베끼지 않는다)
var GRADE_NOTE = K.등급풀이 || {};
var GRADE_CODES = ["L3", "L2", "L1", "L0"];

// ★ 원본 _split_series — 「분리로 생긴 행인지. 칸이 없으면 전부 False」
function 분리행인가(r) {
  var v = txt(r.split_origin_atomic_id);
  return v !== "" && v !== "nan" && v !== "None" && v !== "N/A";
}

// ★ 원본 _rootcause_grade — rootcause_summary 앞 두 글자가 등급이다
function 등급코드(r) {
  var s = txt(r.rootcause_summary).slice(0, 2);
  return GRADE_NOTE[s] ? s : "";
}

// ★ 원본 overview.py:385-407 `display_columns` — **칸이름을 바꾸지 않는다**(원본도 안 바꾼다).
//   「RC 를 왼쪽에 모은다. 『RC 가 있는 행』 을 눈으로 훑을 수 있어야 한다」 (sky 2026-08-19)
function 현황표칸() {
  var c = ["rootcause_summary", "rootcause_problem", "rootcause_target", "rootcause_cause",
           "source_id", "raw_row_index", "product_category", "topic", "sentiment_dir", "cej",
           "entity_role", "tee_time_score", "tee_effort_score", "tee_emotion_score",
           "tee_success_score", "confidence_rating", "review_required", "atomic_voc_summary"];
  // ★ 원본과 같은 자리에 끼운다 — source_run 은 2번, 그 뒤에 2차분리가 4번
  if ((D.칸 || []).indexOf("source_run") >= 0) c.splice(2, 0, "source_run");
  c.splice(4, 0, "2차분리");
  return c;
}

function viewOverview(rows, groupSource, scopeSource) {
  var total = rows.length;
  var inq = rows.filter(function (r) { return txt(r.inquiry_flag).toUpperCase() === "Y"; }).length;
  var review = rows.filter(function (r) { return r.review_queue === true; }).length;
  var valid = rows.filter(function (r) { return txt(r.validity) === "유효"; }).length;
  // ★ 2026-10-21 Codex 교차점검 — 원본(overview.py:183-195)은 `split_origin_atomic_id` 가
  //   비어 있지 않은 **모든** 행을 센다. 내 것은 `atomic_index != 1` 로 세어 **첫 조각을 빼먹었다**
  //   (실측 — 원본 2행 vs 내 1행).
  var split = rows.filter(분리행인가).length;
  var h = "<h2>VoC 현황</h2><p class=\"sub\">topic 은 제품군·감성과 분리된 <b>이유</b> 라벨이며, " +
    "감성은 TEE/S 기반 sentiment_dir 로 별도 표시합니다.</p>";
  h += cardGrid([
    card("VoC Rows", num(total), "현재 필터 기준", "blue"),
    card("유효 Row", num(valid), pct(valid, total), "green"),
    card("문의 비율", pct(inq, total), num(inq) + "건", "purple"),
    card("사람검토 큐", num(review), "review_required=Y", "orange"),
    card("제품군 수", num(uniq(rows, "product_category")), "product_category", "blue"),
    card("Reason Topic 수", num(uniq(rows, "topic")), "제품·감성 분리", "green"),
    card("2차 분리 행", num(split), "한 댓글에 주제가 여럿이라 나눈 것", "purple")
  ]);
  // 개선/강화 영역 고르개 — ★ 영역 필터만 뺀 집합으로 그린다 (원본 D-1b)
  var gp = countBy(groupSource, "topic_group", "미판정");
  if (gp.length) {
    var now = S.topic_group.length ? S.topic_group.join(" · ") : "전체";
    h += '<div class="pickhead">' + sectionTitle("개선/강화 영역",
      "막대를 누르면 그 영역만 봅니다.  ·  Shift+클릭으로 여러 영역을 함께 고릅니다." +
      "  ·  사이드바 필터와 같은 값을 씁니다.  ·  지금: " + now) +
      '<button id="groupReset"' + (S.topic_group.length ? "" : " disabled") +
      ">전체 보기</button></div>";
    h += barChart(gp, "", "", null, "topic_group");
  }
  h += '<div class="row">';
  h += barChart(countBy(rows, "topic", "N/A").slice(0, 15), "Reason Topic 분포", "상위 15개");
  // 감성은 대체 라벨이 없다 — 원본이 `value_counts()` 그대로라 빈값도 한 칸이다
  h += barChart(countBy(rows, "sentiment_dir", ""), "감성 분포", "TEE/S 기반 긍정·부정·중립", SENTI);
  h += "</div><div class=\"row\">";
  h += barChart(countBy(rows, "cej", "해당없음"), "CEJ 9단계", "데이터사전 v2.7 기준");
  // 문의 Flag — 대문자로 모으고 Y·N 을 항상 그 차례로 둘 다 낸다 (원본 reindex)
  h += barChart(countBy(rows, "inquiry_flag", "N", {upper: true, always: ["Y", "N"],
                order: ["Y", "N"]}), "문의 Flag", "질문형 VoC 비율");
  h += "</div>";

  // ─── Scope 제외 사유 — 원본 overview.py:352-380 (2026-10-23 에 넣었다) ──────────
  //   ★ 전에는 **통째로 없었다.** 「분석에서 빠진 것」 을 볼 자리가 화면에 아예 없었다.
  //   ★ 원본 주석 — 「이 그래프는 『제외된 행』 을 센다. 그런데 위 화면에 오는 frame 에는
  //     제외행이 애초에 걸러져 없다. 그래서 무엇을 하든 0 이 나왔다」 (sky 2026-08-19).
  //     그래서 **제외 전 자료**(제품군·브랜드·국가만 걸린 것)로 센다.
  var 제외들 = 제외사유셈(scopeSource || []);
  var 제외합 = 제외들.reduce(function (a, b) { return a + b[1]; }, 0);
  h += sectionTitle("Scope 제외 사유",
    "분석에서 빠진 " + num(제외합) + "건이 왜 빠졌는지 봅니다  ·  제품군·브랜드·국가 필터만 반영합니다");
  h += '<p class="sub">★ confidence 필터와 영역 필터는 일부러 걸지 않습니다. ' +
    "제외행은 본래 신뢰도가 낮고(513건 중 424건이 Low) 영역이 「미판정」이라, " +
    "그 조건을 걸면 거의 다 사라져 왜 빠졌는지를 볼 수 없습니다.</p>";
  h += barChart(제외들, "Scope 제외 사유별 건수", "건수 0 인 사유도 함께 둡니다");

  // ─── 개별 VoC 개선 포인트 체크 — 원본 overview.py:381-460 ──────────────────────
  h += sectionTitle("개별 VoC 개선 포인트 체크",
    "행을 고르면 그 VoC 의 요약문과 RootCause 를 아래에서 읽습니다");
  // ★ L 등급 거르개 — 원본과 같이 **건수가 있는 등급만** 보기에 둔다
  var 등급셈 = {"": 0};
  GRADE_CODES.forEach(function (c) { 등급셈[c] = 0; });
  rows.forEach(function (r) { var c = 등급코드(r); 등급셈[c] = (등급셈[c] || 0) + 1; });
  var 등급보기 = GRADE_CODES.filter(function (c) { return 등급셈[c]; })
    .map(function (c) { return [c, c + " (" + 등급셈[c] + ")"]; });
  if (등급셈[""]) 등급보기.push(["", "등급 없음 (" + 등급셈[""] + ")"]);
  var 고른등급 = window.__grades || [];
  var 분리만 = !!window.__splitOnly;
  h += '<div class="d60-axis"><b>RootCause 등급으로 거르기</b> ';
  등급보기.forEach(function (q) {
    h += ' <label title="' + esc(GRADE_NOTE[q[0]] || "등급 없음") + '">' +
      '<input type="checkbox" data-grade="' + esc(q[0]) + '"' +
      (고른등급.indexOf(q[0]) >= 0 ? " checked" : "") + "> " + esc(q[1]) + "</label>";
  });
  h += ' <span class="d60-note">L3 문제·대상·원인이 모두 원문에 있다  ·  L2 원인 서술만 없다  ·  ' +
    'L1 개선 대상이 없다  ·  L0 원문에 결핍 서술이 없다. 비워 두면 전부 봅니다.</span></div>';
  // D-5 — 2차가 나눈 행만 골라 보기 (원본 checkbox)
  h += '<div class="d60-axis"><label><input type="checkbox" id="splitOnly"' +
    (분리만 ? " checked" : "") + "> 2차 분리 행만 보기 (" + num(split) + "건)</label>" +
    ' <span class="d60-note">한 댓글에 주제가 여럿이라 2차에서 나눈 행입니다. ' +
    '원행은 RootCause 상세에 나옵니다.</span></div>';
  var 표행 = 분리만 ? rows.filter(분리행인가) : rows;
  if (고른등급.length) {
    표행 = 표행.filter(function (r) { return 고른등급.indexOf(등급코드(r)) >= 0; });
  }
  if (고른등급.length || 분리만) {
    h += '<p class="sub">' + num(표행.length) + "행 / 전체 " + num(rows.length) + "행</p>";
  }
  window.__vocTableRows = 표행;
  var 칸들 = 현황표칸();
  h += table(칸들, 표행.map(function (r) {
    return 칸들.map(function (c) {
      return c === "2차분리" ? (분리행인가(r) ? "Y" : "") : txt(r[c]);
    });
  }), "t-voc", true, "rowDetail");
  // D-3 — 고른 행을 영역 → 주제 → 요약문 → 근본원인 순으로 읽게 한다
  h += '<div class="d60-mini-card">' + sectionTitle("RootCause 상세", "고른 행의 요약문과 문제·대상·원인") +
    '<div id="rowDetail">' + renderRowDetail(표행, S.detail) + "</div></div>";
  return h;
}

// ★ 원본 data_contract.scope_exclusion_reason_distribution —
//   「일곱 가지를 **건수 0 이어도 다 낸다**. 빠진 분류가 보이도록」.
//   등록되지 않은 사유가 자료에 있으면 「미등록/확인 필요」 로 뒤에 붙인다.
function 제외사유셈(scopeRows) {
  var 사유들 = K.제외사유 || [], 이름 = K.제외사유이름 || {};
  var 센것 = {};
  scopeRows.forEach(function (r) {
    if (txt(r.status) !== "scope_excluded") return;
    var v = txt(r.scope_exclusion_reason);
    센것[v] = (센것[v] || 0) + 1;
  });
  var 낸것 = 사유들.map(function (k) { return [이름[k] || k, 센것[k] || 0]; });
  Object.keys(센것).sort().forEach(function (k) {
    if (k && 사유들.indexOf(k) < 0) 낸것.push(["미등록/확인 필요: " + k, 센것[k]]);
  });
  return 낸것;
}

// ★ 원본 _render_row_detail — 「고른 행을 4층 구조로 읽게 한다 (D-3).
//   영역 → 주제 → 요약문 → 근본원인. sky 가 정한 층이다 (CP-23)」
function renderRowDetail(목록, ri) {
  if (ri === null || ri === undefined || ri < 0 || ri >= 목록.length) {
    return '<p class="sub">위 표에서 행을 하나 고르면 그 VoC 의 요약문과 RootCause 를 ' +
      "여기서 읽습니다.</p>";
  }
  var r = 목록[ri];
  var 머리 = [txt(r.product_category), txt(r.topic_group), txt(r.topic)]
    .filter(function (v) { return v; }).join(" · ");
  var h = "<h3>" + esc(머리 || "(라벨 없음)") + "</h3>";
  // D-5 — 나뉜 행이면 원행과의 관계를 알려준다
  var 원행 = txt(r.split_origin_atomic_id), 분리말 = "";
  if (원행 && 원행 !== "nan" && 원행 !== "None" && 원행 !== "N/A") {
    var 형제 = 목록.filter(function (x) {
      return txt(x.split_origin_atomic_id) === 원행; }).length;
    분리말 = "2차 분리 · 원행 " + 원행 + (형제 > 1 ? " · 형제 " + 형제 + "개" : "");
  }
  var 쪽말 = [GRADE_NOTE[등급코드(r)] || "", 분리말, txt(r.decided_by)]
    .filter(function (v) { return v; });
  if (쪽말.length) h += '<p class="sub">' + esc(쪽말.join("  ·  ")) + "</p>";
  // ★ 「요약문」 이라는 말을 박스 안에 넣는다. 밖에 두면 무엇의 제목인지 흐리다 (원본 · sky)
  h += '<div class="d60-preview"><b>요약문</b><br>' +
    esc(txt(r.atomic_voc_summary) || "비어 있습니다.") + "</div>";
  // ★ 원본 주석 — 「데이터사전 정의 그대로 쓴다. 내가 지어낸 『무엇이/어디가/왜』 는
  //   실제 내용과 어긋났다」 (sky 2026-08-19). 이름과 **순서**가 뜻이다.
  var 셋 = [["문제 현상", txt(r.rootcause_problem)], ["개선 대상", txt(r.rootcause_target)],
           ["근본 원인", txt(r.rootcause_cause)]];
  h += "<hr>";
  if (셋.some(function (q) { return q[1]; })) {
    h += '<div class="row">' + 셋.map(function (q) {
      return '<div class="d60-mini-card"><p><b>' + esc(q[0]) + "</b></p><p>" +
        esc(q[1] || "—") + "</p></div>";
    }).join("") + "</div>";
  } else {
    h += '<p class="sub">이 행에는 RootCause 가 채워져 있지 않습니다.</p>';
  }
  h += "<details><summary>원문 보기</summary>";
  // D-7 — 어떤 영상 밑에 달린 말인지. 댓글만 보면 맥락을 모른다 (원본 · sky 2026-08-19)
  var 제목 = txt(r.video_title), 설명 = txt(r.video_description);
  if (제목 || 설명) {
    h += "<p><b>어떤 영상 밑의 말인가</b></p>";
    if (제목) h += "<p>" + esc(제목) + "</p>";
    if (설명) h += '<p class="sub">' + esc(설명.slice(0, 200)) + "</p>";
  }
  var 조각 = txt(r.atomic_voc), 원문 = txt(r.original_voc);
  if (조각 && 조각 !== 원문) h += "<p><b>분리된 조각</b></p><p>" + esc(조각) + "</p>";
  h += "<p><b>원문</b></p><p>" + esc(원문 || "—") + "</p>";
  h += "</details>";
  return h;
}


// ─────────────────────────────────────────────────────────────────────────
// 개선과제 점수 — 원본 scoring.py 를 **공식까지 그대로** 옮겼다 (2026-10-21 정정)
//   ★ 전에는 sentiment_dir=="부정" 을 세고 건수 순으로 줄을 세웠다. 전부 틀렸다.
//     Codex 교차점검 — 엔진 8군집 vs 내 9 · 「제조사 신뢰/품질」 엔진 5건 vs 내 9건.
//   원본 (scoring.py:14-15, 39-160)
//     대상 행 : status != "scope_excluded" AND topic ∉ {"", "N/A", "미분류"}
//               AND entity_role ∈ {"product_brand", "unknown"}   (빈값은 unknown 으로 본다)
//     부정 강도 = min(tee_emotion_score, tee_success_score, 0)   ← 감성 라벨이 아니다
//     priority_score = |mean_neg| × neg_count
//     정렬 = priority_score ↓ · rc_coverage ↓ · n ↓
//     두 축 = volume(neg_count) · severity(부정 행만의 |평균|) · combined = 두 순위의 합
// ─────────────────────────────────────────────────────────────────────────
var EXCLUDED_TOPICS = ["", "N/A", "미분류"];
var IMPROVEMENT_ROLES = ["product_brand", "unknown"];

function numOr(v, d) { var x = parseFloat(v); return isNaN(x) ? d : x; }

function improvementTasks(rows, includeCompetitors) {
  // ★ 원본 _eligible_rows
  var eligible = rows.filter(function (r) {
    if (txt(r.status) === "scope_excluded") return false;
    if (EXCLUDED_TOPICS.indexOf(txt(r.topic)) >= 0) return false;
    if (!includeCompetitors) {
      var role = txt(r.entity_role) || "unknown";
      if (IMPROVEMENT_ROLES.indexOf(role) < 0) return false;
    }
    return true;
  });
  if (!eligible.length) return [];
  // ★ 원본 _negative_intensity — min(감정, 성공, 0)
  eligible.forEach(function (r) {
    r.__neg = Math.min(numOr(r.tee_emotion_score, 0), numOr(r.tee_success_score, 0), 0);
    r.__rc = ["", "N/A"].indexOf(txt(r.rootcause_problem)) < 0;
  });
  var g = {};
  eligible.forEach(function (r) {
    var k = txt(r.product_category) + "\u0001" + txt(r.topic);
    if (!g[k]) g[k] = {pc: txt(r.product_category), topic: txt(r.topic), rows: []};
    g[k].rows.push(r);
  });
  var out = Object.keys(g).map(function (k) {
    var o = g[k], rs = o.rows, n = rs.length;
    var negs = rs.map(function (r) { return r.__neg; });
    var deep = negs.filter(function (v) { return v < 0; });
    var mean = negs.reduce(function (a, b) { return a + b; }, 0) / n;
    var sev = deep.length ? Math.abs(deep.reduce(function (a, b) { return a + b; }, 0) / deep.length) : 0;
    var worst = Math.abs(Math.min.apply(null, negs.concat([0])));
    var rc = rs.filter(function (r) { return r.__rc; }).length / n;
    return {pc: o.pc, topic: o.topic, n: n, neg_count: deep.length,
            neg_ratio: deep.length / n, mean_neg: mean, rc_coverage: rc,
            priority_score: Math.abs(mean) * deep.length,
            volume_score: deep.length,
            severity_score: Math.round(sev * 1000) / 1000,
            worst_score: Math.round(worst * 1000) / 1000};
  });
  // 두 축 순위 — 원본과 같이 (점수 ↓, n ↓) 안정 정렬
  [["volume_score", "volume_rank"], ["severity_score", "severity_rank"]].forEach(function (p) {
    out.map(function (x, i) { return [x, i]; })
      .sort(function (a, b) {
        return (b[0][p[0]] - a[0][p[0]]) || (b[0].n - a[0].n) || (a[1] - b[1]);
      })
      .forEach(function (pair, i) { pair[0][p[1]] = i + 1; });
  });
  out.forEach(function (x) {
    x.combined_rank = x.volume_rank + x.severity_rank;
    var ax = [];
    if (x.volume_rank <= 20) ax.push("건수");
    if (x.severity_rank <= 20 && x.neg_count >= 1) ax.push("심각도");
    x.watch_axis = ax.join(" · ");
  });
  // 원본 정렬 — priority_score ↓ · rc_coverage ↓ · n ↓ (안정)
  return out.map(function (x, i) { return [x, i]; })
    .sort(function (a, b) {
      return (b[0].priority_score - a[0].priority_score) ||
             (b[0].rc_coverage - a[0].rc_coverage) ||
             (b[0].n - a[0].n) || (a[1] - b[1]);
    })
    .map(function (pair) { return pair[0]; });
}

// ★ 정렬 축 넷 — 원본 views/improvement.py:33 SORT_AXES 를 그대로 옮겼다 (이름·순서·설명까지).
//   우리가 지어내면 「건수축/심각도축」 같은 말이 원본과 달라진다.
var SORT_AXES = [
  ["우선순위 점수 (기존)", ["priority_score", "rc_coverage", "n"], [0, 0, 0],
   "|평균 부정강도| x 부정 건수 → RC커버리지 → 볼륨"],
  ["종합 (두 축 순위합)", ["combined_rank", "priority_score"], [1, 0],
   "건수축 순위 + 심각도축 순위가 작은 것부터. 두 축 모두에서 위쪽인 것이 앞에 온다"],
  ["건수축", ["volume_rank"], [1],
   "부정 건수가 많은 것부터. 넓게 퍼진 문제"],
  ["심각도축", ["severity_rank"], [1],
   "화난 사람의 평균 강도가 큰 것부터. 건수를 보지 않는다 — 깊게 아픈 문제"]
];

// ★ 원본 scoring.top_negative_vocs — 군집의 대표 **부정** VoC.
//   부정강도 오름차순(= 더 화난 것 먼저) · rootcause_problem 내림차순 · 같은 말은 한 번만.
function topNegativeVocs(rows, pc, topic, k) {
  var sub = rows.filter(function (r) {
    if (txt(r.status) === "scope_excluded") return false;
    if (EXCLUDED_TOPICS.indexOf(txt(r.topic)) >= 0) return false;
    var role = txt(r.entity_role) || "unknown";
    if (IMPROVEMENT_ROLES.indexOf(role) < 0) return false;
    return txt(r.product_category) === txt(pc) && txt(r.topic) === txt(topic);
  });
  sub.forEach(function (r) {
    r.__neg = Math.min(numOr(r.tee_emotion_score, 0), numOr(r.tee_success_score, 0), 0);
  });
  sub = sub.map(function (x, i) { return [x, i]; })
    .sort(function (a, b) {
      return (a[0].__neg - b[0].__neg) ||
             txt(b[0].rootcause_problem).localeCompare(txt(a[0].rootcause_problem), "ko") ||
             (a[1] - b[1]);
    })
    .map(function (pair) { return pair[0]; });
  // ★ 원본 _representative_key — 같은 말을 두 번 보여 주지 않는다
  var seen = {}, out = [];
  for (var i = 0; i < sub.length && out.length < (k || 3); i++) {
    var key = txt(sub[i].atomic_voc) || txt(sub[i].original_voc);
    if (seen[key]) continue;
    seen[key] = 1;
    out.push(sub[i]);
  }
  return out;
}

// ★ 원본 ui_cards.badge — 톤 이름까지 그대로. 없어서 개선 방향성 화면이 터졌다 (2026-10-23).
//   「있겠지」 하고 부른 내 잘못이다. 원본에 있는 것은 원본대로 옮긴다.
var BADGE_TONE = {"긍정": "positive", "부정": "negative", "중립": "neutral",
                  warning: "warning", negative: "negative", positive: "positive",
                  neutral: "neutral"};
function badge(label, tone) {
  return '<span class="d60-badge ' + (BADGE_TONE[tone] || "neutral") + '">' + esc(label) + "</span>";
}

// ★ 원본 views/improvement.py:_score_badges — 배지 일곱. 글귀·자릿수까지 그대로.
function scoreBadges(x) {
  return [
    badge("볼륨 " + num(x.n) + "건"),
    badge("부정 " + num(x.neg_count) + "건", x.neg_count ? "negative" : "neutral"),
    badge("부정률 " + (x.neg_ratio * 100).toFixed(1) + "%", x.neg_ratio ? "negative" : "neutral"),
    badge("평균 부정강도 " + x.mean_neg.toFixed(2), x.mean_neg < 0 ? "negative" : "neutral"),
    badge("RC 커버리지 " + (x.rc_coverage * 100).toFixed(1) + "%"),
    badge("우선점수 " + x.priority_score.toFixed(2), "warning"),
    badge("건수축 " + x.volume_rank + "위 · 심각도축 " + x.severity_rank + "위 · 종합 " + x.combined_rank,
          "neutral")
  ].join("");
}

// ★ 원본 ui_cards.task_card_html — 클래스를 그대로 써야 원본 CSS 가 먹는다
function taskCard(title, badgesHtml, preview, tone, previewHtml) {
  // ★ 원본 ui_cards.TONE_CLASS — 여섯 가지 그대로
  var TONE = {blue: "tone-blue", green: "tone-green", orange: "tone-orange",
              purple: "tone-purple", red: "tone-red", gray: "tone-gray"};
  var cls = TONE[tone] || TONE.blue;
  return '<div class="d60-task-card ' + cls + '">' +
    '<div class="d60-task-title">' + esc(title) + "</div>" +
    '<div class="d60-task-meta">' + badgesHtml + "</div>" +
    // ★ previewHtml 은 「이미 짜 놓은 HTML 을 그대로 넣는 자리」 다 (원본 preview_html).
    //   부르는 쪽에서 값을 직접 escape 해서 넘긴다. ② 영상 카드의 파란 박스가 쓴다.
    (previewHtml ? previewHtml
     : preview ? '<div class="d60-preview">' + esc(preview) + "</div>" : "") +
    "</div>";
}

// ─────────────────────────────────────────────────────────────────────────
// 화면 ② 개선 방향성 — 원본 views/improvement.py 를 구조째 옮겼다
//   ★ 2026-10-23 다시 썼다. 전에는 지표 카드 3 + 막대 둘 + 표였는데, 원본은
//     **정렬 축 라디오 4 · 먼저 볼 것 Top 3 카드 · 개선과제 후보 카드 10 · 대표 부정 VoC** 다.
//   ★ 「AI 서술 생성」 토글은 **넣지 않는다** — LLM 을 부르므로 서버가 있어야 한다.
//     원본도 기본 OFF 이고, 켜도 L1 점수와 순위는 바뀌지 않는다고 적혀 있다.
// ─────────────────────────────────────────────────────────────────────────
function viewImprovement(rows) {
  var h = "<h2>개선 방향성</h2>";
  h += '<p class="sub">L1 결정론 스코어링입니다. 군집은 product_category × topic, ' +
    "우선순위는 |평균 부정강도| × 부정 건수이며 LLM 호출 없이 계산됩니다.</p>";
  h += '<p class="sub">RC 커버리지 = 군집 VoC 중 Root Cause가 정의된 비율입니다. ' +
    "높을수록 원인/대상이 드러나 실행 가능한 개선과제로 전환하기 쉽다는 뜻입니다.</p>";
  var list = improvementTasks(rows);
  if (!list.length) return h + '<p class="empty">현재 필터 조건에서 개선과제 후보 군집이 없습니다.</p>';

  // 정렬 축 — 고른 것을 기억한다 (원본은 session_state 로 기억한다)
  var axIdx = window.__improveAxis || 0;
  h += '<div class="d60-axis"><b>정렬 축</b> ';
  SORT_AXES.forEach(function (a, i) {
    h += '<label><input type="radio" name="improveAxis" value="' + i + '"' +
      (i === axIdx ? " checked" : "") + "> " + esc(a[0]) + "</label>";
  });
  h += "</div>";
  var ax = SORT_AXES[axIdx];
  h += '<p class="sub">정렬: ' + esc(ax[0]) + " — " + esc(ax[3]) + "</p>";

  // ★ 원본과 같은 다중 키 정렬 (오름/내림을 축마다 따로 준다 · 안정 정렬)
  var sorted = list.map(function (x, i) { return [x, i]; }).sort(function (a, b) {
    for (var k = 0; k < ax[1].length; k++) {
      var c = ax[1][k], asc = ax[2][k];
      var d = (a[0][c] - b[0][c]) * (asc ? 1 : -1);
      if (d) return d;
    }
    return a[1] - b[1];
  }).map(function (p) { return p[0]; });

  h += sectionTitle("먼저 볼 것 Top 3", ax[3]);
  h += '<div class="d60-top3">';
  sorted.slice(0, 3).forEach(function (x, i) {
    var ex = topNegativeVocs(rows, x.pc, x.topic, 1);
    h += taskCard("#" + (i + 1) + " " + x.pc + " × " + x.topic, scoreBadges(x),
                  ex.length ? txt(ex[0].original_voc) : "",
                  i === 0 ? "red" : i === 1 ? "orange" : "purple");
  });
  h += "</div>";

  h += sectionTitle("개선과제 후보 카드", "상위 10개 · 대표 부정 VoC preview");
  sorted.slice(0, 10).forEach(function (x, rank) {
    var ex = topNegativeVocs(rows, x.pc, x.topic, 3);
    h += '<div class="d60-mini-card">';
    h += taskCard("#" + (rank + 1) + " " + x.pc + " × " + x.topic, scoreBadges(x),
                  ex.length ? txt(ex[0].original_voc) : "대표 부정 VoC 없음",
                  rank < 3 ? "red" : "blue");
    // D-4 — 카드 겉면에 「무엇을 고칠까」 를 한 줄 (라벨과 건수만 보이면 현업이 못 움직인다 · sky)
    var head = ex.length ? txt(ex[0].rootcause_problem) : "";
    h += head ? "<p><b>고칠 것</b> &nbsp; " + esc(head) + "</p>"
              : '<p class="sub">이 묶음의 대표 VoC 에는 RootCause 가 없습니다.</p>';
    if (ex.length) {
      h += "<details><summary>대표 부정 VoC " + ex.length + "건 · 문제·대상·원인</summary>";
      ex.forEach(function (e, o) {
        if (o) h += "<hr>";
        h += '<p class="sub">대표 VoC ' + (o + 1) + " · 부정강도 " + (e.__neg || 0).toFixed(1) + "</p>";
        [["문제", "rootcause_problem"], ["대상", "rootcause_target"], ["원인", "rootcause_cause"]]
          .forEach(function (q) {
            var v = txt(e[q[1]]);
            if (v) h += "<p><b>" + q[0] + "</b> &nbsp; " + esc(v) + "</p>";
          });
        h += '<div class="d60-preview">' + esc(txt(e.original_voc)) + "</div>";
      });
      h += "</details>";
    }
    h += "</div>";
  });

  h += sectionTitle("전체 개선과제 후보",
                    list.length + "개 · 내려받아서 봅니다 (화면 카드는 상위 10개)");
  h += '<p class="sub">지금 정렬축 「' + esc(ax[0]) + '」 기준입니다. ' +
    "<b>정렬축을 바꾸면 Top 10 도 바뀝니다.</b> 사이드바 필터도 그대로 반영됩니다.</p>";
  h += table(["제품군", "topic", "n", "부정 건수", "부정 비율", "평균 부정강도", "RC 커버리지",
              "우선순위 점수", "건수 순위", "심각도 순위", "종합", "봐야 할 축"],
             sorted.map(function (x) {
               return [x.pc, x.topic, num(x.n), num(x.neg_count),
                       (x.neg_ratio * 100).toFixed(1) + "%", x.mean_neg.toFixed(3),
                       (x.rc_coverage * 100).toFixed(1) + "%", x.priority_score.toFixed(3),
                       x.volume_rank, x.severity_rank, x.combined_rank, x.watch_axis];
             }), "t-improve");
  h += '<p class="sub"><button class="dl" data-dl="t-improve" data-name="개선과제후보">' +
    "⬇  전체 개선과제 후보 " + list.length + "개 내려받기 (CSV)</button>" +
    " — 건수가 적다고 목록에서 내리지 않습니다. 순서만 달라집니다.</p>";
  return h;
}

// ─────────────────────────────────────────────────────────────────────────
// 화면 ③ 문의 속 니즈 — 원본 views/inquiry.py 를 구조째 옮겼다
//   ★ 2026-10-23 다시 썼다. 전에는 지표 카드 3 + 막대 2 + 네 칸 표였는데, 원본은
//     **카드 정렬 기준 · 표시 개수 · 대표 문의 카드 · 문의 유형 거르개 ·
//       열한 칸 표 · 행 고르면 문의 상세** 까지 있다.
// ─────────────────────────────────────────────────────────────────────────

// ★ 원본 inquiry.py:44 INQUIRY_CARD_SORTS — 이름·순서·정렬 칸까지 그대로.
//   원본 주석 — 「전에는 정렬이 아예 없었다 … 기준을 새로 지어내지 않고, 대시보드가
//   대표 VoC 를 고를 때 이미 쓰는 축(review_queue·topic_score)을 그대로 가져왔다」 (sky 2026-08-20)
var INQUIRY_CARD_SORTS = [
  ["우선 검토 순", ["review_queue", "topic_score"]],
  ["VoC 총점 높은 순", ["voc_total_score", "topic_score"]],
  ["Topic 점수 높은 순", ["topic_score", "voc_total_score"]]
];
var INQUIRY_CARD_COUNTS = ["6", "12", "20", "전체"];
// 원본 INQUIRY_TABLE_COLUMNS · INQUIRY_TABLE_HEADERS — 열한 칸, 순서까지 그대로.
//   ★ 원본 주석 — 「주제를 왼쪽으로 올리고 식별자는 맨 뒤로 보낸다」 (sky 2026-08-20)
//   ★ `원문` 칸은 **공유용에서는 비어 있다** — `original_voc` 는 공유용에서 빼는 칸이다
//     (`자료_담기.py` 의 `공유용_빼는칸`). 꼬리말이 무엇을 뺐는지 적는다.
var INQUIRY_TABLE = [
  ["문의 유형", "inquiry_type", "문의유형이름"], ["니즈 신호 유형", "need_signal_type", "니즈신호이름"],
  ["Atomic 요약", "atomic_voc_summary", null], ["제품군", "product_category", null],
  ["이유 Topic", "topic", null], ["CEJ", "cej", null], ["감성", "sentiment_dir", null],
  ["신뢰도", "confidence_rating", null], ["사람검토", "review_required", null],
  ["원문", "original_voc", null], ["source_id", "source_id", null]
];

function 문의유형표시(r) {
  return (K.문의유형이름 && K.문의유형이름[txt(r.inquiry_type)]) || txt(r.inquiry_type) || "해당없음";
}

// ★ 원본 _render_inquiry_detail — 「원문은 표 안에서 못 읽는다. 가로로 긴 칸이기 때문이다」
function renderInquiryDetail(목록, i) {
  if (i === null || i === undefined || i < 0 || i >= 목록.length) {
    return '<p class="sub">위 표에서 행을 하나 고르면 그 문의의 원문과 판정 근거를 여기서 읽습니다.</p>';
  }
  var r = 목록[i];
  var h = "<h3>" + esc(txt(r.topic) || "Topic 미확인") + "</h3>";
  h += '<p class="sub">' + esc(txt(r.product_category) || "제품군 미확인") + " · " +
    esc(txt(r.cej) || "CEJ 미확인") + " · 신뢰도 " +
    esc(txt(r.confidence_rating) || "미확인") + "</p>";
  var 요약 = txt(r.atomic_voc_summary);
  if (요약) h += '<div class="d60-preview">' + esc(요약) + "</div>";
  h += "<hr>";
  h += '<div class="row"><div class="d60-mini-card"><p><b>문의 유형</b></p><p>' +
    esc(문의유형표시(r)) + "</p></div>";
  h += '<div class="d60-mini-card"><p><b>니즈 신호 유형</b></p><p>' +
    esc((K.니즈신호이름 && K.니즈신호이름[txt(r.need_signal_type)]) ||
        txt(r.need_signal_type) || "해당없음") + "</p></div></div>";
  h += "<details><summary>원문 보기</summary><p>" +
    esc(txt(r.original_voc) || "원문이 없습니다.") + "</p></details>";
  return h;
}

function viewInquiry(rows) {
  var total = rows.length;
  var inq = rows.filter(function (r) { return txt(r.inquiry_flag).toUpperCase() === "Y"; });
  var h = "<h2>문의 속 니즈</h2><p class=\"sub\">질문형 VoC 만 골라 봅니다. 문의율은 감성과 " +
    "<b>별도 축</b>입니다 — 부정적인 문의도 있습니다.</p>";
  h += cardGrid([
    card("문의형 VoC", num(inq.length), pct(inq.length, total), "purple"),
    card("문의 제품군 수", num(uniq(inq, "product_category")), "product_category", "blue"),
    card("문의 Topic 수", num(uniq(inq, "topic")), "reason topic", "green")
  ]);
  if (!inq.length) return h + '<p class="empty">현재 필터 조건에서 문의형 VoC가 없습니다.</p>';
  // ★ 2026-10-22 Codex 교차점검 — 원본의 **핵심 두 분포를 다른 것으로 바꿔** 놓았다.
  //   원본(inquiry.py:167-204)이 그리는 둘은 「문의 유형」 과 「니즈 신호 유형」 이고,
  //   둘 다 **원시 코드값을 한국어 표시값으로 바꾼 뒤** 센다 (`_display_label`).
  //   내 것은 「문의 Topic 분포」·「문의의 CEJ」 를 그리고 원시 `inquiry_type` 막대를
  //   하나 더 붙였을 뿐, `need_signal_type` 분포는 **아예 없었다.**
  //   표시값 사전은 엔진의 `inquiry_labels.py` 에서 실어 온다 (베끼지 않는다).
  h += '<div class="row">';
  h += barChart(countByLabel(inq, "inquiry_type", K.문의유형이름),
                "문의 유형", "문의 목적별 분포");
  h += barChart(countByLabel(inq, "need_signal_type", K.니즈신호이름),
                "니즈 신호 유형", "고객이 원하는 것의 유형");
  h += "</div>";

  // ─── 대표 문의 카드 — 원본 inquiry.py:207-262 ──────────────────────────────
  var sIdx = window.__inqSort || 0, cIdx = window.__inqCount || 0;
  h += '<div class="d60-axis"><b>카드 정렬 기준</b> <select id="inqSort">';
  INQUIRY_CARD_SORTS.forEach(function (a, i) {
    h += '<option value="' + i + '"' + (i === sIdx ? " selected" : "") + ">" + esc(a[0]) + "</option>";
  });
  h += '</select> &nbsp; <b>표시 개수</b> <select id="inqCount">';
  INQUIRY_CARD_COUNTS.forEach(function (c, i) {
    h += '<option value="' + i + '"' + (i === cIdx ? " selected" : "") + ">" + esc(c) + "</option>";
  });
  h += "</select></div>";
  // ★ 원본은 `ascending=False` — 두 칸 **모두 내림차순**, 안정 정렬 (pandas 기본)
  var 정렬칸 = INQUIRY_CARD_SORTS[sIdx][1];
  var ordered = inq.map(function (x, i) { return [x, i]; }).sort(function (a, b) {
    for (var k = 0; k < 정렬칸.length; k++) {
      var c = 정렬칸[k];
      var d = numOr(b[0][c] === true ? 1 : b[0][c] === false ? 0 : b[0][c], 0) -
              numOr(a[0][c] === true ? 1 : a[0][c] === false ? 0 : a[0][c], 0);
      if (d) return d;
    }
    return a[1] - b[1];
  }).map(function (p) { return p[0]; });
  var 개수 = INQUIRY_CARD_COUNTS[cIdx];
  var preview = 개수 === "전체" ? ordered : ordered.slice(0, parseInt(개수, 10));
  h += sectionTitle("대표 문의 카드",
    INQUIRY_CARD_SORTS[sIdx][0] + " · " + preview.length + "개 표시 / 문의형 전체 " +
    inq.length + "건 · 카드 하나가 VoC 「한 건」 이다 (같은 주제를 묶은 것이 아님)");
  h += '<div class="d60-card2">';
  preview.forEach(function (r) {
    h += taskCard(txt(r.topic) || "N/A",
      badge(txt(r.product_category) || "제품군 미확인") +
      badge(txt(r.cej) || "CEJ 미확인") +
      badge(txt(r.confidence_rating) || "confidence 미확인"),
      txt(r.atomic_voc_summary) || txt(r.original_voc) || "", "purple");
  });
  h += "</div>";

  // ─── 문의형 VoC 체크 — 원본 inquiry.py:264-303 ─────────────────────────────
  h += sectionTitle("문의형 VoC 체크",
    "행을 고르면 그 문의의 원문과 판정 근거를 아래에서 읽습니다 · 위 카드는 고른 기준으로 " +
    "몇 건만, 이 표는 " + inq.length + "건 전부");
  var 유형들 = [];
  inq.forEach(function (r) {
    var v = 문의유형표시(r);
    if (유형들.indexOf(v) < 0) 유형들.push(v);
  });
  유형들.sort(function (a, b) { return a.localeCompare(b, "ko"); });
  var 고른유형 = window.__inqTypes || [];
  h += '<div class="d60-axis"><b>문의 유형으로 거르기</b> ';
  유형들.forEach(function (v) {
    h += ' <label><input type="checkbox" data-inqtype="' + esc(v) + '"' +
      (고른유형.indexOf(v) >= 0 ? " checked" : "") + "> " + esc(v) + "</label>";
  });
  h += ' <span class="d60-note">비워 두면 전부 봅니다.</span></div>';
  var 표행 = 고른유형.length
    ? inq.filter(function (r) { return 고른유형.indexOf(문의유형표시(r)) >= 0; })
    : inq;
  if (고른유형.length) {
    h += '<p class="sub">' + num(표행.length) + "건 / 문의형 전체 " + num(inq.length) + "건</p>";
  }
  // ★ 고른 행을 다시 그릴 때 쓴다 — 거르개·정렬을 바꾸면 자리 번호의 뜻이 달라지므로 비운다
  window.__inqTableRows = 표행;
  h += table(INQUIRY_TABLE.map(function (c) { return c[0]; }),
             표행.map(function (r) {
               return INQUIRY_TABLE.map(function (c) {
                 if (c[2]) return (K[c[2]] && K[c[2]][txt(r[c[1]])]) || txt(r[c[1]]) || "해당없음";
                 return txt(r[c[1]]);
               });
             }), "t-inq", true, "inqDetail");
  // ★ 원본 render_table_download 의 글귀 그대로. 「화면에서 숨긴 칸도」 한 마디는 **뺀다** —
  //   우리 표에는 칸 숨기기가 없다 (Streamlit 전용 고르개였다).
  h += '<p class="sub"><button class="dl" data-dl="t-inq" data-name="문의형VoC">' +
    "⬇ 문의형 VoC 통째로 받기 (" + num(표행.length) + "행 · " + INQUIRY_TABLE.length +
    "칸)</button> — 지금 걸린 사이드바 필터와 「문의 유형으로 거르기」 가 그대로 반영됩니다. " +
    "사용자명·이메일·링크는 가려진 판본입니다.</p>";
  h += '<div class="d60-mini-card">' + sectionTitle("문의 상세", "고른 행의 원문과 판정 근거") +
    '<div id="inqDetail">' + renderInquiryDetail(표행, window.__inqDetail) + "</div></div>";
  return h;
}

// ─────────────────────────────────────────────────────────────────────────
// 화면 ④ PL Issue — 원본 views/pl_issue.py 를 **한 줄씩 대조해** 옮겼다 (2026-10-20 정정)
//   ★ 전에는 본문을 정규식으로 뒤졌다. 틀렸다 — 원본은 **라벨 두 개로 정확히** 고른다.
//     PL_TOPICS = ("안전(화재·감전·누수)", "위생/냄새")  ← 2차 기준서 §11 과 짝
//   ★ 거르는 규칙이 세 곳(기준서 §11 · PL이슈_뽑기.py · 화면)에 있다. 넓힐 때는 셋을 함께 고친다.
// ─────────────────────────────────────────────────────────────────────────
var PL_TOPICS = ["안전(화재·감전·누수)", "위생/냄새"];
var PL_겪음 = ["사용", "관리", "교체"];
// 실무자가 보는 칸 — 89칸을 다 주면 아무도 안 본다 (원본 _보일칸 그대로 · 9개)
var PL_COLS = [["topic", "라벨"], ["product_category", "제품군"], ["atomic_voc", "무슨 말인가"],
               ["cej", "여정 단계"], ["sentiment_dir", "긍부정"], ["tee_emotion_score", "감정 강도"],
               ["rootcause_problem", "무엇이 문제인가"], ["rootcause_cause", "왜 그런가"],
               ["video_title", "영상"], ["atomic_id", "행 번호"]];

function viewPl(rows) {
  var h = sectionTitle("★ PL Issue — 안전·위생",
    "안전(화재·감전·누수) · 위생/냄새 를 건수와 무관하게 전량 봅니다. " +
    "개선우선순위 집계에서 빼지 않습니다 — 보기만 따로 둔 자리입니다.");
  // ★ 원본 _고르기 — 라벨이 둘 중 하나이고 status 가 normal 인 행
  var view = rows.filter(function (r) {
    return PL_TOPICS.indexOf(txt(r.topic)) >= 0 && txt(r.status) === "normal";
  });
  if (!view.length) {
    return h + '<p class="empty ok">지금 조건에서 안전·위생으로 잡힌 행이 없습니다.</p>';
  }
  var safe = view.filter(function (r) { return txt(r.topic) === PL_TOPICS[0]; }).length;
  h += cardGrid([
    card("전체", num(view.length), "건수로 거르지 않았습니다", "blue"),
    card("안전(화재·감전·누수)", num(safe), "화재 · 감전 · 누수 · 폭발", "orange"),
    card("위생/냄새", num(view.length - safe), "곰팡이 · 악취 · 세균", "purple")
  ]);
  // ★ 「겪은 것」 과 「써 보기 전 걱정」 을 갈라 본다 (원본 2026-08-25) —
  //   안 가르면 써 보지도 않고 하는 걱정을 겪은 사고로 읽는다
  var 겪음 = view.filter(function (r) { return PL_겪음.indexOf(txt(r.cej)) >= 0; }).length;
  h += '<p class="sub">★ <b>겪은 것 ' + num(겪음) + "건 · 써 보기 전 걱정 " +
    num(view.length - 겪음) + "건</b> — <code>cej</code> 가 사용·관리·교체면 실제로 겪은 것이고, " +
    "인지·탐색·결정이면 아직 써 보지 않은 걱정입니다. 같은 안전 이슈라도 무게가 다릅니다.</p>";
  // ★ 안전을 먼저, 그다음 감정이 센 것부터 (원본 정렬 그대로)
  var sorted = view.slice().sort(function (a, b) {
    var sa = txt(a.topic) === PL_TOPICS[0] ? 0 : 1, sb = txt(b.topic) === PL_TOPICS[0] ? 0 : 1;
    if (sa !== sb) return sa - sb;
    var ea = Math.abs(parseFloat(a.tee_emotion_score) || 0);
    var eb = Math.abs(parseFloat(b.tee_emotion_score) || 0);
    return eb - ea;
  });
  var cols = PL_COLS.filter(function (c) { return D.칸.indexOf(c[0]) >= 0; });
  h += table(cols.map(function (c) { return c[1]; }),
             sorted.map(function (r) { return cols.map(function (c) { return r[c[0]]; }); }),
             "t-pl");
  h += '<p class="sub"><button class="dl" data-dl="t-pl" data-name="PL이슈">PL Issue 통째로 받기</button>' +
    " — 안전·위생 전량입니다. 건수로 거르지 않았습니다.</p>";
  return h;
}
// ─────────────────────────────────────────────────────────────────────────
// 화면 ⑤ 분석 영상 정보 — 원본 views/video.py · data_contract.video_summary
//
// ★ 2026-10-22 Codex 교차점검으로 **세 가지를 고쳤다.** 전에는 전부 틀렸다.
//   ① 대상 행 · 묶음 키 · 분모 (data_contract.py:560-588)
//      - 유효행(`validity == "유효"`)이 하나라도 있으면 **유효행만** 쓴다. 없으면 전체.
//      - 묶음 키는 `video_id` 하나가 아니라 **video_id + video_title + video_url** 셋이다.
//        전에는 제목/URL 이 다른 행이 한 영상으로 합쳐졌다.
//      - 댓글 수는 **`source_id` 가 있는 행 수**다 (`count` 는 빈값을 안 센다).
//        비율(긍·부·문의)의 분모는 **묶음의 행 수**다 — 둘이 다르다. 원본이 그렇다.
//   ② 최소 댓글 수 5 · 기본 정렬 부정률 (video.py:249-309)
//      원본 주석: 「댓글 1~2건짜리 영상이 부정률 100% 로 카드 1위에 오고 있었다.
//      한 건으로 100% 는 비율이라 부를 수 없다. 하한을 5로 둔다.」
//      잘려 나간 것만 따로 보는 상자도 옆에 있다 — 그것까지 옮겼다.
//   ③ 비율 그림 셋 · 0~100% 고정축 (video.py:377-408)
//      원본 주석: 「축을 각자 맞추면 「문의율 50%」 와 「부정률 100%」 가 같은 길이로
//      그려져 잘못 읽힌다. 빈 자리가 곧 정보다.」
//      전에는 댓글 수 막대 하나뿐이었다 — 화면이 답하는 질문 자체가 달랐다.
// ─────────────────────────────────────────────────────────────────────────
// 묶음 키를 이을 글자 — 자료에 절대 안 나오는 것으로 쓴다 (널문자)
var SEP = String.fromCharCode(0);
var VIDEO_SORTS = {
  "부정률 높은 순": ["negative_rate", "inquiry_rate", "comment_count"],
  "문의율 높은 순": ["inquiry_rate", "negative_rate", "comment_count"],
  "댓글 많은 순": ["comment_count", "negative_rate", "inquiry_rate"]
};
var VIDEO_COUNTS = [4, 8, 12, "전체"];

// ── 영상별 집계 — 원본 data_contract.video_summary 를 그대로 ──────────────────
//   ★ 유효행만 쓴다. 비율의 분모는 묶음 행수, 댓글 수는 source_id 가 있는 행.
//   ★ 2026-10-23 더한 것 — 주요 제품군·브랜드 **쪼갠 값**(breakdown) · 제품명 보조(hint) ·
//     영상 설명·태그. 전에는 제품군 하나만 세고 나머지는 아예 없었다.
function videoSummary(rows) {
  // 유효행이 하나라도 있으면 유효행만 (원본 valid / if valid.empty: valid = frame)
  var valid = rows.filter(function (r) { return txt(r.validity) === "유효"; });
  if (!valid.length) valid = rows;
  // ★ 브랜드 칸 고르기 — 원본과 같은 순서 (brand_display 가 있으면 그것)
  var 브랜드칸 = valid.some(function (r) { return r.brand_display !== undefined; })
                ? "brand_display" : "brand";
  // 태그에서 떼어낼 브랜드 이름 — 「LG」·「LG전자」 는 제품이 아니다 (원본 brand_aliases)
  var 별칭 = {};
  valid.forEach(function (r) {
    var b = txt(r[브랜드칸]);
    if (b) { 별칭[b] = 1; 별칭[b + "전자"] = 1; 별칭[b + " 전자"] = 1; }
  });
  // 영상 맥락 — video_id 로 묶어 **처음 비어 있지 않은 값** (원본 context)
  var 맥락 = {};
  valid.forEach(function (r) {
    var v = txt(r.video_id);
    if (!맥락[v]) 맥락[v] = {video_tags: "", video_description: ""};
    ["video_tags", "video_description"].forEach(function (c) {
      if (!맥락[v][c]) 맥락[v][c] = txt(r[c]);
    });
  });
  var g = {}, 차례 = [];
  valid.forEach(function (r) {
    var k = [txt(r.video_id), txt(r.video_title), txt(r.video_url)].join(SEP);
    if (!g[k]) {
      g[k] = {video_id: txt(r.video_id), video_title: txt(r.video_title),
              video_url: txt(r.video_url), rows: 0, comment_count: 0,
              pos: 0, neg: 0, inq: 0, pc: {}};
      차례.push(k);
    }
    var o = g[k];
    o.rows += 1;                                  // 비율의 분모
    if (txt(r.source_id) !== "") o.comment_count += 1;   // 댓글 수 — source_id 가 있는 행
    if (txt(r.sentiment_dir) === "긍정") o.pos += 1;
    if (txt(r.sentiment_dir) === "부정") o.neg += 1;
    if (txt(r.inquiry_flag).toUpperCase() === "Y") o.inq += 1;
    var pc = txt(r.product_category);
    if (pc) o.pc[pc] = (o.pc[pc] || 0) + 1;
  });
  // ★ 쪼갠 값은 **video_id 로** 센다 (원본 subset = valid[video_id == …]).
  //   묶음 열쇠(제목·URL 까지)보다 넓다 — 원본이 그렇게 센다.
  function 셈(열쇠칸, 조건) {
    var m = {};
    valid.forEach(function (r) {
      if (!조건(r)) return;
      var v = txt(r[열쇠칸]);
      if (v) m[v] = (m[v] || 0) + 1;
    });
    // value_counts — 많은 순, 같으면 먼저 나온 순 (pandas 와 같다)
    var 순 = {}, i = 0;
    valid.forEach(function (r) {
      if (!조건(r)) return;
      var v = txt(r[열쇠칸]);
      if (v && 순[v] === undefined) 순[v] = i++;
    });
    return Object.keys(m).map(function (v) { return [v, m[v]]; })
      .sort(function (a, b) { return (b[1] - a[1]) || (순[a[0]] - 순[b[0]]); });
  }
  // product_tags 에서 실제 제품명만 — 원본 _product_hints
  function 제품명보조(조건) {
    var m = {};
    valid.forEach(function (r) {
      if (!조건(r)) return;
      txt(r.product_tags).split(",").forEach(function (조각) {
        var t = 조각.trim();
        if (!t || 별칭[t]) return;
        var 말들 = Object.keys(별칭);
        for (var i = 0; i < 말들.length; i++) {
          var w = 말들[i];
          if (t.indexOf(w) === 0 && t.length > w.length) { t = t.slice(w.length).trim(); break; }
        }
        if (!t || 별칭[t]) return;
        m[t] = (m[t] || 0) + 1;
      });
    });
    return Object.keys(m).sort(function (a, b) {
      return (m[b] - m[a]) || a.localeCompare(b, "ko");
    });
  }
  return 차례.map(function (k) {
    var o = g[k], d = o.rows || 1;
    o.positive_rate = o.pos / d;
    o.negative_rate = o.neg / d;
    o.inquiry_rate = o.inq / d;
    o.positive_count = o.pos;
    o.negative_count = o.neg;
    o.inquiry_count = o.inq;
    o.축이름 = o.video_title || o.video_id;
    var 같은영상 = function (r) { return txt(r.video_id) === o.video_id; };
    o.제품군쪼갬 = 셈("product_category", 같은영상);
    o.브랜드쪼갬 = 셈(브랜드칸, 같은영상);
    o.main_product_category = o.제품군쪼갬.length ? o.제품군쪼갬[0][0] : "";
    o.main_brand = o.브랜드쪼갬.length ? o.브랜드쪼갬[0][0] : "";
    // ★ 제품군이 「기타」·「미분류」·빈값일 때만 보조 이름을 붙인다 (원본과 같은 조건)
    o.제품명보조 = (["기타", "미분류", ""].indexOf(o.main_product_category) >= 0)
                 ? 제품명보조(같은영상).slice(0, 2).join(", ") : "";
    var c = 맥락[o.video_id] || {};
    o.video_tags = c.video_tags || "";
    o.video_description = c.video_description || "";
    return o;
  });
}

// ★ 원본 _pretty_name — 「화면에 데이터 값을 그대로 두지 않는다」 (sky 2026-08-20)
function 이름고치기(v) {
  var t = txt(v);
  return (t === "" || t === "N/A" || t === "nan" || t === "none" || t === "None") ? "미상" : t;
}

// ★ 원본 _subject_rows — 이 카드의 파란 박스가 몇 줄을 쓰는가 (좌우 중 많은 쪽)
function 주제줄수(o) {
  return Math.max(o.제품군쪼갬.length || 1, o.브랜드쪼갬.length || 1);
}

// ★ 원본 _subject_html — 파란 박스. 왼쪽 제품군, 오른쪽 브랜드.
//   「첫 줄이 주요, 그 아래로 나머지를 한 줄씩. 『그 외 N종』 은 무엇인지 알 수 없어 쓸모가 없었다」
function 주제박스(o, 줄수) {
  var 칸들 = [["주요 제품군", o.제품군쪼갬, true], ["주요 브랜드", o.브랜드쪼갬, false]]
    .map(function (q) {
      var 몸;
      if (!q[1].length) {
        몸 = '<div class="d60-subject-sub">판정되지 않음</div>';
      } else {
        몸 = q[1].map(function (p, i) {
          var 글 = 이름고치기(p[0]);
          if (i === 0 && q[2] && o.제품명보조) 글 += " (추정 " + o.제품명보조 + ")";
          return '<div class="' + (i === 0 ? "d60-subject-main" : "d60-subject-sub") +
            '" title="' + esc(글) + '">' + esc(글) + " " + num(p[1]) + "건</div>";
        }).join("");
      }
      return '<div class="d60-subject-col"><div class="d60-subject-label">' + esc(q[0]) +
        "</div>" + 몸 + "</div>";
    }).join("");
  // ★ 원본 셈 그대로 — 라벨 16 + 아래여백 4 + 줄 수 × 20 + 위아래 패딩 20 + 테두리 2
  var 높이 = 42 + (줄수 || 주제줄수(o)) * 20;
  return '<div class="d60-subject" style="min-height:' + 높이 + 'px">' + 칸들 + "</div>";
}

// ★ 원본 _render_video_detail — 「고른 영상 한 개를 읽을 수 있게 편다」
function renderVideoDetail(목록, i) {
  if (i === null || i === undefined || i < 0 || i >= 목록.length) {
    return '<p class="sub">위 표에서 영상을 하나 고르면 그 영상의 제품군·브랜드와 태그·설명을 ' +
      "여기서 읽습니다.</p>";
  }
  var o = 목록[i];
  var h = "<h3>" + esc(o.video_title || o.video_id || "영상 미확인") + "</h3>";
  // ★ 원본 — 「비율 옆에 건수를 같이 적는다. 카드와 같은 규칙이다」
  h += '<p class="sub">댓글 ' + num(o.comment_count) + "건 · 부정 " + num(o.negative_count) +
    "건 " + (o.negative_rate * 100).toFixed(1) + "% · 문의 " + num(o.inquiry_count) +
    "건 " + (o.inquiry_rate * 100).toFixed(1) + "% · 긍정 " + num(o.positive_count) +
    "건 " + (o.positive_rate * 100).toFixed(1) + "%</p>";
  h += 주제박스(o);
  h += "<hr>";
  h += '<div class="row"><div class="d60-mini-card"><p><b>영상 설명</b></p><p>' +
    esc(o.video_description || "기록된 설명이 없습니다.") + "</p></div>";
  h += '<div class="d60-mini-card"><p><b>태그</b></p><p>' +
    esc(o.video_tags || "기록된 태그가 없습니다.") + "</p></div></div>";
  if (o.video_url) {
    h += '<p><a class="d60-link" href="' + esc(o.video_url) + '" target="_blank" ' +
      'rel="noopener">영상 열기</a></p>';
  }
  return h;
}

// ★ 원본 views/video.py 의 `video_columns` 순서와 `VIDEO_TABLE_HEADERS` 이름 그대로 열다섯 칸.
//   원본 주석 — 「표에 쓸 한국어 칸이름. 봐야 할 것을 왼쪽에 두는 순서와 짝이다」
function _쪼갠글(쌍들) {
  // 원본 main_product_note / main_brand_note — " · " 로 이어 붙인 「이름 N건」
  return 쌍들.map(function (p) { return p[0] + " " + num(p[1]) + "건"; }).join(" · ");
}
var VIDEO_TABLE = [
  ["영상 제목", function (o) { return o.video_title; }],
  ["댓글 수", function (o) { return num(o.comment_count); }],
  ["부정 건수", function (o) { return num(o.negative_count); }],
  ["부정률", function (o) { return (o.negative_rate * 100).toFixed(1) + "%"; }],
  ["문의 건수", function (o) { return num(o.inquiry_count); }],
  ["문의율", function (o) { return (o.inquiry_rate * 100).toFixed(1) + "%"; }],
  ["긍정 건수", function (o) { return num(o.positive_count); }],
  ["긍정률", function (o) { return (o.positive_rate * 100).toFixed(1) + "%"; }],
  ["주요 제품군", function (o) { return o.main_product_category; }],
  ["추정 제품", function (o) { return o.제품명보조; }],
  ["제품군 구성", function (o) { return _쪼갠글(o.제품군쪼갬); }],
  ["주요 브랜드", function (o) { return o.main_brand; }],
  ["브랜드 구성", function (o) { return _쪼갠글(o.브랜드쪼갬); }],
  ["링크", function (o) { return o.video_url; }],
  ["영상 ID", function (o) { return o.video_id; }]
];

function sortBy(list, keys) {
  return list.slice().sort(function (a, b) {
    for (var i = 0; i < keys.length; i++) {
      var x = a[keys[i]], y = b[keys[i]];
      if (x !== y) return y - x;
    }
    return 0;
  });
}

// 0~100% 고정축 비율 그림 — 세 그림을 나란히 읽을 수 있게 (원본 scale domain [0,1])
function pctChart(list, metric, title, note) {
  if (!list.length) {
    return '<div class="d60-mini-card">' + sectionTitle(title, note) +
      '<p class="empty">이 조건에서는 담을 것이 없습니다.</p></div>';
  }
  var 줄 = sortBy(list, [metric]);
  var W = 560, NAME = 170, VAL = 56, LH = 26;
  var H = LH * 줄.length + 8, bars = "";
  줄.forEach(function (o, i) {
    var y = i * LH + 4;
    var 값 = Math.max(0, Math.min(1, o[metric] || 0));
    var 폭 = Math.max(1, Math.round((W - NAME - VAL) * 값));     // ★ 0~100% 고정
    var 이름 = o.축이름.length > 24 ? o.축이름.slice(0, 23) + "…" : o.축이름;
    bars += "<g>" +
      '<text x="' + (NAME - 8) + '" y="' + (y + 15) + '" class="bl" text-anchor="end">' +
        esc(이름) + "</text>" +
      '<rect x="' + NAME + '" y="' + (y + 4) + '" width="' + (W - NAME - VAL) +
        '" height="' + (LH - 10) + '" rx="3" fill="#E5E7EB"></rect>' +
      '<rect x="' + NAME + '" y="' + (y + 4) + '" width="' + 폭 + '" height="' + (LH - 10) +
        '" rx="3" fill="' + colorOf(o.축이름, i, null) + '"></rect>' +
      '<text x="' + (NAME + (W - NAME - VAL) + 6) + '" y="' + (y + 15) + '" class="bv">' +
        (값 * 100).toFixed(1) + "%</text></g>";
  });
  return '<div class="d60-mini-card">' + sectionTitle(title, note) +
    '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" role="img">' + bars + "</svg>" +
    '<p class="sub">축은 0~100% 로 고정입니다 — 세 그림을 나란히 읽을 수 있게. 빈 자리가 곧 정보입니다.</p>' +
    "</div>";
}

// ─────────────────────────────────────────────────────────────────────────
// 화면 ② 분석 영상 정보 — 원본 views/video.py
//   ★ 2026-10-23 카드를 다시 썼다. 전에는 제목 + 한 줄 요약이었는데, 원본은
//     **알약 배지 넷 + 주요 제품군·브랜드 파란 박스 + 「이 영상은 무엇을 다루나」
//       접이식 + 영상 열기** 이고, 카드는 **두 칸씩** 놓인다.
// ─────────────────────────────────────────────────────────────────────────
function viewVideo(rows) {
  var h = "<h2>분석 영상 정보</h2>";
  h += '<p class="sub">영상별 댓글 수, 긍정률, 부정률, 문의율과 주요 제품군·브랜드를 ' +
    "66컬럼 결과에서 집계합니다.</p>";
  h += '<p class="sub">문의율은 감성(긍정/부정/중립)과 별도 축입니다. 부정적인 문의도 ' +
    "가능하므로 긍정률+부정률+문의율 합산이 100%를 넘을 수 있습니다.</p>";
  var all = videoSummary(rows);
  // ★ 원본은 `frame['video_id'].nunique()` 다 — 카드 수(제목·URL 까지 묶은 것)가 아니다.
  //   한 video_id 에 제목이 둘이면 카드가 둘, 「영상 수」 는 하나다. 원본이 그렇게 센다.
  h += cardGrid([
    card("집계 Row", num(rows.length), "현재 필터 기준", "blue"),
    card("영상 수", num(uniq(rows, "video_id")), "video_id 기준", "green")
  ]);
  if (!all.length) return h + '<p class="empty">이 조건에서 영상 집계가 없습니다.</p>';

  // ★ 최소 댓글 수 — 기본 5 (원본 number_input value=5)
  var 얇은 = all.filter(function (o) { return o.comment_count < S.video_min; });
  h += '<div class="vopt"><label>최소 댓글 수 <input type="number" id="videoMin" min="1" value="' +
    S.video_min + '" step="1"></label>' +
    '<label class="chk"><input type="checkbox" id="videoThinOnly"' +
    (S.video_thin_only ? " checked" : "") + "> 댓글 " + S.video_min +
    "건 미만인 영상만 보기 (" + 얇은.length + "개)</label>" +
    '<p class="sub">댓글이 적으면 비율이 크게 흔들립니다. 1건 중 1건이 부정이면 부정률 100% 입니다.</p></div>';

  var summary, 알림 = "";
  if (S.video_thin_only) {
    if (!얇은.length) {
      return h + '<p class="empty">댓글 ' + S.video_min + '건 미만인 영상이 없습니다.</p>';
    }
    summary = 얇은;
    알림 = '<p class="warn">댓글 ' + S.video_min + "건 미만인 영상 " + 얇은.length +
      "개만 보고 있습니다. 표본이 적어 비율은 믿을 수 없습니다 — 내용만 참고하세요.</p>";
  } else {
    var 남은 = all.filter(function (o) { return o.comment_count >= S.video_min; });
    if (!남은.length) {
      알림 = '<p class="warn">댓글 ' + S.video_min + "건 이상인 영상이 없습니다. 값을 낮춰 주세요.</p>";
      summary = 남은;
    } else {
      summary = 남은;
      if (남은.length < all.length) {
        알림 = '<p class="sub">영상 ' + 남은.length + "개 / 전체 " + all.length +
          "개 · 댓글 " + S.video_min + "건 미만 " + 얇은.length + "개는 옆 상자로 따로 봅니다</p>";
      }
    }
  }
  h += 알림;
  if (!summary.length) return h;

  // ★ 정렬 축과 표시 개수 — 원본 selectbox 둘 (기본: 부정률 높은 순 · 4개)
  h += '<div class="vopt"><label>카드 정렬 기준 <select id="videoSort">' +
    Object.keys(VIDEO_SORTS).map(function (k) {
      return '<option' + (k === S.video_sort ? " selected" : "") + ">" + esc(k) + "</option>";
    }).join("") + "</select></label>" +
    '<label>표시 개수 <select id="videoCount">' +
    VIDEO_COUNTS.map(function (c) {
      return '<option' + (String(c) === String(S.video_count) ? " selected" : "") + ">" +
        esc(String(c)) + "</option>";
    }).join("") + "</select></label></div>";

  var 정렬된 = sortBy(summary, VIDEO_SORTS[S.video_sort] || VIDEO_SORTS["부정률 높은 순"]);
  var 상위 = String(S.video_count) === "전체" ? 정렬된
             : 정렬된.slice(0, parseInt(S.video_count, 10) || 4);

  // ★ 원본 쪽말 그대로
  h += sectionTitle("영상별 리스트 카드",
    S.video_sort + " · " + 상위.length + "개 표시 / 전체 " + summary.length +
    "개 · 카드 아래 줄은 그 영상 댓글에서 가장 많이 나온 제품군·브랜드");
  // ★ 같은 행 두 카드의 파란 박스 줄 수를 맞춘다 (원본 subject_lines · 실측 238 vs 247 어긋남)
  var 줄맞춤 = {};
  for (var s = 0; s < 상위.length; s += 2) {
    var 짝 = 상위.slice(s, s + 2);
    var 같이 = Math.max.apply(null, 짝.map(주제줄수));
    for (var t = 0; t < 짝.length; t++) 줄맞춤[s + t] = 같이;
  }
  h += '<div class="d60-card2">' + 상위.map(function (o, i) {
    // ★ 원본 tone 규칙 그대로 — 부정 30% 이상 red → 긍정 30% green → 문의 30% purple → blue
    var tone = o.negative_rate >= 0.3 ? "red" : o.positive_rate >= 0.3 ? "green"
             : o.inquiry_rate >= 0.3 ? "purple" : "blue";
    // ★ 「비율만 적으면 『부정 100%』 가 커 보이는데 실은 1건 중 1건일 수 있다.
    //   건수를 앞에 같이 적는다」 (원본 주석 · sky 2026-08-20)
    var 배지 = badge("댓글 " + num(o.comment_count) + "건") +
      badge("긍정 " + num(o.positive_count) + "건 " + (o.positive_rate * 100).toFixed(1) + "%",
            o.positive_rate ? "positive" : "neutral") +
      badge("부정 " + num(o.negative_count) + "건 " + (o.negative_rate * 100).toFixed(1) + "%",
            o.negative_rate ? "negative" : "neutral") +
      badge("문의 " + num(o.inquiry_count) + "건 " + (o.inquiry_rate * 100).toFixed(1) + "%",
            o.inquiry_rate ? "warning" : "neutral");
    var 한장 = "<div>" + taskCard(o.축이름 || "영상 미확인", 배지, "", tone, 주제박스(o, 줄맞춤[i]));
    // D-7 — 이 영상이 무엇을 다룬 영상인지. 댓글만 보면 맥락을 모른다 (원본 주석 · sky)
    //   ★ 값이 없어도 접이식을 그린다 — 안 그리면 그 칸만 짧아져 다음 줄이 위로 당겨진다
    한장 += "<details><summary>이 영상은 무엇을 다루나</summary>";
    if (o.video_description) 한장 += "<p><b>영상 설명</b></p><p>" + esc(o.video_description) + "</p>";
    if (o.video_tags) 한장 += "<p><b>태그</b></p><p>" + esc(o.video_tags) + "</p>";
    if (!o.video_description && !o.video_tags) {
      한장 += '<p class="sub">이 영상에는 기록된 설명·태그가 없습니다.</p>';
    }
    한장 += "</details>";
    if (o.video_url) {
      한장 += '<p><a class="d60-link" href="' + esc(o.video_url) +
        '" target="_blank" rel="noopener">영상 열기</a></p>';
    }
    return 한장 + "</div>";
  }).join("") + "</div>";

  // ★ 비율 그림 셋 — 그리는 대상은 카드와 **같은 집합**이다 (원본 chart_frame = top_videos)
  var 설명 = S.video_sort + " " + 상위.length + "개 영상 / 전체 " + summary.length +
    "개 · 막대는 각 그래프의 값이 큰 순";
  h += pctChart(상위, "negative_rate", "영상별 부정률", 설명);
  h += pctChart(상위, "positive_rate", "영상별 긍정률", 설명);
  h += pctChart(상위, "inquiry_rate", "영상별 문의율", 설명);

  // 표는 **최소 댓글 수를 지난 전체**를 보여 준다 (원본 display = summary)
  //   ★ 원본 주석 — 「봐야 할 칸을 왼쪽으로 옮기고, 행을 고르면 아래에서 상세를 읽는다.
  //     video_id 는 사람이 읽는 값이 아니라 맨 뒤로 보낸다」
  h += sectionTitle("영상별 집계 체크",
    "행을 고르면 그 영상의 태그·설명과 대표 VoC 를 아래에서 읽습니다 · " +
    "위 카드·그래프는 상위 몇 개만, 이 표는 " + summary.length + "개 전부");
  window.__vidTableRows = 정렬된;
  h += table(VIDEO_TABLE.map(function (c) { return c[0]; }),
             정렬된.map(function (o) {
               return VIDEO_TABLE.map(function (c) { return c[1](o); });
             }), "t-video", true, "vidDetail");
  h += '<p class="sub"><button class="dl" data-dl="t-video" data-name="영상별집계">' +
    "⬇ 영상별 집계 통째로 받기 (" + num(정렬된.length) + "행 · " + VIDEO_TABLE.length +
    "칸)</button> — 지금 걸린 필터가 그대로 반영됩니다. " +
    "사용자명·이메일·링크는 가려진 판본입니다.</p>";
  h += '<div class="d60-mini-card">' + sectionTitle("영상 상세", "고른 영상의 제품군·브랜드와 맥락") +
    '<div id="vidDetail">' + renderVideoDetail(정렬된, window.__vidDetail) + "</div></div>";
  return h;
}


// ─────────────────────────────────────────────────────────────────────────
// 사이드바 · 탭 · 다시 그리기 — 원본 app_operating.py
// ─────────────────────────────────────────────────────────────────────────
var TABS = [["voc", "VoC 현황"], ["video", "분석 영상 정보"], ["inquiry", "문의 속 니즈"],
            ["improve", "개선 방향성"], ["pl", "★ PL Issue"]];
var FILTERS = [["product_category", "제품군"], ["topic_group", "개선/강화 영역"],
               ["brand", "브랜드"], ["market", "국가/시장"], ["cej", "고객 여정 단계(CEJ)"],
               ["sentiment_dir", "감성"]];

function sidebar() {
  var h = "<h3>데이터</h3><div class=\"side-box\"><p class=\"sub\">" +
    esc(D.정보.파일) + "<br>raw_voc " + num(D.정보.전체행) + "행 · 만든 날 " +
    esc(D.정보.만든날) + "</p></div>";
  h += "<h3>필터</h3><p class=\"sub\">고르지 않으면 전체입니다.</p>";
  FILTERS.forEach(function (f) {
    var key = f[0], opts = D.고를것[key] || [];
    if (!opts.length) return;
    h += '<div class="fgroup"><div class="flabel">' + esc(f[1]) + "</div>";
    opts.forEach(function (o) {
      // ★ 감성은 null 이 「셋 다 고름」 이다 (원본 기본값). 그래서 전부 체크로 보여 준다
      var on = S[key] === null ? true : S[key].indexOf(o) >= 0;
      h += '<label class="chk"><input type="checkbox" data-filter="' + key + '" value="' +
        esc(o) + '"' + (on ? " checked" : "") + "> " + esc(o) + "</label>";
    });
    h += "</div>";
  });
  // ★ 원본의 「어디까지 볼까」 — 위 칸들과 성격이 다르다 (app_operating.py:425-428)
  h += '<h3>어디까지 볼까</h3><p class="sub">믿을 만한 행만 볼지 정하는 자리입니다. ' +
    '위 칸들과 성격이 다릅니다.</p>';
  h += '<div class="fgroup"><div class="flabel">판정 충족도</div>';
  CONF_LEVELS.forEach(function (o) {
    h += '<label class="chk"><input type="checkbox" data-conf="' + esc(o) + '"' +
      (S.confidence.indexOf(o) >= 0 ? " checked" : "") + "> " + esc(o) + "</label>";
  });
  h += '<p class="sub">판정이 맞을 확률이 아님. 그 행에 정보가 얼마나 채워졌는지' +
    '(정보 충족도)입니다. Topic 없음=Low / Topic만=Medium / Topic+TEE=High / ' +
    'Topic+TEE+RootCause 완결=Very High. 기본값은 Very High·High 입니다.</p></div>';
  h += '<div class="fgroup"><label class="chk"><input type="checkbox" id="reviewOnly"' +
    (S.review_only ? " checked" : "") + "> 사람 검토가 필요한 행만</label>" +
    '<p class="sub">2차 판독에서 사람이 직접 봐야 한다고 표시한 행입니다' +
    "(review_required).</p></div>";
  h += '<button id="resetAll">필터 모두 지우기</button>';
  return h;
}

function render() {
  var all = D.행;
  var rows = applyFilters(all);
  // ★ 영역 고르개는 「영역 필터만 뺀」 집합으로 그린다 (원본 D-1b) —
  //   지금 보는 영역만 그리면 다른 영역으로 옮겨갈 수가 없다
  var groupSource = applyFilters(all, {skip: "topic_group"});
  // ★ 「Scope 제외 사유」 는 제외행이 살아 있는 자료가 필요하다 (원본 scope_source)
  var scopeSource = applyFilters(all, {scope: true});

  document.getElementById("side").innerHTML = sidebar();
  document.getElementById("tabs").innerHTML = TABS.map(function (t) {
    return '<button data-tab="' + t[0] + '" aria-selected="' + (S.tab === t[0]) + '">' +
      esc(t[1]) + "</button>";
  }).join("");
  // ★ 2026-10-22 Codex 교차점검 — 분모가 틀렸다. 「전체 50행」 이라고 적었는데 그 50 에는
  //   scope 제외 행과 판정 충족도로 빠진 행이 다 들어 있어 **화면에 절대 안 나오는 행**이다.
  //   원본의 분모는 `dimension_filtered` — 「무엇을 볼까」 를 통과한 정상 행이다
  //   (app_operating 주석: 「분모는 len(frame) 이 아니라 dimension_filtered 다」).
  var 차원통과 = applyFilters(all, {gate: "none"});
  var 충족통과 = applyFilters(all, {gate: "conf"});
  var 충족에빠진 = Math.max(0, 차원통과.length - 충족통과.length);
  var 걸린조건 = 0;
  ["product_category", "topic_group", "brand", "market", "cej"].forEach(function (k) {
    if (S[k] && S[k].length) 걸린조건 += 1;
  });
  var 감성전부 = (D.고를것.sentiment_dir || []).slice().sort().join("|");
  if (S.sentiment_dir !== null && S.sentiment_dir.slice().sort().join("|") !== 감성전부) 걸린조건 += 1;
  if (S.confidence.slice().sort().join("|") !== CONF_DEFAULT.slice().sort().join("|")) 걸린조건 += 1;
  if (S.review_only) 걸린조건 += 1;
  var 글 = S.confidence.length
    ? ("<b>" + num(rows.length) + "행</b> 보는 중 · 「무엇을 볼까」 통과 " +
       num(차원통과.length) + "행" +
       (걸린조건 ? " · 조건 " + 걸린조건 + "개 적용" : " · 조건 없음") +
       (충족에빠진 ? "<br><span class=\"sub\">판정 충족도 기준으로 " + num(충족에빠진) +
        "행이 빠졌습니다 (선택: " + esc(S.confidence.join(", ")) + ").</span>" : ""))
    : "<b>판정 충족도를 하나도 고르지 않아 볼 행이 없습니다.</b>";
  document.getElementById("seen").innerHTML = 글;

  var body = "";
  if (S.tab === "voc") body = viewOverview(rows, groupSource, scopeSource);
  else if (S.tab === "improve") body = viewImprovement(rows);
  else if (S.tab === "inquiry") body = viewInquiry(rows);
  else if (S.tab === "pl") body = viewPl(rows);
  else if (S.tab === "video") body = viewVideo(rows);
  document.getElementById("body").innerHTML = body;

  wire(rows);
}

// ── 누름 처리 ─────────────────────────────────────────────────────────────
function wire(rows) {
  document.querySelectorAll("#tabs button").forEach(function (b) {
    b.onclick = function () {
      S.tab = b.dataset.tab; S.detail = null;
      window.__inqDetail = null; window.__vidDetail = null;
      render(); window.scrollTo(0, 0);
    };
  });
  document.querySelectorAll('input[data-filter]').forEach(function (c) {
    c.onchange = function () {
      var k = c.dataset.filter, v = c.value;
      // null 은 「전부 고름」 이니, 하나를 끄면 **나머지 전부**가 고른 상태가 된다
      if (S[k] === null) S[k] = (D.고를것[k] || []).slice();
      var i = S[k].indexOf(v);
      if (c.checked && i < 0) S[k].push(v);
      if (!c.checked && i >= 0) S[k].splice(i, 1);
      S.detail = null; render();
    };
  });
  document.querySelectorAll("input[data-conf]").forEach(function (c) {
    c.onchange = function () {
      var v = c.dataset.conf, i = S.confidence.indexOf(v);
      if (c.checked && i < 0) S.confidence.push(v);
      if (!c.checked && i >= 0) S.confidence.splice(i, 1);
      S.detail = null; render();
    };
  });
  // ★ 정렬 축 — 누르면 Top 3 · 후보 카드 10 · 표가 **다 다시 정렬된다** (원본 radio).
  document.querySelectorAll('input[name="improveAxis"]').forEach(function (r) {
    r.onchange = function () {
      window.__improveAxis = parseInt(r.value, 10) || 0;
      S.detail = null; render();
    };
  });
  // ★ 문의 카드 — 정렬 기준·표시 개수를 바꾸면 자리 번호의 뜻이 달라지므로 고른 행을 비운다
  var iq = document.getElementById("inqSort");
  if (iq) iq.onchange = function () {
    window.__inqSort = parseInt(iq.value, 10) || 0;
    window.__inqDetail = null; render();
  };
  var ic = document.getElementById("inqCount");
  if (ic) ic.onchange = function () {
    window.__inqCount = parseInt(ic.value, 10) || 0;
    window.__inqDetail = null; render();
  };
  document.querySelectorAll("input[data-inqtype]").forEach(function (c) {
    c.onchange = function () {
      var v = c.dataset.inqtype, 고름 = (window.__inqTypes || []).slice();
      var i = 고름.indexOf(v);
      if (c.checked && i < 0) 고름.push(v);
      if (!c.checked && i >= 0) 고름.splice(i, 1);
      window.__inqTypes = 고름;
      window.__inqDetail = null; render();
    };
  });
  // ★ RootCause 등급·2차분리 거르개 — 자리 번호의 뜻이 달라지니 고른 행을 비운다
  document.querySelectorAll("input[data-grade]").forEach(function (c) {
    c.onchange = function () {
      var v = c.dataset.grade, 고름 = (window.__grades || []).slice();
      var i = 고름.indexOf(v);
      if (c.checked && i < 0) 고름.push(v);
      if (!c.checked && i >= 0) 고름.splice(i, 1);
      window.__grades = 고름;
      S.detail = null; render();
    };
  });
  var so = document.getElementById("splitOnly");
  if (so) so.onchange = function () {
    window.__splitOnly = so.checked;
    S.detail = null; render();
  };
  var vm = document.getElementById("videoMin");
  if (vm) vm.onchange = function () {
    var v = parseInt(vm.value, 10);
    S.video_min = (isNaN(v) || v < 1) ? 1 : v;
    window.__vidDetail = null; render();
  };
  var vt = document.getElementById("videoThinOnly");
  if (vt) vt.onchange = function () {
    S.video_thin_only = vt.checked; window.__vidDetail = null; render();
  };
  var vs = document.getElementById("videoSort");
  if (vs) vs.onchange = function () { S.video_sort = vs.value; window.__vidDetail = null; render(); };
  var vc = document.getElementById("videoCount");
  if (vc) vc.onchange = function () { S.video_count = vc.value; window.__vidDetail = null; render(); };
  var ro = document.getElementById("reviewOnly");
  if (ro) ro.onchange = function () { S.review_only = ro.checked; S.detail = null; render(); };
  var ra = document.getElementById("resetAll");
  if (ra) ra.onclick = function () {
    FILTERS.forEach(function (f) { S[f[0]] = f[0] === "sentiment_dir" ? null : []; });
    // ★ 「어디까지 볼까」 는 **기본값으로** 돌아간다 (빈 목록이 아니다 — 빈 목록은 0행이다)
    S.confidence = CONF_DEFAULT.slice();
    S.review_only = false;
    S.detail = null; render();
  };
  var gr = document.getElementById("groupReset");
  if (gr) gr.onclick = function () { S.topic_group = []; S.detail = null; render(); };
  // 막대를 누르면 그 영역만 — 원본 D-1b
  document.querySelectorAll("[data-pick]").forEach(function (g) {
    g.onclick = function (e) {
      var k = g.dataset.pickkind, v = g.dataset.pick;
      // ★ Shift+클릭 — 여러 영역을 함께 고른다 (원본 altair 선택과 같은 동작).
      //   원본 주석대로 「전부 해제」 도 되어야 한다 — 고른 것을 다시 Shift+누르면 빠진다.
      if (e && e.shiftKey) {
        var 고름 = S[k].slice(), i = 고름.indexOf(v);
        if (i >= 0) 고름.splice(i, 1); else 고름.push(v);
        S[k] = 고름;
      } else {
        S[k] = (S[k].length === 1 && S[k][0] === v) ? [] : [v];
      }
      S.detail = null; render();
    };
  });
  document.querySelectorAll("tr.pickable").forEach(function (tr) {
    tr.onclick = function () {
      // ★ 표마다 자세히 펼칠 자리가 다르다 — 문의 표는 `inqDetail`, 나머지는 `rowDetail`
      var i = +tr.dataset.row, 어디 = tr.dataset.detail || "rowDetail";
      var 상자 = document.getElementById(어디);
      if (어디 === "inqDetail") {
        window.__inqDetail = i;
        if (상자) 상자.innerHTML = renderInquiryDetail(window.__inqTableRows || [], i);
      } else if (어디 === "vidDetail") {
        window.__vidDetail = i;
        if (상자) 상자.innerHTML = renderVideoDetail(window.__vidTableRows || [], i);
      } else {
        S.detail = i;
        // ★ 거르개(등급·2차분리)가 걸린 **표의 목록**으로 본다. 필터 전 rows 로 보면
        //   고른 줄과 다른 행이 펼쳐진다.
        if (상자) 상자.innerHTML = renderRowDetail(window.__vocTableRows || rows, i);
      }
      document.querySelectorAll("tr.pickable").forEach(function (x) { x.classList.remove("on"); });
      tr.classList.add("on");
    };
  });
  wireDownload();
  document.querySelectorAll("input.find").forEach(function (inp) {
    inp.oninput = function () {
      var q = inp.value.trim().toLowerCase();
      var t = document.getElementById(inp.dataset.for);
      if (!t) return;
      Array.prototype.forEach.call(t.tBodies[0].rows, function (r) {
        r.hidden = q !== "" && r.innerText.toLowerCase().indexOf(q) < 0;
      });
    };
  });
  document.querySelectorAll("table th").forEach(function (th) {
    th.onclick = function () {
      var t = th.closest("table"), i = +th.dataset.i, up = th.dataset.up !== "1";
      Array.prototype.forEach.call(t.tHead.rows[0].cells, function (c) { c.dataset.up = ""; });
      th.dataset.up = up ? "1" : "0";
      var rs = Array.prototype.slice.call(t.tBodies[0].rows);
      var n = function (x) { var v = parseFloat(String(x).replace(/[,%\s]/g, "")); return isNaN(v) ? null : v; };
      rs.sort(function (a, b) {
        var x = a.cells[i].innerText, y = b.cells[i].innerText, nx = n(x), ny = n(y);
        var r = (nx !== null && ny !== null) ? nx - ny : x.localeCompare(y, "ko");
        return up ? r : -r;
      });
      rs.forEach(function (r) { t.tBodies[0].appendChild(r); });
    };
  });
}

// ── ★ 자기검사 — 엔진이 낸 값과 JS 가 낸 값을 **전부** 대본다 ───────────────────
//   ★ 2026-10-21 Codex 교차점검에서 잡혔다 — 전에는 기본 행 수만 보고 초록불을 켰다.
//     같은 파일에서 엔진 개선군집은 8개인데 JS 는 9개였는데도 「맞습니다」 라고 했다.
//     **맞춤값에 담아 둔 것은 하나도 빠짐없이 대본다.** 안 대는 값은 담지도 않는다.
//     (공통 규칙 — 검사기는 크게 실패해야 한다. 「못 찾음」 을 「없음」 으로 돌리지 않는다)
function selfCheck() {
  var 맞 = D.맞춤값 || {}, 어긋남 = [], 댄것 = 0;

  function 대기(이름, 엔진값, 내값) {
    if (엔진값 === undefined || 엔진값 === null) {
      어긋남.push(이름 + " — 엔진 값이 없어 **대보지 못했다**");
      return;
    }
    댄것 += 1;
    if (String(엔진값) !== String(내값)) {
      어긋남.push(이름 + " — 엔진 " + 엔진값 + " · 이 화면 " + 내값);
    }
  }

  var 기본 = applyFilters(D.행);
  대기("기본 행 수", 맞.기본행수, 기본.length);

  // 필터 하나 걸었을 때
  if (맞.맞댈제품군) {
    var 옛 = S.product_category.slice();
    S.product_category = [맞.맞댈제품군];
    var n = applyFilters(D.행).length;
    S.product_category = 옛;
    대기("제품군 「" + 맞.맞댈제품군 + "」 행 수", 맞.맞댈제품군행수, n);
  }

  // ★ 개선과제 — 가장 틀리기 쉬운 자리다. 수와 상위 다섯을 다 댄다
  var 과제 = improvementTasks(기본);
  대기("개선과제 군집 수", 맞.개선과제수, 과제.length);
  if (맞.개선상위 && 맞.개선상위.length) {
    맞.개선상위.forEach(function (x, i) {
      var 내 = 과제[i];
      대기("개선 " + (i + 1) + "위 이름", x[0], 내 ? 내.topic : "(없음)");
      대기("개선 " + (i + 1) + "위 건수", x[1], 내 ? 내.n : "(없음)");
    });
  }

  // ★ 2026-10-22 — 새로 살린 것들도 **대본다.** 안 대면 「돌아간다」 만 보고 「맞다」 를 못 본다
  function 지어보기(바꾸기) {
    var 옛 = {confidence: S.confidence.slice(), review_only: S.review_only,
             brand: S.brand.slice()};
    바꾸기();
    var n = applyFilters(D.행).length;
    S.confidence = 옛.confidence; S.review_only = 옛.review_only; S.brand = 옛.brand;
    return n;
  }
  if (맞.판정충족도별) {
    Object.keys(맞.판정충족도별).forEach(function (레벨) {
      대기("판정 충족도 「" + 레벨 + "」 행 수", 맞.판정충족도별[레벨],
           지어보기(function () { S.confidence = [레벨]; S.review_only = false; }));
    });
  }
  if (맞.판정충족도_빈목록행수 !== undefined) {
    대기("판정 충족도를 하나도 안 고르면", 맞.판정충족도_빈목록행수,
         지어보기(function () { S.confidence = []; S.review_only = false; }));
  }
  if (맞.차원통과행수 !== undefined) {
    대기("「무엇을 볼까」 통과 행 수(상단 분모)", 맞.차원통과행수,
         applyFilters(D.행, {gate: "none"}).length);
  }
  if (맞.사람검토행수_기본충족도 !== undefined) {
    대기("사람검토 행만 (기본 충족도)", 맞.사람검토행수_기본충족도,
         지어보기(function () { S.confidence = CONF_DEFAULT.slice(); S.review_only = true; }));
  }
  if (맞.사람검토행수_전체충족도 !== undefined) {
    대기("사람검토 행만 (충족도 전부)", 맞.사람검토행수_전체충족도,
         지어보기(function () { S.confidence = CONF_LEVELS.slice(); S.review_only = true; }));
  }
  if (맞.브랜드선택지) {
    대기("브랜드 선택지 수", 맞.브랜드선택지.length, (D.고를것.brand || []).length);
    대기("브랜드 선택지", 맞.브랜드선택지.join(" | "), (D.고를것.brand || []).join(" | "));
  }
  if (맞.브랜드별) {
    Object.keys(맞.브랜드별).forEach(function (b) {
      대기("브랜드 「" + b + "」 행 수", 맞.브랜드별[b],
           지어보기(function () { S.brand = [b]; }));
    });
  }

  // 문의 두 분포 — 원본의 핵심 숫자 그림 둘
  if (맞.문의행수 !== undefined) {
    var 문의 = 기본.filter(function (r) { return txt(r.inquiry_flag).toUpperCase() === "Y"; });
    대기("문의형 VoC 행 수", 맞.문의행수, 문의.length);
    [["문의유형분포", "inquiry_type", K.문의유형이름, "문의 유형"],
     ["니즈신호분포", "need_signal_type", K.니즈신호이름, "니즈 신호 유형"]].forEach(function (x) {
      if (!맞[x[0]]) return;
      var 내 = {};
      countByLabel(문의, x[1], x[2]).forEach(function (p) { 내[p[0]] = p[1]; });
      var 엔진키 = Object.keys(맞[x[0]]).sort();
      대기(x[3] + " 분포 — 항목", 엔진키.join(" | "), Object.keys(내).sort().join(" | "));
      엔진키.forEach(function (k) {
        대기(x[3] + " 「" + k + "」", 맞[x[0]][k], 내[k] === undefined ? "(없음)" : 내[k]);
      });
    });
  }

  // 영상 집계 — 엔진 `video_summary` 가 낸 것과 묶음·댓글 수·비율 셋을 다 댄다
  if (맞.영상집계) {
    var 내영상 = videoSummary(기본);
    대기("영상 수(묶음)", 맞.영상수, 내영상.length);
    var 내표 = {};
    내영상.forEach(function (o) { 내표[o.video_id + SEP + o.video_title] = o; });
    맞.영상집계.forEach(function (e) {
      var 내 = 내표[e.video_id + SEP + e.video_title];
      var 이름 = "영상 「" + (e.video_title || e.video_id).slice(0, 14) + "」 ";
      if (!내) { 어긋남.push(이름 + "— 엔진에는 있는데 이 화면에 없다"); 댄것 += 1; return; }
      대기(이름 + "댓글 수", e.comment_count, 내.comment_count);
      [["negative_rate", "부정률"], ["positive_rate", "긍정률"],
       ["inquiry_rate", "문의율"]].forEach(function (x) {
        대기(이름 + x[1], e[x[0]].toFixed(4), 내[x[0]].toFixed(4));
      });
    });
  }

  var el = document.getElementById("selfcheck");
  if (어긋남.length) {
    el.className = "bad";
    el.innerHTML = "<b>숫자가 엔진과 어긋납니다 — 이 화면을 믿지 마십시오. (" +
      어긋남.length + "건)</b><br>" + 어긋남.map(esc).join("<br>");
  } else {
    el.className = "ok";
    el.innerHTML = "엔진이 낸 값과 맞습니다 — " + 댄것 + "가지를 대봤습니다.";
  }
}

document.addEventListener("DOMContentLoaded", function () { render(); selfCheck(); });


// ── 통째로 받기 — 서버 없이 그 표를 CSV 로 내려준다 (원본 render_table_download) ────
function wireDownload() {
  document.querySelectorAll("button.dl").forEach(function (b) {
    b.onclick = function () {
      var t = document.getElementById(b.dataset.dl);
      if (!t) return;
      var lines = [];
      lines.push(Array.prototype.map.call(t.tHead.rows[0].cells, function (c) {
        return '"' + c.innerText.replace(/"/g, '""') + '"'; }).join(","));
      Array.prototype.forEach.call(t.tBodies[0].rows, function (r) {
        if (r.hidden) return;
        lines.push(Array.prototype.map.call(r.cells, function (c) {
          return '"' + c.innerText.replace(/"/g, '""') + '"'; }).join(","));
      });
      // BOM 을 붙인다 — 엑셀에서 한글이 안 깨지게
      var blob = new Blob(["\ufeff" + lines.join("\n")], {type: "text/csv;charset=utf-8"});
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (b.dataset.name || "표") + ".csv";
      a.click();
      URL.revokeObjectURL(a.href);
    };
  });
}

"""
