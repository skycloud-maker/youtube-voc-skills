"""내가 되풀이한 실수를 기계가 잡는다 — 눈으로 확인하는 자리를 없앤다.

sky 2026-08-18 — "언제까지 당신의 실수로 작업 오류를 일으킬 거예요?
                  이제 그간 쌓인 오류만 정리해도 방지가 될 것 같은데"

★ 이 파일은 계속 자란다. 새 실수가 나오면 여기에 검사를 하나 더 붙인다.
  고칠 때마다 「무엇을 잘못 봤는지」 를 주석에 남긴다. 그래야 같은 걸 또 안 짠다

쓰기
    python check_selfcheck.py                       번들 + 판정 파일 전부
    python check_selfcheck.py <번들폴더>              그 번들만
"""
from __future__ import annotations

import collections, csv, glob, json, os, re, sys, time

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)

# ── 대장 폴더가 자리마다 이름이 다르다 (2026-11-05 · 결정 1 · sky 「1번 ㄱ」) ──────────
#   ★ 무엇이 있었나 — 2026-11-05 한 줄 흐름을 끝까지 돌려 보니, 판독자 둘(claude · codex)이
#     **각자 `s9_group → 대장` 바로가기(정션)를 만들어야** 판독이 돌아갔다. 도구가 `s9_group/`
#     만 보는데 판독·감독 꾸러미에 실리는 자리 이름은 `대장/` 이기 때문이다 (꾸러미.py 의 목록).
#   ★ 2026-10-29 에 고른 길은 「이름 대응을 **안내문에** 적는다」 였다. 안내문만으로는
#     **사람은 알아도 도구는 못 찾는다.** 그래서 도구가 스스로 찾게 한다.
#   ★ 사본을 만들지 않는다 — **찾는 자리를 하나 늘릴 뿐**이다 (공통 규칙 6 · 같은 것이 두 벌).
#     총괄 자리에서는 폴더 이름이 진짜 `s9_group` 이라 그 이름도 그대로 본다.
def 대장자리(*이름: str) -> str:
    """대장 파일의 자리 — 판독·감독 폴더는 `대장/`, 총괄 자리는 `s9_group/` 이다."""
    # ★ 순서가 중요하다 — `s9_group` 이 **먼저**다. 2026-11-05 에 거꾸로 했다가 얼린 2차 기준
    #   시험 둘이 떨어졌다 (`topic_group` 값 다름 · `계약위반.csv` 다름). 2판 판독 폴더를
    #   되살려 돌리는 그 시험에는 **둘 다 있다** — `대장/` 은 꾸러미가 깐 **처음 상태**이고
    #   `s9_group/` 은 **판독자가 판독하며 갱신한 살아 있는 대장**이다. `대장` 을 먼저 보면
    #   판독자가 갱신한 것을 버린다. 이 순서라야 **전에 되던 자리가 하나도 안 바뀌고**,
    #   `s9_group` 이 아예 없는 새 판독 폴더에서만 `대장` 으로 간다 — 늘리기만 하는 것이다.
    for 폴더 in ("s9_group", "대장"):
        q = os.path.join(BASE, 폴더, *이름)
        if os.path.exists(q):
            return q
    # 둘 다 없다 — 옛 이름으로 돌려준다. 열리지 않으면 **그 자리에서 크게 실패해야 한다**
    return os.path.join(BASE, "s9_group", *이름)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

NOT = ('', 'N/A', '없음', '-', '미분류', '판단 불가', '제안값 없음')
FREE = ['rootcause_problem', 'topic_evidence', 'atomic_voc_summary',
        'tee_summary', 'cej_evidence', 'topic_provisional']

# ★ 2026-08-18 — S-1 이 오탐한 칸. 여기는 「등급·사유」 를 적는 자리라 반복이 정상이다
#   rootcause_summary  CC "L2 — 문제와 개선 대상은 있으나 원인 서술은 원문에 없다" 121회
#                      Codex "N/A(topic=미분류: RootCause 미부여)" 94회
#   ★ 둘 다 판정 결과를 규정된 말로 적은 것이지 서술을 베낀 것이 아니다
#   검사기도 틀린다. 틀렸을 때는 실물을 뽑아 보고 여기에 적어 둔다
GRADE_LIKE = ['rootcause_summary', 'scope_exclusion_reason', 'na_class']

fails: list[str] = []
warns: list[str] = []


def bad(msg):
    fails.append(msg)
    print('  ✗ %s' % msg)


def warn(msg):
    warns.append(msg)
    print('  ! %s' % msg)


def ok(msg):
    print('  · %s' % msg)


# ─────────────────────────────────────────────────────────────────────
# S-1  틀 찍기
# ─────────────────────────────────────────────────────────────────────
def strip_shell(s):
    """문장에서 「그 행에만 있는 부분」 을 걷어내고 뼈대만 남긴다.

    ★ 내가 두 번 속은 자리다 (2026-08-18)
      1차  통짜 문자열로 고유비율을 재서 100% 로 읽었다.
           실제로는 앞에 원문 인용을 붙였을 뿐 뒷문장은 36종이었다
      2차  공백을 무시하고 부분문자열을 봐서 계약 위반을 통과시켰다
    그래서 여기서는 인용·따옴표·숫자·라벨 이름을 다 걷어내고 뼈대만 비교한다
    """
    s = str(s or '')
    s = re.sub(r'[「『"\'“‘].*?[」』"\'”’]', '§', s)   # 인용 통째로
    s = re.sub(r'\d+', '#', s)
    s = re.sub(r'\s+', '', s)
    return s


