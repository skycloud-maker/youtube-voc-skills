"""역할별 배포 꾸러미 5개 (2026-08-19)

sky —
    "1. 전체 문서 통합 (1~4차 운영을 위해 필요한 자료 전체 = 2,3,4,5번 + 공통 문서)
     2. 2차 LLM 판독자 첨부파일 + 프롬프트 + 사용 가이드
     3. 3차 LLM 감독자 첨부파일 + 프롬프트 + 사용 가이드
     4. 마지막 검토 방법 + 번들 sheet 설명
     5. 대시보드 사용 설명서
     zip 으로 묶을 때 온전하게 역할을 하는지도 점검할 것"

★ 점검한다는 것
  · 넣기로 한 파일이 실제로 들어갔는가 (빠진 파일 = 실패)
  · 안내문이 가리키는 파일이 그 꾸러미 안에 있는가
  · 스크립트가 읽는 파일이 같이 들어갔는가
  · 요약본이 아니라 원본이 들어갔는가 (크기로 확인)
"""
from __future__ import annotations

import glob, io, os, re, subprocess, sys, zipfile

# ★ 꾸러미로 풀면 스크립트는 「스크립트/」 안에 있고 데이터는 그 옆이다.
#   BASE 는 언제나 「꾸러미 뿌리」 를 가리킨다 (sky 2026-08-21).
#   sky 작업 폴더에서는 둘이 같은 자리라 달라지는 것이 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(_HERE)
        if os.path.basename(_HERE) in ('스크립트', 'scripts') else _HERE)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def _최신판():
    """★ 결과 데이터는 **가장 나중 판**에서 가져온다 (2026-08-26).

    왜 — 여기가 `_판독패키지/_결과/master_final` 로 박혀 있었다. 그것은 1판이다.
      2판을 돌린 뒤에도 꾸러미와 릴리스는 계속 **1판 데이터**를 실었다.
      그리고 그 1판에는 5차 동결의 용어 일괄 치환이 **실제 댓글 본문**을 덮은
      자국이 있었다 — 「담당자」 가 「총괄」 로 4곳 (93_오류발견대장 참조).
      낡은 판을 실으니 훼손본이 GitHub 에 그대로 올라가 있었다.

    ★ 판 이름을 박지 않는다. `_2판` · `_3판` … 중 가장 큰 것을 스스로 찾는다.
      그래야 다음 판을 돌려도 여기를 고칠 일이 없다.
    """
    끝 = ''
    번호 = 0
    for 이름 in os.listdir(BASE):
        m = re.fullmatch(r'_(\d+)판', 이름)
        if not m or not os.path.isdir(os.path.join(BASE, 이름)):
            continue
        n = int(m.group(1))
        # 그 판에 결과가 실제로 있어야 쓴다 — 빈 폴더면 넘어간다
        if not os.path.isfile(os.path.join(
                BASE, 이름, '_판독패키지', '_결과', 'master_final',
                'raw_voc.csv')):
            continue
        if n > 번호:
            번호, 끝 = n, 이름
    return (끝 + '/') if 끝 else ''


_판 = _최신판()
M = _판 + '_판독패키지/_결과/master_final'
S15 = _판 + 's15_master'

# ★ 돌리는 중에 만들어지는 것 — 꾸러미에 미리 넣지 않는다
RUNTIME = {
    'judge_input.csv', 'ab_mapping.json', 'voc_secondary_dataset.csv',
    'raw_voc.csv', '사람이볼목록.csv', '보정요청.csv',
    '1차_인계서.md', '2차_인계서.md', '3차_인계서.md', '4차_인계서.md',
    # ★ 3차가 만들어 실무자가 옆에 놓는 것 — 꾸러미에 없는 것이 맞다 (2026-08-23).
    #   전에는 4차 꾸러미가 이것들을 안고 있어 9MB 였고,
    #   데이터가 바뀌면 꾸러미를 다시 만들어야 했다. 안 만들면 옛 결과로 회의한다.
    '3차_최종데이터.xlsx', 'voc_dashboard_export_bundle_2차시험본.xlsx',
    '보정요청_논의본.md', '개선우선순위_두축.csv', '지표.json',
    '전체_최종_번들.xlsx',
}

# ★ 가이드 4종은 서로를 가리킨다. 어느 꾸러미에나 다 넣는다
GUIDES = [
    ('60_2차판독_실무자_사용가이드.md', '가이드/'),
    ('61_3차감독_실무자_사용가이드.md', '가이드/'),
    ('62_4차검토_및_번들해설.md', '가이드/'),
    ('63_대시보드_사용설명서.md', '가이드/'),
]

# 어느 꾸러미에나 들어가는 것 — 「지금 무엇이 정본인가」 를 알려 준다
COMMON = [
    ('64_VoC_2차_pilot_전체안내.md', '0_전체안내.md'),
    ('_설계서/16_VoC_분석엔진_재현설계서_v13.docx', '공통/' + os.path.basename('_설계서/16_VoC_분석엔진_재현설계서_v13.docx')),
    ('15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx', '공통/' + os.path.basename('15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx')),
    # * 검사기 S-16 이 대조하는 기준. 이것이 빠지면 S-16 이 그냥 넘어간다 (2026-08-19)
    ('_판독패키지/_기준/출력칸목록.txt', '공통/출력칸목록.txt'),
    # ★ 누가 무엇을 하나 — 매번 다시 묻던 것을 한 자리에 (2026-08-24)
    ('98_전체흐름_1차부터_4차까지.md', '0_전체흐름_누가_무엇을.md'),
    # ★ 시트·칸을 묶음별로 풀어 쓴 안내 (sky 2026-08-23)
    ('_배포/VoC_데이터_안내.xlsx', '공통/VoC_데이터_안내.xlsx'),
]

