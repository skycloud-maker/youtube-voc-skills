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
  return rows.filter(function (r) {
    if (txt(r.status) !== "normal") return false;
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
function table(head, rows, id, pickable) {
  if (!rows.length) return '<p class="empty">이 조건에서는 담을 것이 없습니다.</p>';
  var th = head.map(function (c, i) { return '<th data-i="' + i + '">' + esc(c) + "</th>"; }).join("");
  var tb = rows.map(function (r, ri) {
    return '<tr' + (pickable ? ' data-row="' + ri + '" class="pickable"' : "") + ">" +
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
function viewOverview(rows, groupSource) {
  var total = rows.length;
  var inq = rows.filter(function (r) { return txt(r.inquiry_flag).toUpperCase() === "Y"; }).length;
  var review = rows.filter(function (r) { return r.review_queue === true; }).length;
  var valid = rows.filter(function (r) { return txt(r.validity) === "유효"; }).length;
  // ★ 2026-10-21 Codex 교차점검 — 원본(overview.py:183-195)은 `split_origin_atomic_id` 가
  //   비어 있지 않은 **모든** 행을 센다. 내 것은 `atomic_index != 1` 로 세어 **첫 조각을 빼먹었다**
  //   (실측 — 원본 2행 vs 내 1행).
  var split = rows.filter(function (r) { return txt(r.split_origin_atomic_id) !== ""; }).length;
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
      "막대를 누르면 그 영역만 봅니다. · 사이드바 필터와 같은 값을 씁니다. · 지금: " + now) +
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
  // 행 자세히 — 표에서 고르면 아래에 요약문·RootCause·원문
  var head = ["atomic_id", "topic", "감성", "CEJ", "제품군", "요약문"];
  var body = rows.map(function (r) {
    return [r.atomic_id, r.topic, r.sentiment_dir, r.cej, r.product_category,
            (r.atomic_voc_summary || r.atomic_voc || "").slice(0, 60)];
  });
  h += sectionTitle("행 자세히 보기", "표에서 행을 하나 고르면 그 VoC 의 요약문과 RootCause 를 아래에서 읽습니다.");
  h += table(head, body, "t-voc", true);
  h += '<div id="rowDetail"></div>';
  return h;
}

function renderRowDetail(rows, ri) {
  var r = rows[ri];
  if (!r) return "";
  var meta = ["제품군 " + txt(r.product_category), "topic " + txt(r.topic),
              "영역 " + txt(r.topic_group), "CEJ " + txt(r.cej),
              "감성 " + txt(r.sentiment_dir)].filter(function (x) { return x.length > 4; });
  var h = '<div class="d60-mini-card detail"><h4>' + esc(r.topic || "(라벨 없음)") + "</h4>" +
    '<p class="sub">' + esc(meta.join("  ·  ")) + "</p>";
  if (txt(r.atomic_voc_summary)) h += "<p><b>요약문</b><br>" + esc(r.atomic_voc_summary) + "</p>";
  var rc = [["문제", r.rootcause_problem], ["원인", r.rootcause_cause], ["대상", r.rootcause_target]]
    .filter(function (x) { return txt(x[1]) && txt(x[1]) !== "N/A"; });
  if (rc.length) {
    h += "<p><b>RootCause</b></p>" + rc.map(function (x) {
      return "<p>" + esc(x[0]) + " — " + esc(x[1]) + "</p>"; }).join("");
  } else {
    h += '<p class="sub">이 행에는 RootCause 가 채워져 있지 않습니다.</p>';
  }
  if (txt(r.video_title)) h += "<p><b>어떤 영상 밑의 말인가</b><br>" + esc(r.video_title) + "</p>";
  if (txt(r.atomic_voc)) h += "<p><b>조각</b><br>" + esc(r.atomic_voc) + "</p>";
  if (txt(r.original_voc)) h += "<p><b>원문</b><br>" + esc(r.original_voc) + "</p>";
  if (!txt(r.atomic_voc) && !txt(r.original_voc)) {
    h += '<p class="sub">공유용이라 원문은 담지 않았습니다.</p>';
  }
  return h + "</div>";
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

// ─────────────────────────────────────────────────────────────────────────
// 화면 ② 개선 방향성 — 원본 views/improvement.py
// ─────────────────────────────────────────────────────────────────────────
function viewImprovement(rows) {
  var h = "<h2>개선 방향성</h2><p class=\"sub\">건수와 부정 강도 <b>두 축</b>으로 매긴 개선과제입니다. " +
    "점수는 원본 <code>scoring.score_improvement_tasks</code> 와 같은 공식입니다 — " +
    "<code>priority_score = |평균 부정강도| × 부정 건수</code>.</p>";
  var list = improvementTasks(rows);
  if (!list.length) return h + '<p class="empty">현재 필터 조건에서 개선과제 후보 군집이 없습니다.</p>';
  h += cardGrid([
    card("개선과제 군집", num(list.length), "제품군 × topic", "blue"),
    card("부정 건수 합", num(list.reduce(function (a, b) { return a + b.neg_count; }, 0)),
         "min(감정,성공,0) < 0 인 행", "orange"),
    card("봐야 할 것", num(list.filter(function (x) { return x.watch_axis; }).length),
         "어느 축으로든 상위 20", "purple")
  ]);
  var byVol = list.slice().sort(function (a, b) { return a.volume_rank - b.volume_rank; });
  var bySev = list.slice().sort(function (a, b) { return a.severity_rank - b.severity_rank; });
  h += '<div class="row">';
  h += barChart(byVol.slice(0, 15).map(function (x) { return [x.topic, x.volume_score]; }),
                "축 A — 건수", "얼마나 많은 사람이 말했나 (부정 건수) · 상위 15개");
  h += barChart(bySev.slice(0, 15).map(function (x) { return [x.topic, x.severity_score]; }),
                "축 B — 심각도", "화난 사람은 얼마나 화났나 (부정 행만의 평균) · 상위 15개");
  h += "</div>";
  h += table(["제품군", "topic", "n", "부정 건수", "부정 비율", "평균 부정강도", "RC 커버리지",
              "우선순위 점수", "건수 순위", "심각도 순위", "종합", "봐야 할 축"],
             list.map(function (x) {
               return [x.pc, x.topic, num(x.n), num(x.neg_count),
                       (x.neg_ratio * 100).toFixed(1) + "%", x.mean_neg.toFixed(3),
                       (x.rc_coverage * 100).toFixed(1) + "%", x.priority_score.toFixed(3),
                       x.volume_rank, x.severity_rank, x.combined_rank, x.watch_axis];
             }), "t-improve");
  h += '<p class="sub"><button class="dl" data-dl="t-improve" data-name="개선과제">개선과제 전체 받기</button>' +
    " — 건수가 적다고 목록에서 내리지 않습니다.</p>";
  return h;
}

// ─────────────────────────────────────────────────────────────────────────
// 화면 ③ 문의 속 니즈 — 원본 views/inquiry.py (카드 3 · 그림 2)
// ─────────────────────────────────────────────────────────────────────────
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
  if (!inq.length) return h + '<p class="empty">이 조건에서 문의형 VoC 가 없습니다.</p>';
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
  h += table(["atomic_id", "topic", "CEJ", "요약문"],
             inq.map(function (r) {
               return [r.atomic_id, r.topic, r.cej,
                       (r.atomic_voc_summary || r.atomic_voc || "").slice(0, 70)];
             }), "t-inq");
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

function videoSummary(rows) {
  // 유효행이 하나라도 있으면 유효행만 (원본 valid / if valid.empty: valid = frame)
  var valid = rows.filter(function (r) { return txt(r.validity) === "유효"; });
  if (!valid.length) valid = rows;
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
  return 차례.map(function (k) {
    var o = g[k], d = o.rows || 1;
    o.positive_rate = o.pos / d;
    o.negative_rate = o.neg / d;
    o.inquiry_rate = o.inq / d;
    o.축이름 = o.video_title || o.video_id;
    return o;
  });
}

// 여러 축으로 내림차순 — 원본 `sort_values([...], ascending=False)`
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

function viewVideo(rows) {
  var h = "<h2>분석 영상 정보</h2><p class=\"sub\">영상별 댓글 수, 긍정률, 부정률, 문의율을 집계합니다. " +
    "문의율은 감성과 별도 축이라 <b>합이 100%를 넘을 수 있습니다.</b></p>";
  var all = videoSummary(rows);
  h += cardGrid([
    card("집계 Row", num(rows.length), "현재 필터 기준", "blue"),
    card("영상 수", num(all.length), "video_id + 제목 + URL 묶음", "green")
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
  var 설명 = S.video_sort + " " + 상위.length + "개 영상 / 전체 " + summary.length +
    "개 · 막대는 각 그래프의 값이 큰 순";

  h += sectionTitle("영상별 리스트 카드", 설명);
  h += '<div class="vcards">' + 상위.map(function (o) {
    var top = Object.keys(o.pc).sort(function (a, b) { return o.pc[b] - o.pc[a]; })[0] || "";
    return '<div class="d60-mini-card"><b>' + esc(o.축이름) + "</b>" +
      '<p class="sub">댓글 ' + num(o.comment_count) + "건 · 부정 " +
      (o.negative_rate * 100).toFixed(1) + "% (" + num(o.neg) + "건) · 긍정 " +
      (o.positive_rate * 100).toFixed(1) + "% · 문의 " +
      (o.inquiry_rate * 100).toFixed(1) + "%" + (top ? " · " + esc(top) : "") + "</p>" +
      (o.video_url ? '<p class="sub">' + esc(o.video_url) + "</p>" : "") + "</div>";
  }).join("") + "</div>";

  // ★ 비율 그림 셋 — 그리는 대상은 카드와 **같은 집합**이다 (원본 chart_frame = top_videos)
  h += pctChart(상위, "negative_rate", "영상별 부정률", 설명);
  h += pctChart(상위, "positive_rate", "영상별 긍정률", 설명);
  h += pctChart(상위, "inquiry_rate", "영상별 문의율", 설명);

  // 표는 **최소 댓글 수를 지난 전체**를 보여 준다 (원본 display = summary)
  h += table(["영상", "video_id", "댓글 수", "긍정률", "부정률", "문의율", "주요 제품군"],
             정렬된.map(function (o) {
               var top = Object.keys(o.pc).sort(function (a, b) { return o.pc[b] - o.pc[a]; })[0] || "";
               return [o.축이름, o.video_id, num(o.comment_count),
                       (o.positive_rate * 100).toFixed(1) + "%",
                       (o.negative_rate * 100).toFixed(1) + "%",
                       (o.inquiry_rate * 100).toFixed(1) + "%", top];
             }), "t-video");
  h += '<p class="sub"><button class="dl" data-dl="t-video" data-name="영상별집계">영상별 집계 받기</button></p>';
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
  if (S.tab === "voc") body = viewOverview(rows, groupSource);
  else if (S.tab === "improve") body = viewImprovement(rows);
  else if (S.tab === "inquiry") body = viewInquiry(rows);
  else if (S.tab === "pl") body = viewPl(rows);
  else if (S.tab === "video") body = viewVideo(rows);
  document.getElementById("body").innerHTML = body;

  if (S.tab === "voc" && S.detail !== null) {
    var d = document.getElementById("rowDetail");
    if (d) d.innerHTML = renderRowDetail(rows, S.detail);
  }
  wire(rows);
}

// ── 누름 처리 ─────────────────────────────────────────────────────────────
function wire(rows) {
  document.querySelectorAll("#tabs button").forEach(function (b) {
    b.onclick = function () { S.tab = b.dataset.tab; S.detail = null; render(); window.scrollTo(0, 0); };
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
  var vm = document.getElementById("videoMin");
  if (vm) vm.onchange = function () {
    var v = parseInt(vm.value, 10);
    S.video_min = (isNaN(v) || v < 1) ? 1 : v;
    render();
  };
  var vt = document.getElementById("videoThinOnly");
  if (vt) vt.onchange = function () { S.video_thin_only = vt.checked; render(); };
  var vs = document.getElementById("videoSort");
  if (vs) vs.onchange = function () { S.video_sort = vs.value; render(); };
  var vc = document.getElementById("videoCount");
  if (vc) vc.onchange = function () { S.video_count = vc.value; render(); };
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
    g.onclick = function () {
      var k = g.dataset.pickkind, v = g.dataset.pick;
      S[k] = (S[k].length === 1 && S[k][0] === v) ? [] : [v];
      S.detail = null; render();
    };
  });
  document.querySelectorAll("tr.pickable").forEach(function (tr) {
    tr.onclick = function () {
      S.detail = +tr.dataset.row;
      document.getElementById("rowDetail").innerHTML = renderRowDetail(rows, S.detail);
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
