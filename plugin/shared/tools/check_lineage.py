"""원문 - atomic 계보 검사 — 없던 게 만들어졌는가, 분리가 남김없이 되었는가.

사용:
    python check_lineage.py                    1차 산출물을 검사한다 (기준선)
    python check_lineage.py <판독결과.md> ...    판독 결과를 반영해 검사한다

★ sky 2026-08-16 제안
    "1. atomic 이 original 안에 있는가
     2. 'atomic 1개 혹은 2개 이상' · 'residual' · '불필요한 cleaned 된 내용' 이
        합해져서 하나의 original_voc 와 동일한가
     즉 없던 게 만들어진 상황과 분리가 남김없이 잘 이루어졌는가"

지금까지의 계약(부록 §1.3 C-1·C-3)은 **조각 대 atomic_voc** 만 봤다.
이 검사는 **원문(original_voc) 대 전체 계보** 를 본다. 한 층 위다.

    original_voc
      └ voc_cleaned        (원문에서 불필요한 것을 걷어낸 것)
          ├ atomic_voc     (1개 또는 여러 개)
          └ voc_residual   (atomic 으로 안 뽑히고 남은 것)

검사
    L-1  atomic_voc 가 original_voc 안에 문자 그대로 있는가
         ★ 없으면 「없던 것이 만들어진」 것이다. 가장 무거운 결함
    L-2  voc_cleaned 가 original_voc 안에 있는가
    L-3  Σatomic_voc + voc_residual 이 voc_cleaned 를 「빠짐없이 덮는가」
         ★ 「같은가」 가 아니라 「덮는가」 다.
           부록 §1.2 ④ - 조각에는 반응·평가까지 넣는다. 주제가 둘인데 반응이
           하나면 그 반응은 두 조각에 다 들어가야 각 조각이 온전한 VoC 가 된다.
           그래서 합이 원문보다 길 수 있다. 빠진 데가 있는지만 본다
    L-4  조각이 다른 조각에 통째로 들어 있는가
         ★ 겹침 자체는 정상이다. 통째로 포함되면 그 조각은 아무것도 더 말하지 않는다
    L-5  겹침 규모 - 결함이 아니라 관측값. 공유 반응이 얼마나 되는지 본다

공백·문장부호는 무시하고 비교한다. 판독자마다 다듬는 방식이 달라
그것까지 틀렸다고 하면 실제 결함이 묻힌다.
원본을 수정하지 않는다. 읽기 전용.
"""
from __future__ import annotations

import collections, os, re, sys

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다
from build_bundle import read_csv, PRODUCTS, read_judgments, SRC

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 공백·문장부호·이모지를 걷어내고 비교한다
STRIP = re.compile(r'[\s\.,!?~・…"\'‘’“”\(\)\[\]{}·\-—:;/\\]+')
# residual 은 여러 조각을 이어 붙인 값이다. 두 칸 이상 공백·줄바꿈으로 쪼갠다
RESID_SPLIT = re.compile(r'\s{2,}|[\r\n]+')


def norm(s):
    return STRIP.sub('', str(s or ''))


def load():
    rows, seen = {}, set()
    for prod in PRODUCTS:
        rs, _ = read_csv(SRC[prod])
        for r in rs:
            if r['atomic_id'] not in seen:
                seen.add(r['atomic_id'])
                rows[r['atomic_id']] = dict(r)
    return rows


