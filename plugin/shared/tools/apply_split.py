"""분리·재지정 회차를 반영한다 — 마지막 판독 회차 (2026-08-19)

총괄이 「지금 라벨이 아니다」 또는 「여러 주제가 다 맞다」 고 표시한 48행을,
「불만·요청이 향하는 대상이 다르면 나눈다」 기준으로 처리한 결과다.

조각을 새로 만들 때
    부모 행의 값을 물려받되, 조각마다 다시 판정한 칸만 덮어쓴다.
    ★ atomic_id 는 부모 source_id 뒤에 남는 번호를 붙인다 (계약 V-0-1)
"""
from __future__ import annotations

import collections, csv, glob, io, json, os, re, sys

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



# ★ 부록 §2.4 — 조각이 부모에게서 **이어받는** 칸 (2026-08-25)
#   여기 없는 칸은 조각마다 다시 판정한 값이 들어가야 한다.
#   부모 값을 몰래 물려주면 「디자인」 조각에 「스팀 성능」 이 붙는다.
이어받는_19칸 = (
    'source_id', 'raw_row_index', 'parent_voc_id', 'comment_relation',
    'original_voc', 'voc_cleaned', 'voc_residual', 'reference_brand',
    'market', 'language', 'source_context_summary', 'status',
    'scope_exclusion_reason', 'proposal_flag',
    'video_id', 'video_title', 'video_url',
    'product_category', 'product_category_source',
)


def _조각_나머지칸_채우기(nr: dict, 부모: dict, 순번: int) -> None:
    """★ 조각을 만든 뒤 **남은 칸을 채운다** (2026-08-26).

    ★ 왜 생겼나 — sky 「4차에서 실무자가 분리제안을 승인했으면, 그 승인을
      바탕으로 총괄 AI 가 분리시키면서 빈 값들을 다 채웠어야 하는 그 과정이
      빈 거겠죠? 2차 판독, 3차 감독은 분리시키고 다 채운 걸로 알고 있는데」

      맞는 지적이었다. 세어 보니 이렇다.

          reader_agree (2차 판독)      4,566행   0.7% 빔
          judge_agree  (3차 감독)      1,196행   1.6~3.5% 빔
          감독_분리제안 (3차가 나눈 조각)    37행  13.2% 빔
          sky+분리회차 (4차 이 도구)       570행 **100% 빔**  ← 여기만 통째로 빈다

      `build_bundle.py` (2·3차용 분리)는 조각을 만든 뒤
      `atomic_index` · `trace_summary` · 점수 기본값을 **채운다** (783~813줄).
      이 도구는 그것을 안 했다. 같은 일을 하는 도구를 새로 만들면서
      **앞의 것이 하던 일을 확인하지 않았다.**

    ★ 무엇을 채우나 — **지어내지 않는다.** `build_bundle` 이 하던 것과 같다.
      판정이 필요한 칸(rootcause_problem 등)은 여기서 손대지 않는다.
      그것은 총괄이 `조각_채우기.py` 로 따로 채운다.
    """
    # ① 조각 순번 — 없으면 대시보드·집계가 조각을 순서대로 못 읽는다
    if 'atomic_index' in nr and not str(nr.get('atomic_index') or '').strip():
        nr['atomic_index'] = str(순번)

    # ② 이력 — 부모의 trace 를 지우지 않고 앞에 split_from 을 붙인다
    #    (build_bundle 808~809 와 같은 꼴)
    if 'trace_summary' in nr:
        _옛 = (부모.get('trace_summary') or '').strip()
        nr['trace_summary'] = ' | '.join(
            x for x in ('split_from: %s' % 부모.get('atomic_id', ''), _옛) if x)

    # ③ 점수 칸 — 비면 집계에서 조각이 통째로 빠진다. build_bundle 과 같이 0
    for c in ('topic_score', 'tee_time_score', 'tee_effort_score',
              'tee_emotion_score', 'tee_success_score', 'rootcause_score'):
        if c in nr and not str(nr.get(c) or '').strip():
            nr[c] = '0'


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


def read_jsonl(pat):
    out = {}
    for p in sorted(glob.glob(os.path.join(BASE, '_판독패키지', '_결과', pat))):
        t = io.open(p, encoding='utf-8').read()
        # split 이 들어간 것은 중첩이라 균형 잡힌 괄호로 잘라야 한다
        i = 0
        while True:
            i = t.find('{"atomic_id"', i)
            if i < 0:
                i = t.find('{ "atomic_id"', i)
            if i < 0:
                break
            d, j = 0, i
            while j < len(t):
                if t[j] == '{':
                    d += 1
                elif t[j] == '}':
                    d -= 1
                    if d == 0:
                        break
                j += 1
            try:
                o = json.loads(t[i:j + 1])
                if o.get('atomic_id'):
                    out[o['atomic_id']] = o
            except Exception:
                pass
            i = j + 1
    return out


