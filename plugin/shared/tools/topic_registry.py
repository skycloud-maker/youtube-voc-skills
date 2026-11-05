"""topic 라벨 대장 · 동의어 검사 — 판독자가 새 라벨을 낼 수 있게 하는 장치.

사용:
    python topic_registry.py                     대장 현황 · 동의어 후보 · 표류 검사
    python topic_registry.py <판독결과.md> ...     그 회차 신설 라벨을 검사한다
    python topic_registry.py --register <...>     ★ 신설 라벨을 대장에 등록한다
    python topic_registry.py --drift              ★ 회차 사이 라벨 표류만 본다

★ sky 2026-08-16 결정
    "topic 의 라벨은 제 허가 없이도 채울 수 있어도 됩니다.
     그 자체가 기타의 분류 포션을 넓히고, 오히려 기타의 포션을 나중에
     제일 최우선 과제로 뽑을 수도 있습니다."

    "단 2가지만 잘 후속 대처를 한다면 오히려 더 좋은 방향일 겁니다.
     첫번째, 같은 주제에 대해서는 똑같이 묶어야 한다는 것.
       같은 린트 잔류인데 하나는 린트 잔류, 하나는 먼지 잔류 이런 식으로
       같은 의미를 다르게 표기해서 수치가 묶이지 않는 문제만 발생하지 않는다면
     그리고 두번째는 그 분류된 걸 상위 topic_group 에만 잘 분류해서 넣을 것."

그래서 이 도구가 하는 일은 둘뿐이다
    ① 같은 뜻인데 다르게 쓴 라벨을 찾아낸다   (린트 잔류 ↔ 먼지 잔류)
    ② 새 라벨에 topic_group 이 붙었는지 본다

라벨을 막지 않는다. 흩어지는 것만 막는다.

★ 표류 검사 (CP-41)
    동의어 검사는 「새 라벨 대 기존 라벨」 만 본다.
    실제로 흩어지는 경로는 그것만이 아니었다 —
      같은 원문에 회차마다 다른 라벨이 붙는다        (실측 64행)
      같은 주제 어휘가 여러 라벨로 흩어진다          (물·수도 21건이 10개 라벨로)
    그래서 둘을 따로 본다.

    ★ 등록 경로가 없으면 다음 회차 판독자가 대장에서 못 보고 같은 뜻을
      다른 워딩으로 낸다 (Claude Code 지적 2026-08-16). 그래서 --register 를 만들었다

--register 와 --promote 만 파일을 쓴다. 나머지는 전부 읽기 전용이다.

★ 등록과 승격은 원래 두 단계였는데 CP-44 에서 합쳤다 (sky 지적).
  "토픽은 별도로 승인 절차를 완화하자고 했기에"
  대장에만 올리면 게이트는 통과하는데 반영 단계의 계약 검증이 반려했다.
  낼 수는 있는데 쓸 수는 없는 상태였다. --register 가 이제 둘을 같이 한다
"""
from __future__ import annotations

import collections, glob, json, os, re, sys

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

ENGINE = (os.environ.get('VOC_ENGINE')
          or os.path.dirname(os.path.abspath(__file__)))
SIDE_T = 대장자리('secondary_topics.json')
SIDE_G = 대장자리('topic_group_map.json')
REGISTRY = 대장자리('topic_registry.json')

# 비교 전에 걷어낼 것 — 괄호 주석 · 구분자 · 공백
TRIM = re.compile(r'[\(\（][^\)\）]*[\)\）]')
SEP = re.compile(r'[\s/·,\-—~]+')
# 뜻이 같은데 표기만 다른 흔한 말 — 비교할 때만 통일한다. 라벨을 바꾸지 않는다
SYN = [
    ('먼지', '린트'), ('잔류', '남음'), ('소음', '시끄'), ('냄새', '악취'),
    ('고장', '파손'), ('가격', '값'), ('배송', '배달'), ('설치', '시공'),
    ('편의', '편리'), ('조작', '작동'), ('성능', '효과'), ('품질', '퀄리티'),
    ('보안', '방범'), ('안전', '위험'), ('디자인', '외관'), ('용량', '크기'),
]


def canon(s):
    """비교용 정규형. 괄호 주석·구분자를 걷고 동의어를 한쪽으로 모은다."""
    x = TRIM.sub('', str(s or ''))
    x = SEP.sub('', x)
    for a, b in SYN:
        x = x.replace(b, a)
    return x


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def similarity(a, b):
    """0~1. 글자 2-gram 자카드 + 포함 관계 가산."""
    ca, cb = canon(a), canon(b)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    A, B = bigrams(ca), bigrams(cb)
    j = len(A & B) / len(A | B)
    if ca in cb or cb in ca:
        j = max(j, 0.75)
    return j


