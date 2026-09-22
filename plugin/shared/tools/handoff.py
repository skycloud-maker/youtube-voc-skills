"""차수 인계 — 각 차수가 다음 차수에게 넘길 것을 스스로 만든다 (2026-08-19)

sky —
    "실무자들은 지금 이렇게 채팅에서 실시간으로 논의하며 추가할까요 말까요 하기가
     어려울 것이라 생각합니다. … 규정이 끝났다고 알려줘서 같이 고치기보다는,
     실무자용 pilot 에서는 후속 조치가 필요한 부분은 별도 파일로 남도록 만들어 주시고,
     실무자들이 그걸 시스템 담당자에게 전달하는 형태로 해서
     수정은 시스템 담당자가 하도록 되면 좋겠습니다"

★ 이 프로젝트가 굴러간 것은 총괄과 실시간으로 협상했기 때문이다. 그건 실무자가 못 한다.
  그래서 세 가지를 갈라 놓는다

    판독자(1~3차)  판정만 한다. 규칙이 없으면 「없다」 고 적고 넘어간다. 고치지 않는다
    실무자(4차)    최소한의 판단만 한다. 그리고 보정요청서를 총괄에게 전달한다
    시스템 담당자   규칙·코드·기준서를 고친다. 다음 판에 반영한다

내는 것
    _인계/보정요청.csv        누적. 회차마다 쌓인다. ★ 이 파일이 시스템 담당자에게 간다
    _인계/<N>차_인계서.md     다음 차수에게 무엇을 어떻게 넘기는지
"""
from __future__ import annotations

import collections, csv, datetime, glob, io, json, os, re, sys

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


# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
sys.path.insert(0, _HERE)      # 형제 도구는 스크립트가 있는 자리에서 찾는다

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ★ 꾸러미로 풀었을 때 스크립트는 「스크립트/」 안에 있다 (2026-08-21).
#   인계 파일을 그 안에 만들면 사람이 못 찾는다. 꾸러미 뿌리에 만든다.
_뿌리 = (os.path.dirname(BASE)
        if os.path.basename(BASE) in ('스크립트', 'scripts') else BASE)
OUT = os.path.join(_뿌리, '_인계')
REQ = os.path.join(OUT, '보정요청.csv')
COLS = ['번호', '접수일', '나온_회차', '갈래', '무엇이_문제인가',
        '근거_atomic_id', '근거_원문', '건수', '판독자_제안', '처리상태', '해소경위', '총괄_메모']

# 갈래 — 시스템 담당자가 무엇을 고쳐야 하는지로 나눈다
KIND = {
    '기준서공백': '기준서·택소노미에 담을 자리가 없다 → 라벨 신설 또는 정의 보강',
    '엔진결함': '1차 엔진 로직이 잘못 판단한다 → 코드 수정',
    '검사기': '검사기가 못 잡거나 잘못 잡는다 → check_selfcheck.py 수정',
    '규칙충돌': '문서끼리 어긋난다 → 어느 쪽이 정본인지 정한다',
    '데이터': '원본 수집·전처리 문제 → 수집 단계 확인',
}


def load_req():
    if not os.path.exists(REQ):
        return []
    return list(csv.DictReader(open(REQ, encoding='utf-8-sig')))


def save_req(rows):
    os.makedirs(OUT, exist_ok=True)
    with io.open(REQ, 'w', encoding='utf-8-sig', newline='') as h:
        w = csv.DictWriter(h, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, '') for c in COLS})


def collect(bundle_dir, round_name):
    """번들의 「기준서개정후보」·「구조적결함」 시트를 보정요청으로 옮긴다

    ★ 지금까지 이 둘은 번들 안에 묻혀 있어 아무도 안 봤다.
      회차가 끝날 때마다 여기로 뽑아 쌓는다
    """
    import openpyxl
    xl = glob.glob(os.path.join(bundle_dir, '*.xlsx'))
    if not xl:
        print('  번들 xlsx 를 못 찾았다')
        return []
    w = openpyxl.load_workbook(xl[0], read_only=True)
    got = []
    for sheet, kind in (('기준서개정후보', '기준서공백'), ('구조적결함', '엔진결함')):
        if sheet not in w.sheetnames:
            continue
        ws = w[sheet]
        it = ws.iter_rows(values_only=True)
        hdr = [str(x or '') for x in next(it)]
        for r in it:
            if not any(r):
                continue
            d = dict(zip(hdr, r))
            txt = str(d.get('내용') or d.get('원인') or '').strip()
            if not txt:
                continue
            got.append({
                '갈래': kind,
                '무엇이_문제인가': txt,
                '근거_atomic_id': str(d.get('atomic_id') or ''),
                '근거_원문': ' '.join(str(d.get('atomic_voc') or '').split())[:160],
                '나온_회차': round_name,
            })
    w.close()
    return got