def overlay(rows, paths):
    """판독 결과의 분리 조각과 정제 제안을 얹는다. 원본은 안 건드린다.

    ★ voc_cleaned 제안을 안 얹으면 L-3 오탐이 난다 (CP-43).
      2차가 원문에서 무엇을 걷어냈는데 검사기는 옛 cleaned 로 대조하니
      「덮이지 않은 대목」 이 있다고 잡는다.
      Claude Code 가 1회차에서 7건을 그렇게 맞았다 — 판독 결함이 아니라 내 버그다
    """
    rows = {k: dict(v) for k, v in rows.items()}
    added = 0
    # 먼저 정제 제안을 반영한다. 조각은 그 위에서 잡힌다
    for p in paths:
        for j in read_judgments(p):
            base = rows.get(j.get('atomic_id'))
            if base is None:
                continue
            newc = None
            for f in (j.get('findings') or []):
                if f.get('field') == 'voc_cleaned' and str(f.get('proposed', '')).strip():
                    newc = str(f['proposed'])
                    base['voc_cleaned'] = newc
            # ★ 안 나눈 행은 조각이 곳 cleaned 전체다 (CP-44 · Claude Code 지적).
            #   정제만 반영하고 atomic_voc 를 그대로 두면 옛 본문과 새 cleaned 를
            #   대조하게 되어 L-3 오탐이 난다. CC 두 회차에서 34건이 그것이었다
            if newc and not (j.get('structure') or {}).get('split'):
                base['atomic_voc'] = newc
    for p in paths:
        for j in read_judgments(p):
            st = j.get('structure') or {}
            if not st.get('split'):
                continue
            base = rows.get(j.get('atomic_id'))
            if base is None:
                continue
            for i, seg in enumerate(st.get('segments') or []):
                key = j['atomic_id'] if i == 0 else '%s#seg%02d' % (j['atomic_id'], i + 1)
                nr = dict(base)
                nr['atomic_id'] = key
                nr['atomic_voc'] = seg.get('atomic_voc', '')
                if i:
                    added += 1
                rows[key] = nr
    return rows, added


