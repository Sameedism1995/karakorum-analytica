from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.llm_dashboard import (
    AuditPostRequest,
    AuditPostResponse,
    GeneratePostRequest,
    GeneratePostResponse,
    KeywordPostRequest,
    KeywordPostResponse,
    SavePostRequest,
    SeoRequest,
    SeoResponse,
    UpdateStatusRequest,
)
from app.services.llm_newsroom_service import (
    audit_post,
    delete_saved_post,
    generate_post,
    keyword_post,
    list_saved_posts,
    save_post,
    seo_assist,
    update_post_status,
)

router = APIRouter(prefix="/dashboard", tags=["LLM Dashboard"])


@router.post("/generate-post", response_model=GeneratePostResponse)
def dashboard_generate_post(body: GeneratePostRequest) -> GeneratePostResponse:
    return generate_post(body)


@router.post("/keyword-post", response_model=KeywordPostResponse)
def dashboard_keyword_post(body: KeywordPostRequest) -> KeywordPostResponse:
    return keyword_post(body)


@router.post("/audit-post", response_model=AuditPostResponse)
def dashboard_audit_post(body: AuditPostRequest) -> AuditPostResponse:
    return audit_post(body)


@router.post("/seo", response_model=SeoResponse)
def dashboard_seo(body: SeoRequest) -> SeoResponse:
    return seo_assist(body)


@router.get("/posts")
def dashboard_list_posts(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    items = list_saved_posts(db, limit=limit)
    return {"count": len(items), "items": items}


@router.post("/posts/save")
def dashboard_save_post(body: SavePostRequest, db: Session = Depends(get_db)) -> dict:
    record = save_post(db, body)
    return {"message": "Saved", "post": record}


@router.put("/posts/{post_id}/status")
def dashboard_update_status(
    post_id: int,
    body: UpdateStatusRequest,
    db: Session = Depends(get_db),
) -> dict:
    record = update_post_status(db, post_id, body.status)
    if not record:
        raise HTTPException(status_code=404, detail="Saved post not found")
    return {"message": "Status updated", "post": record}


@router.delete("/posts/{post_id}")
def dashboard_delete_post(post_id: int, db: Session = Depends(get_db)) -> dict:
    deleted = delete_saved_post(db, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved post not found")
    return {"message": "Deleted", "id": post_id}