def check_templates(rows, label):
    """자유서술 칸이 틀로 찍혔는가."""
    print('\n[S-1] 틀 찍기 — %s' % label)
    for f in FREE:
        v = [str(r.get(f) or '').strip() for r in rows]
        v = [x for x in v if x not in NOT]
        if len(v) < 20:
            continue
        skel = [strip_shell(x) for x in v]
        skel = [x for x in skel if x]
        if not skel:
            continue
        u = len(set(skel))
        pct = 100 * u / len(skel)
        top = collections.Counter(skel).most_common(1)[0]
        line = '%-20s %4d개 · 뼈대 고유 %3d (%2.0f%%)' % (f, len(v), u, pct)
        if f in GRADE_LIKE:
            ok(line + '   (등급 칸 — 반복이 정상)')
            continue
        if pct < 50:
            bad('%s   ★ 틀 — 한 뼈대가 %d회' % (line, top[1]))
        elif pct < 75:
            warn('%s   한 뼈대가 %d회' % (line, top[1]))
        else:
            ok(line)


# ─────────────────────────────────────────────────────────────────────
# S-2  판정 파일이 아직 쓰이는 중인가
# ─────────────────────────────────────────────────────────────────────
def check_fresh(paths, secs=60):
    """★ 2026-08-18 — CC 파일을 쓰는 중에 읽고 「25행에서 멈췄다」 고 보고했다.
    실제로는 114행이었다. mtime 이 방금이면 아직 쓰는 중일 수 있다"""
    print('\n[S-2] 판정 파일이 안정됐는가')
    now = time.time()
    hot = [p for p in paths if now - os.path.getmtime(p) < secs]
    if hot:
        for p in hot:
            warn('%s — %.0f초 전에 쓰였다. 다 쓰였는지 확인하고 읽어라'
                 % (os.path.basename(p), now - os.path.getmtime(p)))
    else:
        ok('판정 파일 %d개 · 최근 %d초 안에 바뀐 것 없음' % (len(paths), secs))


# ─────────────────────────────────────────────────────────────────────
# S-3  한 행에 판정이 둘일 때 칸 단위로 합쳐졌는가
# ─────────────────────────────────────────────────────────────────────
def check_merge(paths):
    """★ 2026-08-18 CP-51 — 나중 파일이 앞 파일을 통째로 덮어
    앞 회차가 낸 status=scope_excluded 가 316행에서 사라졌다"""
    print('\n[S-3] 한 행에 판정이 둘일 때')
    from build_bundle import read_judgments
    seen = collections.defaultdict(list)
    for p in paths:
        for j in read_judgments(p):
            if j.get('atomic_id'):
                seen[j['atomic_id']].append((os.path.basename(p), j))
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    if not dup:
        ok('겹치는 행 없음')
        return
    lost = 0
    for aid, items in dup.items():
        early = set()
        for _, j in items[:-1]:
            early |= {f.get('field') for f in (j.get('findings') or [])}
        late = {f.get('field') for f in (items[-1][1].get('findings') or [])}
        lost += len(early - late)
    msg = ('겹치는 행 %d · 앞 회차에만 있는 칸 %d개' % (len(dup), lost))
    if lost:
        warn(msg + '  → build_bundle 이 칸 단위로 합치는지 확인 (CP-51)')
    else:
        ok(msg)


# ─────────────────────────────────────────────────────────────────────
# S-4  지표는 한 함수로만 낸다
# ─────────────────────────────────────────────────────────────────────
def kind(r):
    """★ 행의 갈래는 여기서만 정한다 (2026-08-18)

    회차마다 계산을 다시 짜서 일치율을 64.4% 로 냈다. 실제는 81.2% 였다.
    원인 — 판독자가 1차 값을 그대로 받아들이면 finding 이 안 나오는데
           그것을 「미판정」 으로 셌다. 이제 이 함수 하나만 쓴다
    """
    if str(r.get('status') or '') == 'scope_excluded':
        return '제외'
    t = str(r.get('topic') or '').strip()
    return '라벨' if t not in ('', 'N/A', '미분류') else '미판정'


def check_metrics(rows):
    print('\n[S-4] 지표 — kind() 한 함수로만 낸다')
    c = collections.Counter(kind(r) for r in rows)
    n = len(rows)
    for k in ('라벨', '제외', '미판정'):
        ok('%-4s %5d  (%.1f%%)' % (k, c[k], 100 * c[k] / n))
    room = sum(1 for r in rows if kind(r) != '제외'
               and str(r.get('rootcause_problem') or '').strip() not in NOT)
    ok('해석 여지 있음 %d  (%.1f%%)' % (room, 100 * room / n))
    # ★ 2026-09-22 고침 (섹션 5b) — N/A · 미분류는 정당한 결과다 (sky 08-26 §17 · 1a §7.9 ②).
    #   08-18 「제외 또는 라벨 둘 중 하나」 경고가 판독자를 §17 반대쪽으로 밀었다. 빈칸만 경고한다
    빈칸 = sum(1 for r in rows if kind(r) == '미판정' and not str(r.get('topic') or '').strip())
    if c['미판정']:
        ok('N/A · 미분류 %d행 — 모수에 남고 topic 집계에서만 빠진다 (0_최신결정_먼저 [가3])' % (c['미판정'] - 빈칸))
    if 빈칸:
        warn('topic 빈칸 %d행 — 라벨 · N/A · 미분류 · 제외 중 하나를 적는다' % 빈칸)


