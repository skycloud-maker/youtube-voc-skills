"""판정 JSON → 대시보드 번들 생성 (환원 스크립트)

사용:
    python build_bundle.py <판정.jsonl> [--product robot] [--apply]

기본(제안 모드)  raw_voc 원본 유지 + 2차 컬럼 표시 + 수정로그 시트
--apply          [오류] 확정 건과 분리 제안을 raw_voc 에 실제 반영
                 ★ 사람 승인 후에만 쓴다 (정본 §11-1 3단 검증)

원본을 수정하지 않는다. 결과는 별도 폴더에 쓴다.

정본 §0-2 준수 — 문자열 "N/A" 를 결측치로 읽지 않는다 (keep_default_na=False)
"""
from __future__ import annotations

import csv, json, os, re, sys, collections, datetime
import collections

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)

# ★ 꾸러미를 어디에 풀어도 돌아가야 한다 (sky 2026-08-21)
#   전에는 여기에 pilot 3개 경로가 박혀 있었다. 그래서 실무자 컴퓨터에서는
#   `full_batches.py` 가 첫 줄에서 FileNotFoundError 로 멈췄고,
#   새로 돌린 분석 결과로는 아예 2차 판독에 들어갈 수 없었다.
#   이제 「판독할 데이터」 를 스스로 찾는다. 경로를 코드에 박지 않는다.
ROOT = (os.path.dirname(BASE)
        if os.path.basename(BASE) in ('스크립트', 'scripts') else BASE)

# 폴더 이름에서 걷어낼 말 — `p1_overlabel_suggest_robot_20260814` → `robot`
_NOISE = {'p1', 'p0', 'overlabel', 'suggest', 'voc', 'secondary', 'dataset', 'data'}


def _short_name(folder):
    parts = [p for p in os.path.basename(folder).split('_')
             if p and p.lower() not in _NOISE and not p.isdigit()]
    return '_'.join(parts) or os.path.basename(folder)


def _discover():
    """판독할 데이터(voc_secondary_dataset.csv)가 어디 있는지 스스로 찾는다.

    보는 자리 — 앞의 것이 이긴다
      ① 환경변수 VOC_판독대상 (또는 VOC_DATA) 이 가리키는 폴더
      ② <뿌리>/판독대상/*/voc_secondary_dataset.csv    ← 꾸러미로 풀었을 때
      ③ <뿌리>/*/voc_secondary_dataset.csv             ← 원래 작업 폴더
    """
    import glob as _glob

    # ★ 아무 데나 훑지 않는다 (sky 2026-08-21).
    #   처음엔 작업 폴더까지 훑게 했더니 smoke 시험 폴더 4개와 robot_recovery 까지
    #   끌어와 판독 대상이 3개에서 7개로 늘었다.
    #   숫자가 우연히 같아 안 드러났을 뿐, 조용히 대상이 바뀌는 것은
    #   가장 나쁜 종류의 오류다. 「여기가 판독 대상이다」 라고 밝힌 자리만 본다.
    homes = []
    picked = os.environ.get('VOC_판독대상') or os.environ.get('VOC_DATA')
    if picked:
        homes.append(picked)
    homes.append(os.path.join(ROOT, '판독대상'))

    for home in homes:
        hits = sorted(_glob.glob(os.path.join(home, '*', 'voc_secondary_dataset.csv')))
        if hits:
            return {_short_name(os.path.dirname(h)): h for h in hits}
    return {}


SRC = _discover()

# ★ 아무것도 못 찾으면 예전 자리를 써 본다 (sky 작업 폴더를 지키는 되돌림장치)
#   ★ 다만 그 파일이 **실제로 있을 때만** 쓴다 (2026-08-22).
#     없는데도 이름을 채우면 자가점검이 「dishwasher 데이터가 없습니다」 처럼
#     실무자에게 아무 뜻 없는 말을 한다. 비어 있으면 비어 있다고 말해야
#     「엑셀을 주십시오」 로 이어진다.
if not SRC:
    _옛 = {
        'robot':      f'{BASE}/p1_overlabel_suggest_robot_20260814/voc_secondary_dataset.csv',
        'dishwasher': f'{BASE}/p1_overlabel_suggest_dishwasher_20260814/voc_secondary_dataset.csv',
        'multi':      f'{BASE}/p1_overlabel_suggest_multi_20260814/voc_secondary_dataset.csv',
    }
    SRC = {k: v for k, v in _옛.items() if os.path.exists(v)}

# ★ 도는 차례를 고정한다. pilot 3종이 있으면 예전 차례를 그대로 지킨다 —
#   회차 배치가 이 차례로 짜여 있어서, 바뀌면 예전 결과와 대조가 안 된다
_LEGACY = ('dishwasher', 'robot', 'multi')
PRODUCTS = tuple([k for k in _LEGACY if k in SRC]
                 + sorted(k for k in SRC if k not in _LEGACY))
SEC_COLS = ['na_class', 'qc_status_summary', 'qc_rule_ids',
            'split_origin_atomic_id', 'secondary_topic_source']
# ★ CP-48 (sky 2026-08-18) — 2차가 새로 만드는 칸. 1차 원본에 없다
#   topic_group    열린 어휘 topic 이 어느 층에 묶이는지
#   review_reason  Y 인 이유. 지금까지 Y 만 있고 까닭이 없었다
#   ★ SEC_COLS 에 넣으면 안 된다. 저기는 1차 값을 떠오는 칸이라
#     sec = {c: r.get(c, '')} 가 빈 값으로 덮어쓴다
NEW_COLS = ['topic_group', 'review_reason']
SECONDARY_ENUMS = os.path.join(BASE, 's9_group', 'secondary_enums.json')
SECONDARY_TOPICS = os.path.join(BASE, 's9_group', 'secondary_topics.json')
GROUP_MAP = os.path.join(BASE, 's9_group', 'topic_group_map.json')
# 2차 신설 컬럼 (66컬럼 계약 밖 · 대시보드는 여분 컬럼을 통과시킨다)
QC_COLS = ['qc_verdict', 'qc_finding_count', 'qc_entity', 'qc_confidence',
           'qc_criteria_uncovered', 'qc_structural_defect']
SOURCE_LEVEL = (
    'source_id', 'raw_row_index', 'parent_voc_id', 'comment_relation',
    'original_voc', 'voc_cleaned', 'voc_residual', 'reference_brand',
    'market', 'language', 'source_context_summary', 'status',
    'scope_exclusion_reason', 'proposal_flag', 'video_id', 'video_title',
    'video_url', 'product_category', 'product_category_source',
)


