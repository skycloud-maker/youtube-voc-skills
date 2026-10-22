# 키워드 결합 OR · AND — 무엇이 어떻게 걸러지는가 (엔진 코드에서 확인한 것)

> **왜 이 파일이 있나** (sky 2026-10-22 「or 와 and 의 조건을 명확하게 해야 합니다.
> 기존에 잡혀져 있던 그 기준을 명확히 기록해주세요」)
>
> 2026-08-20 에 대시보드 안내문이 **코드와 달랐던 적이 있다.** 「키워드별 개별 검색 후 공통」
> 이라 적혀 있었으나 실제로는 그렇지 않았다 (sky 가 찾아 고쳤다 —
> `analysis_runner.py:1417-1420` 의 주석). 같은 일이 또 생기지 않도록 **엔진 코드를 읽어**
> 여기에 적는다. 안내문이 아니라 **코드가 기준**이다.
>
> 읽은 자리 — 동결 엔진 사본 (`plugin/engine/`)
> - `src/pipelines/ingest_pipeline.py:19-21` (상수) · `:36-41` (갈림) ·
>   `:87-129` (OR) · `:131-142` (정렬) · `:144-182` (AND) · `:184-221` (걸러내기) ·
>   `:223-237` (후보 수 · 최소 맞춤 수) · `:239-252` (글자 맞추기)
> - `src/cli.py:40-43` (상수) · `:45-76` (할당량 어림)
> - `src/dashboard60/analysis_runner.py:1333-1356` (사람에게 보여 주는 안내문)
>
> 바꾸지 말 것 — 엔진은 동결 사본이다. 이 파일은 **엔진이 하는 일을 적은 것**이고,
> 엔진을 고쳐야 할 일이 생기면 7차 엔진 개정에서 모아서 한다.

## 한 줄로

- **OR** — 키워드마다 **따로 검색**해서 합친다. **적는 순서는 상관없다.**
- **AND** — **맨 윗줄 키워드로만 검색**하고, 아랫줄 키워드는 그 결과 영상의
  **제목·설명·채널명·태그에서 글자로** 찾아 걸러낸다. **맨 윗줄이 모수를 정한다.**

★ AND 는 「키워드마다 검색해서 교집합」 이 **아니다.** 이것이 2026-08-20 에 틀려 있던 바로 그 자리다.

## 언제 어느 길로 가는가

`ingest_pipeline.py:36-41`

```python
search_keywords = [kw for kw in (config.keywords if config.keywords else [config.keyword]) if kw]
keyword_mode = str(config.keyword_mode or "OR").upper()
if keyword_mode == "AND" and len(search_keywords) > 1:
    all_videos = self._search_keyword_intersection(config, manifest, search_keywords)
else:
    all_videos = self._search_keyword_union(config, manifest, search_keywords)
```

- 기본값은 **OR** 이다 (값이 비면 OR).
- **AND 인데 키워드가 하나면 OR 와 똑같이 돈다.** AND 는 둘 이상일 때만 다른 길이다.
- `키워드들` 을 비우면 `검색어` 하나를 목록으로 쓴다.

## OR — 따로 찾아 합친다

`ingest_pipeline.py:87-129`

1. **키워드마다 `search` 를 한 번씩 부른다.** 그때 각 호출의 영상 수는
   **요청한 영상 수 그대로**다 (`max_videos=max(1, int(config.max_videos or 1))`).
2. **같은 영상(`video_id`)은 하나로 합친다.** 합친 영상에는 맞은 키워드가 쌓인다 —
   `matched_keyword` 가 `"로봇청소기 OR 로니"` 꼴이 되고 `keyword_match_count` 가 올라간다.
3. 모은 것을 **아래 「고르는 차례」** 로 정렬해 앞에서 **요청한 영상 수만큼** 자른다.

적히는 칸 — `keyword_match_mode="OR"` · `matched_keyword` · `matched_keywords` · `keyword_match_count`

**할당량** — `search.list` 호출이 **키워드 수만큼** 늘어난다
(`cli.py:57` `search_keyword_multiplier = keyword_count`). 키워드를 셋 적으면 검색 호출도 세 배다.