# 어느 부품이 문제라고 말하는가 — 시스템 담당자는 부품 단위로 고친다
#   ★ 낱개로 73건을 던지면 안 본다. 총괄이 보는 것은 「어디를 손대야 하나」 다
COMPONENT = [
    ('택소노미 — 담을 라벨이 없다', r'택소노미|담을 자리|라벨이 없|담을 라벨|축이 기준서에 없'),
    ('E1 어휘가드 — 근거 어휘를 헐겁게 읽는다', r'E1|어휘\s*가드|evidence_guard'),
    ('entity_role — 대상 판정이 뒤집힌다', r'entity_role|경쟁사명'),
    ('제외 사유가 모자란다', r'scope_exclusion|제외 사유|out_of_scope|business_signal|운영자'),
    ('R14 RootCause 3-게이트', r'R14|Gate1|Gate3|rootcause'),
    ('R18 본문 우선 판정', r'R18|본문 우선'),
    ('극성·감정 오독', r'극성|감정|positive_message|뒤집어|완료형|R16'),
    ('분리·과분리', r'분리|atomic|과분리'),
    ('제품군 배정', r'제품군|product_category|기타\('),
    ('brand 오염', r'brand'),
    ('CEJ 단계', r'cej|여정'),
    ('confidence 계산', r'confidence'),
]


def component_of(text):
    for name, pat in COMPONENT:
        if re.search(pat, text, re.I):
            return name
    return '그 외 — 분류 안 됨'


def merge(new):
    """같은 문제를 여러 행이 말하면 하나로 묶고 건수를 센다

    ★ 시스템 담당자가 보는 것은 「몇 행에서 같은 말이 나왔나」 다.
      행 단위로 53건을 던지면 안 본다
    """
    old = load_req()
    seen = {r['무엇이_문제인가']: r for r in old}
    # ★ 부품 단위로 묶는다. 같은 곳을 고치면 여러 건이 한꺼번에 풀린다
    grp = collections.defaultdict(list)
    for g in new:
        # ★ 확인 요청은 판독자가 이미 묶어서 낸 것이다 — 다시 묶지 않는다
        #   (2026-08-23 · 5묶음이 1건으로 뭉쳐 129건이 1건이 됐다)
        grp[(g['갈래'],
             g.get('부품') or component_of(g['무엇이_문제인가']))].append(g)

    today = datetime.date.today().isoformat()
    n = max([int(r['번호']) for r in old if str(r.get('번호', '')).isdigit()] or [0])
    for key, items in sorted(grp.items(), key=lambda x: -len(x[1])):
        kk = '%s / %s' % key
        if kk in seen:                        # 이미 접수된 건이면 건수만 갱신
            seen[kk]['건수'] = str(max(int(seen[kk].get('건수') or 0), len(items)))
            continue
        n += 1
        g = items[0]
        # ★ 같은 부품에 묶인 지적을 다 적는다. 총괄이 한 번에 본다
        # ★ 판독자가 쓴 설명이 있으면 그것이 먼저다 (2026-08-23).
        #   제목으로 덮었더니 감독자가 쓴 「무엇을 확인해야 하는가」 가 버려졌다.
        #   논의본에서 「판독자가 본 것」 이 제목 반복이 되어 쓸모가 없었다.
        _쓴것 = [x.get('판독자_제안') for x in items
                      if (x.get('판독자_제안') or '').strip()]
        if _쓴것:
            detail = ' / '.join(dict.fromkeys(_쓴것))[:1600]
        elif os.environ.get('VOC_얼린기준_재현') == '1':
            detail = ' / '.join(dict.fromkeys(
                x['무엇이_문제인가'].split('.')[0].strip()[:88] for x in items))[:900]
        else:
            # ★ 2026-09-22 고침 (섹션 5b) — 첫 문장 88자만 남기니 판독자가 적은 영상 목록([가2])이
            #   첫 영상 설명 중간에서 잘렸다 (5개 중 1개만 남음). 판독자가 쓴 글은 자르지 않는다.
            #   옛 동작은 얼린 3차 기준 재현 시험만 쓴다 — VOC_얼린기준_재현=1
            detail = ' / '.join(dict.fromkeys(
                x['무엇이_문제인가'].strip() for x in items))[:1600]
        old.append({
            '번호': n, '접수일': today, '나온_회차': g['나온_회차'],
            '갈래': g['갈래'], '무엇이_문제인가': kk,
            '근거_atomic_id': ' | '.join(x['근거_atomic_id'] for x in items[:3]),
            '근거_원문': g['근거_원문'],
            # ★ 판독자가 센 건수가 맞다 — 다시 세면 129건이 1건이 된다
            '건수': (g['건수'] if str(g.get('건수') or '').isdigit()
                    else len(items)),
            '판독자_제안': detail, '처리상태': '대기', '총괄_메모': '',
        })
    save_req(old)
    return old


