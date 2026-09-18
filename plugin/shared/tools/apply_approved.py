"""승인된 수정만 반영하고, 지표가 어떻게 움직였는지 낸다.

사용:
    python apply_approved.py <bundle 폴더> [--product all]

절차
    1  build_bundle.py 로 번들을 뽑는다 (--apply 없이 = 제안 모드)
    2  사람이 수정로그_*.csv 의 [승인상태] 칸을 채운다
         승인 · 반려 · (빈칸이면 보류)
    3  이 스크립트를 돌린다 → 승인된 것만 반영된다

★ 반영은 원본 데이터셋에서 다시 시작한다. 여러 번 돌려도 결과가 같다.
★ 반려·보류는 반영하지 않는다. 되돌리려면 승인상태를 지우고 다시 돌리면 된다.

지표는 반영 전/후를 나란히 낸다.
정확도(관대·보수)는 여기서 내지 않는다 — 판독자가 지적한 것을 그대로 고친
뒤 다시 세면 반드시 100% 가 나오고, 그것은 자기채점이라 뜻이 없다.
움직임을 볼 수 있는 것은 산출물 자체의 지표뿐이다.
"""
from __future__ import annotations

import csv, json, os, re, sys, collections, datetime

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다
from build_bundle import read_csv, PRODUCTS, SRC, SEC_COLS

APPROVED = {'승인', 'Y', 'y', 'O', 'o', '반영'}
REJECTED = {'반려', 'N', 'n', 'X', 'x'}
LOGS = ('수정로그_오류확정.csv', '수정로그_재검토필요.csv')


def load_rows(prod):
    if prod == 'all':
        rows, hdr, seen = [], None, set()
        for p in PRODUCTS:
            rs, h = read_csv(SRC[p])
            hdr = hdr or h
            for r in rs:
                if r['atomic_id'] not in seen:
                    seen.add(r['atomic_id'])
                    rows.append(r)
        return rows, hdr
    return read_csv(SRC[prod])


NEVER = re.compile(r'(?!x)x')
# 08-13 종료기준선 이후 na_rules.py 에 추가된 3분기. 기준선 재현 시 끈다 (정본 §8.4-2)
ADDED_BRANCHES = ('CONTENT_MEME_REACTION', 'NEWS_INDUSTRY_REACTION', 'OTHER_VIEWER_REQUEST')


def legitimate_na(text, baseline=True):
    """정당 N/A 판정. baseline=True 면 08-13 종료기준선과 같은 규칙을 쓴다.

    ★ na_class 컬럼과 현 na_rules 는 275건을 잡는다. 기준선은 144건이다.
      차이 131건은 위 3분기에서 나오며, 그중 118건이 08-13 분류에서
      「실질 VoC인데 N/A」 — 즉 2차 최우선 표적이다 (정본 §8.4-2).
    """
    for _cand in (os.environ.get('VOC_CONTRACTS'),):
        if _cand and os.path.isdir(_cand):
            sys.path.insert(0, _cand)
            break
    try:
        import 엔진자리
        엔진자리.앉히기()          # ★ 남의 PC 에는 engine/ 뿐이다
    except ImportError:
        pass
    import src.voc_secondary.na_rules as NR
    if not baseline:
        return NR.legitimate_na_rule(text)[0]
    keep = {n: getattr(NR, n) for n in ADDED_BRANCHES}
    for n in ADDED_BRANCHES:
        setattr(NR, n, NEVER)
    try:
        return NR.legitimate_na_rule(text)[0]
    finally:
        for n, v in keep.items():
            setattr(NR, n, v)