def read_csv(path):
    """정본 §0-2 — "N/A" 를 결측치로 바꾸지 않는다."""
    with open(path, encoding='utf-8-sig', newline='') as h:
        rd = csv.DictReader(h)
        return [dict(r) for r in rd], list(rd.fieldnames)


def read_judgments(path):
    """판정 결과를 읽는다.

    아래 셋을 모두 받는다.
      1) JSONL   한 줄에 객체 하나
      2) JSON    배열 하나
      3) 채팅 답변 전문   ```json 코드블록 안의 객체들을 골라낸다
                         설명 문단이 섞여 있어도 된다
    """
    txt = open(path, encoding='utf-8').read().strip()

    # 0) 전체가 JSON 배열인 경우만. 실패하면 조용히 다음으로 넘어간다
    #    ★ 채팅 답변이 "[0단계 — 전제 점검]" 처럼 대괄호로 시작할 수 있다
    if txt.startswith('['):
        try:
            v = json.loads(txt)
            if isinstance(v, list) and v and isinstance(v[0], dict) and 'atomic_id' in v[0]:
                return v
        except json.JSONDecodeError:
            pass

    # 1) JSONL 먼저 시도
    out, ok = [], True
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        if not line.startswith('{'):
            ok = False
            break
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            ok = False
            break
    if ok and out:
        return out

    # 2) ```json 코드블록 추출
    fence = chr(96) * 3
    blocks = re.findall(fence + r'(?:json)?\s*\n(.*?)' + fence, txt, re.S)
    out = []
    for b in blocks:
        b = b.strip()
        if not b.startswith('{') and not b.startswith('['):
            continue
        try:
            v = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(v, list):
            out.extend(v)
        elif isinstance(v, dict) and 'atomic_id' in v:
            out.append(v)
    if out:
        return out

    # 3) 코드펜스 없이 흩어진 최상위 객체 긁기
    depth, start = 0, None
    for i, ch in enumerate(txt):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    v = json.loads(txt[start:i + 1])
                    if isinstance(v, dict) and 'atomic_id' in v:
                        out.append(v)
                except json.JSONDecodeError:
                    pass
                start = None
    if not out:
        raise SystemExit('판정 객체를 찾지 못했습니다. atomic_id 를 가진 JSON 이 필요합니다: ' + path)
    return out


# ★ 조각 id 충돌 방지 (CP-46). source 별로 이미 쓴 번호를 기억한다
_seg_seq = {}
_used_ids = set()


def akey(r):
    m = re.search(r'\d+', str(r.get('atomic_index') or ''))
    return (int(m.group()) if m else 10 ** 9, str(r.get('atomic_id') or ''))


def compact(s):
    return re.sub(r'\s+', '', str(s or ''))



def compute_derived(row):
    """정본 §7.10 — confidence_rating 은 후처리 계산값. LLM 출력을 쓰지 않는다.
    review_required 는 2차 검수 큐 플래그(§8.3)."""
    def num(v):
        try:
            return float(str(v).strip() or 0)
        except Exception:
            return 0.0
    topic = str(row.get('topic') or '').strip()
    has_topic = topic not in ('', 'N/A', '미분류')
    if has_topic and num(row.get('topic_score')) == 0:
        # 2차 A01 회차는 topic/topic_evidence 만 판정한다.
        # topic 이 새로 확정됐는데 score 를 0 으로 두면 대시보드 점수 필터에서 사라진다.
        row['topic_score'] = '3'
    elif not has_topic:
        # ★ CP-48 — 라벨이 없으면 점수도 없다 (sky 2026-08-18)
        #   실측 140행이 「미분류」 인데 topic_score=3 이었다. 1차 값이 그대로 남거나
        #   분리 조각이 부모 점수를 물려받은 것이다. 대시보드 점수 필터가 이 행들을
        #   「라벨이 확실한 행」 과 같은 칸에 세운다
        row['topic_score'] = '0'
    has_tee = any(num(row.get(c)) != 0 for c in
                  ('tee_time_score', 'tee_effort_score', 'tee_emotion_score', 'tee_success_score'))
    has_rc = str(row.get('rootcause_problem') or '').strip() not in ('', 'N/A') and num(row.get('rootcause_score')) > 0
    if not has_topic:
        # ★ R17 v4.9 정합 — 「라벨 부재」 와 「판정 실패」 를 가른다 (CP-31)
        #   라벨이 없어 미분류가 됐어도 RootCause 가 살아 있으면 내용은 확인된 행이다.
        #   여기서 Low 를 강제하면 sky 가 승인한 R17 개정이 무력화된다 —
        #   RootCause 를 살려 놓고 대시보드 신뢰도 필터에서 다시 걸러 버린다
        #   ★ Claude Code 도구형 지적 2026-08-16. 실증으로 확인했다
        #   1차 미분류 293행은 전량 RootCause 가 비어 있어 이 분기에 걸리지 않는다.
        #   즉 이 조항은 2차가 채운 행에만 적용된다
        row['confidence_rating'] = 'Medium' if has_rc else 'Low'
    elif has_topic and has_tee and has_rc:
        row['confidence_rating'] = 'Very High'
    elif has_topic and has_tee:
        row['confidence_rating'] = 'High'
    else:
        row['confidence_rating'] = 'Medium'
    for c in ('confidence_cej', 'confidence_inquiry', 'confidence_need_signal',
              'confidence_entity_role', 'confidence_score'):
        if not str(row.get(c) or '').strip():
            row[c] = 'Low'          # 2차가 판정하지 않은 축은 Low 로 둔다
    if not str(row.get('confidence_topic') or '').strip():
        row['confidence_topic'] = 'Low'
    # ★ CP-48 ④ — topic_group 신설 (sky 2026-08-18)
    #   66컬럼 계약에도 1차 71열에도 없던 칸이다. 열린 어휘 topic 을 쓰기로 한 이상
    #   「같은 주제는 같은 워딩 · topic_group 에 반드시 배정」 이 지켜졌는지
    #   번들에서 바로 볼 수 있어야 한다 (topic_registry.json 지켜야 할 두 가지)
    row['topic_group'] = _group_of(topic) if has_topic else '미판정'
    row['voc_total_score'] = str(int(
        num(row.get('topic_score')) + num(row.get('rootcause_score')) +
        sum(num(row.get(c)) for c in ('tee_time_score', 'tee_effort_score',
                                      'tee_emotion_score', 'tee_success_score'))))
    # ★ CP-48 ① — review_required 를 2차 기준으로 다시 찍는다 (sky 2026-08-18)
    #   실측 1,680행 중 Y 가 1,498행(89%) 이었다. 그중 1,383행은 1차 엔진이
    #   찍어 둔 것을 그대로 물려받은 값이다. 1차의 Y 는 「엔진이 자신 없다」 는 뜻인데,
    #   2차가 사람 대신 읽고 나면 그 근거는 사라진다. 89% 가 검수 대상이면
    #   실무자에게는 아무것도 안 알려 준 것과 같다
    #   ★ 여기서는 표시만 하고, 실제 판정은 mark_review() 가 판정 파일을 보고 한다
    return row