def write_handoff(stage, rows_req, stats):
    """다음 차수에게 넘기는 인계서"""
    NEXT = {
        1: ('2차 판독자 LLM', '_판독패키지/0_붙여넣을_프롬프트_도구형.md',
            '서로 다른 LLM 둘에게 각각 붙입니다. 상대의 답을 보지 않게 해야 합니다'),
        2: ('3차 감독 LLM', '_판독패키지/0_붙여넣을_프롬프트_감독.md',
            '갈린 행만 넘깁니다. 두 답을 A·B 로 익명화하고 행마다 순서를 섞습니다'),
        3: ('4차 사람 (실무자)', '채점지', '감독자끼리 갈린 행만 넘깁니다'),
        4: ('시스템 담당자', '_인계/보정요청.csv',
            '★ 실무자는 판정만 하고, 이 파일을 총괄에게 전달합니다'),
    }
    nxt, how, note = NEXT[stage]
    L = []
    L.append('# %d차 → %s 인계서\n' % (stage, nxt))
    L.append('작성 %s · 자동 생성 (`handoff.py`)\n' % datetime.date.today().isoformat())
    L.append('---\n')
    L.append('## 넘기는 것\n')
    L.append('```')
    for k, v in stats.items():
        L.append('%-22s %s' % (k, v))
    L.append('```\n')
    L.append('## 어떻게 넘기는가\n')
    L.append('```')
    L.append('받는 곳   %s' % nxt)
    L.append('붙일 것   %s' % how)
    L.append('★ %s' % note)
    L.append('```\n')

    if stage < 4:
        L.append('## ★ 판독자에게 — 규칙이 없으면 고치지 말고 적으십시오\n')
        L.append('```')
        L.append('기준서에 담을 자리가 없거나 엔진이 잘못 판단한 것 같으면')
        L.append('  ❌ 규칙을 새로 만들어 적용하지 마십시오')
        L.append('  ❌ 총괄에게 물어보려고 멈추지 마십시오')
        L.append('  ✅ 판정은 가장 가까운 값으로 하고, 무엇이 없었는지 적어서 넘기십시오')
        L.append('')
        L.append('     기준서개정후보 시트   담을 자리가 없다')
        L.append('     구조적결함 시트      엔진이 잘못 판단한다 (원인 단위로. 행 단위 아님)')
        L.append('')
        L.append('★ 그 둘이 자동으로 보정요청.csv 에 쌓여 시스템 담당자에게 갑니다')
        L.append('```\n')

    # ★ 앞 차수에서 해소된 것은 접어 둔다 (sky 2026-08-25)
    #   「3차 감독 과정에서 해소되는 내용은 보정요청 시트에 담지 말고
    #     이력만 남기는 것으로」
    #   ★ 버리지 않는다 — 예전에 번들만 떼어 옮기다 2차 보정요청 3건이
    #     사라진 적이 있다. 그래서 이어받게 만든 것이다.
    #     칸으로 가를 뿐이고, 파일에는 그대로 남는다.
    _접을것 = ('반영', '해소', '3차해소', '7차이월', '반려')
    pend = [r for r in rows_req
            if str(r.get('처리상태', '')).strip() not in _접을것]
    _해소 = [r for r in rows_req
             if str(r.get('처리상태', '')).strip() in _접을것]
    if _해소:
        L.append('')
        L.append('★ 앞 차수에서 해소된 %d건은 접어 두었습니다 — '
                 '`_인계/보정요청.csv` 의 「해소경위」 칸에 있습니다' % len(_해소))
    L.append('## 지금까지 쌓인 보정요청 — %d건 (대기 %d건)\n' % (len(rows_req), len(pend)))
    if pend:
        L.append('| # | 갈래 | 무엇이 문제인가 | 건수 |')
        L.append('|---|---|---|---:|')
        for r in sorted(pend, key=lambda x: -int(x.get('건수') or 0))[:12]:
            L.append('| %s | %s | %s | %s |'
                     % (r['번호'], r['갈래'],
                        r['무엇이_문제인가'].replace('|', '·')[:78], r['건수']))
        if len(pend) > 12:
            L.append('')
            L.append('*외 %d건 — `_인계/보정요청.csv` 를 보십시오*' % (len(pend) - 12))
    L.append('')

    if stage == 4:
        L.append('---\n')
        L.append('## ★ 실무자가 하실 것 — 둘뿐입니다\n')
        L.append('```')
        L.append('① 채점지에 O / X 를 적습니다')
        L.append('     ★ 규칙을 고치려 하지 마십시오. 「이건 X, 맞는 건 이것」 만 적으면 됩니다')
        L.append('     여러 개가 맞아 보이면 다 적으셔도 됩니다')
        L.append('')
        L.append('② _인계/보정요청.csv 를 시스템 담당자에게 전달합니다')
        L.append('     ★ 열어서 판단하실 필요 없습니다. 그대로 넘기시면 됩니다')
        L.append('     총괄이 「처리상태」 와 「총괄_메모」 를 채웁니다')
        L.append('```\n')
        L.append('## 시스템 담당자가 하실 것\n')
        L.append('```')
        for k, v in KIND.items():
            L.append('%-10s %s' % (k, v))
        L.append('')
        L.append('★ 고친 뒤 「처리상태」 를 반영 / 보류 로 바꾸십시오.')
        L.append('  다음 판 인계서에서 그 건은 빠집니다')
        L.append('```')

    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, '%d차_인계서.md' % stage)
    io.open(p, 'w', encoding='utf-8').write('\n'.join(L))
    return p


