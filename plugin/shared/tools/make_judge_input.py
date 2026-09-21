"""3차 감독 입력 만들기 — 두 판독자를 대조해 갈린 행을 뽑고 A·B 로 익명화한다.

    python make_judge_input.py <판독자1_번들> <판독자2_번들> [--per 145]

    예)  python make_judge_input.py _판독패키지/_결과/final_v62 _판독패키지/_결과/cc_final

★ 왜 익명화하는가
  감독자에게 「이건 X사 답, 이건 Y사 답」 이라고 알려 주면 자기 쪽을 편들 수 있다.
  두 답을 A·B 로만 주고 행마다 어느 쪽이 A 인지 무작위로 섞는다.
  매핑은 ab_mapping.json 에 따로 두고 감독자에게 주지 않는다.
  ★ 실측 — 이렇게 했더니 감독자가 자기 답을 39% 만 골랐다. 편들지 않았다는 증거다

★ 비교는 반드시 번들끼리 한다
  판정 파일을 손으로 재구성해 비교하면 틀린다. 판독자가 1차 값을 그대로 받아들이면
  finding 이 안 나오는데, 그것을 「미판정」 으로 세면 일치율이 64% 로 잘못 나온다
  (실제는 81% 였다)

내는 것
    s13_judge/judge_input.csv     감독자에게 줄 것
    s13_judge/ab_mapping.json     ★ 감독자에게 주지 않는다
    s13_judge/judge_NN_ids.txt    회차 나누기
"""
from __future__ import annotations

import glob, collections, csv, io, json, os, random, sys

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다
from check_selfcheck import kind

# ★ --확인만 — 돌긴 돌되 **아무것도 안 남긴다** (sky 2026-08-25)
#   「도구가 도는지 보려고」 돌렸다가 데이터를 바꾼 일이 하루에 세 번 있었다.
#   셋 다 성공으로 끝났다 — 에러가 없어서 더 나빴다.
#   오류를 막는 것이 아니라, **잘 돌아도 안 건드리게** 하는 갈래다.
_확인만 = "--확인만" in __import__("sys").argv


def _확인만이면_멈춘다(무엇: str) -> bool:
    """쓰기 직전에 부른다. True 면 쓰지 말고 돌아간다."""
    if not _확인만:
        return False
    print()
    print("  ── 확인만 ──────────────────────────────────────────")
    print("     여기까지 돌았습니다. **아무것도 안 남겼습니다.**")
    print("     원래대로면 이것을 만들거나 덮어씁니다:")
    for x in 무엇.split(" · "):
        print("       · %s" % x.strip())
    print("     실제로 하려면 --확인만 을 빼고 다시 돌리십시오.")
    print("  ────────────────────────────────────────────────────")
    return True


try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def load(d):
    p = os.path.join(d, 'raw_voc.csv')
    if not os.path.exists(p):
        sys.exit('번들에 raw_voc.csv 가 없다: %s' % d)
    return {r['atomic_id']: r for r in csv.DictReader(open(p, encoding='utf-8-sig'))}