def load_known():
    """1차 캐노니컬 + 2차 사이드카 + 대장에 쌓인 신설 라벨."""
    sys.path.insert(0, ENGINE)
    from src.voc_rebuild.schema import CANONICAL_TOPICS
    known = {t: '1차' for t in CANONICAL_TOPICS}
    if os.path.exists(SIDE_T):
        for t in (json.load(open(SIDE_T, encoding='utf-8')).get('확장 라벨') or {}):
            known[t] = '2차 확장'
    if os.path.exists(REGISTRY):
        for t, v in (json.load(open(REGISTRY, encoding='utf-8')).get('신설 라벨') or {}).items():
            known[t] = '판독자 신설 (%s)' % v.get('처음 낸 회차', '?')
    return known


def load_groups():
    if not os.path.exists(SIDE_G):
        return {}
    return json.load(open(SIDE_G, encoding='utf-8')).get('topic_to_group') or {}


def collect(paths):
    """판정 파일에서 (topic, topic_group, 회차, 근거) 를 모은다."""
    out = []
    for p in paths:
        from build_bundle import read_judgments
        stem = os.path.basename(p)[5:-3]
        for j in read_judgments(p):
            for f in (j.get('findings') or []):
                if f.get('field') == 'topic' and str(f.get('proposed', '')).strip():
                    out.append((str(f['proposed']).strip(),
                                str(f.get('topic_group') or j.get('topic_group') or '').strip(),
                                stem, str(f.get('quote') or '')[:40]))
            for s in ((j.get('structure') or {}).get('segments') or []):
                if str(s.get('topic') or '').strip():
                    out.append((str(s['topic']).strip(),
                                str(s.get('topic_group') or '').strip(),
                                stem, str(s.get('topic_evidence') or '')[:40]))
    return out


# 주제 축 — 같은 뜻인데 여러 라벨로 흩어지는지 본다.
# 여기 없는 축은 검사하지 않는다. 늘려야 할 때 sky 승인 없이 추가해도 되지만
# ★ 넓게 잡으면 오탐이 늘어난다. 좁게 잡는다
AXES = {
    # ★ 좁게 잡는다. 헐거우면 오탐이 실제 표류를 덮는다 (CP-41 에서 33건 중 17건이 오탐)
    #   "절약" 만 넣었더니 "가격도 떨어지고 시간도 절약되고" 가 걸렸고,
    #   "물사용" 만 넣었더니 "물사용 가능한 다용도실" 이 걸렸다
    '물·수도': r'물\s*사용[량양]|물\s*적게\s*쓰|물\s*많이\s*쓰|수도\s*[비료세]|'
               r'절수|물\s*아껴|물\s*절약|급수',
    '알림음':   r'알림음|종료음|멜로디|엔딩송|경고음|버튼음',
    '린트':     r'린트|보풀|먼지가\s*옷|옷에\s*먼지',
    '보안':     r'해킹|개인정보|와이파이.{0,6}정보|도청|정보.{0,4}유출',
}

# ★ 표류를 셀 때 「한 원문이 여러 조각으로 나뉜 것」 은 표류가 아니다.
#   조각마다 다른 라벨이 붙는 것이 정상이다 (CP-41)


def read_all_judgments():
    """모든 회차의 (회차, atomic_id, 조각 본문, 라벨) 을 모은다."""
    from build_bundle import read_judgments, read_csv, SRC, PRODUCTS
    rows = {}
    for prod in PRODUCTS:
        rs, _ = read_csv(SRC[prod])
        for r in rs:
            rows.setdefault(r['atomic_id'], r)
    out = []
    for p in sorted(glob.glob(os.path.join(BASE, '_판독패키지', '_결과', '판독결과_*.md'))):
        stem = os.path.basename(p)[5:-3]
        for j in read_judgments(p):
            body = (rows.get(j.get('atomic_id'), {}).get('atomic_voc') or '')
            for f in (j.get('findings') or []):
                if f.get('field') == 'topic' and str(f.get('proposed', '')).strip():
                    out.append((stem, j.get('atomic_id'), body, str(f['proposed']).strip()))
            for s in ((j.get('structure') or {}).get('segments') or []):
                if str(s.get('topic') or '').strip():
                    out.append((stem, j.get('atomic_id'),
                                s.get('atomic_voc') or body, str(s['topic']).strip()))
    return out, rows