def _판독자():
    """이 폴더에서 판독한 사람이 누구인지 판정 파일 이름에서 읽는다.

    판독결과_full_07_Codex.md  →  Codex
    """
    뿌리 = os.path.join(BASE, '_판독패키지', '_결과')
    이름들 = collections.Counter()
    for p in glob.glob(os.path.join(뿌리, '판독결과_full_*.md')):
        m = re.match(r'판독결과_full_[^_]+_(.+)$',
                     os.path.splitext(os.path.basename(p))[0])
        if m:
            이름들[m.group(1)] += 1
    return 이름들.most_common(1)[0][0] if 이름들 else ''


def _최종번들():
    """**자기** 최종 번들을 찾는다.

    ★ 「가장 새 것」 을 고르면 안 된다 (2026-08-23).
      B 폴더에 A 번들이 1분 새것으로 들어와 있었고, 그것을 골라
      **A 의 보정요청 3건이 B 의 것으로 넘어갔다.** 내가 만든 사고다.
      ★ 기준은 새것이 아니라 **자기 것인가** 다.

    회차 번들(bundle_full_01 …)과 「옛판」 은 최종이 아니므로 뺀다.
    """
    뿌리 = os.path.join(BASE, '_판독패키지', '_결과')
    나 = _판독자()
    후보 = []
    for 이름 in sorted(os.listdir(뿌리)) if os.path.isdir(뿌리) else []:
        길 = os.path.join(뿌리, 이름)
        if not os.path.isdir(길):
            continue
        if 이름.startswith('bundle_full_') or '옛판' in 이름:
            continue
        if not os.path.exists(os.path.join(길, 'raw_voc.csv')):
            continue
        후보.append((os.path.getmtime(길), 이름))
    if not 후보:
        return ''

    # ★ 자기 이름이 붙은 번들이 있으면 그것만 쓴다
    내것 = [x for x in 후보 if 나 and 나.lower() in x[1].lower()]
    if 내것:
        return '_판독패키지/_결과/' + max(내것)[1]

    남 = [x[1] for x in 후보 if 나 and 나.lower() not in x[1].lower()]
    if 나 and 남:
        print('  ★ 이 폴더의 판독자는 「%s」 인데 남의 번들이 있습니다: %s'
              % (나, ' · '.join(남)))
        print('     판독자 폴더는 섞이면 안 됩니다. 남의 번들을 치우십시오.')
        return ''
    return '_판독패키지/_결과/' + max(후보)[1]


