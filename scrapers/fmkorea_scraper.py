"""
scrapers/fmkorea_scraper.py
──────────────────────────────────────
펨코(FMKorea) 크롤러
대상: www.fmkorea.com (모바일 버전 사용 - 봇 차단 우회)
──────────────────────────────────────
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config import FMKOREA_BOARDS, SCRAPE_DAYS

BASE_URL = "https://www.fmkorea.com"

BOARD_URLS = {
    "phone":   "/phone",
    "hotdeal": "/hotdeal",
}


class FmkoreaScraper:
    SOURCE = "fmkorea"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            # 모바일 UA로 변경 (봇 차단 우회)
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.6367.82 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

    def scrape(self) -> list:
        # 첫 요청으로 쿠키 획득
        try:
            self.session.get(BASE_URL, timeout=15)
            time.sleep(1)
        except Exception:
            pass

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
                    time.sleep(1)
                except Exception as e:
                    print(f"  [펨코] {board_id} {page}p 에러: {e}")
                    break

        print(f"  [펨코] 총 {len(all_posts)}개 수집")
        return all_posts

    def _scrape_page(self, board_path: str, page: int, cutoff: datetime, seen_ids: set):
        url  = f"{BASE_URL}{board_path}?page={page}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        resp.close()

        posts        = []
        page_has_new = False

        # FMKorea 게시판 구조 (여러 셀렉터 시도)
        items = (
            soup.select("ul.bd_lst > li") or
            soup.select("ul.board_list > li") or
            soup.select("ul.list_board > li") or
            soup.select("li.li_bd") or
            soup.select("div.bd_lst_wrp li")
        )

        print(f"  [펨코] {board_path} {page}p → 항목 {len(items)}개 발견")

        for item in items:
            try:
                classes = item.get("class", [])
                if any(c in classes for c in ["notice", "li_notice", "ad"]):
                    continue

                # 제목 & 링크
                title_elem = (
                    item.select_one("h3.title a") or
                    item.select_one("span.title a") or
                    item.select_one(".bd_lst_inner a") or
                    item.select_one("a.hotdeal_var8") or
                    item.select_one("a[href*='/board/']") or
                    item.select_one("a[href*='/hotdeal/']")
                )
                if not title_elem:
                    continue

                href    = title_elem.get("href", "")
                post_id = self._extract_id(href)
                if not post_id or post_id in seen_ids:
                    continue

                title = title_elem.get_text(strip=True)
                title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()
                if not title:
                    continue

                # 날짜
                time_elem = item.select_one("span.time, span.date, time, .time, abbr")
                posted_at = self._parse_date(time_elem.get_text(strip=True) if time_elem else "")
                if posted_at < cutoff:
                    continue
                page_has_new = True

                views    = self._extract_num(item.select_one(".count, .hit, .view_count, span.read, .reads"))
                comments = self._extract_num(item.select_one(".reply_num, .comment_num, .replyCount, .cmt"))

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
            except Exception as e:
                print(f"  [펨코] 항목 파싱 에러: {e}")
                continue

        soup.decompose()
        all_old = (not page_has_new and len(items) > 0)
        return posts, all_old

    def _extract_id(self, href: str) -> str:
        m = re.search(r"/(\d{6,})", href) or re.search(r"document_srl=(\d+)", href)
        return m.group(1) if m else ""

    def _extract_num(self, elem) -> int:
        if not elem:
            return 0
        m = re.search(r"(\d[\d,]*)", elem.get_text(strip=True))
        return int(m.group(1).replace(",", "")) if m else 0

    def _parse_date(self, text: str) -> datetime:
        s = text.strip()
        try:
            if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", s):
                parts = s.split(":")
                return datetime.now().replace(
                    hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0
                )
            m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})", s)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))
            m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", s)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]))
            m = re.match(r"(\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})", s)
            if m:
                return datetime(datetime.now().year, int(m[1]), int(m[2]), int(m[3]), int(m[4]))
        except Exception:
            pass
        return datetime.now()