PACKS = {
    '2_2차판독': {
        '설명': '2차 LLM 판독자를 돌리는 데 필요한 전부입니다.',
        '차수': '2차 · 판독자 LLM 둘',
        '가이드': ('60_2차판독_실무자_사용가이드.md', '1_사용가이드.md'),
        '파일': [
            ('_판독패키지/0_붙여넣을_프롬프트_도구형.md', '프롬프트/' + os.path.basename('_판독패키지/0_붙여넣을_프롬프트_도구형.md')),
            # ★ 멈췄을 때 쓸 것이 꾸러미 안에 없었다 (2026-08-23).
            #   프롬프트모음 zip 에만 있어서 실무자가 2차 폴더에서 못 찾는다.
            ('_판독패키지/0_붙여넣을_프롬프트_이어서.md', '프롬프트/' + os.path.basename('_판독패키지/0_붙여넣을_프롬프트_이어서.md')),
            ('_판독패키지/1a_기준문서_정본_1부.md', '판독패키지/' + os.path.basename('_판독패키지/1a_기준문서_정본_1부.md')),
            ('_판독패키지/1b_기준문서_정본_2부.md', '판독패키지/' + os.path.basename('_판독패키지/1b_기준문서_정본_2부.md')),
            ('_판독패키지/2_택소노미.md', '판독패키지/' + os.path.basename('_판독패키지/2_택소노미.md')),
            ('_판독패키지/3_데이터사전_Enum.md', '판독패키지/' + os.path.basename('_판독패키지/3_데이터사전_Enum.md')),
            ('_판독패키지/4_2차_확장부록.md', '판독패키지/' + os.path.basename('_판독패키지/4_2차_확장부록.md')),
            ('_판독패키지/6_판정대상_컬럼분류.md', '판독패키지/' + os.path.basename('_판독패키지/6_판정대상_컬럼분류.md')),
            ('_판독패키지/7_영상메타.csv', '판독패키지/' + os.path.basename('_판독패키지/7_영상메타.csv')),
            ('_판독패키지/8_topic_그룹.md', '판독패키지/' + os.path.basename('_판독패키지/8_topic_그룹.md')),
            ('_판독패키지/9_택소노미_2차확장.md', '판독패키지/' + os.path.basename('_판독패키지/9_택소노미_2차확장.md')),
            ('30_VoC_2차_번들환원_사양_v0.1.md', '판독패키지/' + os.path.basename('30_VoC_2차_번들환원_사양_v0.1.md')),
            ('40_2차판독_수행지시서.md', '공통/' + os.path.basename('40_2차판독_수행지시서.md')),
            ('build_bundle.py', '스크립트/' + os.path.basename('build_bundle.py')),
            ('check_selfcheck.py', '스크립트/' + os.path.basename('check_selfcheck.py')),
            ('check_submission.py', '스크립트/' + os.path.basename('check_submission.py')),
            # ★ check_submission 이 verify_quotes 를 import 한다 — 없으면 죽는다.
            #   그런데 아래 apply_approved 옆에 **이미 들어 있었다** (2026-08-21).
            #   2026-08-26 에 모르고 여기 또 넣어서 zip 안에 같은 이름이
            #   두 번 들어갔다 (Duplicate name 경고). 한 곳에만 둔다.
            ('check_lineage.py', '스크립트/' + os.path.basename('check_lineage.py')),
            ('topic_registry.py', '스크립트/' + os.path.basename('topic_registry.py')),
            ('run_status.py', '스크립트/' + os.path.basename('run_status.py')),

        # ★ `make_judge_input.py` 는 여기 없다 (2026-08-24).
        #   그것은 **A·B 매핑을 만드는 코드**다. 고정 씨앗을 쓰므로
        #   감독자가 돌리면 매핑을 그대로 재현할 수 있다.
        #   정답지 파일을 안 줘도 만드는 코드를 주면 소용이 없다.
        #   `build_master.py` 도 뺐다 — 통합은 총괄이 한다.
        # ★ 감독자가 한 회차만 꺼내 읽는 도구 (2026-08-23)
        ('감독_읽기.py', '스크립트/' + os.path.basename('감독_읽기.py')),
            ('handoff.py', '스크립트/' + os.path.basename('handoff.py')),
            # ★ 엔진 자리를 찾는 일을 한 곳에 모았다 (2026-08-23)
            ('엔진자리.py', '스크립트/' + os.path.basename('엔진자리.py')),
            # ★ 차수를 넘기기 전에 사람 대신 판단한다 (2026-08-23)
            ('넘어가도_되나.py', '스크립트/' + os.path.basename('넘어가도_되나.py')),
            # ★ 3차를 실무자 손 없이 끝내는 도구 셋 (2026-08-23)
            # ★ 3차_마무리 는 여기 없다 (sky 2026-08-24).
            #   「3차 감독은 각자 파일을 만들고 마무리를 직접 해주시는게」
            #   ★ 통합은 총괄이 한다 — 자동 통합은 감독자 결과를
            #     폴더끼리 복사한다. 그것이 폴더를 섞는다.

            ('보정요청_논의본.py', '스크립트/' + os.path.basename('보정요청_논의본.py')),
            ('시트_붙이기.py', '스크립트/' + os.path.basename('시트_붙이기.py')),
            # ★ 번들_색칠하기 · 데이터안내_만들기 는 여기 없다 (sky 2026-08-24).
            #   「2차 판독 3차 감독에서가 아닌 최종 단계에서 메인 AI 가 반영」
            #   꾸밈은 판독자가 할 일이 아니다 — 총괄이 마지막에 한다.

            ('편향검사.py', '스크립트/' + os.path.basename('편향검사.py')),
            # ★ 2026-08-21 — 아래 셋이 빠져 있어서 실무자 컴퓨터에서
            #   run_status.py 와 check_submission.py 가 import 부터 실패했다
            ('apply_approved.py', '스크립트/' + os.path.basename('apply_approved.py')),
            ('verify_quotes.py', '스크립트/' + os.path.basename('verify_quotes.py')),
            ('자가점검.py', '스크립트/' + os.path.basename('자가점검.py')),
            # ★ 2026-08-22 — 판독이 뒤로 갈수록 얕아지는 것을 스스로 잡는다.
            #   check_submission 은 형식만 본다. 성실성은 아무도 안 봤다
            ('성실성검사.py', '스크립트/' + os.path.basename('성실성검사.py')),
            # ★ 2026-08-26 — 조각이 원래 글을 빠짐없이 덮는가 (2차 계약 L-3).
            #   프롬프트가 이것을 돌리라고 하는데 꾸러미에 없었다.
            #   대표 문장만 오려 내면 원문의 절반이 데이터에서 사라진다
            ('조각덮개검사.py', '스크립트/' + os.path.basename('조각덮개검사.py')),
            # ★ 2026-08-26 — 원문이 1차 원본과 글자까지 같은가 (계약 V-0-3 / L-1).
            #   용어를 일괄로 밀다가 실제 댓글 본문을 덮은 일이 있었다.
            #   계보 검사는 판 안에서만 봐서 못 잡는다 — 판 밖까지 거슬러 본다
            ('원문대조검사.py', '스크립트/' + os.path.basename('원문대조검사.py')),
            # ★ 2026-08-22 — 「고쳐도 되는 것」 을 내가 잘못 갈랐어도,
            #   바뀐 사실 자체를 잡는다. 내 판단에 안 기댄다
            ('지문검사.py', '스크립트/' + os.path.basename('지문검사.py')),
            # ★ 2026-08-21 — 데이터가 바뀔 때 엑셀만 받아 갈아 끼우는 도구.
            #   이것이 있으면 꾸러미를 매번 새로 만들지 않아도 된다
            ('데이터_넣기.py', '스크립트/' + os.path.basename('데이터_넣기.py')),
            # ★ 판독 결과가 쌓일 자리. 폴더가 없으면 판독자가 어디에 쓸지 헤맨다
            ('_판독패키지/_결과/0_여기에_결과가_쌓입니다.md',
             '_판독패키지/_결과/0_여기에_결과가_쌓입니다.md'),
            ('s9_group/topic_group_map.json', '대장/' + os.path.basename('s9_group/topic_group_map.json')),
            ('s9_group/secondary_topics.json', '대장/' + os.path.basename('s9_group/secondary_topics.json')),
            ('s9_group/secondary_enums.json', '대장/' + os.path.basename('s9_group/secondary_enums.json')),
            ('s9_group/topic_registry.json', '대장/' + os.path.basename('s9_group/topic_registry.json')),
        ],
    },
    '3_3차감독': {
        '설명': '3차 LLM 감독자(감독자)를 돌리는 데 필요한 전부입니다.',
        '차수': '3차 · 감독자 LLM 둘',
        '가이드': ('61_3차감독_실무자_사용가이드.md', '1_사용가이드.md'),
        '파일': [
            ('_판독패키지/0_붙여넣을_프롬프트_감독.md', '프롬프트/' + os.path.basename('_판독패키지/0_붙여넣을_프롬프트_감독.md')),
            ('_판독패키지/2_택소노미.md', '판독패키지/' + os.path.basename('_판독패키지/2_택소노미.md')),
            ('_판독패키지/8_topic_그룹.md', '판독패키지/' + os.path.basename('_판독패키지/8_topic_그룹.md')),
            ('_판독패키지/9_택소노미_2차확장.md', '판독패키지/' + os.path.basename('_판독패키지/9_택소노미_2차확장.md')),
            ('40_2차판독_수행지시서.md', '공통/' + os.path.basename('40_2차판독_수행지시서.md')),
        # ★ 감독자가 한 회차만 꺼내 읽는 도구 (2026-08-23)
        ('감독_읽기.py', '스크립트/' + os.path.basename('감독_읽기.py')),
            ('build_bundle.py', '스크립트/' + os.path.basename('build_bundle.py')),
            ('check_selfcheck.py', '스크립트/' + os.path.basename('check_selfcheck.py')),
            ('rank_two_axis.py', '스크립트/' + os.path.basename('rank_two_axis.py')),
            ('topic_registry.py', '스크립트/' + os.path.basename('topic_registry.py')),
            ('make_grading_sheet.py', '스크립트/' + os.path.basename('make_grading_sheet.py')),
            ('handoff.py', '스크립트/' + os.path.basename('handoff.py')),
            # ★ 엔진 자리를 찾는 일을 한 곳에 모았다 (2026-08-23)
            ('엔진자리.py', '스크립트/' + os.path.basename('엔진자리.py')),
            # ★ 차수를 넘기기 전에 사람 대신 판단한다 (2026-08-23)
            ('넘어가도_되나.py', '스크립트/' + os.path.basename('넘어가도_되나.py')),
            # ★ 3차를 실무자 손 없이 끝내는 도구 셋 (2026-08-23)
            ('보정요청_논의본.py', '스크립트/' + os.path.basename('보정요청_논의본.py')),
            ('시트_붙이기.py', '스크립트/' + os.path.basename('시트_붙이기.py')),
            ('편향검사.py', '스크립트/' + os.path.basename('편향검사.py')),
            ('자가점검.py', '스크립트/' + os.path.basename('자가점검.py')),
            # ★ 2026-08-22 — 판독이 뒤로 갈수록 얕아지는 것을 스스로 잡는다.
            #   check_submission 은 형식만 본다. 성실성은 아무도 안 봤다
            ('성실성검사.py', '스크립트/' + os.path.basename('성실성검사.py')),
            # ★ 2026-08-26 — 조각이 원래 글을 빠짐없이 덮는가 (2차 계약 L-3).
            #   프롬프트가 이것을 돌리라고 하는데 3차 꾸러미에 없었다
            ('조각덮개검사.py', '스크립트/' + os.path.basename('조각덮개검사.py')),
            # ★ 2026-08-26 — 원문이 1차 원본과 글자까지 같은가 (계약 V-0-3 / L-1).
            #   용어를 일괄로 밀다가 실제 댓글 본문을 덮은 일이 있었다.
            #   계보 검사는 판 안에서만 봐서 못 잡는다 — 판 밖까지 거슬러 본다
            ('원문대조검사.py', '스크립트/' + os.path.basename('원문대조검사.py')),
            # ★ 2026-08-22 — 「고쳐도 되는 것」 을 내가 잘못 갈랐어도,
            #   바뀐 사실 자체를 잡는다. 내 판단에 안 기댄다
            ('지문검사.py', '스크립트/' + os.path.basename('지문검사.py')),
            ('데이터_넣기.py', '스크립트/' + os.path.basename('데이터_넣기.py')),
            ('s9_group/topic_group_map.json', '대장/' + os.path.basename('s9_group/topic_group_map.json')),
            ('s9_group/secondary_topics.json', '대장/' + os.path.basename('s9_group/secondary_topics.json')),
        ],
    },
    '4_최종검토': {
        # ★ 시트 수가 박혀 있었습니다 (2026-08-26).
        #   12 → 15 → 17 로 늘 때마다 이 줄만 옛 숫자로 남았습니다.
        #   실무자가 번들과 함께 **제일 먼저 읽는** 줄입니다. 숫자를 뺍니다 —
        #   몇 개인지는 번들 첫 장 `0_차례` 가 언제나 맞게 보여 줍니다.
        '설명': '사람이 볼 최소한을 확인하고, 번들을 읽는 법입니다. '
                '번들 첫 장 0_차례 에 어느 시트를 왜 보는지 적혀 있습니다.',
        '차수': '4차 · 사람',
        '가이드': ('62_4차검토_및_번들해설.md', '1_사용가이드_및_번들해설.md'),
        '파일': [
            # ★ 4차는 데이터를 안 담는다 (sky 2026-08-23).
            #   「매번 분석 파일 바뀔때마다 VoC_4 zip을 바꿔야되는지?」
            #   바꿔야 했고 그게 잘못이었다 — 9MB 짜리 결과가 들어 있어
            #   안 바꾸면 옛 결과로 회의한다 (실제로 08-19 판이 들어 있었다).
            #   결과는 3차가 만든 `_최종결과/` 를 실무자가 옆에 놓는다.
            ('_판독패키지/4차_결과를_어디서_받나.md', '0_결과를_어디서_받나.md'),
            ('make_grading_sheet.py', '스크립트/' + os.path.basename('make_grading_sheet.py')),
            ('apply_sky.py', '스크립트/' + os.path.basename('apply_sky.py')),
            # ★ 2026-08-21 — build_master 와 check_selfcheck 가 이것을 부르는데
            #   꾸러미에 없어서 import 부터 실패했다
            ('build_bundle.py', '스크립트/' + os.path.basename('build_bundle.py')),
            ('자가점검.py', '스크립트/' + os.path.basename('자가점검.py')),
            # ★ 2026-08-22 — 판독이 뒤로 갈수록 얕아지는 것을 스스로 잡는다.
            #   check_submission 은 형식만 본다. 성실성은 아무도 안 봤다
            ('성실성검사.py', '스크립트/' + os.path.basename('성실성검사.py')),
            # ★ 2026-08-22 — 「고쳐도 되는 것」 을 내가 잘못 갈랐어도,
            #   바뀐 사실 자체를 잡는다. 내 판단에 안 기댄다
            ('지문검사.py', '스크립트/' + os.path.basename('지문검사.py')),
            ('check_selfcheck.py', '스크립트/' + os.path.basename('check_selfcheck.py')),
            ('handoff.py', '스크립트/' + os.path.basename('handoff.py')),
            # ★ 엔진 자리를 찾는 일을 한 곳에 모았다 (2026-08-23)
            ('엔진자리.py', '스크립트/' + os.path.basename('엔진자리.py')),
            # ★ 차수를 넘기기 전에 사람 대신 판단한다 (2026-08-23)
            ('넘어가도_되나.py', '스크립트/' + os.path.basename('넘어가도_되나.py')),
            # ★ 3차를 실무자 손 없이 끝내는 도구 셋 (2026-08-23)
            ('보정요청_논의본.py', '스크립트/' + os.path.basename('보정요청_논의본.py')),
            ('시트_붙이기.py', '스크립트/' + os.path.basename('시트_붙이기.py')),
            ('편향검사.py', '스크립트/' + os.path.basename('편향검사.py')),
            ('채점지_2차30행.csv', '예시/' + os.path.basename('채점지_2차30행.csv')),
        ],
    },
    '5_대시보드': {
        '설명': '대시보드 화면에서 개선 과제를 찾는 법입니다.',
        '차수': '대시보드',
        '가이드': ('63_대시보드_사용설명서.md', '1_사용설명서.md'),
        '파일': [
            (M + '/개선우선순위_두축.csv', '참고/' + os.path.basename(M + '/개선우선순위_두축.csv')),
            ('62_4차검토_및_번들해설.md', '참고/' + os.path.basename('62_4차검토_및_번들해설.md')),
            ('28_대시보드_반영대기_목록.md', '참고/' + os.path.basename('28_대시보드_반영대기_목록.md')),
            # ★ 설명서가 「회사 밖에 내지 마십시오, 자세한 기준은
            #   이것을 보십시오」 라고 가리키는 문서다. 없었다 (2026-08-24)
            ('65_개인정보_처리_기준_및_제출문안.md',
             '참고/65_개인정보_처리_기준_및_제출문안.md'),
        ],
    },
}


