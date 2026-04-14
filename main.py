"""
main.py
──────────────────────────────────────
커뮤니티 알뜰폰 모니터링 - 메인 실행 파일
실행: python main.py
──────────────────────────────────────
"""

import time
import traceback
import schedule
from datetime import datetime

from scrapers.ppomppu_scraper import PpomppuScraper
from scrapers.fmkorea_scraper  import FmkoreaScraper
from scrapers.dcinside_scraper import DcinsideScraper
from core.filter        import apply_filter
from core.db_handler    import DBHandler
from core.slack_notifier import send_summary, send_error, send_heartbeat
from config import SCHEDULE_INTERVAL_MINUTES


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_monitor():
    """크롤링 → 필터링 → 중복제거 → 슬랙 발송"""
    log("=" * 50)
    log("모니터링 시작")

    db = DBHandler()

    try:
        # ── 1. 크롤링 ──────────────────────────────
        all_posts = []

        log("▶ 뽐뿌 크롤링...")
        try:
            all_posts += PpomppuScraper().scrape()
        except Exception as e:
            log(f"  뽐뿌 에러: {e}")

        log("▶ 펨코 크롤링...")
        try:
            all_posts += FmkoreaScraper().scrape()
        except Exception as e:
            log(f"  펨코 에러: {e}")

        log("▶ 디시인사이드 크롤링...")
        try:
            all_posts += DcinsideScraper().scrape()
        except Exception as e:
            log(f"  디시 에러: {e}")

        log(f"총 수집: {len(all_posts)}개")

        if not all_posts:
            log("수집된 게시글 없음 → 종료")
            return

        # ── 2. 키워드 + 조회수 필터링 ──────────────
        log("▶ 필터링...")
        filtered = apply_filter(all_posts)
        if not filtered:
            log("필터 통과 게시글 없음 → 종료")
            return

        # ── 3. 중복(기발송) 제거 ───────────────────
        new_posts = db.filter_new(filtered)
        log(f"신규 게시글: {len(new_posts)}개 (중복 제외 {len(filtered) - len(new_posts)}개)")

        if not new_posts:
            log("발송할 신규 게시글 없음 → 종료")
            return

        # ── 4. 슬랙 발송 ────────────────────────────
        log("▶ 슬랙 발송...")
        send_summary(new_posts)

        # ── 5. 발송 완료 표시 ───────────────────────
        for post in new_posts:
            db.mark_sent(post)

        # ── 6. 오래된 레코드 정리 (30일) ─────────────
        db.cleanup_old(days=30)

        stats = db.stats()
        log(f"완료 | 누적 발송 {stats['total']}건 | {stats['by_source']}")

    except Exception as e:
        error_msg = f"모니터링 에러: {e}\n{traceback.format_exc()}"
        log(error_msg)
        send_error(error_msg[:500])


def run_once():
    """1회 즉시 실행 (테스트용)"""
    run_monitor()


def run_scheduled():
    """주기 실행 (cron 없이 process로 돌릴 때)"""
    interval = SCHEDULE_INTERVAL_MINUTES
    log(f"스케줄 시작: {interval}분마다 실행")

    # 시작 즉시 1회 실행
    run_monitor()

    schedule.every(interval).minutes.do(run_monitor)
    # 매일 09:00에 상태 알림
    schedule.every().day.at("09:00").do(
        lambda: send_heartbeat(DBHandler().stats())
    )

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import sys

    # python main.py once  → 1회 실행 (테스트)
    # python main.py       → 스케줄 모드 (2시간마다 반복)
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        run_once()
    else:
        run_scheduled()
