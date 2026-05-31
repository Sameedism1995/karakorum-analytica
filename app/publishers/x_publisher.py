import json
from datetime import datetime, timezone

from loguru import logger

from app.config import get_settings
from app.models.draft_post import DraftPost
from app.models.posted_item import PostedItem
from sqlalchemy.orm import Session


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

    if draft.status != "approved":
        return {"success": False, "error": "Draft must be approved before posting."}

    try:
        import tweepy

        if settings.x_bearer_token:
            client = tweepy.Client(bearer_token=settings.x_bearer_token)
        else:
            client = tweepy.Client(
                consumer_key=settings.x_api_key,
                consumer_secret=settings.x_api_secret,
                access_token=settings.x_access_token,
                access_token_secret=settings.x_access_token_secret,
            )

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