def 판독대상_파일들():
    """범용 꾸러미에 넣을 「판독대상」 — ★ 데이터를 담지 않는다.

    ★ sky 2026-08-22
      「zip 범용인데 그렇게 1570행에 맞춰 돌게 해놓으면 어떻게하나요?
        같이 첨부하는 분석데이터로 돌게 해놔야지」

      pilot 데이터를 넣어 두면, 실무자가 자기 엑셀을 같이 줘도 AI 가
      자가점검에서 「1,570행 준비됐습니다」 를 보고 그냥 pilot 을 판독한다.
      31시간이 통째로 헛돈다. 가장 나쁜 종류의 오류다.

      비워서 내면 자가점검이 「판독할 데이터를 못 찾았습니다」 로 막고,
      프롬프트 0단계가 「엑셀을 달라고 해서 앉혀라」 로 이어진다.

    ★ 데이터를 넣어 통째로 건네려면 `판독꾸러미_만들기.py` 를 쓴다.
      로니 꾸러미가 그렇게 나온 것이다.
    """
    return [('_판독패키지/_판독대상_안내.md', '판독대상/0_이_폴더는.md')]


def 프롬프트_묶음():
    """프롬프트만 따로 모은 묶음 — 단계 순서가 이름에 보이게 담는다.

    ★ sky 2026-08-21
      「프롬프트 파일만 보려고 zip 을 풀었다가 다시 복사해서 붙여넣기는 불편하니까」
      그래서 프롬프트만 따로 낸다. 흐름 문서와 구조도를 같이 넣어
      「어느 것을 언제 쓰는지」 가 이 묶음만 봐도 서게 한다.
    """
    out = []

    # 늘 쓰는 것 — 단계 번호를 앞에 붙여 차례가 보이게 한다
    #   ★ sky 2026-08-23 — 「클로드코드는 1개, 코덱스는 2개가 나와야 한다」
    #     코덱스는 10회차쯤에서 스스로 멈춘다(원문이 쌓이면 막히기 때문).
    #     그때 무엇을 붙여넣는지 **이름만 보고 알게** 한다.
    늘 = [
        ('_판독패키지/0_붙여넣을_프롬프트_도구형.md',
         '2차_① 처음에_붙여넣기 (클로드코드·코덱스 공통).md'),
        ('_판독패키지/0_붙여넣을_프롬프트_이어서.md',
         '2차_② 코덱스가_멈추면_붙여넣기 (몇 번이고).md'),
        ('_판독패키지/0_붙여넣을_프롬프트_감독.md',
         '3차_감독자에게_붙여넣기.md'),
    ]
    for s, d in 늘:
        out.append((s, d))

    # 먼저 읽을 것
    out.append(('_판독패키지/0_전체흐름_어느_프롬프트를_언제.md',
                '0_먼저_읽으십시오_전체흐름.md'))
    for 그림 in ('_배포/AI_서비스_구조도.jpg', '_배포/AI_서비스_구조도.png'):
        if os.path.exists(그림):
            out.append((그림, '0_AI_서비스_구조도' + os.path.splitext(그림)[1]))
            break

    # 평소 안 쓰는 것 — 아래로 내린다
    보조 = sorted(glob.glob('_판독패키지/0_붙여넣을_*.md'))
    이미 = {s for s, _ in 늘}
    for p in 보조:
        p = p.replace(os.sep, '/')
        if p in 이미:
            continue
        out.append((p, '그밖에_평소엔_안_씁니다/' + os.path.basename(p)))

    return out


