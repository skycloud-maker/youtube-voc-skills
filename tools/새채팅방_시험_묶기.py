# -*- coding: utf-8 -*-
"""새 채팅방에서 스킬이 저절로 잡히는지 **시험할 꾸러미 하나**를 만든다 (2026-10-29).

★ 왜 — sky 「새채팅방 테스트를 위한 파일 zip 을 별도로 하나 만들어놓으시고요」.
  지금까지는 제가 **파일 경로를 직접 가리켜** 돌렸다. 스킬로 옮긴 뜻은 그게 아니다 —
  새 채팅방에서 사람이 한마디 하면 AI 가 **스스로 스킬을 집어야** 한다. 그것을 시험한다.

★ 무엇이 드는가 — 세 개뿐이다.
  `0_새채팅방에서_이렇게_하십시오.md`  순서 (이 파일이 정본이다 — 손으로 두 벌 적지 않는다)
  `시험기록표.md`                      본 것을 적는 빈 표. **적지 않으면 「해 봤다」 가 아니다**
  `Ver2_한줄흐름.zip`                  꾸러미 자체 (`tools/판_묶기.py` 가 만든 것을 **바이트 그대로**)

★ 꾸러미를 다시 묶지 않는다 — `dist/판/Ver2_한줄흐름.zip` 을 베낀다. 없으면 **멈춘다**
  (「못 찾음」 은 통과가 아니다). 베낀 뒤 지문을 대어 같은지 확인하고 적는다.

쓰기
    python tools/새채팅방_시험_묶기.py              dist/ 에 만든다
    python tools/새채팅방_시험_묶기.py <자리>       다른 자리에
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
바탕zip = REPO / "dist" / "판" / "Ver2_한줄흐름.zip"
이름 = "새채팅방_시험"

_순서 = """# 새 채팅방 시험 — 이대로만 하십시오

> 이 꾸러미는 `tools/새채팅방_시험_묶기.py` 가 만듭니다. 손으로 고치지 마십시오.

## 왜 하나

스킬을 **플러그인으로 등록**했습니다. 지금까지는 파일 경로를 직접 가리켜 돌렸습니다.
이 시험은 **새 채팅방에서 한마디 했을 때 AI 가 스스로 스킬을 집는가**를 봅니다.
그게 되면 「업무를 스킬로 넘겼다」 가 비로소 참이 됩니다.

★ **돈은 안 씁니다.** 아래 ④ 까지만 하면 AI 는 묻기만 하고 아무것도 돌리지 않습니다.
  ⑤ 는 `--확인만` 이라 역시 공짜입니다. 승인은 하지 마십시오.

---

## ㉮ 이 컴퓨터에서 (플러그인이 **이미 등록돼 있습니다**)

① **Claude Code 를 닫고 다시 엽니다.** 등록은 다시 열 때 읽힙니다 — 이 한 걸음이 빠지면
   새 방에서도 스킬이 안 보입니다.

② 판이 맞는지 봅니다. 터미널에서:

```
claude plugin list
```

   `youtube-voc@youtube-voc-skills` 가 **@판@ · enabled** 로 보여야 합니다.
   그보다 낮은 판으로 보이면 `claude plugin update youtube-voc` 를 치고
   **다시 닫았다 엽니다.**

③ **새 채팅방**을 엽니다 (지금 방이 아니라 새 방이어야 합니다).

④ 이렇게 한마디만 칩니다 — **파일 경로를 주지 마십시오.** 그걸 주면 시험이 아닙니다.

```
유튜브 댓글 VoC 분석 해 주세요
```

   ★ **기대하는 것** — AI 가 `coordinating-voc-pipeline` 스킬을 집고,
     **실행조건 열 칸**(검색어 · 키워드들 · 결합 OR/AND · 게시일 시작/종료 · 국가 · 언어 ·
     영상 수 · 영상당 댓글 수 · 대댓글 포함)을 **묻습니다.** 묻지 않고 바로 돌리면 틀린 것입니다.

   ★ **스킬이 안 잡히면** — 「어떤 스킬을 쓸 수 있나요?」 라고 물어 보십시오.
     여섯이 보이는지 봅니다 (1차 · 2차 판독 · 3차 감독 · 총괄 · 보고서 · 대시보드).
     안 보이면 ① 을 안 한 것입니다.