# ─────────────────────────────────────────────────────────────────────
# S-5  근거는 원문에서 뽑았는가
# ─────────────────────────────────────────────────────────────────────
def check_evidence(rows):
    """★ topic_evidence 는 원문에서 문자 그대로 뽑은 어휘여야 한다.
    설명문("댓글 내용이 구체적인 의견을 제기하지 않음")이 들어가 있던 적이 있다"""
    print('\n[S-5] 근거가 원문에 있는가')
    miss = notquote = 0
    for r in rows:
        ev = str(r.get('topic_evidence') or '').strip()
        if ev in NOT or kind(r) != '라벨':
            continue
        src = re.sub(r'\s+', '', str(r.get('voc_cleaned') or r.get('atomic_voc') or ''))
        if re.sub(r'\s+', '', ev) not in src:
            miss += 1
            if re.search(r'(하지 않음|없음\.|판단할 수 없|나타내고 있|재판정)', ev):
                notquote += 1
    if miss:
        warn('라벨 근거가 원문에 없는 행 %d  (그중 설명문으로 보이는 것 %d)' % (miss, notquote))
    else:
        ok('라벨 근거가 전부 원문 안에 있다')


# ─────────────────────────────────────────────────────────────────────
# S-6  1차 잔재가 남아 있는가
# ─────────────────────────────────────────────────────────────────────
def check_leftover(rows):
    """★ 2026-08-18 sky 지적 — 라벨 없는 148행의 topic_provisional·topic_evidence 가
    148/148 전부 1차 값 그대로였다. 뒤 단계를 건너뛰게 만든 내 프롬프트 탓이다"""
    print('\n[S-6] 1차 엔진 잔재')
    pat = re.compile(r'(이 (문장|리뷰)은|나타내고 있|독립 분석 주제를 찾지 못함|'
                     r'N/A: 원문 근거 없음|판단할 수 없음)')
    hit = collections.Counter()
    for r in rows:
        for f in ('topic_provisional', 'topic_evidence', 'atomic_voc_summary'):
            if pat.search(str(r.get(f) or '')):
                hit[f] += 1
    if hit:
        for f, n in hit.most_common():
            warn('%-20s 1차 서술이 남은 행 %d' % (f, n))
    else:
        ok('1차 서술 잔재 없음')


# ─────────────────────────────────────────────────────────────────────
# S-7  해석은 있는데 아무 판정도 없는 행
# ─────────────────────────────────────────────────────────────────────
def check_rootcause(rows):
    """★ 2026-08-18 — rootcause_cause 가 빈 것은 결손이 아니라 판정일 수 있다.
    실측 661행 중 93%는 rootcause_summary 에 「L2 — 원인 서술은 원문에 없다」 가
    적혀 있었다. 원문에 원인이 없는데 채우면 판독자가 지어낸 것이 된다.
    ★ 다만 등급도 원인도 없는 행은 진짜 결손이다. 그것만 잡는다"""
    print(chr(10)+'[S-7] 해석은 있는데 판정이 없는 행')
    room = [r for r in rows if kind(r) != '제외'
            and str(r.get('rootcause_problem') or '').strip() not in NOT]
    if not room:
        ok('해석 여지가 있는 행이 없다')
        return
    bare = [r for r in room
            if str(r.get('rootcause_cause') or '').strip() in NOT
            and not re.match(r'L\d', str(r.get('rootcause_summary') or '').strip())]
    graded = len([r for r in room if re.match(r'L\d', str(r.get('rootcause_summary') or '').strip())])
    ok('해석 여지 %d · 등급이 적힌 행 %d (%.0f%%)' % (len(room), graded, 100 * graded / len(room)))
    if bare:
        warn('원인도 등급도 없는 행 %d — 진짜 결손인지 봐야 한다' % len(bare))
    else:
        ok('원인이 비어 있어도 전부 등급으로 설명돼 있다')



# ─────────────────────────────────────────────────────────────────────
# S-8 ~ S-12  총괄이 정한 규칙을 기계가 지킨다  【2026-08-19】
#
# ★ 이 다섯은 「이번 데이터를 고치는 코드」 가 아니라
#   「다음 데이터에서 같은 일이 또 생기는지 보는 코드」 다.
#   총괄이 한 번 판정한 것을 매번 다시 판정하지 않게 하는 것이 목적이다
# ─────────────────────────────────────────────────────────────────────

