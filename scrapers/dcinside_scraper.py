"""
scrapers/dcinside_scraper.py
──────────────────────────────────────
디시인사이드 갤러리 크롤러
대상: gall.dcinside.com/board/lists/?id=mvno (알뜰폰 갤러리)
──────────────────────────────────────
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config import DCINSIDE_GALLERIES, SCRAPE_DAYS

BASE_URL  = "https://gall.dcinside.com/board/lists/"
# 미니갤러리는 아래 URL 사용 (갤러리 종류에 따라 자동 분기)
MINI_URL  = "https://gall.dcinside.com/mgallery/board/lists/"


class DcinsideScraper:
    SOURCE = "dcinside"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://gall.dcinside.com",
        })

    def scrape(self) -> list:
        cutoff    = datetime.now() - timedelta(days=SCRAPE_DAYS)
        all_posts = []
        seen_ids  = set()

        for gallery_id in DCINSIDE_GALLERIES:
            print(f"  [디시] {gallery_id} 갤러리 수집 중...")
            page = 1
            consecutive_old = 0

            while True:
                try:
                    posts, all_old = self._scrape_page(gallery_id, page, cutoff, seen_ids)
                    if all_old:
                        consecutive_old += 1
                        if consecutive_old >= 2:
                            break
                    else:
                        consecutive_old = 0
                    all_posts.extend(posts)
                    page += 1
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  [디시] {gallery_id} {page}p 에러: {e}")
                    break

        print(f"  [디시] 총 {len(all_posts)}개 수집")
        return all_posts

    # ──────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────

    def _scrape_page(self, gallery_id: str, page: int, cutoff: datetime, seen_ids: set):
        # 일반갤 먼저 시도, 실패 시 미니갤로 fallback
        url  = f"{BASE_URL}?id={gallery_id}&page={page}"
        resp = self.session.get(url, timeout=30)

        # 미니갤 redirect 감지 (페이지 URL이 mgallery로 바뀌거나 목록이 비어있을 때)
        if "mgallery" in resp.url or resp.status_code == 404:
            url  = f"{MINI_URL}?id={gallery_id}&page={page}"
            resp = self.session.get(url, timeout=30)

        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        resp.close()

        posts        = []
        page_has_new = False

        # 디시인사이드 목록 구조: table.gall_list > tbody > tr
        rows = soup.select("table.gall_list tbody tr.ub-content")
        if not rows:
            rows = soup.select("tr.ub-content")

        for row in rows:
            try:
                # 공지·광고 제외
                gall_num = row.select_one(".gall-num, .gall_num")
                if gall_num:
                    num_text = gall_num.get_text(strip=True)
                    if num_text in ("공지", "AD", "설문"):
                        continue

                # 제목 & 링크
                title_elem = row.select_one(".gall-tit a, .title a")
                if not title_elem:
                    continue
                href  = title_elem.get("href", "")
                title = title_elem.get_text(strip=True)
                # 댓글 수 제거 [N]
                title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()
                if not title:
                    continue

                # 게시글 번호
                post_id = self._extract_id(href)
                if not post_id or post_id in seen_ids:
                    continue

                # 날짜
                date_elem = row.select_one(".gall-date, .date")
                posted_at = self._parse_date(
                    date_elem.get("title", date_elem.get_text(strip=True)) if date_elem else ""
                )
                if posted_at < cutoff:
                    continue
                page_has_new = True

                # 조회수
                views    = self._extract_num(row.select_one(".gall-count, .view"))
                comments = self._extract_num(row.select_one(".gall-comment, .reply_num"))

                full_url = href if href.startswith("http") else f"https://gall.dcinside.com{href}"

                posts.append({
                    "post_id":   post_id,
                    "source":    self.SOURCE,
                    "title":     title,
                    "url":       full_url,
                    "views":     views,
                    "comments":  comments,
                    "posted_at": posted_at,
                })
                seen_ids.add(post_id)
            except Exception:
                continue

        soup.decompose()
        all_old = (not page_has_new and len(rows) > 0)
        return posts, all_old

    def _extract_id(self, href: str) -> str:
        m = re.search(r"no=(\d+)", href)
        return m.group(1) if m else ""

    def _extract_num(self, elem) -> int:
        if not elem:
            return 0
        m = re.search(r"(\d[\d,]*)", elem.get_text(strip=True))
        return int(m.group(1).replace(",", "")) if m else 0

    def _parse_date(self, text: str) -> datetime:
        """
        디시 날짜 형식:
          - "2026.04.14 10:30:00"  (title 속성)
          - "04.14 10:30"          (화면 표시)
          - "10:30"                (오늘)
        """
        s = text.strip()
        try:
            # "YYYY.MM.DD HH:MM:SS"
            m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))
            # "MM.DD HH:MM"
            m = re.match(r"(\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})", s)
            if m:
                return datetime(datetime.now().year, int(m[1]), int(m[2]), int(m[3]), int(m[4]))
            # "HH:MM"
            m = re.match(r"(\d{1,2}):(\d{2})", s)
            if m:
                return datetime.now().replace(
                    hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0
                )
        except Exception:
            pass
        return datetime.now()
