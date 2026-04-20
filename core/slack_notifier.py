"""
core/slack_notifier.py
──────────────────────────────────────
슬랙 Incoming Webhook 발송 (Block Kit 카드 형식)
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
    "dcinside": "📱",
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


def _build_post_blocks(post: dict) -> list:
    """게시글 1개를 Block Kit 블록 리스트로 변환"""
    source   = post.get("source", "unknown")
    label    = SOURCE_LABEL.get(source, source)
    emoji    = SOURCE_EMOJI.get(source, "📌")
    views    = post.get("views", 0)
    posted   = post.get("posted_at")
    date_str = posted.strftime("%m-%d %H:%M") if hasattr(posted, "strftime") else str(posted)
    keywords = post.get("matched_keywords", [])
    kw_tags  = "  ".join(f"`{kw}`" for kw in keywords)
    title    = post.get("title", "")
    url      = post.get("url", "")

    return [
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"{emoji}  *{label}*  ·  {date_str}"
            }]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{url}|{title}>*"
            }
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"조회 {views:,}   {kw_tags}"
            }]
        },
        {"type": "divider"},
    ]


def send_summary(posts: list):
    """전체 게시글을 카드 1장으로 묶어서 발송"""
    if not posts:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    blocks = [
        # ── 헤더 ──────────────────────────────────
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔔  *알뜰폰 커뮤니티 모니터링*\n{now}"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": f"신규 {len(posts)}건",
                    "emoji": True
                },
                "style": "primary"
            }
        },
        {"type": "divider"},
    ]

    # ── 게시글 블록 추가 (Slack 최대 50블록 고려하여 분할) ──
    BLOCK_PER_POST = 4   # context + section + context + divider
    MAX_POSTS = (50 - 2) // BLOCK_PER_POST  # 헤더 2블록 제외

    for post in posts[:MAX_POSTS]:
        blocks.extend(_build_post_blocks(post))

    if len(posts) > MAX_POSTS:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"_외 {len(posts) - MAX_POSTS}건 추가 발견 (한도 초과로 생략)_"
            }]
        })

    ok = _send_raw({
        "channel":      SLACK_CHANNEL,
        "blocks":       blocks,
        "unfurl_links": False,
    })

    print(f"[Slack] {'발송 완료' if ok else '발송 실패'} ({len(posts)}건)")


def send_error(msg: str):
    """에러 알림"""
    _send_raw({
        "channel": SLACK_CHANNEL,
        "text":    f"❌ *[모니터링 에러]*\n{msg}",
    })


def send_heartbeat(stats: dict):
    """정상 동작 확인용 주기 메시지 (선택)"""
    now      = datetime.now().strftime("%Y-%m-%d %H:%M")
    by_src   = "\n".join(
        f"  • {SOURCE_LABEL.get(k, k)}: {v}건"
        for k, v in stats.get("by_source", {}).items()
    )
    _send_raw({
        "channel": SLACK_CHANNEL,
        "text": (
            f"💚 *모니터링 정상 동작 중* | {now}\n"
            f"누적 발송: {stats.get('total', 0)}건\n{by_src}"
        ),
        "unfurl_links": False,
    })