# 폐기된 값 — 총괄이 「이제 쓰지 말자」 고 정한 것
DEAD_REASON = {'out_of_scope_product'}      # 「다중가전」 은 가전 전반을 뜻한다
# ★ 2026-09-22 고침 (섹션 5b [가1] 「가전이면 살린다」) — out_of_scope_product 는 **가전이 아닌 제품**에 쓰는 살아 있는 사유다.
#   폐기로 보면 판독자가 새 판대로 쓸 때마다 경고가 나 보정요청으로 간다. 옛 동작은 얼린 기준 재현 때만
if os.environ.get('VOC_얼린기준_재현') != '1':
    DEAD_REASON = set()
DEAD_TOPIC = {'구매의사/이탈',              # → 구매의사
              '주거 수납/공간',             # → 공간 활용성 이 흡수
              '위생/냄새(곰팡이)',         # → 위생/냄새 (sky 08-26) — 2026-09-22 더함: 폐기라벨_정리.바꿀것 과 짝이 어긋나 있었다
              # ★ sky 2026-10-08 (가13 · 섹션 7a) — 「기타」 를 하나로 합친다. 제품군은 product_category 에 이미 있다
              '기타(로봇청소기)', '기타(식기세척기)', '기타(세탁기)', '기타(냉장고)',   # → 기타
              # ★ 2026-10-09 전체 재점검 — 새 판 [나12] · [나13] 에 적혀 있는데 폐기 목록에 없었다
              '위생/살균',                 # → 위생/냄새 (sky 2026-08-25·26 · 9 §9)
              '배수·부품'}                 # → 배수/급배수 가 흡수 (sky 2026-08-26 · 9 §18)


def 엔진이_아직_받아주는가(값, 자리):
    """★ 문서로는 폐기했는데 엔진 ENUM 에는 아직 남아 있는가 (2026-08-22).

    실제로 겪었다 — `out_of_scope_product` 707행, `구매의사/이탈` 279행이
    반려로 나왔는데, 둘 다 엔진에는 **유효한 값으로 살아 있었다.**
    프롬프트가 「컬럼 소유권은 코드가 정본」 이라 하므로 판독자는 코드를 따랐다.
    그런데 검사기는 문서를 따라 반려했다. 판독자가 고칠 수 없는 일이다.

    엔진이 아직 받아주면 → 알림(!)  + 보정요청으로 총괄에게
    엔진에서도 빠졌으면   → 반려(✗)  판독자가 고쳐야 한다
    """
    import sys as _sys
    for _cand in (os.environ.get('VOC_ENGINE'),):
        if _cand and os.path.isdir(_cand):
            if _cand not in _sys.path:
                _sys.path.insert(0, _cand)
            break
    try:
        from src.voc_rebuild import schema as _s
    except Exception:
        return None                      # 엔진을 못 보면 판단하지 않는다
    if 자리 == 'reason':
        return 값 in (getattr(_s, 'ENUM_COLUMNS', {}) or {}).get(
            'scope_exclusion_reason', [])
    return 값 in (getattr(_s, 'CANONICAL_TOPICS', []) or [])


def check_rules(rows):
    """S-8  제외 사유가 총괄 규칙과 어긋나는가"""
    print(chr(10) + '[S-8] 제외 사유가 규칙대로인가')
    ts = trans = dead = 0
    for r in rows:
        src = ' '.join(((r.get('atomic_voc') or '') + ' ' + (r.get('voc_cleaned') or '')).split())
        reason = str(r.get('scope_exclusion_reason') or '')
        # 영상 대본을 옮긴 댓글 — 타임스탬프가 박혀 있다
        if re.search(r'\[\d{1,2}:\d{2}', src) and reason != 'video_transcript':
            ts += 1
        # 리뷰어가 제휴 고정 댓글에 쓴 평가 — 고객의 소리가 아니라 광고다
        if (re.search(r'(수수료|링크로 구매|구매 가이드정리|카톡\s*친구)',
                      r.get('voc_cleaned') or '')
                and kind(r) == '라벨'):
            trans += 1
        if reason in DEAD_REASON:
            dead += 1
    if ts:
        warn('타임스탬프가 있는데 video_transcript 가 아닌 행 %d' % ts)
    if trans:
        warn('제휴 고정 댓글인데 라벨이 붙은 행 %d — operator_notice 여야 한다' % trans)
    if dead:
        살아있음 = 엔진이_아직_받아주는가('out_of_scope_product', 'reason')
        if 살아있음:
            warn('제외 사유 out_of_scope_product 를 쓴 행 %d — '
                 '문서로는 폐기했지만 엔진 ENUM 에는 아직 살아 있습니다' % dead)
            print('       * 판독자가 고칠 일이 아닙니다. 보정요청서로 총괄에게 갑니다')
        else:
            bad('★ 폐기된 제외 사유(out_of_scope_product)를 쓴 행 %d' % dead)
    if not (ts or trans or dead):
        ok('제외 사유가 전부 규칙대로다')


