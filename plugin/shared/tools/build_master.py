"""최종본을 만든다 — 어느 칸을 누구 것으로 쓸지 한 곳에서 정한다.

sky 2026-08-18 결정
    라벨(topic·status)   감독자가 정한 값. 두 감독자가 갈리면 사람이 본다
    서술 칸               ★ CC 것을 쓴다 (Codex 는 틀을 찍었다 — 뼈대 고유 11~16%)
    product_category      제품군 확인 회차의 값
    확인요청 4묶음         ①스타일러 ④대상 밖 가전 → 살린다
                          ②리뷰어 고정 댓글 → operator_notice
                          ③AI 요약 붙여넣기 → ★ video_transcript 신설

무엇을 근거로 이렇게 정했는가
    익명(A/B) 감독자 두 번 — 원 판독자 채택률
        Codex 감독자   Codex 답 39% · CC 답 61%
        CC 감독자      Codex 답 37% · CC 답 63%
    ★ 감독자가 누구든 CC 답을 1.6배 더 골랐다. 자기 것을 알 수 없는 상태였다

내는 것
    s15_master/raw_voc.csv · 사람이볼목록.csv · 지표.json
"""
from __future__ import annotations

import collections, csv, glob, io, json, os, re, shutil, sys

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다
from check_selfcheck import kind, NOT

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

R = os.path.join(BASE, '_판독패키지', '_결과')

# ★ CC 것을 쓰는 칸 — 서술이 들어가는 자리
CC_FIELDS = [
    'rootcause_problem', 'rootcause_target', 'rootcause_cause', 'rootcause_summary',
    'rootcause_score', 'atomic_voc_summary', 'topic_provisional', 'tee_summary',
    'cej_evidence', 'tee_time_evidence', 'tee_effort_evidence',
    'tee_emotion_evidence', 'tee_success_evidence',
    'tee_time_score', 'tee_effort_score', 'tee_emotion_score', 'tee_success_score',
    'need_signal_flag', 'need_signal_type', 'inquiry_flag', 'inquiry_type',
    'cej', 'entity_role', 'brand',
]


def load(d):
    """번들 하나를 읽는다.

    ★ 짚어 준 자리가 실제로 있으면 그대로 쓴다 (2026-08-23).
      늘 `_결과/<이름>` 으로 붙였더니, 2차 결과를 옆 폴더에 놓은
      실무자 자리에서 없는 곳을 가리켜 멈췄다.
    """
    바로 = os.path.join(d, 'raw_voc.csv')
    길 = 바로 if os.path.exists(바로) else os.path.join(R, d, 'raw_voc.csv')
    with open(길, encoding='utf-8-sig') as h:
        return {r['atomic_id']: r for r in csv.DictReader(h)}


def jsonl(pat):
    """판정 파일에서 JSON 을 긁는다 — **중첩도 읽는다.**

    ★ 왜 고쳤나 (2026-08-25) — 시험이 잡았다
      옛 무늬는 중괄호 사이에 `[^{}]` 만 허용했다.
      `[^{}]` 는 중괄호를 못 담으므로 안에 {…} 가 또 있는 판정은
      **아예 안 걸린다.** 에러가 아니라 그 행이 없는 것처럼 된다.

          {"atomic_id": "...", "verdict": "D",
           "segments": [{"atomic_voc": "...", "topic": "디자인"}]}

      D(나눠야 한다) 가 바로 그 꼴이다. 넣어 놓고 못 읽고 있었다.
      ★ apply_split 은 이미 알고 있었다 — 「균형 잡힌 괄호로 잘라야 한다」.
        그 앎이 여기로 안 옮겨져 있었다.
    """
    out = {}
    for p in sorted(glob.glob(os.path.join(R, pat))):
        t = io.open(p, encoding='utf-8').read()
        i = 0
        while True:
            i = t.find('{', i)
            if i < 0:
                break
            # ★ 균형 잡힌 괄호로 자른다 (따옴표 안의 중괄호는 세지 않는다)
            깊이, j, 따옴표, 벗김 = 0, i, False, False
            while j < len(t):
                c = t[j]
                if 벗김:
                    벗김 = False
                elif c == '\\':
                    벗김 = True
                elif c == '"':
                    따옴표 = not 따옴표
                elif not 따옴표:
                    if c == '{':
                        깊이 += 1
                    elif c == '}':
                        깊이 -= 1
                        if 깊이 == 0:
                            break
                j += 1
            토막 = t[i:j + 1]
            i = j + 1 if j > i else i + 1
            if '"atomic_id"' not in 토막:
                continue
            try:
                d = json.loads(토막)
            except Exception:                                   # noqa: BLE001
                continue
            if isinstance(d, dict) and d.get('atomic_id'):
                out[d['atomic_id']] = d
    return out


def _감독자가름():
    """감독자 둘의 이름을 결과 파일에서 알아낸다.

    감독결과_07_codex.md  →  codex
    ★ 이름을 박으면 다음 판에 다른 판독자를 쓸 때 하나도 못 읽는다.
    """
    이름 = collections.Counter()
    for p in glob.glob(os.path.join(R, '감독결과_*.md')):
        m = re.match(r'감독결과_[^_]+_(.+)$',
                     os.path.splitext(os.path.basename(p))[0])
        if m:
            이름[m.group(1)] += 1
    골라진 = [k for k, _ in 이름.most_common(2)]
    if len(골라진) < 2:
        print('  감독자가 둘이어야 합니다 — 찾은 이름: %s'
              % (' · '.join(골라진) or '없음'))
        print('    본 자리: %s' % R)
        sys.exit(1)
    return 골라진[0], 골라진[1]