# ★ CP-48 ④ — topic → topic_group
_GROUP = {}


def _group_of(topic):
    global _GROUP
    if not _GROUP:
        try:
            g = json.load(open(GROUP_MAP, encoding='utf-8')).get('그룹') or {}
            for grp, labels in g.items():
                for lb in labels:
                    _GROUP[lb] = grp
        except Exception:
            pass
    return _GROUP.get(str(topic or '').strip(), '미판정')


def mark_review(row, reader_flag=False):
    """★ CP-48 ① — 실무자가 정말 봐야 할 행만 Y 로 남긴다 (sky 2026-08-18)

    sky — "review_required 가 너무 많음. 대부분의 voc 에 해당함.
           정말 필요한 것만 되어야 하는데"

    Y 로 남기는 것은 셋뿐이다. 그 외는 전부 N 이다
      ㉠ 판독자가 스스로 「재검토 필요」 라고 낸 행
      ㉡ 라벨은 「미분류」 인데 해석 여지가 있는 행
         ★ 실무자에게 알릴 것은 있는데 자동으로 라벨이 안 붙은 행이다.
           사람이 라벨을 정해 주면 되는 자리다 (sky 2026-08-18 지적)
      ㉢ 라벨을 붙였는데 근거 어휘(topic_evidence)가 원문에 없는 행
         ★ 근거 없이 붙은 라벨이다. 계약 검증 V-0-3 이 잡는 것과 같은 축이다

    why 를 review_reason 에 적는다. 지금까지는 Y 만 있고 이유가 없었다
    """
    topic = str(row.get('topic') or '').strip()
    has_topic = topic not in ('', 'N/A', '미분류')
    rc = str(row.get('rootcause_problem') or '').strip()
    has_room = rc not in ('', 'N/A', '없음', '-')
    ev = str(row.get('topic_evidence') or '').strip()
    src = compact(row.get('voc_cleaned') or row.get('atomic_voc') or
                  row.get('original_voc') or '')
    why = ''
    if reader_flag:
        why = '판독자 자진 신고'
    elif str(row.get('status') or '') == 'scope_excluded':
        why = ''                                   # 제외 행은 볼 것이 없다
    elif not has_topic and has_room:
        why = '해석 여지는 있는데 라벨이 미분류 — 사람이 라벨을 정한다'
    elif has_topic and ev and ev not in ('N/A', '없음') and compact(ev) not in src:
        why = '라벨 근거 어휘가 원문에 없다'
    row['review_required'] = 'Y' if why else 'N'
    row['review_reason'] = why
    return row



