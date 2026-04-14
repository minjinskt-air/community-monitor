"""
scrapers/ppomppu_scraper.py
──────────────────────────────────────
뽐뿌 커뮤니티 크롤러
대상: m.ppomppu.co.kr (모바일 버전)
──────────────────────────────────────
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config import PPOMPPU_BOARDS, SCRAPE_DAYS

BASE_URL = "https://m.ppomppu.co.kr/new/bbs_list.php"
POP_URL  = "https://m.ppomppu.co.kr/new/pop_bbs.php"

POP_BOARDS = ["ppomppu", "ppomppu2", "phone"]


class PpomppuScraper:
    SOURCE = "ppomppu"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
            )
        })

    def scrape(self) -> list:
        cutoff = datetime.now() - timedelta(days=SCRAPE_DAYS)
        all_posts = []
        seen_ids  = set()

        # 일반 게시판
        for board_id in PPOMPPU_BOARDS:
            print(f"  [뽐뿌] {board_id} 게시판 수집 중...")
            page = 1
            consecutive_old = 0

            while True:
                try:
                    posts, all_old, total = self._scrape_page(board_id, page, cutoff, seen_ids)
                    if all_old or (not posts and total == 0):
                        consecutive_old += 1
                        if consecutive_old >= 2:
                            break
                    else:
                        consecutive_old = 0
                    all_posts.extend(posts)
                    page += 1
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  [뽐뿌] {board_id} {page}p 에러: {e}")
                    break

        # 인기 게시판
        for board_id in POP_BOARDS:
            try:
                pop_posts = self._scrape_pop(board_id, cutoff, seen_ids)
                all_posts.extend(pop_posts)
            except Exception as e:
                print(f"  [뽐뿌] 인기:{board_id} 에러: {e}")

        print(f"  [뽐뿌] 총 {len(all_posts)}개 수집")
        return all_posts

    # ──────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────

    def _scrape_page(self, board_id, page_num, cutoff, seen_ids):
        url = f"{BASE_URL}?id={board_id}&page={page_num}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        resp.close()

        posts = []
        links = soup.select('a[href*="bbs_view.php"]')
        links = [
            l for l in links
            if "notice" not in l.get("href", "")
            and any(c in l.get("class", []) for c in ["noeffect", "list_b_01n", "list_b_02n", "list_b_03n"])
        ]
        total = 0

        for link in links:
            try:
                href = link.get("href", "")
                match = re.search(r"no=(\d+)", href)
                if not match:
                    continue
                post_id = match.group(1)
                if post_id in seen_ids:
                    continue
                total += 1

                title = self._parse_title(link)
                if not title or len(title) > 200:
                    continue

                # 날짜
                time_elem = link.select_one("time")
                posted_at = self._parse_date(time_elem.get_text(strip=True) if time_elem else "")
                if posted_at < cutoff:
                    continue

                full_url = f"https://m.ppomppu.co.kr{href}" if href.startswith("/") else href
                views    = self._extract_num(link.select_one(".view"))
                comments = self._extract_num(link.select_one(".rp"))

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
        all_old = (len(posts) == 0 and total > 0)
        return posts, all_old, total

    def _scrape_pop(self, board_id, cutoff, seen_ids):
        posts = []
        for page in range(1, 6):
            url = f"{POP_URL}?id={board_id}&bot_type=pop_bbs&page={page}"
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")
                resp.close()
                page_new = 0

                for link in soup.select('a[href*="bbs_view.php"]'):
                    try:
                        href = link.get("href", "")
                        match = re.search(r"no=(\d+)", href)
                        if not match:
                            continue
                        post_id = match.group(1)
                        if post_id in seen_ids:
                            continue

                        title = self._parse_title(link)
                        if not title or len(title) > 200:
                            continue

                        time_elem = link.select_one("time")
                        posted_at = self._parse_date(time_elem.get_text(strip=True) if time_elem else "")
                        if posted_at < cutoff:
                            continue

                        full_url = f"https://m.ppomppu.co.kr{href}" if href.startswith("/") else href
                        views    = self._extract_num(link.select_one(".view"))
                        comments = self._extract_num(link.select_one(".rp"))

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
                        page_new += 1
                    except Exception:
                        continue

                soup.decompose()
                if page_new == 0:
                    break
                time.sleep(0.3)
            except Exception as e:
                print(f"  [뽐뿌] 인기:{board_id} {page}p 에러: {e}")
                break
        return posts

    def _parse_title(self, link):
        cont = link.select_one("span.cont")
        if cont:
            for img in cont.find_all("img"):
                img.decompose()
            return cont.get_text(strip=True)
        strong = link.select_one("strong")
        if strong:
            for tag in strong.find_all(["img", "span"]):
                tag.decompose()
            return strong.get_text(strip=True)
        return ""

    def _extract_num(self, elem) -> int:
        if not elem:
            return 0
        m = re.search(r"(\d[\d,]*)", elem.get_text(strip=True))
        return int(m.group(1).replace(",", "")) if m else 0

    def _parse_date(self, time_str: str) -> datetime:
        s = time_str.strip()
        try:
            if ":" in s and len(s.split(":")) == 3:
                return datetime.combine(datetime.today(), datetime.strptime(s, "%H:%M:%S").time())
            if "-" in s and len(s) <= 8:
                parts = s.split("-")
                year = int(parts[0])
                if year < 100:
                    year += 2000
                return datetime(year, int(parts[1]), int(parts[2]))
        except Exception:
            pass
        return datetime.now()
