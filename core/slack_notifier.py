"""
core/slack_notifier.py
──────────────────────────────────────
슬랙 Incoming Webhook 발송
──────────────────────────────────────
"""

import requests
from datetime import datetime
from config import SLACK_WEBHOOK_URL, SLACK_CHANNEL

SOURCE_LABEL = {
    "ppomppu":  "뽐뿌",
    "fmkorea":  "펨코",
    "dcinside": "디시 알뜰폰갤",
}

SOURCE_EMOJI = {
    "ppomppu":  "🛍",
    "fmkorea":  "🎮",
    "dcinside": "📺",
}


def _send_raw(payload: dict) -> bool:
    """슬랙 Webhook 원문 발송"""
    try:
        r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"[Slack] 발송 실패: {r.status_code} {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[Slack] 에러: {e}")
        return False


def send_post(post: dict) -> bool:
    """게시글 1개 발송"""
    source = post.get("source", "unknown")
    label  = SOURCE_LABEL.get(source, source)
    emoji  = SOURCE_EMOJI.get(source, "📌")

    views    = post.get("views", 0)
    comments = post.get("comments", 0)
    posted   = post.get("posted_at")
    date_str = posted.strftime("%m-%d %H:%M") if hasattr(posted, "strftime") else str(posted)
    keywords = ", ".join(post.get("matched_keywords", []))

    text = (
        f"{emoji} *[{label}]*  |  📅 {date_str}\n"
        f"*{post['title']}*\n"
        f"👁 조회 {views:,}  |  💬 댓글 {comments}\n"
        f"🔑 키워드: {keywords}\n"
        f"🔗 {post['url']}"
    )

    payload = {
        "channel": SLACK_CHANNEL,
        "text":    text,
        "unfurl_links": False,
    }
    return _send_raw(payload)


def send_summary(posts: list, label: str = ""):
    """일괄 발송 + 요약 헤더"""
    if not posts:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = {
        "channel": SLACK_CHANNEL,
        "text": (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 *알뜰폰 커뮤니티 모니터링* {label}\n"
            f"🕐 {now}  |  신규 {len(posts)}건\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "unfurl_links": False,
    }
    _send_raw(header)

    ok = 0
    for post in posts:
        if send_post(post):
            ok += 1

    print(f"[Slack] {ok}/{len(posts)}개 발송 완료")


def send_error(msg: str):
    """에러 알림"""
    _send_raw({
        "channel": SLACK_CHANNEL,
        "text": f"❌ *[모니터링 에러]*\n{msg}",
    })


def send_heartbeat(stats: dict):
    """정상 동작 확인용 주기 메시지 (선택)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    by_source = "\n".join(
        f"  • {SOURCE_LABEL.get(k, k)}: {v}건"
        for k, v in stats.get("by_source", {}).items()
    )
    text = (
        f"💚 *모니터링 정상 동작 중* | {now}\n"
        f"누적 발송: {stats.get('total', 0)}건\n"
        f"{by_source}"
    )
    _send_raw({"channel": SLACK_CHANNEL, "text": text, "unfurl_links": False})