def snap_to_source(out_rows):
    """★ CP-50 — 조각 글자를 voc_cleaned 에 도로 맞춘다 (2026-08-18)

    판독자가 voc_cleaned 는 정제해 놓고 atomic_voc 는 원문 그대로 두는 일이 생긴다.
        atomic   "…대참사가 발생했습니다ㅠㅠ"      원문 그대로
        cleaned  "…대참사가 발생했습니다"          ㅠㅠ 를 걷어냈다
        atomic   "@305망해라 사려 했는데…"         멘션이 남았다
        cleaned  "사려 했는데…"
    계약 V-0-3 은 atomic 이 cleaned 의 부분문자열이기를 요구한다.

    내용 판단은 판독자 것이고, 글자를 맞추는 것은 기계가 할 일이다.
      ㉠ 형제 voc_cleaned 를 부모 값으로 통일 (V-0-5)
      ㉡ atomic 이 cleaned 안에 없으면, 겹치는 구간을 찾아 cleaned 쪽 글자로 바꾼다
         ★ difflib 로 맞춰 본다. 공백만 다른 것도 정제로 빠진 것도 같이 풀린다
      ㉢ 겹치는 구간이 원래 길이의 절반도 안 되면 손대지 않는다.
         억지로 자르면 뜻이 바뀐다
    """
    import difflib
    fixed = collections.Counter()

    by_src = collections.defaultdict(list)
    for r in out_rows:
        by_src[str(r.get('source_id') or '')].append(r)
    for sid, sibs in by_src.items():
        if len(sibs) < 2:
            continue
        parent = max((str(s.get('voc_cleaned') or '') for s in sibs), key=len)
        for s in sibs:
            if str(s.get('voc_cleaned') or '') != parent:
                s['voc_cleaned'] = parent
                fixed['V-0-5 형제 cleaned'] += 1

    for r in out_rows:
        a = str(r.get('atomic_voc') or '')
        c = str(r.get('voc_cleaned') or '')
        if not a or not c or a in c:
            continue
        if a.strip().startswith('N/A'):
            continue
        # 공백을 뺀 사본으로 맞추고, 되돌릴 위치를 기억한다
        ci = [k for k, ch in enumerate(c) if not ch.isspace()]
        cn = ''.join(c[k] for k in ci)
        an = re.sub(r'\s+', '', a)
        if not an or not cn:
            continue
        pos = cn.find(an)
        if pos >= 0:
            r['atomic_voc'] = c[ci[pos]:ci[pos + len(an) - 1] + 1]
            fixed['공백만 달랐다'] += 1
            continue
        # 정제로 글자가 빠졌다 — 겹치는 구간을 찾는다
        blocks = [b for b in difflib.SequenceMatcher(None, cn, an, autojunk=False)
                  .get_matching_blocks() if b.size > 0]
        if not blocks:
            fixed['★ 못 찾음 — 손대지 않음'] += 1
            continue
        lo = blocks[0].a
        hi = blocks[-1].a + blocks[-1].size - 1
        covered = sum(b.size for b in blocks)
        if covered * 2 < len(an):
            fixed['★ 겹침이 절반 미만 — 손대지 않음'] += 1
            continue
        r['atomic_voc'] = c[ci[lo]:ci[hi] + 1]
        fixed['정제로 빠진 글자'] += 1

    # ㉠-2 cleaned 가 조각을 다 담지 못하면 원문으로 넓힌다
    #      판독자가 voc_cleaned 를 부모 전체가 아니라 첫 조각까지만 적어 놓는 일이 있다.
    #      그러면 뒤 조각이 cleaned 밖으로 나가 V-0-3 · V-0-4 가 걸린다
    for sid, sibs in by_src.items():
        c = str(sibs[0].get('voc_cleaned') or '')
        o = str(sibs[0].get('original_voc') or '')
        if not o:
            continue
        miss = [s for s in sibs
                if str(s.get('atomic_voc') or '')
                and not str(s.get('atomic_voc')).startswith('N/A')
                and re.sub(r'\s+', '', str(s.get('atomic_voc'))) not in re.sub(r'\s+', '', c)
                and re.sub(r'\s+', '', str(s.get('atomic_voc'))) in re.sub(r'\s+', '', o)]
        if miss:
            for s in sibs:
                s['voc_cleaned'] = o
            fixed['cleaned 를 원문으로 넓힘'] += 1

    # ㉢-1 지시어가 본문 자리에 새어 든 것 — "structure.merge" 같은 토큰이다
    #      판독자가 병합을 적는 칸과 본문 칸을 헷갈린 것이다
    drop = []
    for r in out_rows:
        a = str(r.get('atomic_voc') or '').strip()
        if not (a.startswith('structure.') or a in ('merge', 'split')):
            continue
        if len(by_src.get(str(r.get('source_id') or ''), [])) > 1:
            # 형제가 있으면 이 행은 병합 지시가 행으로 새어 든 허깨비다. 지운다
            drop.append(id(r))
            fixed['지시어 행 삭제'] += 1
        else:
            r['atomic_voc'] = str(r.get('voc_cleaned') or '')
            fixed['지시어가 본문에 샘'] += 1
    if drop:
        keep = [r for r in out_rows if id(r) not in set(drop)]
        out_rows[:] = keep
        by_src = collections.defaultdict(list)
        for r in out_rows:
            by_src[str(r.get('source_id') or '')].append(r)

    # ㉢-2 조각이 하나뿐인 행은 atomic 이 곧 cleaned 다
    #      멘션만 남거나("@R카랑이 설거지" 대 "설거지"),
    #      cleaned 는 채웠는데 atomic 이 "N/A (분석 제외)" 로 남은 것들이다.
    #      ★ 나눌 것이 없는 행이라 발췌를 고민할 여지가 없다
    for sid, sibs in by_src.items():
        if len(sibs) != 1:
            continue
        r = sibs[0]
        a, c = str(r.get('atomic_voc') or ''), str(r.get('voc_cleaned') or '')
        if c and a != c and a not in c:
            r['atomic_voc'] = c
            fixed['조각 하나 — cleaned 로'] += 1

    # ㉢-3 형제끼리 status · scope_exclusion_reason 도 같아야 한다 (V-0-5)
    for sid, sibs in by_src.items():
        if len(sibs) < 2:
            continue
        for col in ('status', 'scope_exclusion_reason'):
            vals = [str(s.get(col) or '') for s in sibs]
            if len(set(vals)) < 2:
                continue
            keep = collections.Counter(v for v in vals if v).most_common(1)[0][0]
            for s in sibs:
                if str(s.get(col) or '') != keep:
                    s[col] = keep
                    fixed['V-0-5 형제 ' + col] += 1

    # ㉣ 분리 조각이 뒤 단계를 안 거쳤을 때 — Enum 은 빈칸을 못 받는다 (V-0-2)
    #    1차가 「해당 없음」 을 어떻게 적는지 그대로 따른다.
    #    ★ 값을 지어내는 것이 아니라 「없다」 를 규정된 말로 적는 것이다
    BLANK_OK = {'cej': '해당없음', 'entity_role': 'product_brand',
                'inquiry_type': 'none', 'need_signal_type': 'none',
                'inquiry_flag': 'N', 'need_signal_flag': 'N'}
    for r in out_rows:
        for col, dflt in BLANK_OK.items():
            if not str(r.get(col) or '').strip():
                r[col] = dflt
                fixed['V-0-2 Enum 빈칸'] += 1

    # ㉤ voc_residual 을 다시 계산한다 (V-0-4 atomic+residual 보존 · V-0-5 형제 일치)
    #    residual = cleaned 에서 형제 조각들이 덮지 못한 나머지다.
    #    ★ 조각 글자를 위에서 손봤으니 residual 도 다시 재야 앞뒤가 맞는다
    #      조각이 겹치는 것은 정상이다 (부록 §2.2 공유 반응). 덮인 자리로만 센다
    for sid, sibs in by_src.items():
        c = max((str(s.get('voc_cleaned') or '') for s in sibs), key=len)
        if not c:
            continue
        covered = [False] * len(c)
        for s in sibs:
            a = str(s.get('atomic_voc') or '')
            if not a or a.startswith('N/A'):
                continue
            k = c.find(a)
            if k >= 0:
                for i in range(k, k + len(a)):
                    covered[i] = True
        rest = ''.join(ch for ch, cv in zip(c, covered) if not cv).strip()
        for s in sibs:
            if str(s.get('voc_residual') or '') != rest:
                s['voc_residual'] = rest
                fixed['residual 다시 계산'] += 1

    seen = set()
    for r in out_rows:
        aid = str(r.get('atomic_id') or '')
        if aid and aid not in seen:
            seen.add(aid)
            continue
        sid = str(r.get('source_id') or '')
        n = 1
        while f"{sid}-{n:02d}" in seen:
            n += 1
        r['atomic_id'] = f"{sid}-{n:02d}"
        seen.add(r['atomic_id'])
        fixed['V-0-1 조각 id'] += 1

    for k, v in sorted(fixed.items()):
        print('  되돌림  %-28s %d' % (k, v))
    return out_rows


