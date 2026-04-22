from __future__ import annotations

from backend.api.services.pipeline_service import PipelineService

_pipeline: PipelineService | None = None


def set_pipeline(p: PipelineService) -> None:
    global _pipeline
    _pipeline = p


def get_pipeline() -> PipelineService:
    if _pipeline is None:
        raise RuntimeError("Pipeline not initialised")
    return _pipeline
