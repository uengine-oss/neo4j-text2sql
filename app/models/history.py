"""Query history model and repository using SQLite"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path

# SQLite database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "history.db"


class QueryHistory(BaseModel):
    """Query history entry"""
    id: Optional[int] = None
    question: str
    final_sql: Optional[str] = None
    validated_sql: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    row_count: Optional[int] = None
    status: str = "pending"  # pending, completed, error
    error_message: Optional[str] = None
    steps_count: Optional[int] = None
    execution_time_ms: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None


class QueryHistoryCreate(BaseModel):
    """Request model for creating a history entry"""
    question: str
    final_sql: Optional[str] = None
    validated_sql: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    row_count: Optional[int] = None
    status: str = "completed"
    error_message: Optional[str] = None
    steps_count: Optional[int] = None
    execution_time_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryHistoryResponse(BaseModel):
    """Response model for history list"""
    items: List[QueryHistory]
    total: int
    page: int
    page_size: int


class HistoryRepository:
    """SQLite-based history repository"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure database and table exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                final_sql TEXT,
                validated_sql TEXT,
                execution_result TEXT,
                row_count INTEGER,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                steps_count INTEGER,
                execution_time_ms REAL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_created_at 
            ON query_history(created_at DESC)
        """)
        
        conn.commit()
        conn.close()
    
    def _row_to_model(self, row: tuple) -> QueryHistory:
        """Convert SQLite row to QueryHistory model"""
        return QueryHistory(
            id=row[0],
            question=row[1],
            final_sql=row[2],
            validated_sql=row[3],
            execution_result=json.loads(row[4]) if row[4] else None,
            row_count=row[5],
            status=row[6],
            error_message=row[7],
            steps_count=row[8],
            execution_time_ms=row[9],
            metadata=json.loads(row[10]) if row[10] else None,
            created_at=row[11],
            updated_at=row[12]
        )
    
    def create(self, entry: QueryHistoryCreate) -> QueryHistory:
        """Create a new history entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO query_history 
            (question, final_sql, validated_sql, execution_result, row_count, 
             status, error_message, steps_count, execution_time_ms, metadata,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.question,
            entry.final_sql,
            entry.validated_sql,
            json.dumps(entry.execution_result) if entry.execution_result else None,
            entry.row_count,
            entry.status,
            entry.error_message,
            entry.steps_count,
            entry.execution_time_ms,
            json.dumps(entry.metadata) if entry.metadata else None,
            now,
            now
        ))
        
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return self.get_by_id(entry_id)  # type: ignore
    
    def get_by_id(self, id: int) -> Optional[QueryHistory]:
        """Get a history entry by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM query_history WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_model(row)
        return None
    
    def list(
        self, 
        page: int = 1, 
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> QueryHistoryResponse:
        """List history entries with pagination"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query
        where_clauses = []
        params: List[Any] = []
        
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        
        if search:
            where_clauses.append("(question LIKE ? OR final_sql LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM query_history WHERE {where_sql}", params)
        total = cursor.fetchone()[0]
        
        # Get paginated results
        offset = (page - 1) * page_size
        cursor.execute(f"""
            SELECT * FROM query_history 
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [page_size, offset])
        
        rows = cursor.fetchall()
        conn.close()
        
        items = [self._row_to_model(row) for row in rows]
        
        return QueryHistoryResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    
    def delete(self, id: int) -> bool:
        """Delete a history entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM query_history WHERE id = ?", (id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def delete_all(self) -> int:
        """Delete all history entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM query_history")
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted


# Global repository instance
history_repo = HistoryRepository()

