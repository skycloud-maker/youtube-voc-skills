"""판독 결과 제출 게이트 — 판독자가 자기 답을 내기 전에 스스로 돌린다.

사용:
    python check_submission.py <판독결과.md> [...]

정답 없이 기계로 잴 수 있는 것만 본다. 판정이 맞았는지는 못 잰다.
여기서 걸리면 그 답은 반려다. 사람이 읽기 전에 판독자가 고쳐야 한다.

  ① 형식        atomic_id · verdict 허용값 · findings 구조
  ② Enum 준수   제안값이 1차 schema.py 의 허용값인가
                ★ "scope_excluded / channel_feedback" 처럼 두 값을 한 칸에 붙여 쓰면 걸린다
  ③ 짝필드 완결  status=scope_excluded 를 제안했으면 scope_exclusion_reason 도 함께 냈는가
                (정본 §7.9 ④ — 제외 판정은 사유와 한 쌍이다)
                ★ verdict 도 같아야 한다. 반쪽만 승인되면 사유가 공란이 된다 (CP-31)
  ④ 근거 실재    finding.quote 가 1차 산출물 어느 칸에 실제로 있는가
  ⑤ 분리 계약    조각마다 「서로 다른 캐노니컬 라벨」 인가 (부록 §1.2 ①)
                ★ 같은 라벨로 두 조각을 내면 나눌 근거 자체가 없다
                ★ 라벨 없는 조각은 verdict=기준서 미커버 일 때만 허용한다 (R17 v4.9)
                CP-29 이전에는 이 조건을 기계가 안 봐서 판독 6회에 14건이 샜다
  ⑥ 검토 필요    재검토 필요로 넘길 때 tried(무엇을 대보았는가) · 근거 인용이 있는가
                ★ 자기 재확인(부록 §3-6-1)을 안 하고 넘기면 반려한다
                ★ 배치의 5%% 를 넘으면 경고한다 — 사람이 부족한 게 아니라
                  규칙이 부족한 것이다 (sky 2026-08-16)

  ⑦ 신설 topic   ★ topic 은 열린 어휘다 (CP-40 · sky 결정). 막지 않는다
                대신 둘을 본다 — topic_group 이 붙었는가 · 기존 라벨과 겹치지 않는가
                "같은 린트 잔류인데 하나는 린트 잔류, 하나는 먼지 잔류 이런 식으로
                 같은 의미를 다르게 표기해서 수치가 묶이지 않는 문제만 발생하지 않는다면"

Enum 은 1차 엔진 schema.py 에서 직접 읽는다. 여기에 값을 베껴 적지 않는다.
"""
from __future__ import annotations

import json, os, sys, collections

# ★ cp949 콘솔에서 em dash 하나 때문에 UnicodeEncodeError 가 나서
#   반려 0건인데 exit code 1 로 끝났다. 판독자가 반려로 오인한다 (CP-37)
#   Claude Code 도구형 지적 2026-08-16
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

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
from build_bundle import read_judgments
from verify_quotes import norm, contains, load_source

ENGINE = (os.environ.get('VOC_ENGINE')
          or os.path.dirname(os.path.abspath(__file__)))
VERDICTS = {'정상', '오류', '재검토 필요', '기준서 미커버'}
PAIRED = {'status': ('scope_excluded', 'scope_exclusion_reason')}


# 점수 컬럼 — 코드 ENUM_COLUMNS 에는 없다. 정본 §7.7·§7.8 과 데이터사전 표가 근거다.
# ★ 여기에 없으면 게이트가 점수 제안값을 검증 없이 통과시킨다 (CP-18 에서 발견)
SCORE_ENUMS = {
    'topic_score':      {'0', '1', '3', '5'},
    'rootcause_score':  {'0', '1', '3', '5'},
    'tee_time_score':    {'-5', '-3', '-1', '0', '1', '3', '5'},
    'tee_effort_score':  {'-5', '-3', '-1', '0', '1', '3', '5'},
    'tee_emotion_score': {'-5', '-3', '-1', '0', '1', '3', '5'},
    'tee_success_score': {'-5', '-3', '-1', '0', '1', '3', '5'},
}


