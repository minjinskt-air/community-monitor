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

BOARD_URLS = {
    "phone":   "/phone",
    "hotdeal": "/hotdeal",
    "stock":   "/stock",
}


class FmkoreaScraper:
    SOURCE = "fmkorea"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.6367.118 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Cache-Control": "max-age=0",
        })

    def scrape(self) -> list:
        # 메인 페이지 먼저 방문해서 쿠키 획득
        try:
            resp = self.session.get(BASE_URL, timeout=15)
            print(f"  [펨코] 메인 접속: {resp.status_code}")
            time.sleep(2)
        except Exception as e:
            print(f"  [펨코] 메인 접속 실패: {e}")

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
                    time.sleep(1.5)
                except Exception as e:
                    print(f"  [펨코] {board_id} {page}p 에러: {e}")
                    break

        print(f"  [펨코] 총 {len(all_posts)}개 수집")
        return all_posts

    def _scrape_page(self, board_path: str, page: int, cutoff: datetime, seen_ids: set):
        # Referer를 이전 페이지로 설정 (자연스러운 브라우징 흉내)
        if page == 1:
            self.session.headers.update({"Referer": BASE_URL})
        else:
            self.session.headers.update({"Referer": f"{BASE_URL}{board_path}?page={page-1}"})

        url  = f"{BASE_URL}{board_path}?page={page}"
        resp = self.session.get(url, timeout=30)
        print(f"  [펨코] {board_path} {page}p → 상태코드: {resp.status_code}")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        resp.close()

        posts        = []
        page_has_new = False

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