def check_labels(rows):
    """S-9  폐기된 라벨 이름이 남았는가 · 대장에 없는 라벨인가"""
    print(chr(10) + '[S-9] 라벨 이름이 대장과 맞는가')
    import json
    gp = 대장자리('topic_group_map.json')
    known = set()
    try:
        for v in json.load(open(gp, encoding='utf-8'))['그룹'].values():
            known |= set(v)
    except Exception:
        pass
    dead = collections.Counter()
    unknown = collections.Counter()
    nogroup = 0
    for r in rows:
        if kind(r) != '라벨':
            continue
        tp = r['topic'].strip()
        if tp in DEAD_TOPIC:
            dead[tp] += 1
        elif known and tp not in known:
            unknown[tp] += 1
        if str(r.get('topic_group') or '') in ('', '미판정'):
            nogroup += 1
    for k, n in dead.items():
        if 엔진이_아직_받아주는가(k, 'topic'):
            warn('라벨 「%s」 가 %d행 — 문서로는 폐기했지만 '
                 '엔진 대장에는 아직 살아 있습니다' % (k, n))
            print('       * 판독자가 고칠 일이 아닙니다. 보정요청서로 총괄에게 갑니다')
        else:
            bad('★ 폐기된 라벨 「%s」 가 %d행 남아 있다' % (k, n))
    for k, n in unknown.most_common(5):
        warn('대장에 없는 라벨 「%s」 %d행 — topic_registry.py --register 를 돌렸는가' % (k, n))
    if nogroup:
        warn('라벨은 있는데 topic_group 이 미판정인 행 %d' % nogroup)
    if not (dead or unknown or nogroup):
        ok('라벨 이름이 전부 대장과 맞는다')


def check_split_needed(rows):
    """S-10  ★ 「여러 주제가 있다」 고 표시해 놓고 나누지 않은 행

    총괄 결정 — 비슷한 주제면 topic_secondary 에 보조로 두고,
                 불만·요청이 향하는 대상이 다르면 행을 나눈다
    ★ 보조 라벨이 붙어 있다는 것은 「여러 주제가 있다」 는 뜻이다.
      그중 대상이 다른 것은 나뉘어야 하는데, 자동으로는 가릴 수 없다.
      그래서 세어서 보여 주기만 한다 — 사람이 한 번 보라는 신호다
    """
    print(chr(10) + '[S-10] 나눠야 할지 봐야 하는 행')
    sec = [r for r in rows if str(r.get('topic_secondary') or '').strip()]
    if sec:
        warn('보조 라벨이 붙은 행 %d — 대상이 다르면 나눠야 한다 (총괄 결정)' % len(sec))
    else:
        ok('보조 라벨이 붙은 행이 없다')


def _어휘():
    """제품군·자사 어휘를 공통/어휘.json 에서 읽는다.

    ★ 박아 두면 다른 회사 데이터에서 자사를 경쟁사로 읽는다 (2026-08-23).
    ★ 어휘는 그 파일 한 곳에만 둔다. 코드에 기본값을 남기면 두 곳이 되어
      파일을 고쳐도 어느 쪽이 도는지 알 수 없다.
      파일이 없으면 빈 값을 돌려주고, 그 검사 두 개는 쉰다 —
      틀린 답을 내는 것보다 낫다.
    """
    _여기 = os.path.dirname(os.path.abspath(__file__))
    for _d in (_여기, os.path.dirname(_여기)):
        _p = os.path.join(_d, '공통', '어휘.json')
        if os.path.exists(_p):
            with open(_p, encoding='utf-8') as _h:
                _j = json.load(_h)
            return [tuple(x) for x in _j['제품군']], '(%s)' % _j['자사']
    return [], ''      # ★ 어휘가 없다 — 그 검사 두 개는 쉰다


PRODUCTS, _자사 = _어휘()


def check_product(rows):
    """S-11  ★ 제품군이 본문과 어긋나는가

    총괄 결정 — 「본문에 그 제품 이름이 나온다」 와
                 「본문의 주인공이 그 제품이다」 는 다르다.
    ★ 그래서 제품 이름이 하나만 나오는 행만 본다. 여럿 나오면 판단이 필요하다
      product_category 는 개선 우선순위를 제품군별로 가르는 칸이라
      틀리면 그 줄 전체가 엉뚱한 제품 밑에 들어간다
    """
    print(chr(10) + '[S-11] 제품군이 본문과 맞는가')
    n = 0
    for r in rows:
        if kind(r) != '라벨':
            continue
        src = ' '.join(((r.get('atomic_voc') or '') + ' ' + (r.get('voc_cleaned') or '')).split())
        g = [nm for nm, pat in PRODUCTS if re.search(pat, src)]
        if len(g) == 1 and str(r.get('product_category') or '') != g[0]:
            n += 1
    if n:
        warn('본문에 한 제품만 나오는데 product_category 가 다른 행 %d' % n)
    else:
        ok('제품군이 본문과 어긋나는 행이 없다')


def check_foreign(rows):
    """S-12  ★ 외국어 원문인데 번역이 없는가

    총괄 결정 — "영어인 경우 한글로 번역이 되어야 함.
                  외국어는 맥락 파악을 위해 본문도 놔두지만 번역도 해줘야 함"
    """
    print(chr(10) + '[S-12] 외국어 댓글에 번역이 있는가')
    n, ex = 0, []
    for r in rows:
        t = (r.get('atomic_voc') or '').strip()
        if len(t) < 20:
            continue
        ko = sum(1 for ch in t if '\uac00' <= ch <= '\ud7a3')
        if ko / max(1, len(t)) < 0.15:
            n += 1
            if len(ex) < 3:
                ex.append(t[:60])
    if n:
        warn('한글이 거의 없는 원문 %d행 — 번역 칸이 없다' % n)
        for e in ex:
            print('       %s' % e)
    else:
        ok('외국어 원문이 없다')