def 꾸러미_지문(담긴것):
    """담은 파일 중 「건드리면 안 되는 것」 의 지문을 뜬다.

    ★ 쓰는 중인 zip 에서는 읽을 수 없다 (BadZipFile).
      담은 (원본, 자리) 짝을 받아 원본에서 뜬다.

    ★ 지문검사.py 와 같은 자리·같은 방식이어야 한다.
      줄바꿈(CRLF/LF)은 하나로 맞춰 센다 — 판마다 달라 흔들린 적이 있다.
    """
    import hashlib as _h
    import json as _j
    import datetime as _d

    # ★ 지문검사.py 와 같아야 한다 — 「누구도 바꿀 이유가 없는 것」 만
    #   판독대상·회차배치·대장은 판독 흐름이 정당하게 바꾼다. 빼야 한다
    볼곳 = ('스크립트/', '판독패키지/', '공통/', '프롬프트/')
    지문 = {}
    for 원본, 자리 in 담긴것:
        n = 자리.replace(os.sep, '/')
        if not n.startswith(볼곳):
            continue
        if '__pycache__' in n or n.endswith('지문.json'):
            continue
        if n.startswith('스크립트/') and not n.endswith('.py'):
            continue
        try:
            재료 = open(원본, 'rb').read()
        except OSError:
            continue
        try:
            재료 = 재료.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        except UnicodeDecodeError:
            pass
        지문[n] = _h.sha256(재료).hexdigest()[:16]
    return _j.dumps({'뜬날': _d.datetime.now().strftime('%Y-%m-%d %H:%M'),
                     '파일수': len(지문), '지문': 지문},
                    ensure_ascii=False, indent=1)


