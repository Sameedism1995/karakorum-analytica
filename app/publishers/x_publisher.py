import json
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.x_client import get_x_write_client
from app.models.draft_post import DraftPost
from app.models.posted_item import PostedItem


def post_draft_to_x(db: Session, draft: DraftPost) -> dict:
    """
    Post approved draft to X/Twitter.
    Disabled unless X_POSTING_ENABLED=true in environment.
    """
    settings = get_settings()
    if not settings.x_posting_enabled:
        return {
            "success": False,
            "error": "X posting is disabled. Set X_POSTING_ENABLED=true to enable (Phase 1 default: off).",
        }

    if not settings.x_oauth_configured:
        return {
            "success": False,
            "error": (
                "X OAuth credentials missing. Posting requires X_API_KEY, X_API_SECRET, "
                "X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET (not bearer token alone)."
            ),
        }

    if draft.status != "approved":
        return {"success": False, "error": "Draft must be approved before posting."}

    try:
        client = get_x_write_client()
        response = client.create_tweet(text=draft.post_text[:280])
        tweet_id = str(response.data["id"])
        post_url = f"https://x.com/i/web/status/{tweet_id}"

        draft.status = "posted"
        draft.posted_at = datetime.now(timezone.utc)
        draft.x_post_id = tweet_id

        posted = PostedItem(
            draft_post_id=draft.id,
            platform="x",
            platform_post_id=tweet_id,
            post_url=post_url,
            posted_at=datetime.now(timezone.utc),
            response_json=json.dumps({"id": tweet_id}),
        )
        db.add(posted)
        db.commit()

        logger.info(f"Posted draft {draft.id} to X: {post_url}")
        return {"success": True, "post_url": post_url, "x_post_id": tweet_id}
    except Exception as exc:
        logger.error(f"X posting failed: {exc}")
        return {"success": False, "error": str(exc)}