def main():
    if _확인만이면_멈춘다('분리 반영된 raw_voc.csv'):
        return 0

    J = read_jsonl('분리재지정_*.md')
    M = list(csv.DictReader(open(os.path.join(BASE, 's15_master', 'raw_voc.csv'),
                                 encoding='utf-8-sig')))
    print('판정 %d행 읽음' % len(J))

    used = {r['atomic_id'] for r in M}
    out, stats = [], collections.Counter()

    for r in M:
        j = J.get(r['atomic_id'])
        if not j:
            out.append(r)
            continue

        if j.get('split'):
            sid = r.get('source_id') or r['atomic_id'].rsplit('-', 1)[0]
            n = 0
            # ★ 안 덮인 글을 **소리 없이 버리지 않는다** (2026-08-26).
            #   조각이 원래 글을 다 덮어야 한다 (2차 계약 L-3).
            #   그래도 빠져나온 글이 있으면 voc_residual 에 남긴다.
            #   ★ 실제로 겪었다 — 3차 감독의 D 177건 중 166건이 원래 글의
            #     절반만 덮었다. 「정수통이랑 오수통까지 안쪽에 숨겨지는 구조라」
            #     같은 실제 VoC 가 사라질 뻔했다.
            _남는글 = ' '.join((r.get('atomic_voc') or '').split())
            for _s in j['split']:
                _t = ' '.join((_s.get('atomic_voc') or '').split())
                if _t:
                    _남는글 = _남는글.replace(_t, ' ', 1)
            _남는글 = ' '.join(_남는글.split())
            # ★ 이름을 짧게 돌려쓰지 않는다 — 오늘 `_s2` 를 겹쳐 써서
            #   사람이볼목록의 칸 이름이 VoC 본문이 되는 사고가 있었다.
            _감독이_적은_나머지 = str(j.get('residual') or '').strip()
            if _감독이_적은_나머지:
                _남는글 = ' '.join((_감독이_적은_나머지 + ' ' + _남는글).split())
            _첫조각 = True
            for seg in j['split']:
                # ★★ §2.4 — 이어받는 19칸만 물려받는다 (2026-08-25에 고침).
                #   전에는 `nr = dict(r)` 로 89칸을 통째로 복사했다.
                #   그래서 「디자인」 조각에 「스팀 성능」 이라는 근본원인이 붙었다.
                #   실측 — 사람이 쪼갠 11원문 전부가 TEE·RC·CEJ 를 물려받고 있었다.
                #   ★ 3차 감독은 조각마다 26칸을 직접 채워 낸다.
                #     통째로 복사하면 그 값이 버려진다.
                nr = {k: '' for k in r}
                for k in 이어받는_19칸:
                    if k in r:
                        nr[k] = r[k]
                # 감독이 낸 값을 그대로 받는다 (없는 칸은 빈 채로 둔다)
                for k, v in seg.items():
                    if k in nr:
                        nr[k] = v
                # ★ 남는 번호를 찾아 붙인다
                n += 1
                while '%s-%02d' % (sid, n) in used:
                    n += 1
                nr['atomic_id'] = '%s-%02d' % (sid, n)
                used.add(nr['atomic_id'])
                nr['atomic_voc'] = seg.get('atomic_voc', r.get('atomic_voc', ''))
                nr['topic'] = seg.get('topic', '')
                nr['topic_evidence'] = seg.get('topic_evidence', '')
                nr['status'] = 'normal'
                nr['split_origin_atomic_id'] = r['atomic_id']
                nr['decided_by'] = 'sky+분리회차'
                nr['decided_note'] = '대상이 다른 주제라 나눴다'
                # 남는 글은 첫 조각에 한 번만 담는다 (조각마다 되풀이하지 않는다)
                # ★ `n == 1` 로 판별하지 않는다 — id 가 겹치면 n 이 건너뛴다
                if _남는글 and _첫조각:
                    _첫조각 = False
                    nr['voc_residual'] = _남는글
                    nr['decided_note'] += (
                        ' | 어느 조각에도 안 들어간 글 %d자를 voc_residual 에 남겼다'
                        % len(_남는글))
                    stats['★ 남는 글을 residual 에 남김'] += 1
                nr['topic_secondary'] = ''
                _조각_나머지칸_채우기(nr, r, n)
                out.append(nr)
            stats['나눈 행'] += 1
            stats['생긴 조각'] += len(j['split'])
            continue

        if j.get('status') == 'scope_excluded':
            r['status'] = 'scope_excluded'
            r['scope_exclusion_reason'] = j.get('scope_exclusion_reason', 'no_analytic_value')
            r['topic'] = 'N/A'
            r['decided_by'] = 'sky+분리회차'
            r['decided_note'] = '분석할 내용이 없다'
            stats['제외로 보냄'] += 1
        elif j.get('topic'):
            r['status'] = 'normal'
            r['topic'] = j['topic']
            if j.get('topic_evidence'):
                r['topic_evidence'] = j['topic_evidence']
            r['decided_by'] = 'sky+분리회차'
            r['decided_note'] = '총괄 의견대로 라벨을 다시 붙였다'
            stats['라벨만 바꿈'] += 1
        out.append(r)

    cols = list(out[0].keys())
    with io.open(os.path.join(BASE, 's15_master', 'raw_voc.csv'), 'w',
                 encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c, '') for c in cols})

    for k, v in stats.most_common():
        print('   %-16s %4d' % (k, v))
    c = collections.Counter(kind(r) for r in out)
    print()
    print('   %d행 → 라벨 %d · 제외 %d · 미판정 %d'
          % (len(out), c['라벨'], c['제외'], c['미판정']))


if __name__ == '__main__':
    main()