def _판독번들():
    """2차 판독자 두 명의 최종 번들 폴더 이름을 찾는다.

    ★ 인자로 주는 것이 먼저다 —
          python build_master.py <판독자1_번들> <판독자2_번들>
      안 주면 `_판독패키지/_결과/` 에서 회차 번들이 아닌 것 둘을 찾는다.
      둘이 아니면 어디를 봐야 하는지 말하고 멈춘다. 짐작하지 않는다.
    """
    준것 = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(준것) >= 2:
        # ★ 이름만 떼면 옆 폴더에 있는 번들을 못 찾는다 — 자리를 그대로 준다
        return 준것[0].rstrip('/\\'), 준것[1].rstrip('/\\')

    후보 = []
    if os.path.isdir(R):
        for 이름 in sorted(os.listdir(R)):
            길 = os.path.join(R, 이름)
            if not os.path.isdir(길) or 이름.startswith('bundle_'):
                continue
            if '옛판' in 이름 or 이름 == 'master_final':
                continue
            if os.path.exists(os.path.join(길, 'raw_voc.csv')):
                후보.append(이름)
    if len(후보) == 2:
        return 후보[0], 후보[1]

    print('  2차 판독자 두 명의 번들을 못 찾았습니다.')
    print('    본 자리 : %s' % R)
    print('    찾은 것 : %s' % (' · '.join(후보) or '없음'))
    print()
    print('  ★ 통합은 **총괄이** 자기 자리에서 합니다.')
    print('    감독 폴더에는 2차 판독 번들이 없어야 맞습니다 —')
    print('    A·B 가 누구인지 알면 감독자가 편들게 되기 때문입니다.')
    print()
    print('  쓰기 — python build_master.py <판독자1_번들> <판독자2_번들>')
    sys.exit(1)


