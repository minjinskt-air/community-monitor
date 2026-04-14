"""
scrapers/dcinside_scraper.py
──────────────────────────────────────
디시인사이드 갤러리 크롤러
대상: gall.dcinside.com (알뜰폰 갤러리 id=mvno, 미니갤)
──────────────────────────────────────
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config import DCINSIDE_GALLERIES, SCRAPE_DAYS

GALL_URL = "https://gall.dcinside.com/board/lists/"
MINI_URL = "https://gall.dcinside.com/mgallery/board/lists/"


class DcinsideScraper:
    SOURCE = "dcinside"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://gall.dcinside.com",
        })

    def scrape(self) -> list:
        cutoff    = datetime.now() - timedelta(days=SCRAPE_DAYS)
        all_posts = []
        seen_ids  = set()

        for gallery_id, is_mini in DCINSIDE_GALLERIES:
            base_url = MINI_URL if is_mini else GALL_URL
            print(f"  [디시] {gallery_id} {'미니갤' if is_mini else '일반갤'} 수집 중... URL: {base_url}")

            page = 1
            consecutive_old = 0

            while True:
                try:
                    posts, all_old = self._scrape_page(base_url, gallery_id, page, cutoff, seen_ids)
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

    def _scrape_page(self, base_url: str, gallery_id: str, page: int, cutoff: datetime, seen_ids: set):
        url  = f"{base_url}?id={gallery_id}&page={page}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        resp.close()

        posts        = []
        page_has_new = False

        rows = soup.select("tr.ub-content")
        print(f"  [디시] {gallery_id} {page}p → 행 {len(rows)}개 발견")

        for row in rows:
            try:
                # 공지·광고 제외
                num_elem = row.select_one("td.gall_num")
                if num_elem:
                    num_text = num_elem.get_text(strip=True)
                    if num_text in ("공지", "AD", "설문", ""):
                        continue

                # 제목 & 링크
                title_elem = row.select_one("td.gall_tit a")
                if not title_elem:
                    continue

                href = title_elem.get("href", "")
                for em in title_elem.find_all("em"):
                    em.decompose()
                title = title_elem.get_text(strip=True)
                title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()
                if not title:
                    continue

                post_id = self._extract_id(href)
                if not post_id or post_id in seen_ids:
                    continue

                # 날짜
                date_elem = row.select_one("td.gall_date")
                if date_elem:
                    date_str = date_elem.get("title") or date_elem.get_text(strip=True)
                else:
                    date_str = ""
                posted_at = self._parse_date(date_str)
                if posted_at < cutoff:
                    continue
                page_has_new = True

                views    = self._extract_num(row.select_one("td.gall_count"))
                comments = self._extract_num(row.select_one("td.gall_comment"))

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
            except Exception as e:
                print(f"  [디시] 행 파싱 에러: {e}")
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
        s = text.strip()
        try:
            m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
            if m:
                return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))
            m = re.match(r"(\d{1,2})[.\-](\d{1,2})\s+(\d{1,2}):(\d{2})", s)
            if m:
                return datetime(datetime.now().year, int(m[1]), int(m[2]), int(m[3]), int(m[4]))
            m = re.match(r"(\d{1,2}):(\d{2})", s)
            if m:
                return datetime.now().replace(
                    hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0
                )
        except Exception:
            pass
        return datetime.now()