⑤ 조건을 작게 주고 **확인만** 시킵니다 (여기까지 공짜입니다).

```
검색어는 LG 로봇청소기, 영상 1개, 댓글 20개로 확인만 해 주세요
```

   ★ **기대하는 것** — 「갖춤새 — 다 됐습니다 (꾸러미 · 명령 · 키)」 와 어림(모을 댓글 수 ·
     걸리는 시간 · 대략 비용 · 유튜브 할당량)을 말하고 **멈춥니다.**
     ★ 키 **값**을 보여 주면 **그 자리에서 멈추고 알려 주십시오** — 있다/없다만 말해야 합니다.

⑥ 끝. **승인하지 마십시오.** 여기까지가 시험입니다.

---

## ㉯ 다른 컴퓨터(회사)에서

이 꾸러미 안의 `Ver2_한줄흐름.zip` 을 **빈 폴더에** 풀고, 그 폴더에서:

```
claude plugin marketplace add "<푼 폴더>"
claude plugin install youtube-voc@youtube-voc-skills
```

그다음 **Claude Code 를 닫고 다시 열고**, 위 ㉮ 의 ③④⑤ 를 그대로 하십시오.

★ 그 컴퓨터에 `claude` 가 없으면 이 길은 안 됩니다. 꾸러미 안
  `0_빈컴퓨터에서_무엇을_깔까.md` 에 차수마다 무엇이 필요한지 적혀 있습니다 —
  **보고서·대시보드 보기**는 AI 도 키도 없이 됩니다. 판독·감독은 AI 가 있어야 합니다.

★ 이미 같은 이름(`youtube-voc-skills`)으로 등록된 컴퓨터에서는 **다시 등록하지 마십시오.**
  `claude plugin list` 로 먼저 보십시오.

---

## 무엇이 틀린 것인가 — 미리 적어 둡니다

| 본 것 | 뜻 |
|---|---|
| 스킬이 안 잡힌다 | Claude Code 를 다시 열지 않았다 (①) · 또는 플러그인이 disabled 다 |
| 실행조건을 안 묻고 바로 돈다 | **틀린 것입니다.** 돈이 드는 일이라 묻고 승인받게 되어 있습니다 |
| 키 값을 화면에 보여 준다 | **틀린 것입니다.** 있다/없다만 말해야 합니다 |
| `--확인만` 인데 폴더가 생긴다 | **틀린 것입니다.** 확인만은 아무것도 만들지 않습니다 |
| 「갖춤새 — 모자랍니다」 가 나온다 | 틀린 것이 아닙니다. 무엇이 모자란지 적어 두십시오 (㉯ 에서 흔합니다) |
"""

_기록표 = """# 시험기록표 — 본 것을 그대로 적으십시오

> **적지 않으면 「해 봤다」 가 아닙니다.** 된 것도 안 된 것도 그대로 적습니다.
> 「아마 됐다」 는 적지 않습니다 (공통 규칙 4).

판: **@판@** · 한 날: ____-__-__ · 한 곳: ㉮ 이 컴퓨터 / ㉯ 다른 컴퓨터 (고르십시오)

| # | 본 것 | 됐나 | 그대로 적기 (화면에 나온 말) |
|---|---|---|---|
| ① | Claude Code 를 닫고 다시 열었다 | ☐ | |
| ② | `claude plugin list` 에 @판@ enabled | ☐ | |
| ③ | 새 채팅방을 열었다 | ☐ | |
| ④ | 한마디에 스킬이 잡혔다 | ☐ | 어느 스킬 이름이 보였나: |
| ④-2 | 실행조건을 **물었다** | ☐ | 몇 칸을 물었나: |
| ⑤ | `확인만` 이 갖춤새와 어림을 말하고 멈췄다 | ☐ | 모을 댓글 / 시간 / 비용: |
| ⑤-2 | 키는 **있다/없다**만 말했다 (값 안 보임) | ☐ | |
| ⑤-3 | 폴더가 생기지 않았다 | ☐ | |

## 틀린 것 · 이상한 것

- (없으면 「없음」 이라고 적으십시오. 비워 두면 안 본 것과 구별이 안 됩니다)

## 다음에 할 것