READER = ('_claudecode_tool', '_codex_tool', '_claudecode', '_codex', '_chat', '_tool')


def batch_of(stem):
    """회차 이름에서 판독자를 떼어낸다."""
    for w in READER:
        if stem.endswith(w):
            return stem[:-len(w)]
    return stem


def drift(items, rows):
    """표류를 본다.

    ★ 「회차 간 표류」 와 「판독자 간 판단 차이」 는 다른 것이다 (CP-41).
      전자는 대장을 못 봐서 생긴 워딩 분산이고 — 이 도구가 막아야 할 것
      후자는 규칙이 부족해서 생긴 판단 차이다 — 규칙을 고쳐야 할 것
      섞어 세면 141행이 나오는데 그중 상당수가 후자였다
    """
    print()
    print('=' * 70)
    print('  표류 ① 같은 원문에 다른 라벨이 붙었는가')
    print('=' * 70)
    byrow = collections.defaultdict(list)
    for stem, aid, _, t in items:
        byrow[aid].append((batch_of(stem), t))

    cross, same = {}, {}
    for aid, pairs in byrow.items():
        labs = {t for _, t in pairs}
        if len(labs) < 2:
            continue
        batches = {b for b, _ in pairs}
        if len(batches) > 1:
            cross[aid] = labs       # 회차가 다르다 — 진짜 표류
        else:
            same[aid] = labs        # 같은 회차 — 판독자 판단 차이
    print()
    print('  ★★ 회차 간 표류 %d행 — 대장을 못 봐서 생긴 워딩 분산' % len(cross))
    for a, v in list(cross.items())[:8]:
        print('     %-40s %s' % ((rows.get(a, {}).get('atomic_voc') or '')[:40],
                                 ' | '.join(sorted(v))))
    if len(cross) > 8:
        print('     ... 외 %d행' % (len(cross) - 8))
    print()
    print('  판독자 간 판단 차이 %d행 — 규칙이 부족한 것이다. 표류가 아니다' % len(same))
    for a, v in list(same.items())[:5]:
        print('     %-40s %s' % ((rows.get(a, {}).get('atomic_voc') or '')[:40],
                                 ' | '.join(sorted(v))))
    if len(same) > 5:
        print('     ... 외 %d행' % (len(same) - 5))
    multi = cross

    print()
    print('=' * 70)
    print('  표류 ② 같은 주제 어휘가 여러 라벨로 흩어졌는가')
    print('=' * 70)
    n2 = 0
    for name, pat in AXES.items():
        rx = re.compile(pat)
        # ★ 같은 회차·같은 행의 조각들은 한 건으로 접는다.
        #   한 문장이 5조각으로 나뉘어 각기 다른 라벨을 받는 것은 정상 분리다
        seen_key, hit = set(), []
        for stem, aid, b, t in items:
            if not rx.search(b):
                continue
            k = (batch_of(stem), aid, t)
            if k in seen_key:
                continue
            seen_key.add(k)
            hit.append((t, b))
        if not hit:
            continue
        c = collections.Counter(t for t, _ in hit)
        mark = '★' if len(c) > 2 else ' '
        if len(c) > 2:
            n2 += 1
        print('  %s %-8s %3d건 → 라벨 %d종  %s'
              % (mark, name, len(hit), len(c), dict(c.most_common(6))))
    print()
    print('  ★ 라벨이 3종 이상으로 흩어진 축 %d개' % n2)
    print('    같은 주제는 같은 워딩으로 묶여야 한다 (sky 2026-08-16)')
    return len(multi), n2