# ─────────────────────────────────────────────────────────────────────
# S-13 ~ S-15  아직 규칙이 아니던 총괄 판정  【2026-08-19 추가】
# ─────────────────────────────────────────────────────────────────────

# 불만이 담긴 말 — 이런 어휘가 있으면 부정으로 세어져야 한다
#   ★ 2026-08-19 — 처음엔 「손상」 「문제」 같은 낱말만 봤더니 87행이 걸렸는데
#     "옷감 손상도 없고" · "의미가 없을 것" 처럼 부정문·긍정 맥락이 섞여 있었다.
#     오늘만 세 번째로 겪은 「어휘 검색이 헐거워 부풀린」 사례다.
#     그래서 ㉠ 뒤에 부정 종결이 붙은 것을 걷어내고
#            ㉡ 낱말을 강한 불만으로 좁혔다
COMPLAIN = re.compile(
#   ★ 2026-08-19 두 번째 손질 — 「하자」 가 「음악 시작하자마자」 에 걸렸다.
#     조사·어미까지 붙여서 낱말이 홀로 서는 경우만 잡는다
    r'(망가|고장\s*(?:나|났|이|다)|안\s*됨|안돼요|안되네|못\s*쓰|짜증|실망|'
    r'불편하|아쉬(?:워|웠|운\s*점)|별로|최악|빡치|열받|후회|비추|'
    r'하자(?:가|를|는|로|다)|불량|시끄러|귀찮|번거로|답답|'
    r'아깝|속았|사기꾼|엉망|형편없|쓰레기|반품|환불)')
# ★ 「손상도 없고」 「문제 없」 처럼 부정을 부정하는 꼬리
NEGATED = re.compile(r'(없고|없어|없네|없음|없습니다|않아|않고|않네|아니)')
# 경험을 나누기만 하는 말 — 의견도 니즈도 없다
SHARE_ONLY = re.compile(r'(쓰고\s*있어요|사용\s*중이|쓰는\s*중|잘\s*쓰고|'
                        r'저는\s*.{0,10}씁니다|정도\s*나와요|정도\s*걸려)')
COMPETITOR = re.compile(r'(삼성|로보락|다이슨|나르왈|에코백스|쿠쿠|SK\s*매직|위닉스|쉐프본)')
# ★ 어휘가 없으면 아무것도 안 맞는 무늬를 쓴다.
#   빈 무늬는 **모든 글에 맞아** 온 발화를 자사로 읽는다 — 오탐도 사고다.
OWN = re.compile(_자사 or r'(?!)')


def _neg(r):
    def n(v):
        try:
            return float(str(v).strip() or 0)
        except Exception:
            return 0.0
    return min(n(r.get('tee_emotion_score')), n(r.get('tee_success_score')), 0)


def check_sentiment(rows):
    """S-13  ★ 감정 방향이 원문과 어긋나는가

    총괄 지적 — "로청이 바닥재에 손상을 주고있다는 의견으로 보이기 때문에
                  부정의견으로 취합되는 게 맞아 보임"
    ★ 개선 우선순위가 부정 건수로 정렬된다. 여기가 틀리면 순위가 통째로 흔들린다
    """
    print(chr(10) + '[S-13] 감정 방향이 원문과 맞는가')
    miss, ex = 0, []
    for r in rows:
        if kind(r) != '라벨':
            continue
        t = (r.get('atomic_voc') or '')
        m = COMPLAIN.search(t)
        if not m or _neg(r) != 0:
            continue
        # 걸린 낱말 바로 뒤 8자에 부정 꼬리가 있으면 불만이 아니다
        if NEGATED.search(t[m.end():m.end() + 8]):
            continue
        if True:
            miss += 1
            if len(ex) < 3:
                ex.append('[%s] %s' % (m.group(0), ' '.join(t.split())[:52]))
    if miss:
        warn('불만 어휘가 있는데 부정 점수가 0 인 행 %d — 개선 우선순위에서 빠진다' % miss)
        for e in ex:
            print('       %s' % e)
    else:
        ok('불만 어휘와 부정 점수가 어긋나는 행이 없다')


def check_share_only(rows):
    """S-14  경험 공유·원리 설명만 있는데 라벨이 붙었는가

    총괄 지적 — "단순 사용법 공유로 분석 제외 대상"
                 "단순 원리 설명하는 댓글로 분석 내용 없어보임"
    ★ 라벨이 맞아도 볼 것이 없으면 제외다. 남기면 건수만 부풀린다
    """
    print(chr(10) + '[S-14] 경험 공유만 있는데 라벨이 붙었는가')
    n, ex = 0, []
    for r in rows:
        if kind(r) != '라벨':
            continue
        t = (r.get('atomic_voc') or '')
        room = str(r.get('rootcause_problem') or '').strip() in NOT
        # 공유 어휘는 있는데 불만도 없고 해석 여지도 없다
        if SHARE_ONLY.search(t) and not COMPLAIN.search(t) and room and _neg(r) == 0:
            n += 1
            if len(ex) < 3:
                ex.append(' '.join(t.split())[:58])
    if n:
        warn('경험 공유만 있고 불만·해석이 없는 행 %d — 제외 대상인지 본다' % n)
        for e in ex:
            print('       %s' % e)
    else:
        ok('경험 공유만 있는 행이 없다')