## AND — 맨 윗줄로 찾고, 나머지는 글자로 걸러낸다

`ingest_pipeline.py:144-182`

### ① 맨 윗줄 키워드로 **한 번만** 검색한다

그때 가져오는 후보 수는 요청한 영상 수가 아니라 **넓힌 수**다 (`:223-227`)

```python
AND_CANDIDATE_MULTIPLIER = 5
AND_CANDIDATE_MIN = 200
AND_CANDIDATE_CAP = 300

def _and_candidate_limit(cls, max_videos: int) -> int:
    requested = max(1, int(max_videos or 1))
    expanded = max(cls.AND_CANDIDATE_MIN, requested * cls.AND_CANDIDATE_MULTIPLIER)
    return max(requested, min(cls.AND_CANDIDATE_CAP, expanded))
```

즉 **후보 = max(요청, min(300, max(200, 요청 × 5)))** 이다.
영상 5개를 달라고 해도 후보는 200개를 가져와 걸러낸 뒤 5개를 고른다.
걸러낸 결과가 요청보다 적으면 **적게 나온다** (억지로 채우지 않는다).

### ② 아랫줄 키워드는 **검색하지 않는다** — 영상 정보의 글자에서 찾는다

`:239-252`

```python
def _keyword_matches_video_metadata(cls, keyword, video) -> bool:
    normalized_keyword = cls._normalize_match_text(keyword)
    if not normalized_keyword:
        return True
    metadata_text = cls._video_metadata_text(video)
    return normalized_keyword in metadata_text or normalized_keyword.replace(" ", "") in metadata_text.replace(" ", "")

def _video_metadata_text(cls, video: dict) -> str:
    parts = []
    for field in ("title", "description", "channel_title", "channel_name"):
        parts.append(cls._normalize_match_text(video.get(field)))
    tags = video.get("tags")
    ...

def _normalize_match_text(value) -> str:
    return " ".join(str(value or "").casefold().split())
```

찾아보는 자리 네 곳 + 태그 — **제목 · 설명 · 채널명(channel_title) · 채널명(channel_name) · 태그.**
★ **댓글 본문은 보지 않는다.** 영상을 고르는 단계이기 때문이다.

맞추는 법 —
- 대소문자를 없애고(`casefold`) 띄어쓰기를 하나로 고른 뒤 **그 글자가 들어 있는지**만 본다.
- 한 번 더, **공백을 모두 없앤** 것끼리도 비교한다. 그래서 「로봇 청소기」 와 「로봇청소기」 가 같이 걸린다.
- **빈 키워드는 무조건 통과**로 센다 (`if not normalized_keyword: return True`).
- 형태소 분석이나 유사어는 **없다.** 글자가 들어 있는지뿐이다.

### ③ 몇 개가 맞아야 남는가

`:184-221` · `:229-237`

```python
def _and_min_keyword_matches(search_keywords, configured) -> int:
    keyword_count = len(search_keywords)
    if keyword_count <= 0:
        return 0
    if configured is None:
        return keyword_count
    return max(1, min(keyword_count, int(configured)))
```

- `최소매칭` 을 **비우면 = 키워드 전체 수** → 「모든 키워드 포함」 이다.
- 적으면 1 과 키워드 수 사이로 **잘라서** 쓴다 (3개인데 9 를 적으면 3 으로 본다).
- **맨 윗줄은 항상 맞은 것으로 센다** (`matched_keywords = [search_keywords[0]]` 로 시작).
  그러니 키워드 셋에 `최소매칭=2` 는 「맨 윗줄 + 아랫줄 중 하나」 를 뜻한다.
- 대시보드 화면에서는 이 칸이 **키워드가 셋 이상일 때만** 보인다
  (`analysis_runner.py:1431` `len(keywords) >= 3`). 둘이면 늘 「둘 다 포함」 이다.