def register(paths):
    """판독 결과의 신설 라벨을 대장에 넣는다. ★ 이것만 파일을 쓴다."""
    known, groups = load_known(), load_groups()
    items = collect(paths)
    reg = {}
    if os.path.exists(REGISTRY):
        reg = json.load(open(REGISTRY, encoding='utf-8'))
    reg.setdefault('신설 라벨', {})
    added = []
    for val, grp, stem, quote in items:
        if not val or val in known or val in ('N/A', '미분류'):
            continue
        if val in reg['신설 라벨']:
            continue
        reg['신설 라벨'][val] = {
            'topic_group': grp,
            '처음 낸 회차': stem,
            '근거': quote,
        }
        added.append(val)
    if added:
        json.dump(reg, open(REGISTRY, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        # ★ 등록과 동시에 사이드카에도 올린다 (CP-44 · sky 지적)
        #   "토픽은 별도로 승인 절차를 완화하자고 했기에"
        #   대장에만 있으면 게이트는 통과하는데 build_bundle --apply 의
        #   계약 검증(V-0-2)이 반려한다. 「낼 수는 있는데 반영은 안 되는」 상태였다.
        #   문을 두 개 둘 이유가 없다. 게이트가 이미 두 조건을 검사한다
        _promote()
    print('  대장에 등록 %d종: %s' % (len(added), added or '(없음)'))
    return added


def _promote():
    """대장에 있는데 사이드카에 없는 라벨을 올린다. 등록과 함께 자동으로 돈다."""
    if not os.path.exists(REGISTRY):
        return 0
    reg = json.load(open(REGISTRY, encoding='utf-8'))
    side = json.load(open(SIDE_T, encoding='utf-8'))
    gm = json.load(open(SIDE_G, encoding='utf-8'))
    n = 0
    for t2, v in (reg.get('신설 라벨') or {}).items():
        if t2 in side['확장 라벨']:
            continue
        grp = v.get('topic_group') or gm.get('topic_to_group', {}).get(t2, '')
        side['확장 라벨'][t2] = {'영역': grp, '근거 어휘': [],
                              'include': v.get('근거', ''), 'exclude': '',
                              '출처': '판독자 신설 · %s' % v.get('처음 낸 회차', '')}
        gm['topic_to_group'][t2] = grp
        if grp and t2 not in gm['그룹'].setdefault(grp, []):
            gm['그룹'][grp].append(t2)
        n += 1
    if n:
        json.dump(side, open(SIDE_T, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(gm, open(SIDE_G, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  ★ 사이드카로 함께 올림 %d종 — 바로 반영 가능하다' % n)
    return n


def main():
    if '--register' in sys.argv:
        paths = [a for a in sys.argv[1:] if a.endswith('.md')]
        if not paths:
            print('★ --register 는 판독결과 파일이 필요하다')
            sys.exit(1)
        register(paths)
        return
    if '--drift' in sys.argv:
        items, rows = read_all_judgments()
        drift(items, rows)
        return

    paths = [a for a in sys.argv[1:] if a.endswith('.md')]
    known = load_known()
    groups = load_groups()

    print('=' * 70)
    print('  topic 대장 — %d종' % len(known))
    print('=' * 70)
    by = collections.Counter(known.values())
    for k, v in by.most_common():
        print('    %-24s %3d' % (k, v))

    # ── 대장 안에서 이미 흩어진 것이 있는가
    ks = sorted(known)
    dup = []
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            s = similarity(a, b)
            if s >= 0.55:
                dup.append((s, a, b))
    print()
    print('  ★ 대장 안 동의어 후보 %d쌍 (유사도 0.55 이상)' % len(dup))
    for s, a, b in sorted(dup, reverse=True)[:12]:
        print('     %.2f  %-22s  <->  %s' % (s, a, b))

    # ── 그룹이 안 붙은 라벨
    miss = [t for t in known if t not in groups and t not in ('N/A', '미분류')]
    print()
    print('  ★ topic_group 이 안 붙은 라벨 %d종' % len(miss))
    for t in miss[:12]:
        print('     %s' % t)

    if not paths:
        items, rows = read_all_judgments()
        drift(items, rows)
        print()
        print('판독 결과를 검사하려면:  python topic_registry.py <판독결과.md> ...')
        print('신설 라벨을 등록하려면:  python topic_registry.py --register <판독결과.md> ...')
        return

    # ── 판독 결과의 신설 라벨 검사
    items = collect(paths)
    new = [x for x in items if x[0] not in known]
    print()
    print('=' * 70)
    print('  판독 결과 %d개 · topic 제안 %d건 · ★ 신설 라벨 %d건'
          % (len(paths), len(items), len({x[0] for x in new})))
    print('=' * 70)
    bad = 0
    for t in sorted({x[0] for x in new}):
        rows = [x for x in new if x[0] == t]
        g = next((x[1] for x in rows if x[1]), '')
        near = sorted(((similarity(t, k), k) for k in known), reverse=True)[:2]
        flag = []
        if not g:
            flag.append('★ topic_group 없음')
            bad += 1
        if near and near[0][0] >= 0.55:
            flag.append('★ 기존 「%s」 와 유사 %.2f' % (near[0][1], near[0][0]))
            bad += 1
        print('  %-24s %2d건  group=%-10s %s'
              % (t, len(rows), g or '(없음)', ' · '.join(flag)))
        print('        근거: %s' % rows[0][3])
    print()
    print('  ★ 조치 필요 %d건' % bad)
    if not bad:
        print('  ★ 신설 라벨이 전부 그룹을 갖고 있고 기존 라벨과 겹치지 않는다')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