def metrics(rows, baseline=True):
    """산출물 지표 — 정본 23번 v4.5 §8.4 산식을 그대로 쓴다.

        분석 대상  = status=normal − 정당 N/A − 애매
        라벨 부여율 = 캐노니컬 topic 행 / 분석 대상
        미판정률   = (미분류 + 기타(제품명) + N/A 오판정) / 분석 대상

    ★ 기타(제품군) 4종은 라벨로 세지 않는다 (택소노미 §8). 미판정에 넣는다
    ★ 「애매」는 08-13 기준선에서 0건이었다. 정의가 문서에 없다 (§8.4-3 미결)

    고정 기준선 재현 — 분석대상 1,392 · 라벨 559(40.16%) · 미판정 833(59.84%)
    """
    normal = [r for r in rows if (r.get('status') or '').strip() == 'normal']
    leg = [r for r in normal
           if (r.get('topic') or '').strip() == 'N/A'
           and legitimate_na(r.get('atomic_voc', ''), baseline)]
    legset = {id(r) for r in leg}
    denom = [r for r in normal if id(r) not in legset]

    def top(r):
        return (r.get('topic') or '').strip()
    etc = [r for r in denom if top(r).startswith('기타(')]
    labeled = [r for r in denom
               if top(r) not in ('', 'N/A', '미분류') and not top(r).startswith('기타(')]
    unclass = [r for r in denom if top(r) == '미분류']
    na_left = [r for r in denom if top(r) == 'N/A']
    excl = [r for r in rows if (r.get('status') or '').strip() == 'scope_excluded']
    no_reason = [r for r in excl if not (r.get('scope_exclusion_reason') or '').strip()]
    d = len(denom)
    unjudged = len(unclass) + len(etc) + len(na_left)
    return {
        '전체 행': len(rows),
        'status=normal': len(normal),
        '정당 N/A': len(leg),
        '분석 대상 (분모)': d,
        '라벨': len(labeled),
        '라벨 부여율(%)': round(len(labeled) / d * 100, 2) if d else 0,
        '미판정': unjudged,
        '미판정률(%)': round(unjudged / d * 100, 2) if d else 0,
        '  미분류': len(unclass),
        '  기타(제품군)': len(etc),
        '  N/A 오판정': len(na_left),
        'scope_excluded': len(excl),
        '  사유 없음': len(no_reason),
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    outdir = sys.argv[1]
    prod = 'all'
    if '--product' in sys.argv:
        prod = sys.argv[sys.argv.index('--product') + 1]

    rows, hdr = load_rows(prod)
    base_cols = [c for c in hdr if c not in SEC_COLS]
    by_id = {r['atomic_id']: r for r in rows}
    before = metrics(rows)

    # ---- 수정로그 읽기 ----------------------------------------------------
    approved, rejected, pending, missing = [], [], [], []
    for fn in LOGS:
        p = os.path.join(outdir, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8-sig', newline='') as h:
            for r in csv.DictReader(h):
                st = (r.get('승인상태') or '').strip()
                if st in APPROVED:
                    approved.append((fn, r))
                elif st in REJECTED:
                    rejected.append((fn, r))
                else:
                    pending.append((fn, r))

    if not (approved or rejected or pending):
        print('★ 수정로그를 찾지 못했습니다: %s' % outdir)
        sys.exit(1)

    # ---- 승인된 것만 반영 -------------------------------------------------
    applied = collections.Counter()
    skipped = []
    for fn, r in approved:
        aid, fld, new = r.get('atomic_id', ''), r.get('field', ''), r.get('제안값', '')
        row = by_id.get(aid)
        if row is None:
            missing.append(aid)
            continue
        if fld not in base_cols:
            skipped.append((aid, fld, '66컬럼이 아니다'))
            continue
        if not str(new).strip():
            skipped.append((aid, fld, '제안값이 비었다'))
            continue
        row[fld] = new
        applied[fld] += 1

    after = metrics(rows)

    # ---- 계약 검증 --------------------------------------------------------
    contract, viol = None, []
    try:
        for _cand in (os.environ.get('VOC_CONTRACTS'),):
            if _cand and os.path.isdir(_cand):
                sys.path.insert(0, _cand)
                break
        from src.voc_secondary.contracts import validate_contract
        chk = validate_contract([{c: r.get(c, '') for c in base_cols} for r in rows], base_cols)
        for name, res in chk['checks'].items():
            if res['violations']:
                viol.append((name, res['violations'], json.dumps(res['details'][:2], ensure_ascii=False)[:150]))
        contract = not chk['fatal'] and not viol
    except Exception as exc:
        viol.append(('IMPORT_FAIL', -1, str(exc)[:120]))

    # ---- 출력 -------------------------------------------------------------
    dst = os.path.join(outdir, 'raw_voc_승인반영.csv')
    with open(dst, 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=base_cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, '') for c in base_cols})

    print('=' * 74)
    print('승인 반영   %s' % outdir)
    print('=' * 74)
    print('  승인 %d건  ·  반려 %d건  ·  보류(빈칸) %d건' % (len(approved), len(rejected), len(pending)))
    if not approved:
        print()
        print('  ★ 승인된 건이 없습니다. 수정로그의 [승인상태] 칸을 채우십시오')
        print('     승인 / 반려 / 빈칸(보류) 중 하나를 적습니다')
    if applied:
        print('  반영된 필드   %s' % dict(applied.most_common()))
    for aid, fld, why in skipped[:8]:
        print('    건너뜀  %-44s %-24s %s' % (aid[:44], fld[:24], why))
    if missing:
        print('    ★ 원본에 없는 atomic_id %d건' % len(missing))

    print()
    print('-' * 74)
    print('%-26s %12s %12s %10s' % ('지표', '반영 전', '반영 후', '변화'))
    print('-' * 74)
    for k in before:
        b, a = before[k], after[k]
        d = round(a - b, 2)
        mark = '' if d == 0 else ('  ▲%s' % d if d > 0 else '  ▼%s' % abs(d))
        print('%-26s %12s %12s %10s' % (k, b, a, mark))

    print()
    print('  계약 검증   %s' % ('통과' if contract else ('실패' if contract is False else '미확인')))
    for n, v, d in viol[:5]:
        print('    %-12s %4s  %s' % (n, v, d))
    print()
    print('  출력   %s' % dst)

    json.dump({'생성': datetime.datetime.now().isoformat(timespec='seconds'),
               '승인': len(approved), '반려': len(rejected), '보류': len(pending),
               '반영 필드': dict(applied), '반영 전': before, '반영 후': after,
               '계약 검증': contract},
              open(os.path.join(outdir, '승인반영_요약.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