def add(z, src, dst, missing):
    if os.path.exists(src):
        z.write(src, dst)
        return 1
    missing.append(src)
    return 0


def readme(name, spec, files):
    L = ['# %s\n' % spec['차수'], spec['설명'], '',
         '기준 2026-08-19 · VoC 2차 판독 pilot 1차 완료본\n', '---\n',
         # ★ 첫 벽은 「AI 에게 이 폴더를 어떻게 열어 주나」 다 (sky 2026-08-22)
         '## ★ 시작하는 법 — 세 줄\n', '```',
         '1. 이 폴더 빈 곳에서 마우스 오른쪽 → 「터미널에서 열기」',
         '   (안 보이면 「추가 옵션 표시」 를 먼저)',
         '2. 까만 창에   claude   또는   codex   를 치고 Enter',
         '3. 프롬프트/ 안의 글을 통째로 붙여넣기',
         '',
         '★ 그다음은 AI 가 알아서 합니다. 명령어를 치실 일이 없습니다',
         '```\n',
         '## 먼저 여십시오\n', '```', '가이드/%s' % os.path.basename(spec['가이드'][0]),
         '   ★ 여기에 무엇을 어떤 순서로 하는지 다 적혀 있습니다', '```\n',
         '## 이 꾸러미에 든 것\n', '```']
    for f in sorted(files):
        L.append('  %s' % f)
    L += ['```\n', '## 정본이 무엇인지\n', '```',
          '공통/재현설계서_v13.docx        ★ 문서끼리 어긋나면 이것이 이깁니다',
          '공통/데이터사전_v3.2_90컬럼.xlsx  칸 90개의 정의',
          '0_전체안내.md                   프로젝트 전체 지도', '```\n',
          '## 규칙이 없거나 이상하면\n', '```',
          '★ 그 자리에서 고치지 마십시오.',
          '  판독자는 「무엇이 없었는지」 를 적어서 넘기고,',
          '  실무자는 보정요청서를 시스템 담당자에게 전달합니다.',
          '  수정은 총괄이 다음 판에 반영합니다', '```']
    return '\n'.join(L)


