from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.schemas import AnalyzeRequest, AnalyzeResponse
from src.data.repositories import Repository
from src.orchestration.graph import build_graph

router = APIRouter(prefix="/api/v1/affordability")
_repository = Repository()
_graph = build_graph(_repository)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        request = _repository.get_request(payload.request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown request_id") from exc
    result = _graph.invoke({"request_id": request.request_id, "request": request})
    decision = result["decision"]
    row = decision.to_row()
    return AnalyzeResponse(**row)


@router.get("/{request_id}", response_model=AnalyzeResponse)
def get_result(request_id: str) -> AnalyzeResponse:
    return analyze(AnalyzeRequest(request_id=request_id))