def norm_score(v):
    """+3 · ＋3 · 3.0 을 3 으로 맞춘다. 부호는 살린다."""
    s = str(v).strip().replace('＋', '+').replace('−', '-').replace('–', '-')
    s = s.lstrip('+')
    try:
        f = float(s)
        return str(int(f)) if f == int(f) else s
    except ValueError:
        return s


SECONDARY_TOPICS = 대장자리('secondary_topics.json')
SECONDARY_ENUMS = 대장자리('secondary_enums.json')


def load_enums():
    """1차 schema.py 의 Enum + 2차 확장 라벨.

    ★ 1차는 동결이라 CANONICAL_TOPICS 를 건드리지 않는다.
      2차가 신설한 라벨은 s9_group/secondary_topics.json 에 두고 여기서 합친다
      (27_택소노미_2차확장_4종.md · CP-27)
    """
    sys.path.insert(0, ENGINE)
    from src.voc_rebuild.schema import ENUM_COLUMNS
    enums = {**ENUM_COLUMNS, **SCORE_ENUMS}
    if os.path.exists(SECONDARY_TOPICS):
        ext = json.load(open(SECONDARY_TOPICS, encoding='utf-8')).get('확장 라벨') or {}
        if ext and 'topic' in enums:
            enums['topic'] = set(enums['topic']) | set(ext)
    # 2차 확장 Enum (topic 외) — 같은 이유로 사이드카에 둔다 (CP-33)
    if os.path.exists(SECONDARY_ENUMS):
        for col, vals in (json.load(open(SECONDARY_ENUMS, encoding='utf-8'))
                          .get('확장 Enum') or {}).items():
            if col in enums:
                enums[col] = set(enums[col]) | set(vals)
    return enums


