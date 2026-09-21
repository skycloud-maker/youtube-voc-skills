"""4차 채점지 만들기 — 사람이 볼 최소한만 뽑는다.

    python make_grading_sheet.py <번들> [--구간 갈림|합의|감독자] [--개수 30]

    갈림   두 감독자가 서로 다른 답을 낸 행        「어느 쪽이 맞나」 를 묻는다
    합의   두 판독자가 같은 답을 낸 행에서 표본   「합의한 답이 맞나」 를 묻는다
    감독자   감독자가 정한 행에서 표본               「감독자 판정이 맞나」 를 묻는다

★ 왜 구간을 나누는가
  정확도를 하나의 숫자로 말할 수 없다. 행마다 누가 정했는지가 다르다.
  실측 — 판독자 둘이 합의한 구간 93% · 감독자까지 거치고도 갈린 구간 73%
  구간별로 재야 「어디까지 믿고 어디부터 사람이 볼지」 가 나온다

★ 채점지를 만들 때 지키는 것
  · 표본을 바꾸지 않는다. 앞뒤를 비교하려면 같은 행이어야 한다
  · 「여러 개가 맞아 보이면 다 적으셔도 됩니다」 를 넣는다
    ★ 그 정보가 라벨 6종 신설로 이어졌다. 하나만 고르게 하면 그게 안 나온다
  · 선을 미리 적어 둔다. 결과를 보고 기준을 바꾸지 않기 위해서다

내는 것
    채점지_<구간>_<개수>행.md   읽기 편한 쪽
    채점지_<구간>_<개수>행.csv  엑셀로 볼 쪽
"""
from __future__ import annotations

import collections, csv, io, os, random, sys

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


def answer_of(r):
    if kind(r) == '제외':
        return '제외 (%s)' % (r.get('scope_exclusion_reason') or '')
    return str(r.get('topic') or '').strip()


def pick_rows(rows, band, n):
    """구간별로 대상을 고른다"""
    if band == '갈림':
        # decided_by 가 sky_필요 = 감독자끼리 갈려 사람이 봐야 하는 행
        tgt = [r for r in rows if 'sky_필요' in str(r.get('decided_by') or '')]
        return tgt, False                       # 표본이 아니라 전량이다
    if band == '합의':
        tgt = [r for r in rows if str(r.get('decided_by') or '').startswith('reader_agree')]
    else:
        tgt = [r for r in rows if str(r.get('decided_by') or '').startswith('judge')]
    # 라벨·제외 비율대로 뽑는다
    by = collections.defaultdict(list)
    for r in tgt:
        by[kind(r)].append(r)
    random.seed(20260819)
    out = []
    for k, v in sorted(by.items(), key=lambda x: -len(x[1])):
        random.shuffle(v)
        out += v[:max(1, round(n * len(v) / max(1, len(tgt))))]
    random.shuffle(out)
    return out[:n], True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print(__doc__)
        sys.exit(1)
    band = sys.argv[sys.argv.index('--구간') + 1] if '--구간' in sys.argv else '갈림'
    n = int(sys.argv[sys.argv.index('--개수') + 1]) if '--개수' in sys.argv else 30
    os.chdir(BASE)

    rows = list(csv.DictReader(open(os.path.join(args[0], 'raw_voc.csv'),
                                    encoding='utf-8-sig')))
    pick, sampled = pick_rows(rows, band, n)
    if not pick:
        print('%s 구간에 해당하는 행이 없다' % band)
        return
    print('%s 구간 %d행%s' % (band, len(pick), ' (표본)' if sampled else ' (전량)'))
    print('  ', dict(collections.Counter(kind(r) for r in pick)))

    L = ['# 채점지 — %s 구간 %d행\n' % (band, len(pick))]
    if band == '갈림':
        L += ['자동 판독이 **끝까지 답을 못 낸 행**입니다. 사람이 정해야 하는 마지막 묶음입니다.\n',
              '```', '1 또는 2   맞는 쪽 번호',
              '3          둘 다 아니다 — 옆에 맞는 주제를 한 단어로', '?          모르겠다', '```']
    else:
        L += ['확정된 답이 맞는지 봐 주십시오.\n',
              '```', 'O   맞다', 'X   아니다 — 옆에 맞는 주제를 한 단어로', '?   모르겠다', '```']
    L += ['```',
          '★ 여러 개가 맞아 보이면 다 적으셔도 됩니다',
          '  「제외」 는 이 댓글이 제품 얘기가 아니라는 뜻입니다',
          '  (채널 칭찬 · 인사 · 잡담 · 광고 · 영상 대본)',
          '```', '']
    if sampled:
        L += ['```',
              'O %d개 이상 (90%%)  → 이 구간을 믿고 갑니다' % round(n * 0.9),
              'O %d~%d개 (80%%)    → 쓰되 「참고」 로 표시합니다' % (round(n * 0.8), round(n * 0.9) - 1),
              'O %d개 이하        → 이 구간을 사람이 봐야 합니다' % (round(n * 0.8) - 1),
              '★ 결과를 보고 이 선을 바꾸지 않습니다',
              '```', '']
    L += ['---', '']

    for i, r in enumerate(pick, 1):
        t = ' '.join((r.get('atomic_voc') or '').split())
        if len(t) > 190:
            t = t[:190] + ' …'
        L.append('**%2d.** %s' % (i, t))
        L.append('')
        if band == '갈림':
            note = str(r.get('decided_note') or '')
            L.append('> %s   ·   *%s*' % (note or answer_of(r), r.get('product_category') or ''))
        else:
            L.append('> 확정된 답 — **%s**   ·   *%s*'
                     % (answer_of(r), r.get('product_category') or ''))
        L.append('')
        L.append('`답:        `')
        L.append('')

    stem = '채점지_%s_%d행' % (band, len(pick))
    io.open(stem + '.md', 'w', encoding='utf-8').write('\n'.join(L))
    with io.open(stem + '.csv', 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.writer(h)
        w.writerow(['번호', 'atomic_id', '제품군', '원문', '확정된 답 / 감독자 의견',
                    '답', '아니면 무엇'])
        for i, r in enumerate(pick, 1):
            w.writerow([i, r['atomic_id'], r.get('product_category', ''),
                        ' '.join((r.get('atomic_voc') or '').split()),
                        str(r.get('decided_note') or '') if band == '갈림' else answer_of(r),
                        '', ''])
    print('  %s.md / .csv' % stem)


if __name__ == '__main__':
    main()