def build_xlsx(outdir, prod):
    """1차 동결본의 export_bundle.py 를 그대로 호출해 6시트를 만들고,
    2차 수정로그 시트를 뒤에 붙인다. 1차 코드를 수정하지 않는다."""
    import pandas as pd
    # ★ 1차 엔진이 있는 자리. 없는 컴퓨터에서는 xlsx 만 못 만들고 나머지는 돈다
    for _cand in (os.environ.get('VOC_ENGINE'),
                  os.path.join(ROOT, 'engine')):
        if _cand and os.path.isdir(_cand):
            sys.path.insert(0, _cand)
            break
    from src.dashboard60.export_bundle import write_export_bundle

    # 정본 §0-2 — "N/A" 를 결측치로 읽지 않는다
    frame = pd.read_csv(os.path.join(outdir, 'raw_voc.csv'),
                        keep_default_na=False, na_values=[], dtype=str)
    xlsx = os.path.join(outdir, 'voc_dashboard_export_bundle_2차시험본.xlsx')
    write_export_bundle(frame, xlsx)

    # 2차 시트 추가
    extra = [
        ('수정로그_오류확정',   '수정로그_오류확정.csv'),
        ('수정로그_재검토필요', '수정로그_재검토필요.csv'),
        ('분리제안',           '분리제안.csv'),
        ('기준서개정후보',      '기준서개정후보.csv'),
        ('구조적결함',         '구조적결함.csv'),
        ('판정불일치',         '판정불일치.csv'),
    ]
    added = []
    with pd.ExcelWriter(xlsx, engine='openpyxl', mode='a',
                        if_sheet_exists='replace') as wr:
        for sheet, fname in extra:
            fp = os.path.join(outdir, fname)
            if not os.path.exists(fp):
                continue
            # ★ 0건이어도 시트를 만든다. 머리글만 있는 빈 시트가 곧 "0건" 이라는 증거다
            df = pd.read_csv(fp, keep_default_na=False, na_values=[], dtype=str)
            df.to_excel(wr, sheet_name=sheet[:31], index=False)
            added.append((sheet, len(df)))
    return xlsx, added


PAIR_SPLIT = {'status': 'scope_exclusion_reason'}