적히는 칸 — `keyword_match_mode` 가 `"AND"`(전부 맞음) 또는 `"AND_MIN"`(최소 N) ·
`matched_keyword` 가 `"로봇청소기 AND 로니"` 꼴 · `matched_keywords` ·
`keyword_match_count` · `keyword_match_min_required` · `and_base_keyword`(맨 윗줄)

**할당량** — `search.list` 는 **한 키워드 몫만** 센다 (키워드 수를 곱하지 않는다).
다만 후보를 200~300개까지 넓혀 가져오므로 **페이지 수가 늘어** 호출이 많아질 수 있다
(`cli.py:50-57` — `per_keyword_videos` 를 넓힌 수로 잡고 `search_keyword_multiplier = 1`).

## 고르는 차례 (두 길이 똑같이 쓴다)

`ingest_pipeline.py:131-142`

```python
return sorted(
    videos,
    key=lambda item: (
        bool(item.get("video_selection_excluded", False)),
        -float(item.get("selection_score") or 0.0),
        -cls._safe_int(item.get("comment_count")),
        cls._safe_int(item.get("search_rank"), default=999999),
        cls._normalize_video_id(item.get("video_id")),
    ),
)
```

1. 제외 표시가 **안 된 것** 먼저
2. `selection_score` **높은 것** 먼저
3. 댓글 수 **많은 것** 먼저
4. 검색 순위 **앞선 것** 먼저 (없으면 맨 뒤로)
5. `video_id` 오름차순 — 앞이 다 같을 때 **차례가 흔들리지 않게**

## 사람에게 보여 주는 안내문 (원문 그대로)

`analysis_runner.py:1333-1356` — 고른 방식에 따라 말이 달라진다.

```python
def _keyword_mode_note(mode: str, keywords: list[str]) -> str:
    if str(mode).upper() != "AND":
        return "키워드마다 따로 찾아 결과를 합칩니다. 적는 순서는 상관없습니다."
    if not keywords:
        return "위에서 아래로 범위를 좁혀 갑니다. 넓은 말을 위에 적으십시오."
    if len(keywords) == 1:
        return f"「{keywords[0]}」 로 찾습니다. 아래에 말을 더 적으면 그 안에서 더 좁혀 갑니다."

    steps = [f"「{keywords[0]}」 로 찾고"]
    for word in keywords[1:]:
        steps.append(f"그중 「{word}」 가 있는 것만")
    return (
        " → ".join(steps)
        + " 남깁니다. (두 번째 줄부터는 영상의 제목·설명·채널명·태그에서 찾습니다)"
    )
```

그리고 고르개의 도움말 원문 (`analysis_runner.py:1421-1426`)

```
OR — 키워드마다 따로 검색해서 결과를 합칩니다. 중복 영상은 하나로 칩니다.

AND — 맨 윗줄 키워드로만 검색합니다. 아랫줄 키워드는 그 결과 영상의 제목·설명·채널명·태그에
      그 말이 들어 있는지로 걸러냅니다.
★ 그래서 맨 윗줄을 무엇으로 적느냐가 결과를 좌우합니다.
```

## 그래서 사람에게 물을 때

| 하려는 것 | 어떻게 적나 |
|---|---|
| 여러 제품·브랜드를 **넓게** 모은다 | **OR** · 키워드를 나열한다. 순서 상관없음 |
| 한 주제 안에서 **좁혀** 간다 | **AND** · **맨 윗줄에 넓은 말**, 아랫줄에 좁히는 말 |
| AND 인데 너무 적게 잡힌다 | `최소매칭` 을 키워드 수보다 작게 (예: 셋 중 둘) |
| AND 인데 엉뚱한 것이 섞인다 | 맨 윗줄을 더 좁은 말로 바꾼다 — 모수가 거기서 정해진다 |

★ AND 에서 **맨 윗줄에 좁은 말을 적으면 거기서 이미 끝난다.** 아랫줄로는 넓힐 수 없다.
★ 아랫줄 키워드는 **검색어가 아니라 글자 필터**다. 영상 제목·설명·채널명·태그에 그 말이
  실제로 적혀 있지 않으면, 내용이 그 얘기라도 걸러진다.
