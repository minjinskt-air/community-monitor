"""
scrapers/fmkorea_scraper.py
──────────────────────────────────────
펨코(FMKorea) 크롤러
대상: www.fmkorea.com
──────────────────────────────────────
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config import FMKOREA_BOARDS, SCRAPE_DAYS

BASE_URL = "https://www.fmkorea.com"

# 게시판 ID → URL 경로 매핑
BOARD_URLS = {
    "phone":   "/phone",     # 스마트폰
    "hotdeal": "/hotdeal",   # 핫딜
}


class FmkoreaScraper:
    SOURCE = "fmkorea"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.fmkorea.com",
        })

    def scrape(self) -> list:
        cutoff    = datetime.now() - timedelta(days=SCRAPE_DAYS)
        all_posts = []
        seen_ids  = set()

        for board_id in FMKOREA_BOARDS:
            board_path = BOARD_URLS.get(board_id, f"/{board_id}")
            print(f"  [펨코] {board_id} 게시판 수집 중...")
            page = 1
            consecutive_old = 0

            while True:
                try:
                    posts, all_old = self._scrape_page(board_path, page, cutoff, seen_ids)
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
                    print(f"  [펨코] {board_id} {page}p 에러: {e}")
                    break

        print(f"  [펨코] 총 {len(all_posts)}개 수집")
        return all_posts

    # ──────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────

    def _scrape_page(self, board_path: str, page: int, cutoff: datetime, seen_ids: set):
        url  = f"{BASE_URL}{board_path}?page={page}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        resp.close()

        posts   = []
        page_has_new = False

        # FMKorea XE 게시판 구조: ul.board_list > li
        items = soup.select("ul.board_list > li")
        # hotdeal은 다른 클래스일 수 있으므로 fallback
        if not items:
            items = soup.select("li.li_hotdeal_var") or soup.select("div.fm_best_widget ul li")

        for item in items:
            try:
                # 공지 제외
                if "notice" in item.get("class", []):
                    continue

                # 링크 & 게시글 ID
                a_tag = item.select_one("a[href]")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                post_id = self._extract_id(href)
                if not post_id or post_id in seen_ids:
                    continue

                # 제목
                title_elem = item.select_one(".title") or item.select_one("a.hotdeal_var8") or a_tag
                title = title_elem.get_text(strip=True) if title_elem else ""
                # 댓글 수 제거 [N]
                title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()
                if not title:
                    continue

                # 날짜
                time_elem = item.select_one(".time, .date, time")
                posted_at = self._parse_date(time_elem.get_text(strip=True) if time_elem else "")
                if posted_at < cutoff:
                    continue
                page_has_new = True

                # 조회수
                views    = self._extract_num(item.select_one(".count, .view_count, .hit"))
                comments = self._extract_num(item.select_one(".reply_num, .comment"))

                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"

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
        all_old = (not page_has_new and len(items) > 0)
        return posts, all_old

    def _extract_id(self, href: str) -> str:
        # /board/12345678 또는 ?document_srl=12345678
        m = re.search(r"/(\d{6,})", href) or re.search(r"document_srl=(\d+)", href)
        return m.group(1) if m else ""

    def _extract_num(self, elem) -> int:
        if not elem:
            return 0
        m = re.search(r"(\d[\d,]*)", elem.get_text(strip=True))
        return int(m.group(1).replace(",", "")) if m else 0

    def _parse_date(self, text: str) -> datetime:
        """
        펨코 날짜 형식:
          - "2026.04.14 10:30"
          - "2026-04-14"
          - "04.14 10:30"  (올해)
          - "10:30"        (오늘)
        """
        s = text.strip()
        try:
            # "HH:MM" or "HH:MM:SS" (오늘)
            if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", s):
                parts = s.split(":")
                return datetime.now().replace(
                    hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0
                )
            # "YYYY.MM.DD HH:MM"
            m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})", s)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))
            # "YYYY.MM.DD"
            m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", s)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]))
            # "MM.DD HH:MM" (올해)
            m = re.match(r"(\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})", s)
            if m:
                return datetime(datetime.now().year, int(m[1]), int(m[2]), int(m[3]), int(m[4]))
        except Exception:
            pass
        return datetime.now()
