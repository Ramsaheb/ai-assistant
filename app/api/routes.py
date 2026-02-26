from fastapi import APIRouter, HTTPException
from app.models.schemas import QueryRequest, QueryResponse
from app.services.agent import process_query
from app.utils.logger import logger

router = APIRouter(prefix="/api", tags=["BI Agent"])


@router.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """Process a business intelligence question and return an AI-generated answer."""
    logger.info(f"Incoming query: {request.question!r}")
    result = await process_query(
        request.question,
        conversation_history=[
            {"role": m.role, "content": m.content}
            for m in request.conversation_history[-10:]  # cap at 10 turns
        ],
    )
    return result


@router.get("/health")
async def health():
    """Lightweight health check."""
    return {"status": "healthy"}