def main():
    # ★ 이름을 박지 않는다 (2026-08-23) — 판독자마다 다르다.
    #   `final_v62` · `cc_final` 은 내 08-18 작업 폴더였다.
    #   3차 마무리가 그 이름을 못 찾아 멈췄다.
    _1, _2 = _판독번들()
    X, K = load(_1), load(_2)                           # 판독자 1 · 2
    # ★ 정답지는 감독자가 못 보는 자리(_총괄만/)에 있다 (2026-08-23).
    #   통합은 총괄 자리이므로 거기서 읽는다. 옛 자리도 함께 본다.
    _답 = ''
    for _c in (os.path.join(BASE, '_총괄만', 'ab_mapping.json'),
               os.path.join(BASE, 's13_judge', 'ab_mapping.json')):
        if os.path.exists(_c):
            _답 = _c
            break
    if not _답:
        print('  정답지(ab_mapping.json)를 못 찾았습니다.')
        print('    A·B 가 어느 판독자인지 담은 파일입니다 — 총괄이 갖고 있습니다.')
        print('    _총괄만/ 에 놓고 다시 돌리십시오.')
        sys.exit(1)
    with open(_답, encoding='utf-8') as _h:
        MAP = json.load(_h)
    # ★ 회차 수와 감독자 이름을 박지 않는다 (2026-08-23).
    #   `judge_0*` 이라 judge_10·11·12 를 못 읽었다 — 08-18 에는 회차가
    #   4개라 안 드러났다. 이름도 박혀 있어 다른 판독자면 하나도 못 읽는다.
    _s1, _s2 = _감독자가름()
    JX = jsonl('감독결과_*_%s.md' % _s1)
    JK = jsonl('감독결과_*_%s.md' % _s2)
    print('   감독자 — %s %d행 · %s %d행' % (_s1, len(JX), _s2, len(JK)))
    if not (JX and JK):
        print()
        print('  ★ 두 감독자의 결과가 다 있어야 판정을 반영합니다.')
        print('    한쪽만 있으면 아무것도 안 바뀝니다 — 3차가 헛일이 됩니다.')
        print('    빠진 쪽 결과를 _판독패키지/_결과/ 에 넣고 다시 돌리십시오.')
        sys.exit(1)
    PC = jsonl('제품군확인_*.md')
    EV = jsonl('근거재작업_*.md')          # ★ 라벨은 맞는데 인용이 옛 라벨 것이던 행

    def _어느번들(길):
        """매핑이 가리키는 곳이 첫 번째 번들인가 두 번째인가.

        ★ 이름으로 견주면 안 된다 (2026-08-25).
          번들 이름은 판마다 다르다 — final_v62·cc_final 이던 적도 있다.
          **자리**로 견준다. 폴더 이름만 떼어 맞춘다.
        """
        if not 길:
            return '?'
        끝 = os.path.basename(str(길).replace('\\', '/').rstrip('/'))
        if 끝 == os.path.basename(str(_1).replace('\\', '/').rstrip('/')):
            return '1'
        if 끝 == os.path.basename(str(_2).replace('\\', '/').rstrip('/')):
            return '2'
        return '?'

    def verdict_value(aid, j):
        """감독자 한 명이 낸 최종값 → ('제외', 사유) 또는 ('라벨', 이름, 어느 판독자)"""
        v = j.get('verdict')
        # ★ D — 둘 다 맞다, 나눠야 한다 (2026-08-25 신설)
        #   여기서 받지 않으면 MAP 에 'D' 가 없어 빈 라벨이 조용히 들어간다.
        if v == 'D':
            if j.get('merge'):
                return ('분리', 'MERGE', 'judge')
            return ('분리', j.get('segments') or [], 'judge')
        if v == 'C':
            if j.get('status') == 'scope_excluded':
                return ('제외', j.get('scope_exclusion_reason') or 'no_analytic_value', 'judge')
            return ('라벨', str(j.get('topic') or '').strip(), 'judge')
        # ★★ 경로로 가른다 (2026-08-25에 고침).
        #   옛 코드는 `X if who == 'codex' else K` 였다.
        #   MAP 은 '_판독패키지/_결과/claudecode_bundle' 같은 **경로**를 담는데
        #   'codex' 라는 문자열과 견주니 **늘 False** 였다.
        #   → A 를 고르든 B 를 고르든 같은 번들을 읽었다.
        #     A 대 B 로 갈린 행이 전부 「합의」 로 세어졌다.
        #     실전 사람이볼목록 69행은 C 판정에서만 나온 것이었다.
        #   ★ 실전 2차 결과로 끝까지 돌려 보고서야 드러났다.
        who = MAP.get(aid, {}).get(v)
        r = (X if _어느번들(who) == '1' else K).get(aid) or {}
        if kind(r) == '제외':
            return ('제외', r.get('scope_exclusion_reason') or '', who)
        return ('라벨', r.get('topic', '').strip(), who)

    # ★ 행 집합은 CC 것으로 통일한다 (2026-08-18)
    #   두 판독자가 분리를 다르게 해서 조각 id 가 갈렸다.
    #   합집합으로 두면 같은 댓글이 두 벌로 들어가 1,745행이 된다.
    #   서술도 라벨도 CC 기준으로 가기로 했으므로 조각도 CC 것을 쓴다
    only_x = sorted(set(X) - set(K))
    if only_x:
        print('   ※ Codex 에만 있던 조각 %d행은 뺐다 (CC 분리를 정본으로 삼음)' % len(only_x))

    # ★ 판독자 이름을 번들 폴더에서 읽는다 — 실명으로 쓰기 위해
    _이름1 = os.path.basename(str(_1).rstrip('/\\')) or '판독자1'
    _이름2 = os.path.basename(str(_2).rstrip('/\\')) or '판독자2'

    def _이차값(r):
        """2차 판독자가 낸 값 한 줄."""
        if not r:
            return ''
        if kind(r) == '제외':
            return '제외 %s' % (r.get('scope_exclusion_reason') or '')
        return '라벨 %s' % (r.get('topic') or '')

    # ★ 부모 댓글 — 답글은 이것 없이는 뜻이 안 통한다 (실무자 공통 제안 1)
    _부모 = {}
    for _r in list(K.values()) + list(X.values()):
        _글 = _r.get('original_voc') or ''
        if not _글:
            continue
        for _키 in (_r.get('source_id', ''), _r.get('atomic_id', '')):
            if _키:
                _부모.setdefault(_키, _글)

    out, need_human, stats = [], [], collections.Counter()
    분리제안 = []          # ★ 감독이 D 로 낸 것
    for aid in sorted(K):
        base = dict(K[aid])                            # ★ 바탕은 CC
        cx = X.get(aid)

        # ── 서술 칸은 CC 것 (CC 에 그 행이 없으면 어쩔 수 없이 Codex)
        if aid in K:
            for f in CC_FIELDS:
                if f in K[aid]:
                    base[f] = K[aid][f]

        # ── 라벨 · 제외 판정
        if aid in JX and aid in JK:
            a, b = verdict_value(aid, JX[aid]), verdict_value(aid, JK[aid])
            # ★ 한쪽이라도 「나눠야 한다」 면 라벨 싸움이 아니다 (2026-08-25).
            #   감독이 본 조각을 분리제안으로 넘기고, 사람은 승인만 한다.
            if a[0] == '분리' or b[0] == '분리':
                # ★★ 두 감독 것을 **둘 다** 담는다 (2026-08-26에 고침).
                #   옛 코드는 `a[1] if a[0]=='분리' else b[1]` 로
                #   감독1 이 분리를 냈으면 감독2 것을 **쳐다보지도 않았다.**
                #   · 둘이 다르게 나눠도 감독1 것만 쓰였다
                #   · 한쪽 「합쳐라」 · 한쪽 「쪼개라」 인데도 감독1 것만 쓰였다
                #   · 그리고 사람이 볼 목록에 **안 올라갔다** — 아무도 몰랐다
                #   ★ 실전 전에 시험으로 잡았다.
                _가 = a[1] if a[0] == '분리' else None
                _나 = b[1] if b[0] == '분리' else None
                _낸쪽 = ((_s1 + ' · ' + _s2) if (_가 is not None and _나 is not None)
                        else (_s1 if _가 is not None else _s2))
                # 둘 다 냈는데 내용이 다르면 사람이 정해야 한다
                _둘이어긋남 = (_가 is not None and _나 is not None
                            and json.dumps(_가, ensure_ascii=False, sort_keys=True)
                            != json.dumps(_나, ensure_ascii=False, sort_keys=True))
                _한쪽만 = (_가 is None) != (_나 is None)
                stats['★ 감독이 분리를 냈다'] += 1
                if _둘이어긋남:
                    stats['★★ 감독 둘이 **다르게** 나눴다 (사람이 정함)'] += 1
                elif _한쪽만:
                    stats['감독 한쪽만 분리를 냈다'] += 1
                else:
                    stats['감독 둘이 같게 나눴다'] += 1
                base['decided_by'] = '감독_분리제안'
                base['decided_note'] = str(_가 if _가 is not None else _나)[:300]
                분리제안.append({
                    'origin_atomic_id': aid,
                    'atomic_voc': ' '.join((base.get('atomic_voc') or '').split()),
                    'original_voc': ' '.join((base.get('original_voc') or '').split()),
                    '낸_감독': _낸쪽,
                    # ★ 두 감독 것을 나란히 둔다 — 사람이 견줄 수 있어야 한다
                    ('3차_%s' % _s1): (json.dumps(_가, ensure_ascii=False)
                                      if _가 is not None else '(분리를 안 냈습니다)'),
                    ('3차_%s' % _s2): (json.dumps(_나, ensure_ascii=False)
                                      if _나 is not None else '(분리를 안 냈습니다)'),
                    'segments': json.dumps(
                        _가 if _가 is not None else _나, ensure_ascii=False),
                    'why': str(JX.get(aid, {}).get('why')
                               or JK.get(aid, {}).get('why') or ''),
                    ('왜_%s' % _s1): str(JX.get(aid, {}).get('why') or ''),
                    ('왜_%s' % _s2): str(JK.get(aid, {}).get('why') or ''),
                    '승인상태': ('★ 감독 둘이 다르게 나눴습니다 — 사람이 정하십시오'
                              if _둘이어긋남 else
                              ('한쪽 감독만 냈습니다 — 사람 확인'
                               if _한쪽만 else '사람 최종 승인 대기')),
                })
            elif a[:2] == b[:2]:
                kindv, val, who = a
                stats['감독자 합의'] += 1
                if kindv == '제외':
                    base['status'] = 'scope_excluded'
                    base['scope_exclusion_reason'] = val
                    base['topic'] = 'N/A'
                else:
                    base['status'] = 'normal'
                    base['topic'] = val
                    # ★ 근거는 그 라벨을 낸 쪽 것을 가져온다. 감독자가 새로 냈으면 비운다
                    # ★ who 는 **경로** 다 (2026-08-25에 고침).
                    #   전에는 {'codex': ..., 'claudecode': ...}.get(who) 로 찾아
                    #   **늘 None** 이었다 → topic_evidence 가 항상 비었다.
                    #   A/B 해석과 똑같은 버그가 여기에도 있었다.
                    src = X.get(aid) if _어느번들(who) == '1' else K.get(aid)
                    base['topic_evidence'] = (src or {}).get('topic_evidence', '')
                # ★ 이력 칸에 **경로**를 적으면 안 된다 (2026-08-25에 고침).
                #   실무자에게 나간 데이터 1,535행에 내 로컬 임시 경로가 박혔다.
                #     judge_agree(C:\Users\blues\AppData\Local\Temp\...)
                #   이력은 「누가 정했나」 를 적는 자리다. 실명을 적는다.
                _고른쪽 = {'1': _이름1, '2': _이름2}.get(_어느번들(who), str(who))
                base['decided_by'] = 'judge_agree(%s)' % _고른쪽
                base['decided_note'] = ''
                if kindv == '라벨' and who == 'judge':
                    base['decided_note'] = str(JK[aid].get('why') or JX[aid].get('why') or '')
            else:
                # ★ 두 감독자가 갈렸다 — 사람이 본다
                stats['★ 감독자 갈림 (사람이 봄)'] += 1
                base['decided_by'] = 'sky_필요'
                base['decided_note'] = '감독자 A: %s / 감독자 B: %s' % (
                    ' '.join(map(str, a[:2])), ' '.join(map(str, b[:2])))
                # ★ 칸을 나눈다 (sky 2026-08-25).
                #   예전에는 「감독자1」 한 칸에 세 가지가 같은 모양으로 들어갔다 —
                #   2차 A 의 값 · 2차 B 의 값 · 감독이 직접 낸 값.
                #   실무자가 「이게 2차 결과인지 3차 결과인지」 를 물었다.
                # ★ 경로가 아니라 **실명**을 보여 준다 (2026-08-25).
                #   전에는 '_판독패키지/_결과/claudecode_bundle 채택' 이 찍혔다.
                #   실무자가 보는 칸에 내 폴더 구조가 나올 자리가 아니다.
                def _누구(길):
                    n = _어느번들(길)
                    return _이름1 if n == '1' else (_이름2 if n == '2' else 'C(직접)')

                _고른것 = {'judge': 'C(직접)'}
                _who_a, _who_b = _누구(a[2]), _누구(b[2])
                need_human.append({
                    'atomic_id': aid,
                    'product_category': base.get('product_category', ''),
                    'atomic_voc': ' '.join((base.get('atomic_voc') or '').split())[:300],
                    # ★ 실무자 공통 제안 1 — raw_voc 를 왔다갔다 하지 않게
                    'original_voc': ' '.join((base.get('original_voc') or '').split())[:400],
                    # ★ 답글일 때만 채운다 (2026-08-25).
                    #   부모 댓글은 parent_voc_id 가 **자기 source_id** 라
                    #   조건 없이 찾으면 자기 자신이 부모로 찍힌다.
                    #   make_judge_input 에서 고친 것을 여기로 안 옮겼었다.
                    'parent_voc': (
                        ' '.join((_부모.get(base.get('parent_voc_id', '')) or '').split())[:300]
                        if str(base.get('comment_relation', '')) == 'reply' else ''),
                    'video_title': ' '.join((base.get('video_title') or '').split()),
                    'cej': base.get('cej', ''),
                    # ★ 2차 판독자 둘의 값 — 실명으로 (익명화는 판정 중에만)
                    '2차_%s' % _이름1: _이차값(X.get(aid)),
                    '2차_%s' % _이름2: _이차값(K.get(aid)),
                    # ★ 3차 감독 둘 — 무엇을 골랐고 그 값이 무엇인가
                    '3차_%s' % _s1: '%s → %s' % (
                        _who_a if _who_a == 'C(직접)' else '%s 채택' % _who_a,
                        ' '.join(map(str, a[:2]))),
                    '3차_%s' % _s2: '%s → %s' % (
                        _who_b if _who_b == 'C(직접)' else '%s 채택' % _who_b,
                        ' '.join(map(str, b[:2]))),
                    # ★ 총괄 의견 — **의견이다.** 사람이 뒤집을 수 있어야 한다
                    '총괄_의견': '',
                    '총괄_근거': '',
                    '지금값(2차 %s)' % _이름2: base.get('topic', ''),
                })
        else:
            stats['두 판독자 합의'] += 1
            base['decided_by'] = 'reader_agree'
            base['decided_note'] = ''

        # ── 제품군 확인
        if aid in PC and PC[aid].get('product_category'):
            if base.get('product_category') != PC[aid]['product_category']:
                base['product_category'] = PC[aid]['product_category']
                stats['제품군 고침'] += 1

        # ── 확인요청 ②③ 처리 (sky 2026-08-18 승인)
        _t = ' '.join(((base.get('atomic_voc') or '') + ' ' +
                       (base.get('voc_cleaned') or '')).split())
        # ③ 시청자가 AI 요약을 통째로 붙여 넣은 댓글 — 타임스탬프가 박혀 있다
        #    ★ 제품 얘기지만 본인 경험도 의견도 없다. 남기면 topic 집계가 영상 대본으로 부푼다
        #      no_analytic_value(무의미 감탄·비난·농담) 와 성격이 달라 사유를 신설한다
        if re.search(r'\[\d{1,2}:\d{2}', _t):
            base['status'] = 'scope_excluded'
            base['scope_exclusion_reason'] = 'video_transcript'
            base['topic'] = 'N/A'
            base['decided_by'] = 'sky_결정'
            base['decided_note'] = '영상 대본을 옮긴 댓글이다'
            stats['③ 영상 요약 → 제외'] += 1
        # ② 리뷰어가 제휴 링크 고정 댓글에 쓴 제품 평가
        #    ★ 고객의 소리가 아니라 우리가 판 광고다. 긍정 VoC 로 집계되면 안 된다
        elif (re.search(r'(수수료|구매\s*링크|제휴|카톡\s*친구|링크로 구매|구매 가이드정리)',
                        base.get('voc_cleaned') or '')
              and kind(base) == '라벨'):
            base['status'] = 'scope_excluded'
            base['scope_exclusion_reason'] = 'operator_notice'
            base['topic'] = 'N/A'
            base['decided_by'] = 'sky_결정'
            base['decided_note'] = '리뷰어가 제휴 고정 댓글에 쓴 평가다'
            stats['② 리뷰어 고정댓글 → 제외'] += 1

        # ── topic_evidence 에 붙은 군더더기를 뗀다 (2026-08-18)
        #    1차가 인용 뒤에 「| E1 evidence_guard(가격/가성비): 가격」 같은 표시를 붙여 놨다.
        #    그대로 두면 「근거가 원문에 없다」 로 걸린다. 인용만 남긴다
        #    ★ 실측 392행 중 133행이 이것만으로 풀린다
        _ev = str(base.get('topic_evidence') or '').strip()
        if _ev and kind(base) == '라벨':
            _src = re.sub(r'\s+', '', (base.get('voc_cleaned') or '') + (base.get('atomic_voc') or ''))
            if re.sub(r'\s+', '', _ev) not in _src:
                for _c in (_ev.split('|')[0], _ev.split('|')[-1],
                           re.sub(r'E1\s*evidence_guard\([^)]*\)\s*:', '', _ev)):
                    _c = _c.strip(' :·')
                    if _c and re.sub(r'\s+', '', _c) in _src:
                        base['topic_evidence'] = _c
                        stats['근거 군더더기 뗌'] += 1
                        break

        # ── 근거 재작업 회차 반영
        #    감독자가 topic 만 정해서 인용이 옛 라벨 것으로 남아 있던 행들이다
        if aid in EV:
            _e = EV[aid]
            if _e.get('no_evidence'):
                # ★ 라벨을 뒷받침할 어휘가 원문에 없다는 판정.
                #   억지 인용보다 낫지만, 라벨 자체를 다시 봐야 할 수 있으니 사람에게 올린다
                base['topic_evidence'] = ''
                base['decided_note'] = (base.get('decided_note') or '') +                     ' | 근거 없음: ' + str(_e.get('why') or '')
                stats['★ 근거 없음 (라벨 재검토)'] += 1
            elif _e.get('topic_evidence'):
                base['topic_evidence'] = _e['topic_evidence']
                stats['근거 다시 뽑음'] += 1

        #    ★ 근거를 둘 이어 붙일 때 이음표가 원문과 다른 경우가 있다
        #      원문 "정제소금 확인 // 베이킹소다" 를 판독자가 "|" 로 적었다.
        #      조각마다 따로 대조해 보고, 각각이 원문에 있으면 통과로 본다
        _ev2 = str(base.get('topic_evidence') or '').strip()
        if _ev2 and '|' in _ev2 and kind(base) == '라벨':
            # ★ 이름을 `_s2` 로 쓰면 안 된다 (2026-08-25에 고침).
            #   `_s2` 는 위에서 **감독자 이름**을 담아 둔 것이고
            #   사람이볼목록의 칸 이름('3차_%s')으로 쓰인다.
            #   여기서 덮어쓰니 칸 이름이 VoC 본문이 되어 파일 쓰기가 죽었다.
            _원문붙임 = re.sub(r'\s+', '', (base.get('voc_cleaned') or '') + (base.get('atomic_voc') or ''))
            if re.sub(r'\s+', '', _ev2) not in _원문붙임:
                _parts = [x.strip() for x in _ev2.split('|') if x.strip()]
                if _parts and all(re.sub(r'\s+', '', x) in _원문붙임 for x in _parts):
                    base['topic_evidence'] = _parts[0]      # 첫 조각만 남긴다
                    stats['근거 이음표 정리'] += 1

        # ── topic_provisional 정리 (sky 2026-08-18)
        #    ★ 이 칸의 원뜻은 「캐노니컬 라벨에 없어서 임시로 적어 둔 주제」 다.
        #      topic 이 열린 어휘가 된 순간 존재 이유가 없어졌다 —
        #      마땅한 라벨이 없으면 새로 내면 되기 때문이다.
        #      그런데 1차가 찍은 "독립 분석 주제를 찾지 못함" 이 479행에 남아 있어,
        #      라벨이 멀쩡히 붙은 행도 「분류가 안 된 것」 처럼 읽힌다.
        #      실측 — 라벨 붙은 1,165행 중 topic_provisional 이 topic 과 같은 것은 0행이었다
        #    ★ 제외 행에서도 비운다 — 제외 사유는 scope_exclusion_reason 에 이미 있고,
        #      "독립 분석 주제를 찾지 못함" 이 355행에 겹쳐 적혀 있을 뿐이다
        if str(base.get('topic_provisional') or '').strip() not in NOT:
            base['topic_provisional'] = ''
            stats['topic_provisional 비움'] += 1

        # ★ sky 결정 — 모든 행은 제외 아니면 라벨이다. 미판정을 남기지 않는다
        # ★ 2026-09-22 고침 (섹션 5b · sky 「§17 대로 남긴다」) — 08-26 sky 결정 §17 이 더 늦다:
        #   감성·니즈 신호만 있는 N/A 행은 모수에 남기고 topic 집계에서만 뺀다. 미분류도 제품 VoC 라 남긴다.
        #   그래서 topic 이 **빈칸**인 행(판정이 아예 없는 행)만 뺀다.
        #   옛 동작(N/A · 미분류까지 빼기)은 얼린 3차 기준을 재현하는 시험만 쓴다 — VOC_얼린기준_재현=1
        _빈칸 = not str(base.get('topic') or '').strip()
        if kind(base) == '미판정' and (_빈칸 or os.environ.get('VOC_얼린기준_재현') == '1'):
            base['status'] = 'scope_excluded'
            if not str(base.get('scope_exclusion_reason') or '').strip():
                base['scope_exclusion_reason'] = 'no_analytic_value'
            base['topic'] = 'N/A'
            base['decided_by'] = (base.get('decided_by') or '') + '+미판정→제외'
            stats['미판정 → 제외'] += 1

        out.append(base)

    # ── 새로 생긴 칸을 컬럼에 넣는다
    cols = list(out[0].keys())
    for c in ('decided_by', 'decided_note'):
        if c not in cols:
            cols.append(c)

    d = os.path.join(BASE, 's15_master')
    if _확인만이면_멈춘다('s15_master/raw_voc.csv · 사람이볼목록.csv · 지표.json'):
        return 0
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, 'raw_voc.csv'), 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c, '') for c in cols})
    if 분리제안:
        with io.open(os.path.join(d, '감독_분리제안.csv'), 'w',
                     encoding='utf-8-sig', newline='') as h:
            w = csv.DictWriter(h, fieldnames=list(분리제안[0].keys()))
            w.writeheader()
            w.writerows(분리제안)
        print('   ★ 감독이 「나눠야 한다」 로 낸 행 %d — 감독_분리제안.csv' % len(분리제안))

    # ★ `총괄_의견`·`총괄_근거` 는 여기서 못 채운다 (2026-08-26).
    #   build_master 는 **2차 판독 번들**에서 다시 만든다 (base = dict(K[aid])).
    #   총괄 판정은 이 도구가 끝난 **뒤에** 붙는다 (총괄검수 · apply_sky · 4차 규칙).
    #   그래서 여기서 채우면 언제나 빈칸이다.
    #   → 채우는 일은 `사람이볼목록_채우기.py` 가 한다. 번들을 묶기 직전에 돈다.

    # ★ 칸 이름에 판독자·감독자 실명이 들어가므로 첫 행에서 가져온다 (2026-08-25)
    if need_human:
        _칸 = list(need_human[0].keys())
        with io.open(os.path.join(d, '사람이볼목록.csv'), 'w',
                     encoding='utf-8-sig', newline='') as h:
            w = csv.DictWriter(h, fieldnames=_칸)
            w.writeheader()
            for r in need_human:
                w.writerow(r)

    lab = [r for r in out if kind(r) == '라벨']
    room = [r for r in out if kind(r) != '제외'
            and str(r.get('rootcause_problem') or '').strip() not in NOT]
    m = {'행': len(out), '라벨': len(lab), '제외': sum(1 for r in out if kind(r) == '제외'),
         '미판정': sum(1 for r in out if kind(r) == '미판정'),
         '해석 여지 있음': len(room), '사람이 볼 행': len(need_human),
         'topic 종수': len(set(r['topic'] for r in lab)),
         '제품군': dict(collections.Counter(r.get('product_category', '') for r in out))}
    json.dump(m, io.open(os.path.join(d, '지표.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('s15_master/  %d행 %d열' % (len(out), len(cols)))
    for k, v in stats.most_common():
        print('   %-24s %5d' % (k, v))
    print()
    print('   라벨 %d (%.1f%%) · 제외 %d · 미판정 %d'
          % (len(lab), 100 * len(lab) / len(out), m['제외'], m['미판정']))
    print('   해석 여지 있음 %d · topic %d종' % (len(room), m['topic 종수']))
    print('   ★ 사람이 볼 행 %d' % len(need_human))

    # ── 12시트 번들 ────────────────────────────────────────────────
    #   ★ build_xlsx 는 outdir 안의 로그 CSV 를 읽어 뒤에 6시트를 붙인다.
    #     CSV 를 안 넣으면 6시트짜리 반쪽 번들이 나온다 (2026-08-18 실측)
    # 최종 통합 번들 — 이름은 고정이다 (총괄 자리에서만 만든다)
    bd = os.path.join(R, 'master_final')
    os.makedirs(bd, exist_ok=True)

    for r in out:                      # 사람이 볼 행을 표시한다
        y = r['atomic_id'] in {x['atomic_id'] for x in need_human}
        r['review_required'] = 'Y' if y else 'N'
        r['review_reason'] = '두 감독자가 다른 답을 냈다 — 사람이 정한다' if y else ''
    with io.open(os.path.join(bd, 'raw_voc.csv'), 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c, '') for c in cols})

    # ── 로그 시트 — 판독자 **둘** 것을 합친다 (2026-10-29) ──────────────────────
    #   ★ 무엇이 있었나 — 전에는 이 자리가 「판독자 2」 번들의 네 파일을 **바이트 그대로**
    #     베꼈다. 주석은 「CC 회차 것을 그대로 잇는다」 였는데 코드는 판독자 2 를 집었고,
    #     한 줄 흐름에서 판독자 2 는 `_판독패키지/_결과/` 를 훑은 **순서**로 정해진다 —
    #     어느 판독자의 발견이 살아남을지가 폴더 이름 순서에 달려 있었다.
    #   ★ 작게 한 번 돌려 보고 드러났다 (2026-10-28 · 영상 1 · 84행). master_final 의 네 파일이
    #     Codex 번들과 지문까지 같았고, 판독A(claude)가 낸 구조적결함 8 · 기준서개정후보 7 ·
    #     분리제안 8 · 수정로그_오류확정 393행이 **최종에 없었다.** 그 안에는 「장문 후기의
    #     소모품 VoC(교체용 먼지봉투 2달째 품절) 한 건이 통째로 사라졌다」 도 들어 있었다.
    #     판독자를 둘 쓰는 뜻이 여기서 깨진다 — 한 쪽을 버리면 교차 검증이 아니다.
    #   ★ 어떻게 합치나
    #     · 머리글은 둘의 **합집합**이다 (판독자마다 칸이 다를 수 있다).
    #     · 어느 판독자가 낸 것인지 `낸_판독자` 칸에 남긴다. 번들 폴더 이름을 그대로 쓴다 —
    #       사람이볼목록의 칸(「지금값(2차 Codex_bundle)」)과 같은 이름이라 사람이 짝지을 수 있다.
    #     · **빈 파일에도 같은 머리글을 쓴다** (CP-29 — 비었을 때와 있을 때 열이 다르면
    #       승인 도구와 대시보드가 시트를 못 읽는다).
    #     · 모든 칸이 똑같은 줄은 한 줄로 줄인다. 둘이 **다른** 제안을 냈으면 둘 다 남긴다 —
    #       그것이 교차 검증의 결과이고, 어느 쪽을 받을지는 사람이 정한다.
    _자리들 = [(os.path.basename(str(x).rstrip('/' + os.sep)),
              x if os.path.isdir(x) else os.path.join(R, x)) for x in (_1, _2)]
    _합친말 = []
    for f in ('수정로그_오류확정.csv', '분리제안.csv', '기준서개정후보.csv', '구조적결함.csv'):
        _모두, _남은 = 로그합치기(bd, _자리들, f)
        _합친말.append('%s %d행%s' % (f[:-4], _남은,
                                   ('(같은 줄 %d 줄임)' % (_모두 - _남은)) if _모두 != _남은 else ''))
    if os.environ.get('VOC_얼린기준_재현') == '1':
        print('   ★ 얼린 기준 재현 — 옛 동작으로 담았다 (판독자 2 것만 · %s)'
              % ' · '.join(_합친말))
    else:
        print('   ★ 판독자 둘의 발견을 합쳤다 — ' + ' · '.join(_합친말))
        print('     (어느 판독자가 낸 것인지 「낸_판독자」 칸에 있다. 둘이 다르면 둘 다 남긴다)')

    # ★ 재검토 시트 = 사람이 볼 153행. 이 시트가 이번 판의 핵심 산출물이다
    # ★ 총괄 판정이 든 행은 지킨다 (2026-08-26에 고침).
    #   마무리를 두 번 돌리면 총괄이 --반영 으로 남긴 것이 통째로 사라졌다.
    #   실측 — 786행이 426행으로 줄었다.
    _로그길 = os.path.join(bd, '수정로그_재검토필요.csv')
    _지킬것 = []
    _머리 = ['source_id', 'atomic_id', 'atomic_voc', 'field',
             '원본값', '제안값', '사유', '근거인용', '오류유형', '승인상태',
             '감독자1', '감독자2']
    if os.path.exists(_로그길):
        try:
            with io.open(_로그길, encoding='utf-8-sig', newline='') as _h:
                _r = csv.DictReader(_h)
                _옛머리 = _r.fieldnames or _머리
                for _x in _r:
                    if '총괄' in str(_x.get('오류유형') or ''):
                        _지킬것.append(_x)
            if _지킬것:
                _머리 = _옛머리          # 총괄이 더한 칸을 살린다
        except Exception:
            _지킬것 = []
    with io.open(_로그길, 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.writer(h)
        w.writerow(_머리)
        for _x in _지킬것:
            w.writerow([_x.get(_c, '') for _c in _머리])
        # ★ 칸 이름 앞머리로 찾는다 (2026-08-25에 고침).
        #   사람이볼목록의 칸에 판독자·감독자 **실명**이 붙어 있다.
        #   ('지금값(2차 Codex_bundle)' · '3차_claudecode' …)
        #   실명은 판마다 바뀌므로 이름을 박아 두면 다음 판에 또 죽는다.
        def _앞머리로(행, 앞, 몇=0):
            골 = [k for k in 행 if str(k).startswith(앞)]
            return 행.get(골[몇], '') if len(골) > 몇 else ''

        for x in need_human:
            _한줄 = [x['atomic_id'].rsplit('-', 1)[0], x['atomic_id'], x['atomic_voc'],
                    'topic', _앞머리로(x, '지금값'), '',
                    '두 감독자가 다른 답을 냈다', '',
                    '판정 불일치', '대기',
                    _앞머리로(x, '3차_', 0), _앞머리로(x, '3차_', 1)]
            # ★ 총괄이 칸을 더해 뒀으면 그 수에 맞춘다 (빈 칸으로)
            _한줄 += [''] * max(0, len(_머리) - len(_한줄))
            w.writerow(_한줄[:len(_머리)])
    with io.open(os.path.join(bd, '판정불일치.csv'), 'w', encoding='utf-8-sig', newline='') as h:
        csv.writer(h).writerow(['source_id', 'atomic_id', '행verdict', 'finding최고심각도'])

    build_bundle_xlsx(bd)
    print()
    print('   ★ 번들  %s' % os.path.join(bd, 'voc_dashboard_export_bundle_2차시험본.xlsx'))


def 로그합치기(받을곳, 자리들, 파일이름, 얼린기준재현=None):
    """판독자 둘의 발견 시트 하나를 합쳐 `받을곳/파일이름` 으로 쓴다 (2026-10-29).

    자리들 — [(이름표, 번들폴더), …]. 이름표는 번들 폴더 이름을 그대로 쓴다.
    돌려주는 것 — (모은 줄 수, 남은 줄 수). 둘이 다르면 똑같은 줄을 줄인 것이다.

    ★ 바깥 함수로 둔 까닭 — 시험이 직접 부를 수 있어야 한다. 안에 숨겨 두면
      「판독자 한 쪽만 담긴다」 는 바로 그 버그를 다시 못 잡는다.

    ★ `VOC_얼린기준_재현=1` 이면 **옛 동작**으로 돈다 — 판독자 2 의 파일을 바이트 그대로
      베낀다(`낸_판독자` 칸도 붙이지 않는다). 얼린 3차 기준은 그 동작으로 만들어졌으므로
      **동결된 정답을 고치지 않고** 재현할 수 있어야 한다. 섹션 5b 에서 §17(미판정→제외)과
      handoff 의 88자 자르기를 같은 스위치로 가른 것과 같은 꼴이다.
      기본 동작(스위치 없음)이 지금 업무에서 도는 것이고, 둘이 같이 있어야
      **바꾼 것이 정확히 그것뿐임**을 안다.
    """
    if 얼린기준재현 is None:
        얼린기준재현 = os.environ.get('VOC_얼린기준_재현') == '1'
    if 얼린기준재현:
        s = os.path.join(자리들[-1][1], 파일이름)      # ★ 옛 동작 — 판독자 2 것만
        if not os.path.exists(s):
            return 0, 0
        shutil.copyfile(s, os.path.join(받을곳, 파일이름))
        with io.open(s, encoding='utf-8-sig', newline='') as h:
            n = sum(1 for r in csv.DictReader(h)
                    if any((v or '').strip() for v in r.values()))
        return n, n
    모은것, 머리 = [], []
    for 이름표, d in 자리들:
        s = os.path.join(d, 파일이름)
        if not os.path.exists(s):
            continue
        with io.open(s, encoding='utf-8-sig', newline='') as h:
            rd = csv.DictReader(h)
            for c in (rd.fieldnames or []):
                if c and c != '낸_판독자' and c not in 머리:
                    머리.append(c)
            for r in rd:
                if not any((v or '').strip() for v in r.values()):
                    continue
                모은것.append((이름표, r))
    머리 = 머리 + ['낸_판독자']
    본것, 줄들 = set(), []
    for 이름표, r in 모은것:
        열쇠 = tuple((r.get(c) or '').strip() for c in 머리[:-1])
        if 열쇠 in 본것:
            continue
        본것.add(열쇠)
        r = dict(r)
        r['낸_판독자'] = 이름표
        줄들.append(r)
    with io.open(os.path.join(받을곳, 파일이름), 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=머리, extrasaction='ignore')
        w.writeheader()
        for r in 줄들:
            w.writerow({c: r.get(c, '') for c in 머리})
    return len(모은것), len(줄들)


def build_bundle_xlsx(bd):
    import build_bundle as BB
    BB.build_xlsx(bd, 'all')


if __name__ == '__main__':
    main()
