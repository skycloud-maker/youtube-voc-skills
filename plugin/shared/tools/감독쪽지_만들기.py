# -*- coding: utf-8 -*-
"""감독자 둘에게 줄 「붙여넣을 쪽지」 를 만든다.

★ 왜
  sky 「주신 프롬프트에 안적혀서 그대로 보내도 된다해서 보내니 안되고
        제가 따로 파일 그 폴더에있다고 말하니가 시작했다고?」

  ★ 폴더를 안 적으면 막힌다. 특히 Codex 는 앱에서 폴더를 못 고른다.
    쪽지 첫 줄에 폴더를 박아 둔다.

  sky 2026-08-23 — 클로드코드는 감독자 2, 코덱스는 감독자 1
"""
import io
import os

# ★ 박힌 경로를 없앴다 (2026-08-25).
#   sky 컴퓨터의 Downloads 가 코드에 박혀 있어 다른 컴퓨터에서는 안 돌았다.
#   3차_준비가 만든 `_감독폴더` 를 본다.
_여기 = os.path.dirname(os.path.abspath(__file__))
_뿌리 = (os.path.dirname(_여기)
        if os.path.basename(_여기) in ('스크립트', 'scripts')
        else _여기)
_감독폴더 = os.path.join(_뿌리, '_감독폴더')

배정 = [
    ("3차 감독1", "Codex"),
    ("3차 감독2", "Claude Code"),
]

틀 = """# {판독자} 에게 붙여넣을 쪽지 — {폴더}

> 아래 회색 칸을 **그대로** 복사해 {판독자} 에 붙여넣으십시오.
> 고칠 것 없습니다.

```
작업 폴더는 여기입니다.

    {길}

거기 있는 `프롬프트\\0_붙여넣을_프롬프트_감독.md` 를 열어 읽고,
그 안에 적힌 대로 3차 감독을 시작하십시오.

★ 먼저 이것부터 한 번 돌립니다.

    python 스크립트\\자가점검.py

★ 감독할 것은 `s13_judge\\judge_input.csv` 입니다 ({행}행 · {회}회차).
  두 판독자가 같은 댓글에 다른 답을 낸 행입니다.

★ A 와 B 가 누구인지는 이 폴더에 없습니다. 총괄이 갖고 있습니다.
  찾으려 하지 마십시오 — 알면 편들게 됩니다.

★ 원문을 화면에 찍지 마십시오. 읽고 판정만 합니다.
★ 10회차쯤 하면 스스로 멈추고 「judge_NN 까지 했습니다」 라고만 알립니다.
```

## 멈췄을 때 (10회차마다)

새 창을 열고 위 칸을 **다시 그대로** 붙여넣으십시오.
어디까지 했는지는 판독자가 `_결과\\` 를 세어서 스스로 압니다.
"""

for 폴더, 판독자 in 배정:
    길 = os.path.join(_감독폴더, 폴더)
    if not os.path.isdir(길):
        print("  ★ 없습니다 — %s" % 길)
        continue
    입력 = os.path.join(길, "s13_judge", "judge_input.csv")
    행 = sum(1 for _ in io.open(입력, encoding="utf-8-sig")) - 1
    회 = len([x for x in os.listdir(os.path.join(길, "s13_judge"))
             if x.startswith("judge_") and x.endswith("_ids.txt")])
    글 = 틀.format(판독자=판독자, 폴더=폴더, 길=길, 행="{:,}".format(행), 회=회)
    낼곳 = os.path.join(길, "0_여기에_붙여넣으십시오.md")
    io.open(낼곳, "w", encoding="utf-8").write(글)
    print("  %-12s → %s  (%s행 · %d회차)" % (판독자, 폴더, "{:,}".format(행), 회))
