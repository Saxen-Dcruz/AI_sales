from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.core import get_db
from app.schema.usage import RAGQueryRequest, RAGQueryResponse
from app.services.usage import execute_rag_flow

router = APIRouter(prefix="/ai", tags=["RAG"])

@router.post("/query", response_model=RAGQueryResponse)
async def ask_adhaan_ai(payload: RAGQueryRequest, db: Session = Depends(get_db)):
    try:
        response = await execute_rag_flow(
            db=db, 
            question=payload.question, 
            session_id=payload.session_id
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/costs")
async def get_total_costs(db: Session = Depends(get_db)):
    """Quick endpoint for your documentation/admin dashboard."""
    from sqlalchemy import func
    from app.models.usage import RAGUsageLog
    
    total = db.query(func.sum(RAGUsageLog.estimated_cost)).scalar()
    return {"total_usd_spent": float(total or 0.0)}