"""End-to-end pipeline test: Ollama draft → Supabase → approve → Buffer."""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.services.buffer_posting_service import post_to_dict
from app.services.buffer_validation_service import validate_post_for_buffer
from app.services.local_llm_service import get_ollama_health, local_llm_service
from app.services.post_approval_service import approve_and_post_now
from app.services.post_service import approve_post_by_id, create_post_from_local_draft
from app.schemas.local_newsroom import LocalDraftRequest

E2E_RAW_TEXT = (
    "Internal system test: Karakorum Analytica pipeline check. "
    "No real incident — safe for testing only."
)

E2E_FALLBACK_POST_TEXT = (
    "Test post from Karakorum Analytica local LLM pipeline. "
    "Official confirmation is pending. This is an internal system test."
)


def run_e2e_local_to_buffer(db: Session, *, dry_run: bool = True) -> dict[str, Any]:
    """Run full pipeline test.

    dry_run=True: approve + validate only (no Buffer call).
    dry_run=False: approve-and-post-now (Buffer shareNow) to X.
    """
    logger.info(f"E2E pipeline start dry_run={dry_run}")

    result: dict[str, Any] = {"ok": False, "dry_run": dry_run, "steps": {}}

    ollama = get_ollama_health()
    result["steps"]["ollama"] = ollama
    logger.info(
        f"E2E ollama enabled={ollama.get('enabled')} reachable={ollama.get('server_reachable')} "
        f"model_available={ollama.get('model_available')}"
    )
    if not ollama.get("server_reachable") or not ollama.get("model_available"):
        result["error"] = ollama.get("error") or "Ollama is not ready"
        return result

    draft_req = LocalDraftRequest(
        raw_text=E2E_RAW_TEXT,
        source_name="Karakorum Analytica E2E Test",
        source_url="https://karakorum-analytica.internal/test",
        location="Pakistan",
        category="system/test",
        verification_status="unverified",
        source_grade="C",
        save=False,
    )
    try:
        draft = local_llm_service.draft_local(db, draft_req)
        result["steps"]["draft"] = draft.model_dump()
        logger.info(f"E2E draft generated post_text_len={len(draft.post_text)}")
    except Exception as exc:
        logger.warning(f"E2E Ollama draft failed, using safe fallback: {exc}")
        draft = None
        result["steps"]["draft"] = {"error": str(exc), "fallback": True}

    post_text = E2E_FALLBACK_POST_TEXT
    headline = "Karakorum Analytica pipeline test"
    if draft and draft.post_text:
        post_text = draft.post_text[:280]
        headline = draft.headline or headline

    post = create_post_from_local_draft(
        db,
        headline=headline,
        post_text=post_text,
        source_name="Karakorum Analytica E2E Test",
        source_url="https://karakorum-analytica.internal/test",
        verification_status="unverified",
        source_grade="C",
        risk_flags=["e2e_test"],
        editor_notes=["Automated E2E pipeline test — not for publication"],
        publish_recommendation="needs_review",
        status="needs_review",
    )
    result["steps"]["saved"] = {"post_id": post.id, "status": post.status}
    logger.info(f"E2E Supabase insert ok post_id={post.id} status={post.status}")

    if dry_run:
        approved = approve_post_by_id(db, post.id)
        result["steps"]["approved"] = {"post_id": approved.id, "status": approved.status}
        logger.info(f"E2E approved post_id={approved.id}")

        ok, reason = validate_post_for_buffer(approved)
        result["steps"]["validation"] = {"ok": ok, "reason": reason or None}
        logger.info(f"E2E validation ok={ok} reason={reason or 'pass'}")

        if not ok:
            result["error"] = reason
            result["post"] = post_to_dict(approved)
            return result

        result["ok"] = True
        result["message"] = "Dry run complete — draft saved and approved; Buffer not called"
        result["post"] = post_to_dict(approved)
        logger.info(f"E2E dry_run complete post_id={approved.id}")
        return result

    # Live path: approve-and-post-now via Buffer shareNow (no queue).
    approve_result = approve_and_post_now(db, post.id)
    result["steps"]["approve_and_post_now"] = {
        "post_id": post.id,
        "buffer_ok": approve_result.get("ok"),
        "status": (approve_result.get("post") or {}).get("status"),
    }
    result["ok"] = bool(approve_result.get("ok"))
    result["message"] = (
        "Live E2E complete — post approved and published to X through Buffer (shareNow)."
        if approve_result.get("ok")
        else "Live E2E failed — Buffer publish-now failed."
    )
    if approve_result.get("ok"):
        logger.info(f"E2E live complete post_id={post.id} status=posted")
    else:
        result["error"] = approve_result.get("error") or "Buffer publish-now failed"
        logger.error(f"E2E buffer failed post_id={post.id} error={result['error'][:120]}")
    result["post"] = approve_result.get("post") or post_to_dict(post)

    return result
