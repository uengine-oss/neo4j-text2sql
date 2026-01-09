"""Query history API router"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.history import (
    QueryHistory,
    QueryHistoryCreate,
    QueryHistoryResponse,
    history_repo
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=QueryHistoryResponse)
async def list_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in question or SQL")
):
    """
    List query history with pagination and optional filters.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **status**: Filter by status (completed, error, pending)
    - **search**: Search keyword in question or SQL
    """
    return history_repo.list(
        page=page,
        page_size=page_size,
        status=status,
        search=search
    )


@router.get("/{id}", response_model=QueryHistory)
async def get_history(id: int):
    """Get a specific history entry by ID."""
    entry = history_repo.get_by_id(id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    return entry


@router.post("", response_model=QueryHistory)
async def create_history(entry: QueryHistoryCreate):
    """
    Create a new history entry.
    
    This is typically called automatically when a query completes,
    but can also be called manually.
    """
    return history_repo.create(entry)


@router.delete("/{id}")
async def delete_history(id: int):
    """Delete a specific history entry."""
    deleted = history_repo.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"message": "History entry deleted", "id": id}


@router.delete("")
async def delete_all_history():
    """Delete all history entries."""
    count = history_repo.delete_all()
    return {"message": f"Deleted {count} history entries", "count": count}