def _확인요청_모으기():
    """판정 파일 안의 {"확인요청": [...]} 를 모은다.

    ★ 프롬프트가 그렇게 내라고 시킨 형식이다 (2026-08-23).
      번들 시트만 보다가 감독자가 낸 200행짜리 요청을 통째로 놓쳤다.
      **낸 것을 안 받으면 안 낸 것과 같다.**
    """
    뿌리 = os.path.join(BASE, '_판독패키지', '_결과')
    나온것 = []
    for p in sorted(glob.glob(os.path.join(뿌리, '*.md'))):
        글 = io.open(p, encoding='utf-8', errors='replace').read()
        if '"확인요청"' not in 글:
            continue
        낸이 = os.path.splitext(os.path.basename(p))[0]
        for m in re.finditer(r'\{\s*"확인요청"\s*:\s*\[', 글):
            # 여는 중괄호부터 짝이 맞는 곳까지 잘라낸다
            i, 깊이 = m.start(), 0
            for j in range(i, len(글)):
                if 글[j] == '{':
                    깊이 += 1
                elif 글[j] == '}':
                    깊이 -= 1
                    if 깊이 == 0:
                        break
            else:
                continue
            try:
                덩이 = json.loads(글[i:j + 1])
            except Exception:                                # noqa: BLE001
                continue
            for 것 in (덩이.get('확인요청') or []):
                나온것.append({
                    '갈래': '기준서공백',
                    '무엇이_문제인가': '기준서공백 / %s' % (것.get('묶음') or ''),
                    '근거_atomic_id': ' | '.join(것.get('대표 행') or [])[:400],
                    '근거_원문': '',
                    '건수': str(것.get('건수') or ''),
                    '판독자_제안': (것.get('무엇을 확인해야 하는가') or '')[:900],
                    '나온_회차': '3차 감독 (%s)' % 낸이,
                    '부품': 것.get('묶음') or '',
                })
    return 나온것


def main():
    if _확인만이면_멈춘다('_인계/보정요청.csv · 인계서'):
        return 0

    os.chdir(BASE)
    bundle = _최종번들()
    if not bundle:
        print('  최종 번들이 없습니다 — 먼저 전 회차를 마치십시오')
        return
    got = collect(bundle, sys.argv[1] if len(sys.argv) > 1 else '2차·3차 통합')
    # ★ 판정 파일에 적힌 확인 요청도 받는다 (2026-08-23).
    #   번들 시트만 보다가 감독자가 낸 200행짜리 요청을 통째로 놓쳤다.
    _추가 = _확인요청_모으기()
    if _추가:
        print('  판정 파일에서 확인 요청 %d묶음을 받았습니다' % len(_추가))
        got = list(got) + _추가
    req = merge(got)
    print('보정요청 %d건 (이번에 새로 %d묶음)' % (len(req), len(set(g['무엇이_문제인가'][:60] for g in got))))
    print('  갈래별 %s' % dict(collections.Counter(r['갈래'] for r in req)))
    print()

    rows = list(csv.DictReader(open(os.path.join(bundle, 'raw_voc.csv'), encoding='utf-8-sig')))
    from check_selfcheck import kind
    k = collections.Counter(kind(r) for r in rows)
    stats = {
        '분석 단위': '%d행' % len(rows),
        '라벨': '%d (%.1f%%)' % (k['라벨'], 100 * k['라벨'] / len(rows)),
        '제외': str(k['제외']),
        '미판정': str(k['미판정']),
        '데이터': bundle + '/raw_voc.csv',
        '번들': bundle + '/voc_dashboard_export_bundle_2차시험본.xlsx',
    }
    for s in (1, 2, 3, 4):
        p = write_handoff(s, req, stats)
        print('  %s' % p)
    print()
    print('  ★ _인계/보정요청.csv — 이 파일이 시스템 담당자에게 갑니다')


if __name__ == '__main__':
    main()