def check_competitor(rows):
    """S-15  ★ 경쟁사 얘기가 자사 행에 섞였는가

    총괄 지적 — "배터리(부정)는 로보락 브랜드의 의견이기에
                  최소한 이 5개로 분리되어야 하는 게 아닌가 싶음.
                  브랜드성도 보장해야 되기 때문에"
    ★ 섞이면 브랜드별 집계가 오염된다. 경쟁사 불만이 자사 개선 과제로 올라간다
    """
    print(chr(10) + '[S-15] 경쟁사 얘기가 자사 행에 섞였는가')
    n, ex = 0, []
    for r in rows:
        if kind(r) != '라벨':
            continue
        t = (r.get('atomic_voc') or '')
        brand = str(r.get('brand') or '')
        # 본문에 경쟁사만 나오는데 brand 가 자사다
        # ★ 2026-08-19 — entity_role · competitor_brand_tags 는 이미 맞게 돼 있었다.
        #   틀린 것은 brand 하나뿐이었다. 그래서 brand 만 본다
        if COMPETITOR.search(t) and not OWN.search(t) and OWN.search(brand):
            n += 1
            if len(ex) < 3:
                ex.append('[%s] %s' % (brand[:10], ' '.join(t.split())[:50]))
    if n:
        warn('본문은 경쟁사인데 brand 가 자사인 행 %d — 브랜드별 집계가 섞인다' % n)
        for e in ex:
            print('       %s' % e)
    else:
        ok('경쟁사 얘기가 자사 행에 섞이지 않았다')

눈먼길 = []          # ★ 엔진 칸 목록을 못 봤다면 여기 적는다. 조용히 넘어가지 않는다


def _엔진_schema():
    """엔진의 `schema.py` **하나만** 읽어 온다 — 꾸러미 전체를 불러오지 않는다.

    ★ 2026-10-27 에 실제 흐름에서 드러난 일 —
      전에는 `from src.voc_rebuild import schema` 였다. 그 꾸러미의 `__init__.py` 가
      `.engine` 을 불러오고, 그것이 `config.py` → `yaml` 로 내려간다.
      **Codex 내장 파이썬에는 yaml 이 없다** (pandas 3.0.1 · openpyxl 3.1.5 는 있다).
      2026-10-09 에 pandas 때문에 그 파이썬을 PATH 앞에 놓았으므로, 판독자·감독자는
      바로 그 파이썬을 쓴다. 그래서 import 가 터지고 아래 `return True` 눈먼 길로 떨어져,
      1차가 애초에 안 내놓는 `video_tags`·`video_description` 을
      「번들에서 빠진 칸 ✗」 으로 보고 **안 깨진 번들을 깨졌다고** 반려했다
      (실측 — 2026-10-27 깨끗한 판 1 의 판독B).
      `schema.py` 자체는 json · typing 만 쓴다. **파일 자리로 바로 읽으면 yaml 이 필요 없다.**

    ★ 한 곳만 보면 꾸러미를 푼 자리에서 그냥 넘어간다 — S-16 과 같은 교훈이라 여러 자리를 본다.
    """
    import importlib.util as _u
    자리들 = []
    _env = os.environ.get('VOC_ENGINE')
    if _env:
        자리들.append(_env)
    for _d in (BASE, _HERE, os.path.dirname(BASE)):
        자리들 += [os.path.join(_d, 'engine'), _d]
    for _c in 자리들:
        _p = os.path.join(_c, 'src', 'voc_rebuild', 'schema.py')
        if not os.path.isfile(_p):
            continue
        try:
            _spec = _u.spec_from_file_location('_voc_schema_only', _p)
            _m = _u.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
            return _m
        except Exception:
            continue
    # 옛 길 — 되돌림으로 남긴다 (파일 자리로 못 읽은 자리에서도 한 번 더 본다)
    import sys as _sys
    for _c in 자리들:
        if os.path.isdir(_c) and _c not in _sys.path:
            _sys.path.insert(0, _c)
    try:
        from src.voc_rebuild import schema as _s
        return _s
    except Exception:
        return None


def _일차가_내놓는가(칸):
    """1차 엔진의 출력 칸에 이 칸이 있는가 (2026-08-22).

    없으면 판독자가 만들어 낼 수 없다. 그걸 반려하면 영원히 못 지나간다.
    """
    _s = _엔진_schema()
    if _s is None:
        if '엔진' not in 눈먼길:
            눈먼길.append('엔진')
        return True                      # 엔진을 못 보면 예전대로 반려한다
    칸들 = (getattr(_s, 'TARGET_COLUMNS', None)
            or getattr(_s, 'OUTPUT_COLUMNS', None) or [])
    return (not 칸들) or (칸 in 칸들)