def check(path, src, enums):
    js = read_judgments(path)
    bad = collections.defaultdict(list)

    for j in js:
        aid = j.get('atomic_id', '') or '(atomic_id 없음)'

        # ① 형식
        if not j.get('atomic_id'):
            bad['형식'].append((aid, 'atomic_id 가 비었다'))
        v = j.get('verdict', '')
        if v not in VERDICTS:
            bad['형식'].append((aid, 'verdict "%s" 는 허용값이 아니다' % v))
        if v in ('오류', '재검토 필요') and not (j.get('findings') or []):
            bad['형식'].append((aid, 'verdict=%s 인데 findings 가 비었다' % v))

        row = src.get(j.get('atomic_id', ''))
        if row is None:
            bad['형식'].append((aid, '원본에 없는 atomic_id'))

        flds = {f.get('field', ''): f for f in (j.get('findings') or [])}
        for f in (j.get('findings') or []):
            fld, prop = f.get('field', ''), str(f.get('proposed', ''))

            # ② Enum 준수
            #
            # ★ topic 은 열린 어휘다 (CP-40 · sky 결정 2026-08-16)
            #   "topic 의 라벨은 제 허가 없이도 채울 수 있어도 됩니다"
            #   대신 지켜야 할 두 가지를 아래 ⑦ 에서 검사한다 —
            #     ① 같은 주제가 같은 워딩으로 묶이는가 (동의어 분산 금지)
            #     ② topic_group 이 붙었는가
            #   Enum 으로 막으면 판독자가 억지로 기존 라벨에 밀어 넣는다.
            #   그러면 기타가 커지는 대신 오분류가 늘어난다
            if fld == 'topic':
                allow = None
            else:
                allow = enums.get(fld)
            if fld in SCORE_ENUMS:
                prop = norm_score(prop)
            if allow is not None and prop and prop not in allow:
                hint = ''
                if '/' in prop or ' 또는 ' in prop:
                    hint = '  ← 두 값을 한 칸에 붙여 썼다. finding 을 나눠라'
                bad['Enum'].append((aid, '%s = "%s" 는 허용값이 아니다%s' % (fld, prop[:40], hint)))

            # ③ 짝필드 완결
            if fld in PAIRED:
                trig, mate = PAIRED[fld]
                if prop == trig and mate not in flds:
                    bad['짝필드'].append((aid, '%s=%s 를 제안했는데 %s finding 이 없다' % (fld, trig, mate)))
                # ★ 짝은 verdict 도 같아야 한다 (CP-31)
                #   status 를 [오류], 사유를 [재검토 필요] 로 내면 이 게이트는 통과하지만
                #   apply_approved 가 status 만 반영해 사유가 공란이 되고 V-0-2 계약 위반이 난다
                #   ★ Claude Code 도구형이 실제로 발생시켜 확인했다
                elif prop == trig and flds[mate].get('verdict') != f.get('verdict'):
                    bad['짝필드'].append(
                        (aid, '%s=[%s] 인데 %s=[%s] 다 — 짝은 verdict 가 같아야 한다. '
                              '반쪽만 승인되면 계약 위반이 난다'
                         % (fld, f.get('verdict'), mate, flds[mate].get('verdict'))))

            # ④ 근거 실재
            if row is not None:
                q = f.get('quote', '')
                if not norm(q):
                    bad['근거'].append((aid, '%s — quote 가 비었다' % fld))
                elif not any(contains(norm(x), q) for x in row.values() if x):
                    bad['근거'].append((aid, '%s — quote 가 원문 어느 칸에도 없다: %s' % (fld, str(q)[:34])))

        # ⑤ 분리 계약 — 조각마다 서로 다른 캐노니컬 라벨 (부록 §1.2 ①)
        st = j.get('structure') or {}
        if st.get('split'):
            segs = st.get('segments') or []
            tops = [(s.get('topic') or '').strip() for s in segs]

            if len(segs) < 2:
                bad['분리'].append((aid, 'split=true 인데 조각이 %d개다' % len(segs)))

            dup = [t for t, n in collections.Counter(tops).items() if n > 1 and t]
            for t in dup:
                bad['분리'].append((aid, '조각 %d개가 같은 라벨 "%s" 다 — 나눌 근거가 없다'
                                   % (tops.count(t), t)))

            # 라벨 없는 조각은 원칙적으로 나눌 근거가 없다.
            # 예외 — verdict=기준서 미커버 로 「담을 라벨이 아직 없다」고 밝힌 경우 (R17 v4.9)
            nc = [t or '(공란)' for t in tops if t in ('미분류', 'N/A', '')]
            if nc and j.get('verdict') != '기준서 미커버':
                bad['분리'].append(
                    (aid, '조각 %d개가 캐노니컬 라벨이 아니다 (%s) — 라벨 부재면 '
                          'verdict 를 [기준서 미커버] 로 내라' % (len(nc), ' · '.join(nc))))

    # ⑥ 검토 필요 — 근거 없이 넘기지 못한다 (부록 §3-6-4 · CP-35)
    rv = [j for j in js if j.get('verdict') == '재검토 필요']
    for j in rv:
        aid = j.get('atomic_id', '') or '(atomic_id 없음)'
        # tried = 무엇을 대보았는가. 이것이 없으면 자기 재확인을 안 한 것이다
        blob = ' '.join(str(j.get(k) or '') for k in ('tried', 'review_reason', 'rationale'))
        blob += ' ' + ' '.join(str(f.get(k) or '')
                               for f in (j.get('findings') or [])
                               for k in ('tried', 'reason', 'rationale'))
        if not str(j.get('tried') or '').strip() and 'tried' not in blob:
            bad['검토'].append((aid, '재검토 필요인데 tried(무엇을 대보았는가)가 없다 — '
                                   '자기 재확인(§3-6-1)을 먼저 하라'))
        if not any(str(f.get('quote') or '').strip() for f in (j.get('findings') or []))                 and not str(j.get('quote') or '').strip():
            bad['검토'].append((aid, '재검토 필요인데 근거 인용이 없다'))

    # 상한 — 넘치면 사람이 부족한 것이 아니라 규칙이 부족한 것이다 (sky 2026-08-16)
    if js and len(rv) > max(2, len(js) * 0.05):
        bad['검토'].append(('(배치 전체)',
                          '재검토 필요 %d/%d = %.0f%% — 상한 5%% 를 넘었다. '
                          '사유를 모아 규칙을 고쳐라' % (len(rv), len(js), 100 * len(rv) / len(js))))

    # ⑦ 신설 topic — 막지 않는다. 흩어지는 것만 막는다 (CP-40 · sky 결정)
    try:
        from topic_registry import load_known, load_groups, similarity
        known, groups = load_known(), load_groups()
        seen_new = {}
        for j in js:
            cands = [(f.get('proposed'), f.get('topic_group'), j)
                     for f in (j.get('findings') or []) if f.get('field') == 'topic']
            cands += [(s.get('topic'), s.get('topic_group'), j)
                      for s in ((j.get('structure') or {}).get('segments') or [])]
            # ★ 신설 라벨이 아닌 값을 걸러낸다 (CP-43 · Claude Code 지적)
            #   정본 §11 은 「제안값이 없으면 재검토 필요」 라 한다.
            #   판독자가 topic 의 proposed 에 그런 뜻의 말을 쓰면
            #   이 검사가 신설 라벨로 읽고 반려했다. 판독자가 실제로 겪었다
            NOT_LABEL = {'N/A', '미분류', '없음', '판단 불가', '제안값 없음',
                         '재검토 필요', '-', '—', 'TBD', 'unknown'}
            for val, grp, jj in cands:
                val = str(val or '').strip()
                if not val or val in known or val in NOT_LABEL:
                    continue
                seen_new.setdefault(val, (str(grp or '').strip(), jj.get('atomic_id', '')))
        for val, (grp, aid) in seen_new.items():
            if not grp:
                bad['라벨'].append(
                    (aid, '신설 topic "%s" 에 topic_group 이 없다 — '
                          '새 라벨은 그룹을 함께 내야 한다 (sky 2026-08-16)' % val))
            near = sorted(((similarity(val, k), k) for k in known), reverse=True)[:1]
            if near and near[0][0] >= 0.55:
                bad['라벨'].append(
                    (aid, '신설 topic "%s" 이 기존 "%s" 와 유사하다 (%.2f) — '
                          '같은 주제는 같은 워딩으로 묶어라'
                     % (val, near[0][1], near[0][0])))
    except Exception as exc:
        bad['라벨'].append(('(전체)', '신설 topic 검사를 못 돌렸다: %s' % exc))

    return js, bad


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src, enums = load_source(), load_enums()
    worst = 0

    for path in sys.argv[1:]:
        js, bad = check(path, src, enums)
        total = sum(len(v) for v in bad.values())
        worst = max(worst, total)

        print()
        print('=' * 74)
        print('%s   판정 %d행' % (os.path.basename(path), len(js)))
        print('=' * 74)
        if not total:
            print('  통과 — 반려 사유 없음')
            continue
        print('  ★ 반려  %d건' % total)
        for kind in ('형식', 'Enum', '짝필드', '근거', '분리', '검토', '라벨'):
            items = bad.get(kind) or []
            if not items:
                continue
            print()
            print('  [%s] %d건' % (kind, len(items)))
            for aid, msg in items[:10]:
                print('    %-46s %s' % (aid[:46], msg))
            if len(items) > 10:
                print('    ... 외 %d건' % (len(items) - 10))

    print()
    sys.exit(1 if worst else 0)


if __name__ == '__main__':
    main()
