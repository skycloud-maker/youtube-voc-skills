# ★ 0 으로 나누지 않는다 (2026-08-26에 고침).
#   데이터가 0행일 때 ZeroDivisionError 로 죽었다.
#   빈 꾸러미에서 돌리면 안내 대신 에러가 났다.
# -*- coding: utf-8 -*-
"""1차 훑기 진행 현황 — 라벨이 얼마나 붙었는가.

사용:
    python run_status.py

★ 판독자별로 어느 회차까지 했는지, 읽은 행 중 라벨이 몇 %인지 본다.
  회차가 어긋나면 여기서 보인다 — 두 판독자는 같은 회차를 봐야 대조가 된다.

★ 읽은 행 기준 비율과 1차의 40.2% 는 분모가 다르다.
  1차 40.2%  = 분석 대상(제외 제거 후) 중 라벨
  pass1 %    = 읽은 행 전체 중 라벨 (제외가 아직 분모에 있다)
  다 읽은 뒤 build_final.py 로 같은 잣대의 최종 수치를 낸다

원본을 수정하지 않는다. 읽기 전용.
"""
import sys, os, glob, collections

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
# ★ 전에는 여기서 sky 컴퓨터 폴더로 os.chdir 했다 (sky 2026-08-21).
#   그 폴더가 없는 컴퓨터에서는 이 줄에서 바로 멈췄다.
#   이제 자기 자리를 기준으로 삼는다.
B = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, B)
os.chdir(os.path.dirname(B) if os.path.basename(B) in ('스크립트', 'scripts') else B)
from build_bundle import read_judgments, read_csv, SRC, PRODUCTS
try:
    from apply_approved import legitimate_na
except ImportError:      # 꾸러미에 없을 때 — 이 화면은 이 함수를 안 쓴다
    def legitimate_na(*_a, **_k):
        return False

rows, order, seen = {}, [], set()
for p in PRODUCTS:
    rs, _ = read_csv(SRC[p])
    for r in rs:
        if r['atomic_id'] not in seen:
            seen.add(r['atomic_id']); rows[r['atomic_id']] = r; order.append(r['atomic_id'])

# pass1 판정만 모은다. 판독자별로 따로
per = collections.defaultdict(dict)   # reader -> aid -> ('라벨'|'제외'|'그외', 라벨명)
for p in sorted(glob.glob('_판독패키지/_결과/판독결과_full_*.md')):
    stem = os.path.basename(p)[5:-3]
    # ★ 대소문자를 가리지 않는다 (2026-08-22).
    #   `판독결과_full_01_Codex.md` 를 claudecode 로 세어 화면이 거짓이 됐다
    reader = 'codex' if 'codex' in stem.lower() else 'claudecode'
    for j in read_judgments(p):
        aid = j.get('atomic_id')
        if not aid: continue
        fl = {x.get('field'): str(x.get('proposed', '')) for x in (j.get('findings') or [])}
        segs = ((j.get('structure') or {}).get('segments') or [])
        labs = [s.get('topic') for s in segs if s.get('topic')]
        if fl.get('topic'): labs.append(fl['topic'])
        cur = (rows[aid].get('topic') or '').strip()
        final = labs[0] if labs else cur
        if fl.get('status') == 'scope_excluded':
            per[reader][aid] = ('제외', '')
        elif final and final not in ('N/A', '미분류', '') and not final.startswith('기타('):
            per[reader][aid] = ('라벨', final)
        elif final == '기타' or (final or '').startswith('기타('):
            per[reader][aid] = ('기타', final)
        else:
            per[reader][aid] = ('미판정', final)

rounds = collections.defaultdict(set)
for p in sorted(glob.glob('_판독패키지/_결과/판독결과_full_*.md')):
    nm = os.path.basename(p)[5:-3]
    rd = nm.split('_')[1]
    rounds['codex' if 'codex' in nm else 'claudecode'].add(rd)

print('=' * 66)
print('  전량 재분석(full) 진행 현황')
print('=' * 66)
print('  전체 %d행' % len(order))
for reader in ('codex', 'claudecode'):
    d = per[reader]
    if not d: continue
    c = collections.Counter(v[0] for v in d.values())
    print()
    print('  [%s]  회차 %s  ·  읽은 행 %d  (%.0f%%)'
          % (reader, ' '.join(sorted(rounds[reader])) or '-', len(d), 100 * len(d) / max(1, len(order))))
    for k in ('라벨', '기타', '제외', '미판정'):
        n = c.get(k, 0)
        print('     %-6s %4d행   읽은 것의 %5.1f%%' % (k, n, 100 * n / max(1, len(d))))

# 두 판독자 합쳐 — 읽힌 행 기준
allread = set(per['codex']) | set(per['claudecode'])
print()
print('=' * 66)
print('  분석 대상 기준 — 1차와 견주면')
print('=' * 66)
nm = [r for r in rows.values() if (r.get('status') or '').strip() == 'normal']
leg = {r['atomic_id'] for r in nm if (r.get('topic') or '').strip() == 'N/A'
       and legitimate_na(r.get('atomic_voc') or '')}
den = [r for r in nm if r['atomic_id'] not in leg]
def top(r): return (r.get('topic') or '').strip()
lab1 = [r for r in den if top(r) not in ('', 'N/A', '미분류') and not top(r).startswith('기타')]
print('  1차   분석 대상 %d · 라벨 %d = %.1f%%' % (len(den), len(lab1), 100*len(lab1)/ max(1, len(den))))
print()
print('  읽은 행 %d / 전체 %d = %.0f%%' % (len(allread), len(order), 100*len(allread)/ max(1, len(order))))
print('  ★ 아직 %d행 남았다. 지금 수치로 전체를 말할 수 없다' % (len(order) - len(allread)))

print()
allr = sorted(set(rounds['codex']) | set(rounds['claudecode']))
both = sorted(set(rounds['codex']) & set(rounds['claudecode']))
print('  회차   둘 다 한 것 %s' % (' '.join(both) or '-'))
for r in ('codex', 'claudecode'):
    only = sorted(set(rounds[r]) - set(both))
    if only:
        print('         %s 만 %s' % (r, ' '.join(only)))
if sorted(rounds['codex']) != sorted(rounds['claudecode']):
    print('  ★ 회차가 어긋나 있다. 뒤진 쪽이 따라잡아야 대조가 된다')
