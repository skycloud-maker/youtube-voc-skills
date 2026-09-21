"""sky 채점 159행을 읽어 데이터에 반영한다 (2026-08-19)

채점이 「1 또는 2」 하나만 고르는 형태가 아니었다. sky 가 폭넓게 적었다.
  1 · 2          한쪽이 맞다                        91
  3              둘 다 아니다 — 옆에 대안을 적었다      37
  1,2 / 2,3 …    여러 개가 다 맞다                   17
  (빈칸)         원문만으로는 판단이 안 된다 (parent 필요)  11

★ 이 갈래가 뜻하는 것
  「여러 개가 다 맞다」 는 감독자가 틀린 것이 아니라 한 행에 주제가 여럿이라는 뜻이다.
  sky 결정 — 비슷한 주제면 topic_secondary 에 보조로 두고,
             불만·요청이 향하는 대상이 다르면 행을 나눈다
"""
from __future__ import annotations

import collections, csv, io, os, re, sys

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다
from check_selfcheck import kind

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ★ 전에는 sky 개인 OneDrive 파일이 박혀 있었다 (sky 2026-08-21).
#   이제 채점지를 인자로 받는다. 안 주면 옆에 있는 것을 쓴다.
XLSX = next((a for a in sys.argv[1:] if a.endswith(('.xlsx', '.csv'))), '')
if not XLSX:
    import glob as _g
    _here = os.path.dirname(os.path.abspath(__file__))
    _hits = (_g.glob(os.path.join(_here, '채점지*.xlsx'))
             + _g.glob(os.path.join(_here, '..', '예시', '채점지*.csv'))
             + _g.glob(os.path.join(_here, '채점지*.csv')))
    XLSX = _hits[0] if _hits else ''
# sky 가 「분석할 내용이 없다 · 제외」 라고 적은 말들
EXCL = re.compile(r'(^제외$|분석 제외|분석할 내용이 없|분석 가치는 없|분석 내용 없|단순 사용법|단순 원리)')


