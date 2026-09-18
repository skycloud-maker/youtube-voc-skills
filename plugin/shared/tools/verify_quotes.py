"""판독자가 댄 근거가 원문에 실재하는지 기계로 검증한다.

사용:
    python verify_quotes.py <판독결과.md> [<판독결과2.md> ...]

정답이 없어도 잴 수 있는 단 하나의 지표다.
판독이 맞았는지는 못 재지만, 근거를 지어냈는지는 잰다.

두 가지를 본다.
  ① 인용 실재율   finding.quote 가 1차 산출물의 어느 칸에 실제로 있는가
  ② 전사 정확도   판정이 되받아 적은 atomic_voc 가 원본과 같은가
                  ★ 되받아 적는 과정에서 원문이 변하면 그 뒤 판정은 전부 무효다

일치 판정은 관대하게 한다 — 공백·따옴표·말줄임을 정규화하고,
"앞부분…뒷부분" 형태의 생략 인용은 조각이 순서대로 다 있으면 통과시킨다.
관대하게 해도 안 걸리는 것만 "실재하지 않는 근거"로 본다.
"""
from __future__ import annotations

import os, re, sys, collections

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다
from build_bundle import read_judgments, read_csv, SRC

# 원문 대조에서 제외할 칸 — 인용이 여기서만 나오면 근거로 치지 않는다는 뜻이 아니라,
# 어느 칸에서 나왔는지를 구분해 보여주기 위해 전 칸을 다 뒤진다.
PRIMARY = ('atomic_voc', 'original_voc', 'voc_cleaned', 'voc_residual')

_WS = re.compile(r'\s+')
_QUOT = re.compile(r'["\'“”‘’「」『』`]')


def norm(s):
    """공백·따옴표를 지운다. 말줄임은 남긴다(조각 분리에 쓴다)."""
    s = _QUOT.sub('', str(s or ''))
    s = s.replace('…', '...')
    return _WS.sub('', s)


def frags(q):
    """말줄임으로 끊어 조각을 낸다. 2자 미만 조각은 버린다."""
    parts = [p for p in re.split(r'\.{2,}', norm(q)) if len(p) >= 2]
    return parts or ([norm(q)] if norm(q) else [])


def contains(hay, q):
    """hay 안에 q 의 조각이 순서대로 다 있으면 True."""
    pos = 0
    for f in frags(q):
        i = hay.find(f, pos)
        if i < 0:
            return False
        pos = i + len(f)
    return True