def check_zip(zp, spec):
    """온전한지 점검 — 안내문이 가리키는 파일이 안에 있는가"""
    z = zipfile.ZipFile(zp)
    names = set(z.namelist())
    base = {os.path.basename(n) for n in names}
    bad = []
    # 가이드 문서가 가리키는 파일명
    # ★ 그 꾸러미의 「주 가이드」 하나만 본다.
    #   가이드 4종을 다 넣었으므로 남의 차수 파일까지 보면 헛경보가 난다
    main_guide = os.path.basename(spec['가이드'][0])
    guide = [n for n in names if os.path.basename(n) == main_guide]
    for g in guide:
        t = z.read(g).decode('utf-8', 'replace')
        for m in re.finditer(r'([\w가-힣_\-\.]+\.(?:md|xlsx|csv|py|docx|json))', t):
            n = m.group(1)
            if any(c in n for c in '<>*') or 'NNN' in n:
                continue
            # ★ 명령줄에 나오는 실행 파일은 꾸러미에 넣을 것이 아니다
            # ★ engine.py 는 「어느 폴더에서 띄우나」 를 견주는 대목에 나온다
            #   (codex_live_merge 4,500줄 · codex 1,934줄).
            #   꾸러미에 넣을 것이 아니다 — 오탐이었다 (2026-08-24)
            if n in ('streamlit_app.py', 'app_admin.py', 'python.exe',
                     'engine.py'):
                continue
            # ★ 총괄 자리에서만 도는 도구 — 꾸러미에 없는 것이 맞다
            #   (sky 2026-08-24 「3차 감독은 각자 파일을 만들고 마무리를 직접」)
            #   가이드가 「총괄이 하는 것」 이라며 이름을 대는데, 그것을
            #   「빠졌다」 로 세면 경고가 늘 떠서 아무도 안 본다.
            if n in ('3차_마무리.py', '번들_마무리꾸미기.py', '3차_준비.py',
                     # ★ 2026-08-26 — 축1 ③ 총괄 검수와 차례 만들기
                     '총괄검수.py', '차례_만들기.py',
                     'make_judge_input.py', '번들_색칠하기.py',
                     '데이터안내_만들기.py', 'rank_two_axis.py',
                     'build_master.py'):
                continue
            # ★ 돌리는 중에 생기는 산출물은 꾸러미에 넣을 것이 아니다
            if n in RUNTIME:
                continue
            if n not in base:
                bad.append('%s 가 가리키는 %s 가 없다' % (os.path.basename(g), n))
    # 스크립트가 import 하는 것
    for n in names:
        if n.endswith('.py'):
            t = z.read(n).decode('utf-8', 'replace')
            for m in re.finditer(r'^from (\w+) import|^import (\w+)$', t, re.M):
                mod = (m.group(1) or m.group(2)) + '.py'
                if mod in ('check_selfcheck.py', 'build_bundle.py') and mod not in base:
                    bad.append('%s 가 import 하는 %s 가 없다' % (os.path.basename(n), mod))
    z.close()
    return sorted(set(bad))