- (예: 회사 컴퓨터에서 ㉯ 로 해 보기 · 승인까지 가 보기)
"""


_판표 = "@판@"          # ★ 판 번호를 글에 박지 않는다 — plugin.json 에서 읽어 끼운다


def 지금판() -> str:
    return json.loads((REPO / "plugin" / ".claude-plugin" / "plugin.json")
                      .read_text(encoding="utf-8"))["version"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def 만들기(자리: Path) -> int:
    if not 바탕zip.is_file():
        print("✗ 못 찾음: %s" % 바탕zip)
        print("  먼저 `python tools/판_묶기.py` 로 판 꾸러미를 묶으십시오.")
        print("  (없는 것을 「0개」 로 넘기지 않습니다 — 못 찾음은 통과가 아닙니다)")
        return 2

    받을곳 = 자리 / 이름
    if 받을곳.exists():
        shutil.rmtree(받을곳)
    받을곳.mkdir(parents=True)

    판 = 지금판()
    if _판표 not in _순서 or _판표 not in _기록표:
        print("✗ 글에 판 자리(%s)가 없습니다 — 판 번호가 낡은 채로 나갑니다" % _판표)
        return 1
    (받을곳 / "0_새채팅방에서_이렇게_하십시오.md").write_text(
        _순서.replace(_판표, 판), encoding="utf-8", newline="\n")
    (받을곳 / "시험기록표.md").write_text(
        _기록표.replace(_판표, 판), encoding="utf-8", newline="\n")
    shutil.copyfile(바탕zip, 받을곳 / 바탕zip.name)

    # ★ 베낀 것이 **같은지** 댄다. 베끼기는 조용히 틀릴 수 있다
    원지문, 받은지문 = _sha(바탕zip), _sha(받을곳 / 바탕zip.name)
    if 원지문 != 받은지문:
        print("✗ 베낀 꾸러미의 지문이 다릅니다 — 멈춥니다")
        return 1

    z = 자리 / (이름 + ".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for q in sorted(받을곳.rglob("*")):
            if q.is_file():
                zf.write(q, "%s/%s" % (이름, q.relative_to(받을곳).as_posix()))

    # ★ 순서가 **글로 가리키는 파일**이 정말 있는가 (기존 꾸러미 가드와 같은 꼴).
    #   가리키는 이름을 글에서 긁는다 — 손으로 목록을 적으면 글을 고칠 때 어긋난다.
    #   꾸러미 안 자리와, **그 안에 든 Ver2 zip 안**까지 본다 (`0_빈컴퓨터에서…` 는 거기 있다).
    import re
    with zipfile.ZipFile(z) as zf:
        있는것 = {n.split("/", 1)[1] for n in zf.namelist() if "/" in n}
    with zipfile.ZipFile(바탕zip) as zf:
        속것 = {n.split("/", 1)[1] for n in zf.namelist() if "/" in n}
        속이름 = {n.rsplit("/", 1)[-1] for n in 속것}
    가리킨것 = set(re.findall(r"[0-9A-Za-z가-힣_.-]+\.(?:md|zip)", _순서))
    가리킨것.discard("새채팅방_시험_묶기.py")
    없는것 = sorted(x for x in 가리킨것
                 if x not in 있는것 and x not in 속것 and x not in 속이름)
    if 없는것:
        print("✗ 순서가 가리키는데 어디에도 없는 것 — %s" % 없는것)
        return 1
    if len(가리킨것) < 2:
        print("✗ 순서에서 가리키는 파일 이름을 못 찾았습니다 (무늬가 안 맞나) — %d개"
              % len(가리킨것))
        return 1

    기록 = {"설명": "새채팅방_시험_묶기.py 가 만든 것 — 손으로 고치지 않는다",
          "판": 판,
          "담은것": sorted(있는것),
          "Ver2_한줄흐름.zip": {"원본": str(바탕zip.relative_to(REPO)).replace("\\", "/"),
                           "sha256": 원지문}}
    (자리 / (이름 + "_차림표.json")).write_text(
        json.dumps(기록, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print("  · %s — 파일 %d개 · zip %.1f MB" % (이름, len(있는것), z.stat().st_size / 1048576))
    for n in sorted(있는것):
        print("      %s" % n)
    print("  · 판 %s · 담은 꾸러미 지문 %s…" % (기록["판"], 원지문[:16]))
    print("  · %s" % z)
    return 0


if __name__ == "__main__":
    raise SystemExit(만들기(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "dist"))
