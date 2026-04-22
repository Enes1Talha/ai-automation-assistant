from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.api.schemas.mail_schema import ProcessResult
from backend.api.services.pipeline_service import PipelineService
from backend.api.dependencies import get_pipeline

router = APIRouter(tags=["pipeline"])


@router.get("/process-mails", response_model=ProcessResult)
async def process_mails(
    db: Session = Depends(get_db),
    pipeline: PipelineService = Depends(get_pipeline),
) -> ProcessResult:
    result = await pipeline.run(db)
    processed = result["processed"]
    errors = result["errors"]

    return ProcessResult(
        success=len(errors) == 0 or processed > 0,
        processed=processed,
        errors=errors,
        message=f"Processed {processed} email(s) with {len(errors)} error(s)",
    )
