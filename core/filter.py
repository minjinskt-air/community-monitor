"""
core/filter.py
──────────────────────────────────────
키워드 + 조회수 기반 필터링
config.py의 KEYWORDS / MIN_VIEWS / EXCLUDE_KEYWORDS 사용
──────────────────────────────────────
"""

from config import KEYWORDS, EXCLUDE_KEYWORDS, MIN_VIEWS


def apply_filter(posts: list) -> list:
    """
    수집된 게시글 중 발송 대상만 추려 반환.

    통과 조건 (AND):
      1) 제목에 EXCLUDE_KEYWORDS 없음
      2) 제목에 KEYWORDS 중 하나 이상 포함
      3) 조회수 >= MIN_VIEWS  (0이면 조회수 무시)

    반환: 필터 통과한 게시글 리스트 (정렬: 조회수 내림차순)
    """
    result = []
    cnt_exclude = 0
    cnt_no_keyword = 0
    cnt_low_views = 0

    for post in posts:
        title = post.get("title", "")
        views = post.get("views", 0)

        # 1) 제외 키워드 체크
        if any(kw in title for kw in EXCLUDE_KEYWORDS):
            cnt_exclude += 1
            continue

        # 2) 포함 키워드 체크
        matched = [kw for kw in KEYWORDS if kw.lower() in title.lower()]
        if not matched:
            cnt_no_keyword += 1
            continue

        # 3) 조회수 체크
        if MIN_VIEWS > 0 and views < MIN_VIEWS:
            cnt_low_views += 1
            print(f"  [Filter] 조회수 미달({views:,} < {MIN_VIEWS:,}) → '{title[:40]}'")
            continue

        post["matched_keywords"] = matched
        result.append(post)

    # 조회수 내림차순 정렬
    result.sort(key=lambda p: p.get("views", 0), reverse=True)

    print(
        f"[Filter] {len(posts)}개 수집 → "
        f"제외키워드:{cnt_exclude} / 키워드없음:{cnt_no_keyword} / 조회수미달:{cnt_low_views} / "
        f"통과:{len(result)}개 (기준: 조회수 {MIN_VIEWS:,} 이상)"
    )
    return result