def read_grade():
    import openpyxl
    from pathlib import Path
    # ★ 없는 파일을 그냥 열지 않는다 (2026-08-26에 고침).
    # ★ 채점지는 .xlsx 여야 한다 (2026-08-26에 고침).
    #   찾기가 `채점지*.csv` 도 함께 잡아 openpyxl 이 csv 를 열다 죽었다.
    #   「없다」 가 아니라 「엉뚱한 것을 잡았다」 가 원인이었다.
    if (not str(XLSX).strip()
            or not Path(str(XLSX)).exists()
            or Path(str(XLSX)).suffix.lower() not in ('.xlsx', '.xlsm')):
        print('  채점 엑셀이 없습니다 — 먼저 넣어야 합니다')
        print('     %s' % XLSX)
        raise SystemExit(1)
    w = openpyxl.load_workbook(XLSX, read_only=True)
    ws = w[w.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    hdr = [str(x or '') for x in next(it)]
    rows = [dict(zip(hdr, r)) for r in it if any(r)]
    w.close()
    return rows


def main():
    G = read_grade()
    M = list(csv.DictReader(open(os.path.join(BASE, 's15_master', 'raw_voc.csv'),
                                 encoding='utf-8-sig')))
    idx = {r['atomic_id']: r for r in M}

    stats = collections.Counter()
    split_need, parent_need = [], []

    for g in G:
        aid = str(g.get('atomic_id') or '').strip()
        r = idx.get(aid)
        if not r:
            stats['★ 행을 못 찾음'] += 1
            continue
        ans = str(g.get('답') or '').strip()
        note = str(g.get('틀렸으면 무엇') or '').strip()
        a1, a2 = str(g.get('①/붙은라벨') or ''), str(g.get('②/판독자판정') or '')

        def put(v):
            """'라벨 세탁 성능' / '제외 no_analytic_value' 를 행에 얹는다"""
            v = v.strip()
            if v.startswith('제외'):
                r['status'] = 'scope_excluded'
                r['scope_exclusion_reason'] = v.replace('제외', '').strip(' ()') or 'no_analytic_value'
                r['topic'] = 'N/A'
            elif v.startswith('라벨'):
                r['status'] = 'normal'
                r['topic'] = v.replace('라벨', '').strip()

        # ── sky 가 제외라고 적었으면 그것이 먼저다
        if note and EXCL.search(note):
            r['status'] = 'scope_excluded'
            r['scope_exclusion_reason'] = 'no_analytic_value'
            r['topic'] = 'N/A'
            r['decided_by'] = 'sky'
            r['decided_note'] = note.replace('\n', ' / ')
            stats['sky → 제외'] += 1
            continue

        if ans in ('1', '2'):
            put(a1 if ans == '1' else a2)
            r['decided_by'] = 'sky'
            r['decided_note'] = ('감독자 %s 채택' % ans) + (' · ' + note.replace('\n', ' / ') if note else '')
            stats['sky 가 한쪽 채택'] += 1
            if note:                       # 의견이 있으면 보조 라벨로 남긴다
                r['topic_secondary'] = note.replace('\n', ' | ')
                stats['보조 라벨 기록'] += 1
        elif ',' in ans:
            # ★ 여러 개가 다 맞다 — 첫 번째를 주 라벨로, 나머지는 보조로
            first = ans.split(',')[0].strip()
            put(a1 if first == '1' else (a2 if first == '2' else ''))
            rest = [x for x in (a1 if '1' in ans else '', a2 if '2' in ans else '', note) if x]
            r['topic_secondary'] = ' | '.join(x.replace('라벨', '').strip() for x in rest[1:])
            r['decided_by'] = 'sky'
            r['decided_note'] = '여러 주제가 있다 (%s) — 분리 검토 대상' % ans
            split_need.append((aid, ans, note))
            stats['★ 여러 주제 — 분리 검토'] += 1
        elif ans == '3':
            # 둘 다 아니다. sky 가 적은 대안을 주 라벨 후보로
            r['decided_by'] = 'sky'
            r['decided_note'] = '둘 다 아니다 — sky 대안: ' + note.replace('\n', ' / ')
            r['topic_secondary'] = note.replace('\n', ' | ')
            split_need.append((aid, ans, note))
            stats['★ 둘 다 아니다 — 라벨 재지정'] += 1
        elif not ans:
            parent_need.append(aid)
            r['decided_by'] = 'sky_보류'
            r['decided_note'] = '원문만으로 판단 불가 — 앞 댓글이 필요하다'
            stats['★ parent 필요'] += 1
        else:
            r['decided_note'] = (r.get('decided_note') or '') + ' | sky: ' + ans
            stats['그 외'] += 1

    # ── 대장 개편 반영 — 「주거 수납/공간」 을 「공간 활용성」 이 흡수했다
    for r in M:
        if r.get('topic', '').strip() == '주거 수납/공간':
            r['topic'] = '공간 활용성'
            stats['주거 수납/공간 → 공간 활용성'] += 1

    cols = list(M[0].keys())
    for c in ('topic_secondary',):
        if c not in cols:
            cols.append(c)
    with io.open(os.path.join(BASE, 's15_master', 'raw_voc.csv'), 'w',
                 encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in M:
            w.writerow({c: r.get(c, '') for c in cols})

    # 다음 회차 입력 두 개
    d = os.path.join(BASE, 's17_sky')
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, 'split_check.csv'), 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.writer(h)
        w.writerow(['atomic_id', 'product_category', 'atomic_voc',
                    'sky_답', 'sky_의견', '지금_라벨'])
        for aid, ans, note in split_need:
            r = idx[aid]
            w.writerow([aid, r.get('product_category', ''),
                        ' '.join((r.get('atomic_voc') or '').split()),
                        ans, note.replace('\n', ' / '), r.get('topic', '')])
    io.open(os.path.join(d, 'parent_need_ids.txt'), 'w',
            encoding='utf-8').write('\n'.join(parent_need) + '\n')

    for k, v in stats.most_common():
        print('   %-28s %4d' % (k, v))
    print()
    print('   s17_sky/split_check.csv       %d행  ← 분리·라벨 재지정 대상' % len(split_need))
    print('   s17_sky/parent_need_ids.txt   %d행  ← parent 붙여 다시 채점' % len(parent_need))
    c = collections.Counter(kind(r) for r in M)
    print()
    print('   라벨 %d · 제외 %d · 미판정 %d' % (c['라벨'], c['제외'], c['미판정']))


if __name__ == '__main__':
    main()
