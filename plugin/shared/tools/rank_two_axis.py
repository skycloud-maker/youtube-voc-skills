"""개선 우선순위를 두 축으로 낸다 (sky 2026-08-19)

sky — "하나라도 크리티컬한 이슈라면 바라봐야 하는 게 맞는 것 같아서
       단순히 건수를 나눠서 낮은 건 돋보이지 못하게 한다는 지양하면 좋겠다.
       건수 위주로 볼 때와 내용으로 볼 때의 순서를 나눠서 직접 조회할 수 있게"

★ 왜 한 축으로는 안 되나
  지금 점수 = |평균 부정 강도| × 부정 건수 다. 둘을 곱해서 하나로 섞는다.
      로봇청소기 내구성/고장   3건 · 평균 -3.67  →  11.0
      세탁기 알림·사운드      86건 · 평균 -0.52  →  11.0
  같은 점수인데 성격이 정반대다 —
      앞은 「세 명이 크게 화났다」, 뒤는 「여든여섯 명이 조금씩 불편하다」
  섞어 놓으면 어느 쪽인지 알 수 없고, 작은 것을 걸러 내면 크리티컬을 놓친다

★ 1차 엔진의 priority_score 는 그대로 둔다 (동결 유지).
  2차는 옆에 두 축을 나란히 붙일 뿐이다
"""
from __future__ import annotations

import collections, csv, io, os, sys

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

D = os.path.join(BASE, '_판독패키지', '_결과', 'master_final')


def num(v):
    try:
        return float(str(v).strip() or 0)
    except Exception:
        return 0.0


def main():
    # ★ 없는 파일을 그냥 열지 않는다 (2026-08-26에 고침).
    #   3차_마무리 가 이 도구를 부른다. 데이터가 없으면 안내 없이 죽어
    #   마무리 전체가 거기서 멈췄다. 다른 도구는 전부 안내하고 멈춘다.
    _p = os.path.join(D, 'raw_voc.csv')
    if not os.path.exists(_p):
        print('  raw_voc.csv 가 없습니다 — 먼저 만들어야 합니다')
        print('     %s' % _p)
        print('     ↳ 3차 통합을 먼저 돌리십시오 (build_master.py)')
        return 1
    rows = list(csv.DictReader(open(_p, encoding='utf-8-sig')))
    g = collections.defaultdict(list)
    for r in rows:
        if kind(r) != '라벨':
            continue
        g[(r.get('product_category', ''), r['topic'].strip())].append(r)

    out = []
    for (pc, tp), v in g.items():
        # 부정 강도 — 감정·성공 점수 중 낮은 쪽. 양수면 0
        neg = [min(num(r.get('tee_emotion_score')), num(r.get('tee_success_score')), 0) for r in v]
        nc = sum(1 for x in neg if x < 0)
        mean_neg = sum(neg) / len(neg) if v else 0
        worst = min(neg) if neg else 0
        deep = [x for x in neg if x < 0]
        mean_when_neg = sum(deep) / len(deep) if deep else 0
        rc = sum(1 for r in v
                 if str(r.get('rootcause_problem') or '').strip()
                 not in ('', 'N/A', '없음', '-')) / len(v)
        out.append({
            'product_category': pc, 'topic': tp,
            'topic_group': v[0].get('topic_group', ''),
            'n': len(v), 'neg_count': nc,
            'neg_ratio': round(nc / len(v), 3),
            'mean_neg': round(mean_neg, 3),
            # ★ 축 A — 얼마나 많은 사람이 말했나
            '건수축_점수': nc,
            # ★ 축 B — 화난 사람은 얼마나 화났나 (건수를 안 본다)
            '심각도축_점수': round(abs(mean_when_neg), 3),
            '최고강도': abs(worst),
            'rc_coverage': round(rc, 3),
        })

    # 두 축으로 각각 순위를 매긴다
    for key, col in (('건수축_점수', '건수축_순위'), ('심각도축_점수', '심각도축_순위')):
        for i, r in enumerate(sorted(out, key=lambda x: (-x[key], -x['n'])), 1):
            r[col] = i
    # ★ 두 축 어느 쪽으로든 상위 20 안에 들면 표시한다 — 이게 「봐야 할 것」 이다
    for r in out:
        top = []
        if r['건수축_순위'] <= 20:
            top.append('건수')
        if r['심각도축_순위'] <= 20 and r['neg_count'] >= 1:
            top.append('심각도')
        r['봐야_하는가'] = ' · '.join(top)

    out.sort(key=lambda r: (min(r['건수축_순위'], r['심각도축_순위']), -r['n']))
    cols = ['product_category', 'topic', 'topic_group', 'n', 'neg_count', 'neg_ratio',
            'mean_neg', '건수축_점수', '건수축_순위', '심각도축_점수', '최고강도',
            '심각도축_순위', 'rc_coverage', '봐야_하는가']
    with io.open(os.path.join(D, '개선우선순위_두축.csv'), 'w',
                 encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c, '') for c in cols})

    print('개선 우선순위 %d줄 → 두 축' % len(out))
    print()
    print('★ 축 A — 건수 (얼마나 많은 사람이 말했나)')
    print('  %-3s %-10s %-18s %4s %4s' % ('', '제품군', '주제', '건수', '부정'))
    for r in sorted(out, key=lambda x: x['건수축_순위'])[:10]:
        print('  %-3d %-10s %-18s %4d %4d' % (r['건수축_순위'], r['product_category'][:10],
                                              r['topic'][:18], r['n'], r['neg_count']))
    print()
    print('★ 축 B — 심각도 (화난 사람은 얼마나 화났나 · 건수를 안 본다)')
    print('  %-3s %-10s %-18s %4s %6s %5s' % ('', '제품군', '주제', '건수', '평균강도', '최고'))
    for r in sorted(out, key=lambda x: x['심각도축_순위'])[:10]:
        if r['neg_count'] < 1:
            continue
        print('  %-3d %-10s %-18s %4d %6.2f %5.0f' % (r['심각도축_순위'], r['product_category'][:10],
                                                      r['topic'][:18], r['n'],
                                                      r['심각도축_점수'], r['최고강도']))
    print()
    both = [r for r in out if r['봐야_하는가'] == '건수 · 심각도']
    only_v = [r for r in out if r['봐야_하는가'] == '건수']
    only_s = [r for r in out if r['봐야_하는가'] == '심각도']
    print('★ 두 축 모두 상위 20  %d줄   ← 가장 먼저 봅니다' % len(both))
    for r in both:
        print('     %s × %s  (%d건)' % (r['product_category'], r['topic'], r['n']))
    print('   건수만 상위    %d줄' % len(only_v))
    print('   ★ 심각도만 상위 %d줄   ← 건수 기준이면 묻혔을 것들입니다' % len(only_s))
    for r in only_s[:8]:
        print('     %s × %s  (%d건 · 강도 %.1f)'
              % (r['product_category'], r['topic'], r['n'], r['심각도축_점수']))


if __name__ == '__main__':
    main()