def load_source():
    rows = {}
    for prod, path in SRC.items():
        if not os.path.exists(path):
            continue
        rs, _ = read_csv(path)
        for r in rs:
            rows[r.get('atomic_id', '')] = r
    return rows


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = load_source()
    print('원본 atomic 행 %d개 적재' % len(src))

    for path in sys.argv[1:]:
        js = read_judgments(path)
        name = os.path.basename(path)

        n_q = n_hit = n_miss = 0
        n_prim = 0                       # 원문 계열 칸에서 나온 인용
        n_empty = 0                      # 지적은 했는데 인용이 비었다
        by_field = collections.Counter()  # 어느 칸에서 맞았나
        misses = []
        transcribe_bad, transcribe_n, no_src = [], 0, []

        for j in js:
            aid = j.get('atomic_id', '')
            row = src.get(aid)
            if row is None:
                no_src.append(aid)
                continue

            # ② 전사 정확도
            transcribe_n += 1
            a_said, a_real = norm(j.get('atomic_voc', '')), norm(row.get('atomic_voc', ''))
            if a_said and not (a_said == a_real or contains(a_real, j.get('atomic_voc', ''))):
                transcribe_bad.append((aid, j.get('atomic_voc', ''), row.get('atomic_voc', '')))

            # ① 인용 실재율
            hay = {k: norm(v) for k, v in row.items()}
            for f in j.get('findings', []) or []:
                q = f.get('quote', '')
                if not norm(q):
                    n_empty += 1
                    continue
                n_q += 1
                hits = [k for k, v in hay.items() if v and contains(v, q)]
                if hits:
                    n_hit += 1
                    pick = next((k for k in PRIMARY if k in hits), hits[0])
                    by_field[pick] += 1
                    if pick in PRIMARY:
                        n_prim += 1
                else:
                    n_miss += 1
                    misses.append((aid, f.get('field', ''), q))

        print()
        print('=' * 74)
        print(name)
        print('=' * 74)

        # ★ 이 도구는 **2차 판독 결과**를 봅니다 (2026-08-26).
        #   3차 감독 결과를 물리면 findings 도 없고, 조각 id(-02·-03)는
        #   1차 원본에 있을 리가 없어 「★ 원본에 없는 atomic_id 145건」
        #   같은 무서운 줄만 뜹니다. 데이터가 상한 게 아니라 **도구가 다릅니다.**
        #   0/0 을 0.0% 로 찍으면 사람이 그걸 「실패」 로 읽습니다.
        if n_q == 0 and n_empty == 0:
            print('  인용(finding.quote)이 하나도 없습니다 — 판정 %d건 읽음'
                  % len(js))
            if no_src:
                print('  원본에 없는 atomic_id %d건 (%s …)'
                      % (len(no_src), ', '.join(no_src[:2])))
            if transcribe_n:
                나쁨 = len(transcribe_bad)
                print('  ② 전사 정확도만 잽니다   %d/%d = %.1f%%'
                      % (transcribe_n - 나쁨, transcribe_n,
                         (transcribe_n - 나쁨) / transcribe_n * 100))
            print('  ★ ① 인용 실재율은 이 파일에서 못 잽니다 — 잴 것이 없습니다.')
            print('    이 도구는 **2차 판독 결과**를 봅니다. 그것은 판정마다')
            print('    findings 를 달고, findings 마다 quote 가 있습니다.')
            print('    3차 감독 결과에는 findings 가 아예 없습니다 (설계가 그렇습니다) —')
            print('    3차가 만든 조각 id 가 1차 원본에 없는 것도 정상입니다.')
            print('    3차는 check_lineage.py 와 조각덮개검사.py 가 봅니다.')
            if transcribe_bad:
                print()
                print('   ★ 원문을 바꿔 적은 행 %d건' % len(transcribe_bad))
                for aid, said, real in transcribe_bad[:6]:
                    print('     %s' % aid[:60])
                    print('       판정   %s' % said[:64])
                    print('       원본   %s' % real[:64])
            continue

        if no_src:
            print('★ 원본에 없는 atomic_id %d건 — %s' % (len(no_src), ', '.join(no_src[:3])))

        print('① 인용 실재율   %d/%d = %.1f%%   (지적 %d건 중 인용 없음 %d건)'
              % (n_hit, n_q, n_hit / n_q * 100 if n_q else 0, n_q + n_empty, n_empty))
        print('   그중 원문 계열(atomic_voc·original_voc·voc_cleaned)에서 나온 것  %d/%d = %.1f%%'
              % (n_prim, n_hit, n_prim / n_hit * 100 if n_hit else 0))
        print('② 전사 정확도   %d/%d = %.1f%%'
              % (transcribe_n - len(transcribe_bad), transcribe_n,
                 (transcribe_n - len(transcribe_bad)) / transcribe_n * 100 if transcribe_n else 0))

        if by_field:
            print()
            print('   인용이 맞은 칸')
            for k, v in by_field.most_common(10):
                mark = '  ← 원문' if k in PRIMARY else ''
                print('     %-28s %3d%s' % (k, v, mark))

        if misses:
            print()
            print('   ★ 원문 어느 칸에도 없는 인용 %d건' % len(misses))
            for aid, fld, q in misses[:12]:
                print('     %-46s %-16s %s' % (aid[:46], fld[:16], str(q)[:40]))

        if transcribe_bad:
            print()
            print('   ★ 원문을 바꿔 적은 행 %d건' % len(transcribe_bad))
            for aid, said, real in transcribe_bad[:6]:
                print('     %s' % aid[:60])
                print('       판정   %s' % said[:64])
                print('       원본   %s' % real[:64])


if __name__ == '__main__':
    main()