def normalize_paired(judgments):
    """한 칸에 붙여 쓴 짝필드를 두 finding 으로 나눈다.

    판독자가 status 에 "scope_excluded / channel_feedback" 처럼 값과 사유를
    슬래시로 붙여 쓰는 일이 있다. 값을 버리지 않고 살려서 나눈다.
    ★ 임시 보정이다. check_submission.py 게이트에서는 그대로 반려된다.
    """
    fixed = []
    for j in judgments:
        out = []
        for f in j.get('findings') or []:
            fld, prop = f.get('field', ''), str(f.get('proposed', ''))
            mate = PAIR_SPLIT.get(fld)
            if mate and '/' in prop:
                head, _, tail = prop.partition('/')
                head, tail = head.strip(), tail.strip()
                if head and tail:
                    out.append({**f, 'proposed': head})
                    out.append({**f, 'field': mate, 'proposed': tail,
                                'current': '', 'reason': f.get('reason', '')})
                    fixed.append((j.get('atomic_id', ''), fld, prop))
                    continue
            out.append(f)
        if out:
            j['findings'] = out
    return fixed


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    # ★ 판정 파일을 여러 개 받는다 (CP-45).
    #   회차마다 번들이 따로 나오면 14개가 생긴다. 최종은 하나여야 한다
    #     python build_bundle.py "_결과/판독결과_full_*.md" --xlsx --out 최종
    jpaths = []
    for a in sys.argv[1:]:
        if a.startswith('--'):
            continue
        if any(ch in a for ch in '*?'):
            import glob as _g
            jpaths += sorted(_g.glob(a))
        elif a.endswith('.md'):
            jpaths.append(a)
    if not jpaths:
        print('판정 파일이 없다')
        sys.exit(1)
    jpath = jpaths[0]
    # ★ 박아 두면 새 PC 에서 KeyError 로 멈춘다 (2026-08-23).
    #   앉아 있는 데이터에서 고른다. 하나뿐이면 그것이 답이다.
    if not PRODUCTS:
        print('판독할 데이터가 없습니다 — 먼저 데이터_넣기.py 로 앉히십시오')
        sys.exit(1)
    prod = PRODUCTS[0]
    apply_mode = '--apply' in sys.argv
    if '--product' in sys.argv:
        prod = sys.argv[sys.argv.index('--product') + 1]

    judgments = []
    for jp in jpaths:
        judgments += read_judgments(jp)
    if len(jpaths) > 1:
        print('  판정 파일 %d개를 합쳐 읽었다 · 판정 %d행' % (len(jpaths), len(judgments)))
    fixed = normalize_paired(judgments)
    if fixed:
        print('  형식 보정 %d건 — 한 칸에 붙여 쓴 짝필드를 두 finding 으로 나눴다' % len(fixed))
        for a, fld, v in fixed[:6]:
            print('     %-44s %s = %s' % (a[:44], fld, v))
    if prod == 'all':
        # 제품군이 섞인 배치 — 3개 데이터셋을 합쳐 읽는다
        rows, hdr, seen_ids = [], None, set()
        for p in PRODUCTS:
            rs, h = read_csv(SRC[p])
            if hdr is None:
                hdr = h
            for r in rs:
                if r['atomic_id'] not in seen_ids:
                    seen_ids.add(r['atomic_id'])
                    rows.append(r)
    else:
        rows, hdr = read_csv(SRC[prod])
    base_cols = [c for c in hdr if c not in SEC_COLS + NEW_COLS]   # 66컬럼
    by_id = {r['atomic_id']: r for r in rows}

    # ★ 판독자마다 폴더를 나눈다. 한 폴더에 쓰면 다른 판독자 번들을 덮어쓴다
    stem = re.sub(r'^판독결과_', '', os.path.splitext(os.path.basename(jpath))[0])
    if '--out' in sys.argv:
        outdir = os.path.join(os.path.dirname(jpath),
                              sys.argv[sys.argv.index('--out') + 1])
    else:
        outdir = os.path.join(os.path.dirname(os.path.abspath(jpath)), 'bundle_' + stem)
    os.makedirs(outdir, exist_ok=True)

    err_log, rev_log, split_log, gap_log, defect_log = [], [], [], [], []
    judged = {}

    for j in judgments:
        aid = j['atomic_id']
        # ★ CP-51 — 같은 행에 판정이 둘이면 합친다 (2026-08-18)
        #   회차를 나눠 돌리면 한 atomic_id 에 판정이 두 번 온다.
        #   재분류 회차는 앞 회차 결과를 보고 「바뀐 칸만」 낸다.
        #   덮어쓰면 앞 회차가 낸 status=scope_excluded 같은 것이 사라진다.
        #   ★ 실측 316행이 그렇게 제외에서 풀려 버렸다
        old = judged.get(aid)
        if old is not None:
            seen = {f.get('field') for f in (j.get('findings') or [])}
            keep = [f for f in (old.get('findings') or []) if f.get('field') not in seen]
            j = dict(j)
            j['findings'] = keep + list(j.get('findings') or [])
            if not (j.get('structure') or {}).get('segments') and (old.get('structure') or {}).get('segments'):
                j['structure'] = old['structure']
        judged[aid] = j
        src = by_id.get(aid)
        orig = (src or {}).get('original_voc', '')

        for f in j.get('findings', []):
            rec = {
                'source_id': j.get('source_id', ''),
                'atomic_id': aid,
                'atomic_voc': j.get('atomic_voc', ''),
                'field': f.get('field', ''),
                '원본값': f.get('current', ''),
                '제안값': f.get('proposed', ''),
                '사유': f.get('reason', ''),
                '근거인용': f.get('quote', ''),
                '오류유형': f.get('error_type', ''),
            }
            v = f.get('verdict', '')
            if v == '오류':
                rec['승인상태'] = ''
                err_log.append(rec)
            elif v == '재검토 필요':
                # ★ 승인상태를 반드시 함께 낸다.
                #   apply_approved.py 가 수정로그 2종 모두에서 [승인상태] 를 읽는다.
                #   이 칸이 없으면 재검토 건은 sky 가 승인해도 반영될 길이 없다
                #   (CP-29 · Claude Code 도구형 지적으로 발견)
                rec['승인상태'] = ''
                rec['원문'] = orig
                rec['왜 애매한지'] = f.get('reason', '')
                rev_log.append(rec)

        st = j.get('structure', {})
        if st.get('split'):
            for seg in st.get('segments', []):
                split_log.append({
                    'source_id': j.get('source_id', ''),
                    'origin_atomic_id': aid,
                    'segment_index': seg.get('index', ''),
                    'atomic_voc': seg.get('atomic_voc', ''),
                    'topic': seg.get('topic', ''),
                    'topic_evidence': seg.get('topic_evidence', ''),
                    'topic_score': seg.get('topic_score', ''),
                    'cej': seg.get('cej', ''),
                    'entity_role': seg.get('entity_role', ''),
                    'confidence_topic': seg.get('confidence_topic', ''),
                    'preservation_check': st.get('preservation_check', ''),
                    'rationale': st.get('rationale', ''),
                    '승인상태': '사람 최종 승인 대기',
                })
        if st.get('merge_with'):
            split_log.append({
                'source_id': j.get('source_id', ''), 'origin_atomic_id': aid,
                'segment_index': 'MERGE', 'atomic_voc': st.get('merge_with', ''),
                'topic': '', 'topic_evidence': '', 'topic_score': '', 'cej': '',
                'entity_role': '', 'confidence_topic': '',
                'preservation_check': '', 'rationale': st.get('rationale', ''),
                '승인상태': '사람 최종 승인 대기',
            })

        if j.get('criteria_uncovered'):
            gap_log.append({'atomic_id': aid, 'atomic_voc': j.get('atomic_voc', ''),
                            '내용': j['criteria_uncovered']})
        if j.get('structural_defect'):
            defect_log.append({'atomic_id': aid, '원인': j['structural_defect']})

    # ---- raw_voc 생성 -----------------------------------------------------
    out_rows = []
    split_applied = 0
    for r in rows:
        aid = r['atomic_id']
        j = judged.get(aid)
        base = {c: r.get(c, '') for c in base_cols}
        sec = {c: r.get(c, '') for c in SEC_COLS}
        qc = {c: '' for c in QC_COLS}

        if not j:
            out_rows.append({**base, **sec, **qc})
            continue

        qc['qc_verdict'] = j.get('verdict', '')
        qc['qc_finding_count'] = len(j.get('findings', []))
        qc['qc_criteria_uncovered'] = j.get('criteria_uncovered', '')
        qc['qc_structural_defect'] = j.get('structural_defect', '')
        for f in j.get('findings', []):
            if f.get('field') == 'entity_role':
                qc['qc_entity'] = f.get('proposed', '')
        sec['qc_status_summary'] = j.get('verdict', '')
        sec['qc_rule_ids'] = 'A/B/C/D'

        st = j.get('structure', {})
        if apply_mode and st.get('split') and st.get('segments'):
            # 분리 반영 — 조각마다 행 생성
            segs = st['segments']
            # ★ 부록 §4.4 — voc_residual 은 source 단위로 재계산한다.
            #   조각이 원문 일부만 덮으면 남는 부분이 잔여다.
            #   이전 판은 SOURCE_LEVEL 복사만 해서 잔여 span 이 사라졌다
            #   (2026-08-15 Claude Code 도구형 발견 · CP-24)
            body = r.get('atomic_voc', '') or ''
            rest, pos = [], 0
            for seg in segs:
                s = seg.get('atomic_voc', '') or ''
                k = body.find(s, pos) if s else -1
                if k < 0:
                    continue
                if k > pos:
                    rest.append(body[pos:k])
                pos = k + len(s)
            if pos < len(body):
                rest.append(body[pos:])
            residual = ' '.join(x.strip() for x in rest if x.strip())

            for i, seg in enumerate(segs, 1):
                nr = {c: '' for c in base_cols}
                for c in SOURCE_LEVEL:
                    if c in nr:
                        nr[c] = r.get(c, '')
                # ★ source 안에서 아직 안 쓴 번호를 찾아 매긴다 (CP-46).
                #   전에는 무조건 -01 부터 다시 세서, 같은 source 의 다른 행을
                #   나누면 조각 id 가 겹쳤다. 회차별 번들에서는 안 드러나고
                #   14회차를 합칠 때 V-0-1 duplicate 19건으로 터졌다
                sid_ = r.get('source_id', '')
                seq = _seg_seq.setdefault(sid_, 0) + 1
                while f"{sid_}-{seq:02d}" in _used_ids:
                    seq += 1
                _seg_seq[sid_] = seq
                nr['atomic_id'] = f"{sid_}-{seq:02d}"
                _used_ids.add(nr['atomic_id'])
                nr['atomic_index'] = str(seq)
                nr['atomic_voc'] = seg.get('atomic_voc', '')
                for k, v in seg.items():
                    if k in nr and k not in ('index',):
                        nr[k] = v
                if 'voc_residual' in nr:
                    nr['voc_residual'] = residual
                # ★ 엔진의 원래 trace 를 지우지 않는다. 앞에 split_from 만 덧붙인다
                #   이전 판은 통째로 대체해 e2_multilabel_after_split 등이 사라졌다
                nr['trace_summary'] = ' | '.join(
                    x for x in (f"split_from: {aid}", (r.get('trace_summary') or '').strip()) if x)
                for c in ('topic_score', 'tee_time_score', 'tee_effort_score',
                          'tee_emotion_score', 'tee_success_score', 'rootcause_score'):
                    if not str(nr.get(c) or '').strip():
                        nr[c] = '0'
                # ★ CP-49 — CP-48 ② 를 되돌린다 (2026-08-18)
                #   조각의 voc_cleaned 를 조각 자신으로 바꿨더니 계약 V-0-5
                #   「형제 voc_cleaned 일치」 가 86건 깨졌다.
                #   설계가 맞다 — voc_cleaned 는 부모 댓글의 정제본이고 형제가 공유한다.
                #   atomic_voc 는 그 안에서 잘라낸 발췌라 부분문자열이어야 한다 (V-0-3).
                #   sky 가 본 「cleaned 는 쿠쿠, atomic 은 타공」 은 어긋난 것이 아니라
                #   한 댓글에 두 주제가 들어 있어서 그렇게 보인 것이다
                compute_derived(nr)
                ns = dict(sec)
                ns['split_origin_atomic_id'] = aid
                ns['secondary_topic_source'] = 'secondary_read'
                mark_review(nr, reader_flag=(j.get('verdict') == '재검토 필요'))
                out_rows.append({**nr, **ns, **qc})
            split_applied += 1
            continue

        if apply_mode:
            changed = False
            for f in j.get('findings', []):
                fld, prop, v = f.get('field'), f.get('proposed', ''), f.get('verdict')
                if v == '오류' and prop and fld in base:
                    base[fld] = prop
                    sec['secondary_topic_source'] = 'secondary_read'
                    changed = True
            if changed:
                # ★ 값이 바뀌었으면 파생값을 다시 계산한다 (정본 §7.10)
                #   이전 판에서는 분리 생성 행에만 호출해, topic·TEE·RC 를 다 채운 행이
                #   confidence_rating=Low · voc_total_score=0 으로 남았다.
                #   대시보드가 신뢰도로 거르므로 채운 값이 화면에서 사라진다.
                #   2026-08-15 Claude Code 도구형 판독자가 발견 (CP-22)
                keep_rr = base.get('review_required', '')
                compute_derived(base)
                base['review_required'] = keep_rr      # 분리 행이 아니면 Y 로 덮지 않는다

        mark_review(base, reader_flag=(j.get('verdict') == '재검토 필요'))
        out_rows.append({**base, **sec, **qc})

    # ★ CP-48 — 판정을 거치지 않은 행에도 같은 잣대를 댄다
    #   그러지 않으면 「이번 회차에 안 걸린 행」 만 1차의 Y 를 그대로 달고 남는다
    for _r in out_rows:
        _t = str(_r.get('topic') or '').strip()
        if _t in ('', 'N/A', '미분류'):
            _r['topic_score'] = '0'          # ★ CP-48 ③ 라벨이 없으면 점수도 없다
            _r['topic_group'] = '미판정'
        else:
            _r['topic_group'] = _group_of(_t)
        if not str(_r.get('review_reason') or '').strip():
            mark_review(_r)

    # ★ CP-50 — 계약 검증에 넣기 전에 글자를 원문에 맞춘다
    snap_to_source(out_rows)

    # ---- 계약 검증 — 1차 공식 검증기를 그대로 쓴다 ----------------------
    pres = []
    try:
        for _cand in (os.environ.get('VOC_CONTRACTS'), ROOT):
            if _cand and os.path.isdir(_cand):
                sys.path.insert(0, _cand)
        from src.voc_secondary import contracts
        if os.path.exists(SECONDARY_TOPICS):
            ext = json.load(open(SECONDARY_TOPICS, encoding='utf-8')).get('확장 라벨') or {}
            if ext and 'topic' in contracts.ENUM_COLUMNS:
                contracts.ENUM_COLUMNS['topic'] = set(contracts.ENUM_COLUMNS['topic']) | set(ext)
        # 2차 확장 Enum (topic 외) — check_submission.py 와 같은 방식으로 합친다 (CP-33)
        #   ★ SECONDARY_ENUMS 상수만 있고 병합이 빠져 있었다. 게이트는 business_signal 을
        #     통과시키는데 여기 계약 검증만 V-0-2 enum_violation 으로 반려했다
        #     (2026-08-17 labelA01 판독에서 발견)
        if os.path.exists(SECONDARY_ENUMS):
            for col, vals in (json.load(open(SECONDARY_ENUMS, encoding='utf-8'))
                              .get('확장 Enum') or {}).items():
                if col in contracts.ENUM_COLUMNS:
                    contracts.ENUM_COLUMNS[col] = set(contracts.ENUM_COLUMNS[col]) | set(vals)
        validate_contract = contracts.validate_contract
        chk = validate_contract([{c: r.get(c, '') for c in base_cols} for r in out_rows], base_cols)
        for name, res in chk['checks'].items():
            if res['violations']:
                pres.append({'check': name, 'violations': res['violations'],
                             'detail': json.dumps(res['details'][:3], ensure_ascii=False)})
        contract_ok = not chk['fatal'] and not pres
    except Exception as exc:
        pres.append({'check': 'IMPORT_FAIL', 'violations': -1, 'detail': str(exc)})
        contract_ok = None

    # ---- 출력 -------------------------------------------------------------
    all_cols = base_cols + SEC_COLS + NEW_COLS + QC_COLS
    raw_path = os.path.join(outdir, 'raw_voc.csv')
    with open(raw_path, 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=all_cols)
        w.writeheader()
        for r in out_rows:
            w.writerow({c: r.get(c, '') for c in all_cols})

    # 0건일 때도 머리글만 있는 파일을 남긴다.
    # ★ 파일·시트가 아예 없으면 "0건인지 스크립트가 안 돌았는지" 구분이 안 된다
    #   (2026-08-15 sky 지적 · CP-22)
    EMPTY_COLS = {
        '수정로그_오류확정':   ['source_id', 'atomic_id', 'atomic_voc', 'field',
                            '원본값', '제안값', '사유', '근거인용', '오류유형', '승인상태'],
        # ★ 실제 레코드 키와 정확히 같아야 한다. 비었을 때와 있을 때 열이 다르면
        #   대시보드·승인 도구가 시트를 못 읽는다 (CP-29)
        '수정로그_재검토필요': ['source_id', 'atomic_id', 'atomic_voc', 'field',
                            '원본값', '제안값', '사유', '근거인용', '오류유형',
                            '승인상태', '원문', '왜 애매한지'],
        '분리제안':          ['source_id', 'atomic_id', 'atomic_voc', '조각수',
                            '조각', 'topic', '보존식', '사유'],
        '기준서개정후보':     ['atomic_id', 'atomic_voc', '미커버 사유'],
        '구조적결함':        ['atomic_id', '원인'],
        '판정불일치':        ['atomic_id', '행 verdict', 'findings 최고 심각도', 'findings'],
    }

    def dump(name, recs):
        p = os.path.join(outdir, name + '.csv')
        if not recs:
            cols = EMPTY_COLS.get(name, ['(해당 없음)'])
            with open(p, 'w', encoding='utf-8-sig', newline='') as h:
                csv.DictWriter(h, fieldnames=cols).writeheader()
            return 0
        cols = list(recs[0].keys())
        with open(p, 'w', encoding='utf-8-sig', newline='') as h:
            w = csv.DictWriter(h, fieldnames=cols)
            w.writeheader()
            for r in recs:
                w.writerow(r)
        return len(recs)

    n_err = dump('수정로그_오류확정', err_log)
    n_rev = dump('수정로그_재검토필요', rev_log)
    n_spl = dump('분리제안', split_log)
    n_gap = dump('기준서개정후보', gap_log)
    n_def = dump('구조적결함', defect_log)

    # ---- 정확도 (정본 §11-1) ----------------------------------------------
    N = len(judgments)
    n_e = sum(1 for j in judgments if j.get('verdict') == '오류')
    n_r = sum(1 for j in judgments if j.get('verdict') == '재검토 필요')

    # 행 verdict 와 findings verdict 의 정합성
    RANK = {'정상': 0, '기준서 미커버': 1, '재검토 필요': 2, '오류': 3}
    mismatch = []
    for j in judgments:
        fs = [f.get('verdict', '') for f in j.get('findings', [])]
        top = max([RANK.get(v, 0) for v in fs], default=0)
        row = RANK.get(j.get('verdict', ''), 0)
        # ★ 정당한 예외 — 부록 §3-6-2 (CP-37)
        #   담을 라벨이 없어 기타(제품군) 으로 보낼 때는
        #     finding verdict = 오류        (값을 실제로 반영시키려면 이것이어야 한다)
        #     행    verdict = 기준서 미커버   (기준서개정후보 시트로 간다)
        #   두 층이 다른 것을 가리키므로 불일치가 아니다.
        #   이 예외가 없으면 규칙을 지킨 판독이 매번 판정불일치로 잡힌다
        #   (labelA02 에서 Codex 10건 · Claude Code 3건이 이렇게 잡혔다)
        if j.get('verdict') == '기준서 미커버' and top == RANK['오류']:
            continue
        if fs and row != top:
            inv = {v: k for k, v in RANK.items()}
            mismatch.append({'atomic_id': j['atomic_id'],
                             '행 verdict': j.get('verdict', ''),
                             'findings 최고 심각도': inv[top],
                             'findings': ' / '.join(fs)})
    dump('판정불일치', mismatch)      # 0건이어도 머리글 시트를 남긴다
    lenient = (N - n_e) / N * 100 if N else 0
    conservative = (N - n_e - n_r) / N * 100 if N else 0

    # topic 단독 오판정률 — 1차 종료기준(35.5%)과 같은 잣대
    def is_topic_field(name):
        s = str(name or '').lower()
        return 'topic' in s and 'score' not in s and 'evidence' not in s

    topic_err = topic_any = 0
    for j in judgments:
        tf = [f for f in j.get('findings', []) if is_topic_field(f.get('field'))]
        if tf:
            topic_any += 1
            if any(f.get('verdict') == '오류' for f in tf):
                topic_err += 1

    # 필드별 지적 분포 — 개선 우선순위 판단용
    fld = collections.Counter()
    for j in judgments:
        for f in j.get('findings', []):
            fld[str(f.get('field', '')).split('/')[0].strip()] += 1

    summary = {
        '생성': datetime.datetime.now().isoformat(timespec='seconds'),
        '판정파일': os.path.basename(jpath),
        '제품군': prod,
        '모드': 'apply(반영)' if apply_mode else 'propose(제안만)',
        '판정 행': N,
        '오류': n_e, '재검토 필요': n_r,
        '정상': sum(1 for j in judgments if j.get('verdict') == '정상'),
        '기준서 미커버': sum(1 for j in judgments if j.get('verdict') == '기준서 미커버'),
        '① 행단위 관대(%)': round(lenient, 2),
        '① 행단위 보수(%)': round(conservative, 2),
        '② topic 오판정률(%)': round(topic_err / N * 100, 2) if N else 0,
        '  topic 지적 행': topic_any,
        '  1차 종료기준 비교': 'topic 오판정률 35.5% (40건 표본)',
        '필드별 지적': dict(fld.most_common()),
        'raw_voc 행': len(out_rows),
        '원본 행': len(rows),
        '분리 반영': split_applied,
        '수정로그_오류확정': n_err, '수정로그_재검토필요': n_rev,
        '분리제안': n_spl, '기준서개정후보': n_gap, '구조적결함': n_def,
        '계약 검증': ('통과' if contract_ok else ('실패' if contract_ok is False else '미확인')),
        'row-finding 불일치': len(mismatch),
    }
    with open(os.path.join(outdir, 'summary.json'), 'w', encoding='utf-8') as h:
        json.dump(summary, h, ensure_ascii=False, indent=2)
    if pres:
        dump('계약위반', pres)
    if mismatch:
        dump('판정불일치', mismatch)

    xlsx_info = None
    if '--xlsx' in sys.argv:
        try:
            xp, added = build_xlsx(outdir, prod)
            xlsx_info = (xp, added)
        except Exception as exc:
            xlsx_info = ('실패: %s: %s' % (type(exc).__name__, exc), [])

    print('출력:', outdir)
    for k, v in summary.items():
        print('  %-18s %s' % (k, v))
    if pres:
        print('  ★ 계약 위반', len(pres), '건 — 계약위반.csv 확인')
    if xlsx_info:
        print()
        if xlsx_info[1] or str(xlsx_info[0]).endswith('.xlsx'):
            print('  xlsx:', os.path.basename(str(xlsx_info[0])))
            for sh, n in xlsx_info[1]:
                print('     + %-18s %d행' % (sh, n))
        else:
            print('  ★ xlsx', xlsx_info[0])
    if mismatch:
        print('  ★ row-finding 불일치', len(mismatch), '건 — 판정불일치.csv 확인')
        for m in mismatch:
            print('     %s  행=%s  findings=%s' % (m['atomic_id'][:40], m['행 verdict'], m['findings']))


if __name__ == '__main__':
    main()