def 오차기준_검사():
    """감독자가 통합/입력생성을 하라고 적힌 곳이 남았는지 본다.

    ★ 5차 동결 기준 (sky 2026-08-24) — 감독자는 판정까지만.
      정하고 문서를 손으로 고쳤더니 여섯 자리가 빠져 있었다.
      그래서 꾸러미를 만드는 자리에서 매번 본다.
      ★ 막지는 않는다. 막으면 우회하게 되고, 그러면 검사가 죽는다.
    """
    도구 = os.path.join(BASE, '5차기준_검사.py')
    if not os.path.exists(도구):
        return
    r = subprocess.run([sys.executable, 도구, '--조용'],
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print('★ 5차 기준을 어긴 곳이 있습니다 — 꾸러미는 만들지만 보십시오')
        for 줄 in (r.stdout or '').splitlines()[:14]:
            print('  ' + 줄)
        print()


def main():
    os.chdir(BASE)
    오차기준_검사()
    out = os.path.join(BASE, '_배포')
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.zip')):
        os.remove(f)
    print('배포 꾸러미 → %s' % out)
    print()

    made = {}
    for name, spec in PACKS.items():
        zp = os.path.join(out, 'VoC_%s.zip' % name)
        z = zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED)
        miss, files = [], []
        pack = list(spec['파일']) + list(COMMON)
        # ★ 1차 엔진 사본을 싣는다 (2026-08-23).
        #   없으면 남의 PC 에서 최종 xlsx 가 No module named 'src' 로 안 나온다.
        #   실무자가 받아야 할 물건이 바로 그 xlsx 다. 새 PC 흉내로 확인했다.
        #   ★ 고치지 않는다 — 읽기용으로 실어만 나른다. 지문검사가 지킨다.
        if any(k in name for k in ('2차', '3차', '4차', '전체')):
            for _e in sorted(glob.glob('engine/**/*', recursive=True)):
                # ★ 컴파일 찌꺼기는 담지 않는다 (2026-08-25).
                #   엔진을 한 번 import 하면 .pyc 가 생기고, 다음
                #   꾸러미에 그대로 실린다. 파이썬 판이 다르면 못 읽는다.
                if '__pycache__' in _e or _e.endswith(('.pyc', '.pyo')):
                    continue
                if os.path.isfile(_e):
                    _r = _e.replace(os.sep, '/')
                    pack.append((_r, _r))
        pack += [(s, d + os.path.basename(s)) for s, d in GUIDES]
        담긴것 = []
        for src, dst in pack:
            if add(z, src, dst, miss):
                files.append(dst)
                담긴것.append((src, dst))
        # ★ 판독할 데이터와 회차 배치를 함께 넣는다 (sky 2026-08-21).
        #   「zip 이랑 데이터랑 프롬프트만 주면 바로 작업 들어가게」
        #   이것이 없으면 실무자는 데이터를 스스로 만들어야 한다 — 못 한다.
        if name in ('2_2차판독', '3_3차감독'):
            for src, dst in 판독대상_파일들():
                if add(z, src, dst, miss):
                    files.append(dst)
                    담긴것.append((src, dst))
        # ★ 건드리면 안 되는 파일의 지문을 떠서 함께 넣는다 (2026-08-22).
        #   판독이 끝날 때 다시 떠서 견주면, 도구나 기준을 고쳤는지 드러난다.
        #   내가 「고쳐도 된다」 고 잘못 말했어도 이건 사실로 잡는다
        if name in ('2_2차판독', '3_3차감독', '4_최종검토'):
            z.writestr('대장/지문.json', 꾸러미_지문(담긴것).encode('utf-8'))
            files.append('대장/지문.json')
        _안내 = readme(name, spec, files).encode('utf-8')
        z.writestr('0_먼저_읽으십시오.md', _안내)
        # ★ 같은 글을 디스크에도 남긴다 (2026-09-07).
        #   이 안내문은 담긴 파일 목록을 보고 **그때그때 만드는 글**이라
        #   디스크에 원본이 없었다. 그래서 refresh_release_packages 가
        #   「같은 내용의 원본이 없다」 며 못 가렸고,
        #   꾸러미에 무엇을 하나 더 넣을 때마다 시험이 빨간불이 됐다.
        #   원본을 남겨 두면 검사가 스스로 맞출 수 있다.
        #   ★ 사람에게도 쓸모가 있다 — 풀지 않고 안내문만 읽을 수 있다.
        #   ★ `_배포` 안에 두면 안 된다. 거기는 「담은 결과」 라
        #     검사기가 일부러 색인에서 뺀다 (SKIP_PARTS). 밖에 둔다.
        _안내자리 = os.path.join(BASE, '_꾸러미안내문',
                              os.path.basename(zp)[:-4])
        os.makedirs(_안내자리, exist_ok=True)
        with open(os.path.join(_안내자리, '0_먼저_읽으십시오.md'), 'wb') as _h:
            _h.write(_안내)
        z.close()
        made[name] = zp
        bad = check_zip(zp, spec)
        mark = ''
        if miss:
            mark += '  ✗ 빠짐 %d' % len(miss)
        if bad:
            mark += '  ! 참조 %d' % len(bad)
        print('  %-24s %2d개 · %6.2f MB%s'
              % (os.path.basename(zp), len(files) + 1,
                 os.path.getsize(zp) / 1048576, mark or '  OK'))
        for x in miss:
            print('       ✗ 없는 파일 %s' % x)
        for x in bad[:4]:
            print('       ! %s' % x)

    # ── 1번 · 전체 통합 ────────────────────────────────────────
    zp = os.path.join(out, 'VoC_1_전체통합.zip')
    z = zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED)
    n = 0
    for name, p in made.items():                    # 2~5번 꾸러미를 통째로
        z.write(p, '꾸러미/%s' % os.path.basename(p))
        n += 1
    EXTRA = [
        ('64_VoC_2차_pilot_전체안내.md', '0_전체안내.md'),
        ('_설계서/16_VoC_분석엔진_재현설계서_v13.docx', '정본/' + os.path.basename('_설계서/16_VoC_분석엔진_재현설계서_v13.docx')),
        ('15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx', '정본/' + os.path.basename('15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx')),
        # * 검사기 S-16 의 기준. 1번 꾸러미는 EXTRA 를 쓰므로 여기에도 넣어야 한다
        ('_판독패키지/_기준/출력칸목록.txt', '공통/출력칸목록.txt'),
    # ★ 누가 무엇을 하나 — 매번 다시 묻던 것을 한 자리에 (2026-08-24)
    ('98_전체흐름_1차부터_4차까지.md', '0_전체흐름_누가_무엇을.md'),
    # ★ 시트·칸을 묶음별로 풀어 쓴 안내 (sky 2026-08-23)
    ('_배포/VoC_데이터_안내.xlsx', '공통/VoC_데이터_안내.xlsx'),
        ('40_2차판독_수행지시서.md', '정본/' + os.path.basename('40_2차판독_수행지시서.md')),
        ('21a_기준문서_정본_1부.md', '정본/' + os.path.basename('21a_기준문서_정본_1부.md')),
        ('21b_기준문서_정본_2부.md', '정본/' + os.path.basename('21b_기준문서_정본_2부.md')),
        ('11_VoC_Topic_택소노미_재설계_v0.10.md', '정본/' + os.path.basename('11_VoC_Topic_택소노미_재설계_v0.10.md')),
        ('22_VoC_2차_판독_확장부록.md', '정본/' + os.path.basename('22_VoC_2차_판독_확장부록.md')),
        ('30_VoC_2차_번들환원_사양_v0.1.md', '정본/' + os.path.basename('30_VoC_2차_번들환원_사양_v0.1.md')),
        (M + '/voc_dashboard_export_bundle_2차시험본.xlsx', '결과/' + os.path.basename(M + '/voc_dashboard_export_bundle_2차시험본.xlsx')),
        (M + '/raw_voc.csv', '결과/' + os.path.basename(M + '/raw_voc.csv')),
        (M + '/개선우선순위_두축.csv', '결과/' + os.path.basename(M + '/개선우선순위_두축.csv')),
        (S15 + '/지표.json', '결과/지표.json'),
        ('50_사내AI콘테스트_응모안.md', '콘테스트/' + os.path.basename('50_사내AI콘테스트_응모안.md')),
        ('51_콘테스트_PPT소재.md', '콘테스트/' + os.path.basename('51_콘테스트_PPT소재.md')),
        ('44_VoC_프로젝트_인수인계_SUMMARY_v1.0.md', '히스토리/' + os.path.basename('44_VoC_프로젝트_인수인계_SUMMARY_v1.0.md')),
        ('90_변경원장_LEDGER.md', '히스토리/' + os.path.basename('90_변경원장_LEDGER.md')),
        ('_설계서/v12_원본.docx', '히스토리/' + os.path.basename('_설계서/v12_원본.docx')),
        ('15_VoC_데이터사전_스키마_v3.1_87컬럼.xlsx', '히스토리/' + os.path.basename('15_VoC_데이터사전_스키마_v3.1_87컬럼.xlsx')),
    ]
    miss = []
    for src, dst in EXTRA:
        n += add(z, src, dst, miss)
    for f in sorted(glob.glob('_인계/*차_인계서.md')):
        z.write(f, '인계/%s' % os.path.basename(f))
        n += 1
    for f in sorted(glob.glob('*.py')):
        if os.path.basename(f) in (
                'build_bundle.py', 'build_master.py', 'check_selfcheck.py',
                # ★ check_submission 이 verify_quotes 를 import 한다 (2026-08-26).
                #   없으면 전체통합 꾸러미에서 ModuleNotFoundError 로 죽는다
                'check_submission.py', 'verify_quotes.py',
                'check_lineage.py', 'topic_registry.py',
                # ★ 계보 검사는 판 안에서만 본다 — 판 밖(1차 원본)까지
                #   거슬러 견주는 것은 이것이다 (2026-08-26)
                '원문대조검사.py',
                # ★ 2026-08-26 — 파생 칸·라벨 이름이 따로 노는 것을 막는 셋.
                #   셋 다 이번 판에서 실제로 어긋난 자리다
                '그룹_맞추기.py', '사람이볼목록_채우기.py', '폐기라벨_정리.py',
                # ★ 2026-09-07 — 「행을 만든 주체별로 빈칸률이 갈리는가」 를 본다.
                #   조각 570행이 통째로 비었던 것을 기존 검사 12종이 다 지나갔다
                '아무도_안채우는칸_검사.py',
                # ★ 2026-09-07 — 문서가 문서마다 딴소리를 하는 것을 잡는다.
                #   E-1 을 뒤집었을 때 여섯 문서가 옛말을 하고 있었다
                '문서_한말_검사.py',
                # ★ 2026-09-08 — 지금 데이터를 **이 도구가 만들었다.**
                #   「이 값이 어떻게 여기 왔나」 를 물으면 이것을 봐야 한다.
                #   전체통합은 「전체」 여야 한다
                '7차_정리.py',
                'make_judge_input.py', 'make_grading_sheet.py', 'rank_two_axis.py',
                'handoff.py', 'apply_sky.py', 'run_status.py',
                # ★ run_status 가 legitimate_na 를 여기서 가져온다 (2026-08-26).
                #   try/except 로 막혀 있어 죽지는 않지만, 없으면 그 자리가
                #   조용히 빈 함수로 바뀐다 — 전체통합은 「전체」 여야 한다
                #   apply_approved 는 다시 엔진자리 를 부른다 — 사슬이다
                'apply_approved.py', '엔진자리.py',
                'make_zip.py'):
            z.write(f, '스크립트/%s' % os.path.basename(f))
            n += 1
    for f in sorted(glob.glob('_판독패키지/0_붙여넣을_*.md')):
        z.write(f, '프롬프트/%s' % os.path.basename(f))
        n += 1
    z.close()
    print('  %-24s %2d개 · %6.2f MB%s'
          % (os.path.basename(zp), n, os.path.getsize(zp) / 1048576,
             ('  ✗ 빠짐 %d' % len(miss)) if miss else '  OK'))
    for x in miss:
        print('       ✗ 없는 파일 %s' % x)

    # ── 프롬프트만 따로 (sky 2026-08-21) ──────────────────────────
    zp = os.path.join(out, 'VoC_0_프롬프트모음.zip')
    z = zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED)
    miss, n = [], 0
    for src, dst in 프롬프트_묶음():
        n += add(z, src, dst, miss)
    z.close()
    print('  %-24s %2d개 · %6.2f MB%s'
          % (os.path.basename(zp), n, os.path.getsize(zp) / 1048576,
             ('  ✗ 빠짐 %d' % len(miss)) if miss else '  OK'))
    for x in miss:
        print('       ✗ 없는 파일 %s' % x)

    묶은뒤_검사(out)