def check_columns(rows):
    """S-16  * 엔진이 내놓기로 한 칸이 번들에서 사라지지 않았는가

    2026-08-19 에 드러난 일 —
      schema.py 의 TARGET_COLUMNS 에서 video_tags / video_description 두 칸이
      2026-08-05 에 커밋 없이 지워진 채로 2주를 돌았다.
      그 두 칸을 지키라는 시험(tests/test_voc_engine_video_context_schema.py)이
      이미 있었는데 * 아무도 돌리지 않아서 못 잡았다.
      sky 가 최종본을 눈으로 보고서야 "출력물에 나와야하는 데이터인데" 라고 짚었다.

    * 그래서 사람 눈이 아니라 여기서 잡는다.
      기준은 _판독패키지/_기준/출력칸목록.txt 다.
    """
    print(chr(10) + '[S-16] 엔진이 내놓기로 한 칸이 사라지지 않았는가')
    # * 프로젝트 폴더에서 돌릴 때와 꾸러미를 푼 자리에서 돌릴 때 경로가 다르다.
    #   한 곳만 보면 꾸러미에서는 그냥 넘어가서 검사가 무력해진다 (2026-08-19)
    cands = [os.path.join(BASE, '_판독패키지', '_기준', '출력칸목록.txt'),
             os.path.join(BASE, '공통', '출력칸목록.txt'),
             os.path.join(BASE, '..', '공통', '출력칸목록.txt'),
             os.path.join(BASE, '출력칸목록.txt')]
    spec = next((c for c in cands if os.path.exists(c)), None)
    if not spec:
        warn('기준 파일 출력칸목록.txt 를 못 찾았다 — S-16 을 건너뛴다')
        return
    with open(spec, encoding='utf-8') as f:
        want = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    # ~ 로 시작하면 [참고] — 없어도 사고는 아니다
    must = [c for c in want if not c.startswith('~')]
    soft = [c[1:] for c in want if c.startswith('~')]
    have = set(rows[0].keys()) if rows else set()
    gone = [c for c in must if c not in have]
    soft_gone = [c for c in soft if c not in have]
    if gone:
        # ★ 「번들 만들다 잃은 칸」 과 「1차가 애초에 안 내놓는 칸」 을 가른다
        #   (2026-08-22). 로니에서 video_tags·video_description 이 반려로
        #   나왔는데, 1차 엔진이 처음부터 그 칸을 안 냈다.
        #   판독자가 없는 칸을 만들어 낼 수는 없다 — 물으면 안 되는 것이다.
        원본없음 = [c for c in gone if not _일차가_내놓는가(c)]
        진짜잃음 = [c for c in gone if c not in 원본없음]
        if 눈먼길:
            # ★ 못 본 것을 「없음」 으로 돌려주지 않는다 (공통 규칙 4)
            warn('엔진 칸 목록을 못 봤습니다 — 「번들에서 잃은 칸」 과 '
                 '「1차가 애초에 안 내놓는 칸」 을 가르지 못했습니다')
            print('       * 아래 ✗ 는 그대로 믿지 마십시오. VOC_ENGINE 에 엔진 폴더를 주거나')
            print('         이 스크립트 옆에 engine/ 이 오게 두십시오')
        if 진짜잃음:
            bad('번들에서 빠진 칸 %d — %s' % (len(진짜잃음), ' / '.join(진짜잃음)))
            print('       * 엔진 스키마를 손댄 사람이 있다. 커밋 안 된 변경부터 본다')
            print('         git diff -- src/voc_rebuild/schema.py src/voc_rebuild/engine.py')
        if 원본없음:
            warn('1차 엔진이 처음부터 안 내놓는 칸 %d — %s'
                 % (len(원본없음), ' / '.join(원본없음)))
            print('       * 판독자가 고칠 일이 아닙니다. 1차 엔진 쪽 일이라')
            print('         보정요청서로 총괄에게 갑니다')
    else:
        ok('반드시 있어야 할 %d칸이 모두 번들에 있다' % len(must))
    if soft_gone:
        print('       [참고] 선언만 돼 있고 값이 안 실리는 칸 %d — %s'
              % (len(soft_gone), ' / '.join(soft_gone)))


# ─────────────────────────────────────────────────────────────────────
def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    d = args[0] if args else None
    if not d:
        cands = sorted(glob.glob(os.path.join(BASE, '_판독패키지', '_결과', 'final_*')),
                       key=os.path.getmtime)
        d = cands[-1] if cands else None
    if not d or not os.path.exists(os.path.join(d, 'raw_voc.csv')):
        print('번들을 못 찾았다.  python check_selfcheck.py <번들폴더>')
        return 1
    rows = list(csv.DictReader(open(os.path.join(d, 'raw_voc.csv'), encoding='utf-8-sig')))
    paths = sorted(glob.glob(os.path.join(BASE, '_판독패키지', '_결과', '판독결과_*.md')))

    print('=' * 78)
    print('  자기 검사 — %s  (%d행)' % (os.path.basename(d), len(rows)))
    print('=' * 78)
    check_fresh(paths)
    check_merge(paths)
    check_metrics(rows)
    check_templates(rows, os.path.basename(d))
    check_evidence(rows)
    check_leftover(rows)
    check_rootcause(rows)
    check_rules(rows)
    check_labels(rows)
    check_split_needed(rows)
    check_product(rows)
    check_foreign(rows)
    check_sentiment(rows)
    check_share_only(rows)
    check_competitor(rows)
    check_columns(rows)

    print()
    print('=' * 78)
    print('  ✗ %d건 · ! %d건' % (len(fails), len(warns)))
    print('=' * 78)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
