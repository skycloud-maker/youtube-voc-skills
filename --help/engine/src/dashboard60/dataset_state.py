"""올린 데이터셋 경로를 세션 밖에 남긴다.

왜 필요한가
-----------
Streamlit 의 ``session_state`` 는 웹소켓이 끊기면 통째로 사라진다.
새로고침 · 재접속 · 노트북 슬립 · 서버 재시작이 전부 여기에 해당한다.

``app_operating.main()`` 은 세션에 경로가 없으면 기본 데이터셋을 넣는다.
그래서 세션이 끊긴 줄 모르는 사용자에게는
**「필터를 몇 번 만졌더니 첫 데이터로 바뀌었다」** 로 보인다.
필터가 범인이 아니라 세션이 범인이다.

어떻게 고치나
-------------
경로를 두 곳에 남긴다.

① 주소창 (``st.query_params``)
   같은 탭에서 새로고침하거나 웹소켓이 다시 붙으면 URL 은 그대로이므로
   바로 되돌아온다. 사람마다 탭이 다르니 여럿이 같이 써도 안 섞인다.

② 파일 (``outputs/voc_dashboard_60/.last_dataset``)
   탭을 새로 열거나 서버가 재시작해서 URL 마저 없을 때 쓴다.

둘 다 **없거나 그 파일이 실제로 없으면** 기본값으로 간다 —
지운 경로를 붙들고 화면이 안 뜨는 일이 없도록.

여기 함수는 Streamlit 을 부르지 않는다. 값만 넣으면 값이 나오므로
시험에서 그대로 부를 수 있다. Streamlit 을 만지는 것은 호출하는 쪽이다.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

QUERY_KEY = "dataset"
STATE_FILE = ROOT / "outputs" / "voc_dashboard_60" / ".last_dataset"


def _쓸만한가(후보: object) -> str:
    """문자열로 만들고, 실제로 있는 파일일 때만 돌려준다."""
    글 = str(후보 or "").strip()
    if not 글:
        return ""
    길 = Path(글)
    if not 길.is_absolute():
        길 = ROOT / 길
    try:
        return 글 if 길.is_file() else ""
    except OSError:
        # 경로가 너무 길거나 이름에 못 쓰는 글자가 있으면 여기로 온다
        return ""


def choose(
    *,
    session: object = None,
    query: object = None,
    saved: object = None,
    default: object = "",
) -> str:
    """어느 경로를 쓸지 고른다.

    앞선 것이 이긴다 — 세션(지금 보고 있던 것) > 주소창 > 파일 > 기본값.
    앞의 셋은 **파일이 실제로 있을 때만** 채택한다.
    기본값은 마지막 보루라 있는지 따지지 않고 그대로 돌려준다
    (없으면 화면이 「Dataset not found」 를 띄워 사람에게 알린다).
    """
    for 후보 in (session, query, saved):
        골 = _쓸만한가(후보)
        if 골:
            return 골
    return str(default or "").strip()


def recall(*, state_file: Path | None = None) -> str:
    """파일에 남겨 둔 경로를 읽는다. 없으면 빈 글자."""
    p = state_file or STATE_FILE
    try:
        return p.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def remember(path: object, *, state_file: Path | None = None) -> bool:
    """경로를 파일에 남긴다. 남겼으면 True.

    같은 값이면 다시 쓰지 않는다 — Streamlit 은 한 번 만질 때마다
    스크립트를 처음부터 다시 돌리므로, 안 그러면 디스크를 계속 두드린다.
    쓰기에 실패해도 화면은 계속 돌아가야 하므로 조용히 False 를 준다.
    """
    글 = str(path or "").strip()
    if not 글:
        return False
    p = state_file or STATE_FILE
    try:
        if p.is_file() and p.read_text(encoding="utf-8").strip() == 글:
            return False
    except (OSError, UnicodeDecodeError):
        pass
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(글, encoding="utf-8")
        return True
    except OSError:
        return False