def 묶은뒤_검사(out):
    """★ 꾸러미 안에서 import 가 다 풀리는가 (2026-08-26).

    왜 만들었나 — 세 번 같은 일을 겪었습니다.
      · verify_quotes.py 가 없어 check_submission 이 실무자 컴퓨터에서
        import 부터 죽었다 (2026-08-21)
      · 그것을 고치면서 같은 줄을 두 곳에 넣어 zip 안에 같은 이름이
        두 번 들어갔다 (2026-08-26)
      · apply_approved → 엔진자리 로 이어지는 사슬이 끊겨 있었다 (2026-08-26)

    ★ 셋 다 **묶을 때는 OK 로 찍혔습니다.** 받는 사람 컴퓨터에서만 드러납니다.
      그래서 검사를 묶는 자리에 붙였습니다 — 돌리면 반드시 지나갑니다.
    """
    import ast
    있는파이 = {os.path.splitext(os.path.basename(f))[0]
                for f in glob.glob('*.py')}
    탈 = 0
    for zp in sorted(glob.glob(os.path.join(out, '*.zip'))):
        z = zipfile.ZipFile(zp)
        이름들 = z.namelist()
        속 = {os.path.splitext(os.path.basename(x))[0]
              for x in 이름들 if x.endswith('.py')}
        말썽 = []
        겹 = {x for x in 이름들 if 이름들.count(x) > 1}
        for x in sorted(겹):
            말썽.append('%s 가 두 번 들어 있다' % x)
        for nm in 이름들:
            if not nm.endswith('.py'):
                continue
            try:
                t = ast.parse(z.read(nm).decode('utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                말썽.append('%s 를 못 읽는다' % os.path.basename(nm))
                continue
            for node in ast.walk(t):
                딸린것 = []
                if isinstance(node, ast.Import):
                    딸린것 = [a.name.split('.')[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module \
                        and not node.level:
                    딸린것 = [node.module.split('.')[0]]
                for m in 딸린것:
                    if m in 있는파이 and m not in 속:
                        말썽.append('%s 가 %s.py 를 부르는데 꾸러미에 없다'
                                    % (os.path.basename(nm), m))
        z.close()
        for x in sorted(set(말썽)):
            print('       ✗ %s — %s' % (os.path.basename(zp), x))
            탈 += 1
    if 탈:
        print('  ★ 꾸러미 %d곳이 받는 사람 컴퓨터에서 깨집니다 — 위를 고치십시오'
              % 탈)
    else:
        print('  · 꾸러미 안에서 import 가 다 풀립니다 · 겹친 파일 없습니다')
    return 탈


if __name__ == '__main__':
    main()