def main():
    paths = [a for a in sys.argv[1:] if a.endswith('.md')]
    rows = load()
    if paths:
        rows, added = overlay(rows, paths)
        print('판독 결과 %d개 반영 · 조각으로 늘어난 행 %d' % (len(paths), added))

    bysrc = collections.defaultdict(list)
    for r in rows.values():
        bysrc[r['source_id']].append(r)

    bad = collections.defaultdict(list)
    for sid, group in bysrc.items():
        orig = norm(group[0].get('original_voc'))
        cleaned = norm(group[0].get('voc_cleaned'))
        resid = norm(group[0].get('voc_residual'))

        # L-2  voc_cleaned ⊂ original_voc
        if cleaned and orig and cleaned not in orig:
            bad['L-2 cleaned 가 원문에 없다'].append(sid)

        # L-1  atomic_voc ⊂ original_voc
        #
        # ★ 1차 표기 관례는 예외로 둔다 (CP-38)
        #   scope_excluded 행은 atomic_voc 에 "N/A (분석 제외)" 라는 상태 문구를 넣는다.
        #   원문 발췌 칸에 상태가 들어간 것이라 그 자체로 개선 대상이지만(28번 E-3),
        #   1차 동결이라 못 고친다. 매 회차 판독자가 실패로 보고하게 되므로 뺀다.
        #   ★ 대신 몇 건인지는 따로 센다
        for r in group:
            a = norm(r.get('atomic_voc'))
            if not a or not orig:
                continue
            if a in orig:
                continue
            if (r.get('status') or '').strip() == 'scope_excluded' and 'N/A' in str(r.get('atomic_voc')):
                bad['L-0 (기준선) 1차 표기 관례 — scope_excluded 행의 상태 문구'].append(r['atomic_id'])
                continue
            bad['L-1 ★ atomic 이 원문에 없다'].append(r['atomic_id'])

        # L-3  Σatomic + residual 이 cleaned 를 「빠짐없이 덮는가」
        #
        # ★ 「같은가」 가 아니라 「덮는가」 다 (sky 2026-08-16)
        #   부록 §1.2 ④ — 조각에는 반응·평가까지 넣어야 한다.
        #   주제가 둘인데 반응이 하나면 그 반응은 두 조각에 다 들어가야
        #   각 조각이 온전한 VoC 가 된다. 그래서 합이 원문보다 길 수 있다.
        #   검사할 것은 「빠진 데가 있는가」 이지 「길이가 같은가」 가 아니다
        target = cleaned or orig
        spans = []
        if target:
            for r in group:
                a = norm(r.get('atomic_voc'))
                if not a:
                    continue
                k = target.find(a)
                if k >= 0:
                    spans.append((k, k + len(a), r['atomic_id']))
            # ★ residual 은 「이어진 한 덩어리」 가 아니다 (CP-38 에서 확인).
            #   원문 여기저기서 걷어낸 것을 이어 붙인 값이라 통짜로 찾으면
            #   첫 조각만 맞고 나머지를 놓친다. 조각 단위로 쪼개서 대조한다
            raw_resid = str(group[0].get('voc_residual') or '')
            for piece in RESID_SPLIT.split(raw_resid):
                q = norm(piece)
                if len(q) < 3:
                    continue
                k = target.find(q)
                if k >= 0:
                    spans.append((k, k + len(q), '(residual)'))

            gaps, pos = [], 0
            for s, e, _ in sorted(spans):
                if s > pos:
                    gaps.append((pos, s))
                pos = max(pos, e)
            if pos < len(target):
                gaps.append((pos, len(target)))
            excl = (group[0].get('status') or '').strip() == 'scope_excluded'
            for s, e in gaps:
                if e - s >= 3:          # 두 글자 이하는 다듬기 차이로 본다
                    # 위와 같은 이유 — 제외 행은 애초에 발췌를 안 한다
                    key = ('L-0 (기준선) 1차 표기 관례 — 제외 행은 발췌하지 않는다'
                           if excl else 'L-3 덮이지 않은 대목이 있다')
                    bad[key].append((sid, target[s:e][:40]))

        # L-4  조각이 다른 조각에 통째로 들어가 있는가
        #      ★ 겹침 자체는 정상이다 (공유 반응). 통째로 포함되면 그 조각은
        #        아무것도 더 말하지 않으므로 나눌 근거가 없다
        for x in spans:
            for y in spans:
                if x is y or '(residual)' in (x[2], y[2]):
                    continue
                # ★ 「동일」 도 잡는다 (CP-40).
                #   길이가 같으면 「포함」 조건에 안 걸려서 새고 있었다.
                #   labelC01 에서 Codex 가 조각 28개를 전부 원문 통째로 복사했는데
                #   이 검사기가 하나도 못 잡았다 — 내 구멍이었다
                if (x[0], x[1]) == (y[0], y[1]) and x[2] < y[2]:
                    bad['L-4 ★ 조각이 서로 동일하다 — 발췌를 안 했다'].append(
                        '%s = %s' % (x[2], y[2]))
                elif y[0] <= x[0] and x[1] <= y[1] and (y[1] - y[0]) > (x[1] - x[0]):
                    # ★ 부록 §2.2 와 충돌한다 (CP-43 · Claude Code 지적).
                    #   "반응이 하나면 두 조각에 다 넣어라" 를 따르면
                    #   인접한 두 주제가 반응 하나를 공유할 때
                    #   짧은 조각이 긴 조각에 통째로 들어갈 수 있다.
                    #   그때는 결함이 아니다 — 조각의 topic 이 서로 다르면 정상으로 본다
                    tx = next((s.get('topic') for r in group
                               for s in [r] if r.get('atomic_id') == x[2]), None)
                    ty = next((s.get('topic') for r in group
                               for s in [r] if r.get('atomic_id') == y[2]), None)
                    if tx and ty and tx != ty:
                        bad['L-5 (관측) 조각이 겹친다 - 공유 반응이면 정상'].append(
                            '%s in %s  (라벨이 달라 정상으로 본다)' % (x[2], y[2]))
                    else:
                        bad['L-4 조각이 다른 조각에 통째로 들어 있다'].append(
                            '%s in %s' % (x[2], y[2]))

        # L-5  겹침 규모 — 결함이 아니라 관측값이다
        if len(spans) > 1:
            tot = sum(e - s for s, e, _ in spans)
            union, pos = 0, 0
            for s, e, _ in sorted(spans):
                if e > pos:
                    union += e - max(s, pos)
                    pos = e
            if tot > union:
                bad['L-5 (관측) 조각이 겹친다 - 공유 반응이면 정상'].append(
                    '%s  중복 %d자' % (str(sid)[:36], tot - union))

    print()
    print('=' * 68)
    print('  계보 검사 — source %d개 · atomic %d행' % (len(bysrc), len(rows)))
    print('=' * 68)
    LABEL = [
        ('L-0 (기준선) 1차 표기 관례 — scope_excluded 행의 상태 문구',
         '1차 동결이라 못 고친다. 28번 E-3 으로 등록'),
        ('L-0 (기준선) 1차 표기 관례 — 제외 행은 발췌하지 않는다',
         '위와 같은 원인'),
        ('L-1 ★ atomic 이 원문에 없다', '없던 내용이 만들어졌다. 가장 무거운 결함'),
        ('L-2 cleaned 가 원문에 없다', '정제 단계에서 문구가 바뀌었다'),
        ('L-3 덮이지 않은 대목이 있다', '분리 과정에서 내용이 샜다'),
        ('L-4 ★ 조각이 서로 동일하다 — 발췌를 안 했다',
         '같은 대목에 라벨만 바꿔 단 것이다. 분리가 아니다'),
        ('L-4 조각이 다른 조각에 통째로 들어 있다', '그 조각은 아무것도 더 말하지 않는다'),
        ('L-5 (관측) 조각이 겹친다 - 공유 반응이면 정상', '결함이 아니다. 규모만 본다'),
    ]
    total = 0
    for key, why in LABEL:
        items = bad.get(key) or []
        if not key.startswith(('L-5', 'L-0')):
            total += len(items)
        mark = '★' if items else ' '
        print('  %s %-34s %4d건   %s' % (mark, key, len(items), why))
        for it in items[:5]:
            print('        %s' % (str(it)[:90]))
        if len(items) > 5:
            print('        ... 외 %d건' % (len(items) - 5))
    # ★ L-6 엄격 검사 (CP-46).
    #   위 L-1~L-5 는 공백·문장부호를 무시하고 본다. 판독자마다 다듬는 방식이
    #   달라서다. 그런데 1차 계약 검증(V-0-3)은 문자 그대로 본다.
    #   그래서 여기는 통과인데 최종 번들에서 반려되는 일이 생겼다 (203건).
    #   판독자가 「통과」 로 믿고 넘어가지 않도록 따로 알린다
    strict = []
    for sid, group in bysrc.items():
        raw_orig = str(group[0].get('original_voc') or '')
        for r in group:
            a = str(r.get('atomic_voc') or '')
            if not a or not raw_orig:
                continue
            if (r.get('status') or '').strip() == 'scope_excluded':
                continue
            if a not in raw_orig:
                strict.append((r.get('atomic_id'), a[:36]))
    print()
    print('  %s L-6 ★ 공백까지 그대로 원문에 있는가   %4d건   1차 계약 V-0-3 이 보는 것'
          % ('★' if strict else ' ', len(strict)))
    if strict:
        print('     ★ 위 L-1 은 공백을 무시해서 통과했지만 최종 번들에서 반려된다')
        for a, s in strict[:5]:
            print('        %-46s %s' % (str(a)[:46], s))
        if len(strict) > 5:
            print('        ... 외 %d건' % (len(strict) - 5))

    print()
    print('  합계 %d건' % total)
    if not total:
        print('  ★ 계보가 온전하다 — 없던 것이 만들어지지 않았고 남김없이 덮인다')
    sys.exit(1 if bad.get('L-1 ★ atomic 이 원문에 없다') else 0)


if __name__ == '__main__':
    main()