def answer(r):
    """그 판독자의 답을 한 줄로.

    ★ ③ 한쪽만 쪼갠 행에서는 한쪽에 그 조각이 **없다** (2026-08-25).
      없는 것을 「미분류」 로 적으면 감독이 「판독자가 못 골랐다」 로 읽는다.
      안 만든 것과 못 고른 것은 다르다.
    """
    if not r:
        return '(이 판독자는 이 조각을 만들지 않았습니다)'
    if kind(r) == '제외':
        return '제외 (%s)' % (r.get('scope_exclusion_reason') or '사유 없음')
    t = str(r.get('topic') or '').strip()
    return t if t not in ('', 'N/A', '미분류') else '미분류'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    per = 145
    if '--per' in sys.argv:
        per = int(sys.argv[sys.argv.index('--per') + 1])
    os.chdir(BASE)

    X, K = load(args[0]), load(args[1])
    ids = sorted(set(X) & set(K))
    print('겹친 행 %d  (판독자1 %d · 판독자2 %d)' % (len(ids), len(X), len(K)))

    same = [i for i in ids if kind(X[i]) == kind(K[i])]
    dis = [i for i in ids
           if kind(X[i]) != kind(K[i])
           or (kind(X[i]) == '라벨'
               and str(X[i]['topic']).strip() != str(K[i]['topic']).strip())]
    print('   방향 일치 %d = %.1f%%' % (len(same), 100 * len(same) / len(ids)))

    # ★★ 발라내기를 넷으로 (sky 승인 2026-08-25)
    #   전에는 ①② 만 넘겼다. ③④ 는 **감독이 볼 기회가 아예 없었다.**
    갈래 = {}
    for i in dis:
        갈래[i] = ('② 한쪽 라벨 · 한쪽 제외' if kind(X[i]) != kind(K[i])
                  else '① 라벨이 다름')

    # ③ 한쪽만 쪼갠 행 — id 가 한쪽에만 있으면 겹치기에서 빠진다
    #   ★ 1차 원본에 없는 id 다 = 판독자가 **새로 만든** 조각이다.
    #     한쪽은 「여긴 두 주제다」 했고 한쪽은 안 했는데 아무도 심판하지 않았다
    한쪽만 = sorted(set(X) ^ set(K))
    for i in 한쪽만:
        갈래[i] = '③ 한쪽만 쪼갠 행'

    # ④ 과분리 후보 — 둘 다 합의했지만 한 원문이 여러 조각인 것
    #   ★ 판독자 둘 다 병합을 한 건도 안 냈다. 물어야 나온다
    _합의 = [i for i in ids if i not in dis]
    _형제 = collections.defaultdict(list)
    for i in _합의:
        _형제[X[i].get('source_id') or i.rsplit('-', 1)[0]].append(i)
    for _s, _v in _형제.items():
        if len(_v) > 1:
            for i in _v:
                갈래[i] = '④ 과분리 후보 (둘 다 합의)'

    # ★ 갈래를 회차마다 **고루 섞는다** (2026-08-25에 고침).
    #   전에는 갈래 순으로 정렬해서 ③④ 가 마지막 3회차에 몰렸다.
    #   확장의 핵심을 맨 뒤에 두면, 거기서 잘못돼도 11회차를 다 돌고 나서야 안다.
    #   ★ 무리 안에서의 **자리 비율**로 정렬하면 제 비율대로 섞인다.
    _차례 = {}
    _무리 = collections.defaultdict(list)
    for _i in sorted(갈래, key=lambda i: (
            갈래[i],
            (X.get(i) or K.get(i) or {}).get('source_id') or '', i)):
        _무리[갈래[_i]].append(_i)
    for _g, _v in _무리.items():
        for _n, _i in enumerate(_v):
            # 0.0 ~ 1.0 — 그 무리 안에서 몇 번째쯤인가
            _차례[_i] = ((_n + 0.5) / len(_v), _g, _i)
    골라낸것 = sorted(갈래, key=lambda i: _차례[i])
    print('   ★ 감독자에게 넘길 행 %d' % len(골라낸것))
    for _k, _n in sorted(collections.Counter(갈래.values()).items()):
        print('        %-26s %5d' % (_k, _n))

    # ★ 부모 댓글과 조각 수를 미리 모은다 (2026-08-25)
    #   답글은 부모를 봐야 뜻이 통한다. 4차에서 실무자가
    #   「parent 댓글을 참고로 할 때」 라며 여러 번 되짚었다.
    #   조각 수는 과소·과분리를 보는 자리다 — 한 원문이 몇 조각인가.
    조각수 = collections.Counter(
        r.get('source_id', '') for r in X.values() if r.get('source_id'))
    부모 = {}
    for _r in X.values():
        _글 = ' '.join((_r.get('original_voc') or '').split())
        if not _글:
            continue
        for _키 in (_r.get('source_id', ''), _r.get('atomic_id', '')):
            if _키:
                부모.setdefault(_키, _글)

    # ★ 행마다 A/B 를 섞는다. 한쪽이 늘 A 면 그것도 신호가 된다
    # ★ 씨앗을 판마다 바꾼다 — 같은 씨앗이면 매핑이 재현되어 익명화가 뚫린다
    random.seed(20260826)
    rows, mapping = [], {}

    # ★ 형제 조각을 함께 준다 (2026-08-25).
    #   ③④ 는 「이 분리가 맞나」 를 묻는다. 형제를 안 보여 주면 판단할 수가 없다.
    _같은원문 = collections.defaultdict(list)
    for _d in (X, K):
        for _i, _r in _d.items():
            _s = _r.get('source_id') or _i.rsplit('-', 1)[0]
            if _i not in [z[0] for z in _같은원문[_s]]:
                _같은원문[_s].append((_i, ' '.join((_r.get('atomic_voc') or '').split())))

    _물음 = {
        '① 라벨이 다름': 'A 와 B 중 어느 쪽이 맞습니까 (아니면 C·D)',
        '② 한쪽 라벨 · 한쪽 제외': 'A 와 B 중 어느 쪽이 맞습니까 (아니면 C·D)',
        '③ 한쪽만 쪼갠 행': '★ 한쪽만 이 조각을 만들었습니다. 이 분리가 맞습니까',
        '④ 과분리 후보 (둘 다 합의)': '★ 이 원문을 이렇게 나눈 것이 맞습니까 (합칠 것인가)',
    }

    for i in 골라낸것:
        a_is_x = random.random() < 0.5
        _x, _k = X.get(i), K.get(i)
        a, b = (_x, _k) if a_is_x else (_k, _x)
        mapping[i] = {'A': args[0] if a_is_x else args[1],
                      'B': args[1] if a_is_x else args[0]}
        src = _x or _k
        # ★ 원문·parent·조각 수를 함께 준다 (sky 2026-08-25)
        #   감독은 「A 냐 B 냐」 만 고르는 자리가 아니라
        #   **분리가 맞는지까지 보는** 자리다. 그러려면 원문이 있어야 한다.
        같은원문 = 조각수.get(src.get('source_id', ''), 1)
        rows.append({
            'atomic_id': i,
            'product': src.get('product_category', ''),
            'voc_cleaned': ' '.join((src.get('voc_cleaned') or '').split()),
            'atomic_voc': ' '.join((src.get('atomic_voc') or '').split()),
            'original_voc': ' '.join((src.get('original_voc') or '').split()),
            # ★ 답글일 때만 채운다 (2026-08-25).
            #   부모 댓글은 parent_voc_id 가 자기 source_id 라
            #   그냥 찾으면 **자기 글이 부모로** 들어간다.
            'parent_voc': (
                ' '.join((부모.get(src.get('parent_voc_id', '')) or '').split())
                if str(src.get('comment_relation', '')) == 'reply' else ''),
            'video_title': ' '.join((src.get('video_title') or '').split()),
            '이_원문의_조각수': 같은원문,
            # ★ 왜 이 행이 왔는가 · 무엇을 물어보는가 (2026-08-25)
            '갈래': 갈래[i],
            '물음': _물음[갈래[i]],
            # ★ 형제 조각 — 분리가 맞는지 보려면 이것이 있어야 한다
            '형제조각': ' ⁄ '.join(
                '%s %s' % (_j.rsplit('-', 1)[-1], _t[:60])
                for _j, _t in sorted(_같은원문.get(src.get('source_id', ''), []))),
            'A': answer(a), 'B': answer(b),
        })

    if _확인만이면_멈춘다('judge_input.csv · ab_mapping.json · judge_NN_ids.txt'):
        return 0

    d = os.path.join(BASE, 's13_judge')
    os.makedirs(d, exist_ok=True)

    # ★★ 이미 쓴 판정이 있으면 덮어쓰지 않는다 (2026-08-25).
    #   덮어쓰면 매핑과 판정이 짝이 안 맞아 편향검사가 엉뚱한 숫자를 낸다.
    #   에러가 아니라 **그럴듯한 숫자**가 나오므로 더 나쁘다.
    #   ★ 실제로 겪었다 — 시험 삼아 돌렸다가 끝난 판의 정답지를 날렸다.
    _쓴것 = glob.glob(os.path.join(BASE, '_판독패키지', '_결과',
                                  '감독결과_*.md'))
    _매핑 = os.path.join(d, 'ab_mapping.json')
    if _쓴것 and os.path.exists(_매핑) and '--덮어쓰기' not in sys.argv:
        print()
        print('  ★ 이미 감독 판정이 %d개 있습니다. 덮어쓰지 않습니다.' % len(_쓴것))
        print('     지금 덮어쓰면 매핑과 판정이 짝이 안 맞아')
        print('     편향검사가 엉뚱한 숫자를 냅니다 (에러도 안 납니다).')
        print()
        print('     정말 새로 만들려면 판정 파일을 먼저 치우거나:')
        print('        python make_judge_input.py <번들1> <번들2> --덮어쓰기')
        return 1

    with io.open(os.path.join(d, 'judge_input.csv'), 'w',
                 encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=[
            'atomic_id', 'product', 'voc_cleaned', 'atomic_voc',
            # ★ 감독이 분리까지 보려면 원문이 있어야 한다 (2026-08-25)
            'original_voc', 'parent_voc', 'video_title',
            '이_원문의_조각수', '갈래', '물음', '형제조각',
            'A', 'B'])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    json.dump(mapping, io.open(os.path.join(d, 'ab_mapping.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    for k in range(0, len(rows), per):
        io.open(os.path.join(d, 'judge_%02d_ids.txt' % (k // per + 1)), 'w',
                encoding='utf-8').write(
            '\n'.join(r['atomic_id'] for r in rows[k:k + per]) + '\n')

    print()
    print('  s13_judge/judge_input.csv    %d행' % len(rows))
    print('  s13_judge/ab_mapping.json    ★ 감독자에게 주지 마십시오')
    print('  회차 %d개 (한 회차 %d행)' % ((len(rows) + per - 1) // per, per))
    print()
    print('  다음 — _판독패키지/0_붙여넣을_프롬프트_감독.md 를 서로 다른 LLM 둘에게 붙입니다')


if __name__ == '__main__':
    main()
