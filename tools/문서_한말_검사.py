# -*- coding: utf-8 -*-
"""문서들이 같은 것을 **같은 말로** 적고 있나 (2026-10-29).

★ 왜 있는가 — 옛 저장소에 같은 이름의 도구가 있었다. sky 2026-09-07 —
    「전체 문서에 통일되게 같은 내용들이 문제없이 기록되었는지 등 작업을 해야되지 않을까요?」

  그 도구가 적어 둔 까닭을 그대로 옮긴다 —

  > 이 폴더에는 같은 사안을 말하는 문서가 여럿이다 — 로드맵 · 반영대기 · 7차 대장 ·
  > 변경원장 · 안 하기로 한 것 · 동결규칙 · 오류대장 · 인계메모.
  > 한 곳만 고치면 **다음 사람이 딴 문서를 보고 딴소리를 한다.**
  >
  > 실제로 2026-09-07 에 E-1 을 「영구 종결」 로 정했는데, 그 전까지
  > 여섯 문서가 「다음 엔진 개정 때 고친다」 고 적고 있었다.

  **그 도구가 새 저장소로 안 왔다.** 옛 관리 도구 일곱 중 다섯만 기록했고,
  고르지 않은 둘이 하필 「빠진 것을 찾는 도구」 였다
  (`docs/옛꾸러미_대장.md` · `docs/기준서개정후보.md` 후보 2).

  그 구멍은 실제로 드러났다 — 2026-10-29 에 내 글 두 문장이 사실과 달랐다
  (판독자 csv 를 74칸이라 적었는데 79칸이었다 · 돌리개가 보는 파일을 틀리게 적었다).
  아무도 지적하지 않아 내가 다시 세어 보고 알았다.

  원문은 `docs/sources/옛관리도구/문서_한말_검사.py` 에 지문과 함께 있다.
  여기 있는 것은 **그 규칙을 새 저장소의 글에 맞춰 다시 지은 것**이다.

보는 것 다섯
------------
  ① 셀 수 있는 수   `옛꾸러미_목록.json` 이 센 수와 정본 글에 적힌 수가 같은가
                    ★ 표에 손으로 안 적는다 — 세어서 댄다. 그래야 낡지 않는다
  ② 판 번호         `plugin.json` 의 판과 정본 글 머리의 「판 X」 가 같은가
  ③ 낡은 말         더 이상 사실이 아닌 말이 정본 글에 남아 있나 (표 · 손으로 갱신)
  ④ 있어야 할 말    이번에 정한 것이 있어야 할 글에 다 들어갔나 (표 · 손으로 갱신)
  ⑤ 쌍둥이          같은 이름의 글이 두 자리에 있고 내용이 다른가
                    ★ 옛 도구가 겪은 것 — 같은 기준서가 `21a_`·`1a_` 두 이름으로 5벌 있었다

★ 옛 기록은 **지우지 않는다.** 그때 그렇게 정했다는 것이 사실이기 때문이다.
  대신 바로 아래 줄에 **「그 뒤 어떻게 됐는지」** 를 붙인다.
  이 검사는 뒤 이야기가 붙어 있으면 통과시킨다 (옛 도구와 같다).

★ **기록 글은 보지 않는다** — `CHANGELOG.md` · `docs/progress.md` · `docs/decisions/` ·
  `plugin/shared/standards/` 는 날짜순 기록이거나 글자를 바꾸지 않고 복사해 온 원문이다.
  거기에 옛말이 있는 것은 **옳다.** 보는 것은 **지금을 말해야 하는 글**뿐이다.

★ **못 찾으면 종료코드 1** — 「못 찾음」 은 「없음」 이 아니다. 정본 글을 다섯 개도
  못 찾으면 검사를 못 한 것이고, 그것을 「어긋난 곳 없음」 으로 돌려주지 않는다.

쓰기
    python tools/문서_한말_검사.py            # 본다
    python tools/문서_한말_검사.py --자세히    # 걸린 줄을 다 본다
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import REPO  # noqa: E402

자세히 = "--자세히" in sys.argv

# ── 보는 글 — **지금을 말해야 하는 글**만 ────────────────────────────
#    기록 글(CHANGELOG · progress · decisions)과 복사해 온 기준 원문(standards)은 뺀다.
_안보는글 = {"progress.md"}


def 정본글() -> list[Path]:
    글 = [REPO / "README.md"]
    글 += sorted(p for p in (REPO / "docs").glob("*.md") if p.name not in _안보는글)
    return [p for p in 글 if p.is_file()]


# ── ③ 더 이상 사실이 아닌 말 ────────────────────────────────────────
#    (찾을 무늬, 왜 낡았나, 뒤 이야기가 붙었는지 볼 표시 — 없으면 None)
#    ★ 새 판을 닫을 때 손으로 갱신한다. 도구가 대신 못 쓴다 — 무엇이 바뀌었는지는 사람이 안다.
낡은말 = [
    (r"판독자가\s*받는\s*csv\s*(는|은)?\s*74칸", "판독자 csv 는 79칸이다 (74 는 번들 엑셀)", None),
    (r"돌리개가\s*번들\s*엑셀", "1차 돌리개는 voc_dashboard_dataset.csv(66칸)를 센다", "실제로는"),
    (r"대조\s*자료\s*일곱", "대조 자료는 아홉 벌이다 (2026-10-29)", None),
    (r"이\s*114개는\s*아직\s*안\s*봤", "2026-10-29 에 전량을 갈랐다 — 아직 안 본 것은 0 이다", None),
    (r"세는\s*자리를\s*만든\s*것\**입니다", "세는 자리를 만든 뒤 전량을 갈랐다", None),
    (r"옛\s*관리\s*도구\s*5개", "일곱이다 — 2026-10-29 에 둘을 더 기록했다", None),
]

# ── ④ 이번에 정한 것이 들어가 있어야 할 자리 ────────────────────────
있어야 = [
    ("docs/지금_어디인가.md", "ⓑ 는 보내는 것을 막지 않는다"),
    ("docs/지금_어디인가.md", "새 채팅방 시험"),
    ("docs/옛꾸러미_대장.md", "이름이 다른 쌍둥이"),
    ("docs/옛꾸러미_대장.md", "까닭 없이 무늬를 더하지 않는다"),
    ("docs/기준서개정후보.md", "빼는 것은 후보가 아니다"),
    ("docs/대조_원본과_skill.md", "빠진 것을 찾는 도구"),
    ("docs/점검요청_원본과_skill_대조.md", "빠진 것을 찾는 도구"),
    ("docs/메일_붙일_것.md", "빠진 것을 찾는 도구"),
]


def _줄집합(p: Path) -> set:
    """겹침을 재는 데 쓰는 줄 모음 — 짧은 줄과 공백 차이는 뺀다."""
    t = p.read_text(encoding="utf-8", errors="replace")
    return {re.sub(r"\s+", " ", c).strip() for c in t.splitlines()
            if len(re.sub(r"\s+", " ", c).strip()) >= 12}


def _판() -> str:
    p = REPO / "plugin" / ".claude-plugin" / "plugin.json"
    if not p.is_file():
        raise SystemExit("못 찾음: %s — 판 번호를 댈 수 없다 (통과가 아니다)" % p)
    return json.loads(p.read_text(encoding="utf-8"))["version"]


def _센수() -> dict:
    p = REPO / "docs" / "옛꾸러미_목록.json"
    if not p.is_file():
        raise SystemExit("못 찾음: %s — 센 수를 댈 수 없다 (통과가 아니다)\n"
                         "  `python tools/옛꾸러미_대장.py` 를 돌리십시오." % p)
    return json.loads(p.read_text(encoding="utf-8"))["수"]


def main() -> int:
    글들 = 정본글()
    탈 = 0
    print("=" * 72)
    print("  문서가 같은 말을 하나 — 지금을 말해야 하는 글 %d개" % len(글들))
    print("=" * 72)
    print()
    # ★ 글을 못 찾았는데 「없음」 이라고 하면 읽는 사람은 통과로 본다. 못 찾은 것은 통과가 아니다.
    if len(글들) < 5:
        print("  ★ 정본 글을 %d개밖에 못 찾았습니다 — **검사를 못 했습니다.**" % len(글들))
        print("     지금 자리: %s" % REPO)
        return 1

    # ① 셀 수 있는 수 — 세어서 댄다
    수 = _센수()
    아직 = 수["아직안봤다"]
    print("  ① 센 수와 글에 적힌 수가 같은가  (대장이 센 「아직 안 봤다」 = %d)" % 아직)
    무늬 = re.compile(r"아직\s*안\s*(봤다|본\s*것)[^0-9\n]{0,20}([0-9]{1,4})")
    본것 = 0
    for p in 글들:
        for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in 무늬.finditer(l):
                본것 += 1
                if int(m.group(2)) != 아직:
                    탈 += 1
                    print("     ★ %s:%d  글은 %s 라는데 센 것은 %d 다"
                          % (p.name, i, m.group(0).strip()[:40], 아직))
    print("     · 그 수를 말하는 자리 %d곳 — 어긋난 곳 %s" % (본것, "없음" if not 탈 else "위"))

    # ② 판 번호
    판 = _판()
    print()
    print("  ② 판 번호가 `plugin.json` 과 같은가  (판 %s)" % 판)
    판무늬 = re.compile(r"판\s+([0-9]+\.[0-9]+\.[0-9]+)")
    # ★ **지금을 말하는 줄만** 본다. 돌려 보니 「같은 날 둘째 (판 2.0.10)」 ·
    #   「두 번째 요청이었습니다 (… 판 2.0.8)」 처럼 **옛 판을 적는 것이 옳은 줄**이 걸렸다.
    #   그것은 기록이고, 고치면 거짓이 된다. 그래서 「적은 날」 · 「…입니다」 처럼
    #   **지금을 말하는 표시**가 있는 줄만 본다 (「…였습니다」 는 지난 일이다).
    지금줄 = re.compile(r"적은\s*날|요청입니다")
    어긋 = []
    본줄 = 0            # ★ 몇 줄을 보고 그 말을 하는지 — 0 이면 검사를 **못 한** 것이다
    for p in 글들:
        for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not l.lstrip().startswith(">") or not 지금줄.search(l) or "였습니다" in l:
                continue        # 글 머리에서 **지금 판**을 말하는 줄만 본다
            for m in 판무늬.finditer(l):
                본줄 += 1
                if m.group(1) != 판 and "~" not in l:
                    어긋.append((p.name, i, l.strip()))
    # ★ 2026-11-02 — **「못 찾음」 을 「없음」 으로 돌려주지 않는다.**
    #   그날 세 글의 머리를 「그때 판은 2.0.12 였습니다」 (지난 일)로 고쳤더니
    #   이 검사가 볼 줄이 **0개**가 되었는데도 「머리에 적힌 판이 다 2.0.13 다」 라고
    #   찍고 통과했다. 검사 안 한 것을 통과로 보여 준 것이다.
    #   지금 판을 대는 줄은 `docs/지금_어디인가.md` 머리에 있다.
    if 본줄 == 0:
        탈 += 1
        print("     ★ 지금 판을 말하는 줄을 **한 줄도 못 찾았습니다** — 검사를 못 했습니다.")
        print("        (찾는 꼴 — 인용줄 「> … 적은 날 … 판 X.Y.Z」 · 「였습니다」 가 없는 줄)")
        print("        `docs/지금_어디인가.md` 머리의 「적은 날 … 판」 줄을 되살리십시오.")
    elif 어긋:
        탈 += len(어긋)
        for n, i, l in (어긋 if 자세히 else 어긋[:5]):
            print("     ★ %s:%d  %s" % (n, i, l[:70]))
    else:
        print("     · 머리에 적힌 판이 다 %s 다 (본 줄 %d개)" % (판, 본줄))

    # ③ 낡은 말
    print()
    print("  ③ 더 이상 사실이 아닌 말이 남았나")
    for 패, 왜, 뒷이야기 in 낡은말:
        걸림 = []
        for p in 글들:
            줄들 = p.read_text(encoding="utf-8", errors="replace").splitlines()
            for i, l in enumerate(줄들):
                if not re.search(패, l):
                    continue
                # ★ 옛 도구는 **다음 두 줄**만 봤다. 여기서는 **그 줄까지** 본다 —
                #   돌려 보니 「… 라고 적었습니다(실제로는 …)」 처럼 **바로잡는 말이 같은 줄에**
                #   있는 경우가 걸렸다. 바로잡아 놓은 글을 또 잡으면 헛경보가 되고,
                #   헛경보를 내는 검사기는 아무도 안 보게 된다.
                뒤 = " ".join(줄들[i:i + 3])
                if 뒷이야기 and 뒷이야기 in 뒤:
                    continue        # 뒤 이야기(또는 바로잡는 말)가 붙어 있으면 통과
                걸림.append((p.name, i + 1, l.strip()))
        if 걸림:
            탈 += len(걸림)
            print("     ★ %-34s — %s" % (패[:34], 왜))
            for n, i, l in (걸림 if 자세히 else 걸림[:3]):
                print("        %s:%d  %s" % (n, i, l[:70]))
        else:
            print("     · %-34s 없음" % 패[:34])

    # ④ 있어야 할 말
    print()
    print("  ④ 이번에 정한 것이 다 들어갔나")
    for 쪽, 말 in 있어야:
        p = REPO / 쪽
        있 = p.is_file() and 말 in p.read_text(encoding="utf-8", errors="replace")
        print("     %s %-40s %s" % ("·" if 있 else "★", 쪽[:40], 말[:30]))
        if not 있:
            탈 += 1

    # ⑤ 쌍둥이 — 같은 이름의 글이 두 자리에 있고 내용이 다른가
    print()
    print("  ⑤ 같은 이름의 글이 두 자리에 있고 내용이 다른가")
    자리별: dict = {}
    for p in REPO.rglob("*.md"):
        s = p.as_posix()
        if "/dist/" in s or "/.git/" in s or "/.pytest_cache/" in s or "/sources/" in s:
            continue
        자리별.setdefault(p.name, []).append(p)
    쌍 = {n: v for n, v in 자리별.items() if len(v) > 1}
    다른것 = []
    for n, v in sorted(쌍.items()):
        글 = {p.read_bytes().replace(b"\r\n", b"\n") for p in v}
        if len(글) <= 1:
            continue        # 바이트가 같다 — 어긋남이 아니다
        # ★ **이름만 같은 것은 쌍둥이가 아니다.** 돌려 보니 `SKILL.md` 여섯과
        #   `0_계획.md` 둘이 걸렸는데, 서로 다른 글이 **틀만 나눠 쓰는 것**이었다.
        #   재 보니 겹침이 `SKILL.md` 57.4% · `0_계획.md` 6.2% 였다 (2026-10-29).
        #   한 글이 두 이름으로 갈라진 쌍둥이는 거의 다 겹친다 — 옛 저장소의
        #   `21a_`/`1a_` 기준서 5벌이 그랬다. 그래서 **90% 이상 겹칠 때만** 잡는다.
        가장 = 0.0
        집 = [(q, _줄집합(q)) for q in v]
        for i in range(len(집)):
            for j in range(i + 1, len(집)):
                a, b = 집[i][1], 집[j][1]
                if a and b:
                    가장 = max(가장, len(a & b) / min(len(a), len(b)))
        if 가장 >= 0.90:
            다른것.append(("%s (겹침 %.0f%%)" % (n, 가장 * 100),
                         [q.relative_to(REPO).as_posix() for q in v]))
    if 다른것:
        탈 += len(다른것)
        for n, 자리 in (다른것 if 자세히 else 다른것[:5]):
            print("     ★ %-34s %s" % (n[:34], " · ".join(자리)))
    else:
        print("     · 같은 이름이 여러 자리인 글 %d개 — 내용이 다른 것 없음" % len(쌍))

    print()
    print("=" * 72)
    if 탈:
        print("  ★ 어긋난 곳 %d — 글마다 딴소리를 합니다" % 탈)
        print()
        print("  고치는 법")
        print("    · 낡은 말은 고치거나, 옛 기록이면 **바로 아래에** 뒤 이야기를 붙이십시오")
        print("    · 이번 판에서 정한 것이 빠진 글에는 그 말을 넣으십시오")
        print("    · 새 판을 닫을 때는 이 파일 위 「낡은말」·「있어야」 를 손으로 갱신합니다")
        return 1
    print("  · 글이 다 같은 말을 합니다")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
