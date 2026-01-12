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
    
    # Full steps detail - 도구 호출의 전체 과정
    steps: Optional[List[Dict[str, Any]]] = None


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
    steps: Optional[List[Dict[str, Any]]] = None  # 전체 도구 호출 과정


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
                steps TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_created_at 
            ON query_history(created_at DESC)
        """)
        
        # Migration: Add steps column if not exists
        cursor.execute("PRAGMA table_info(query_history)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'steps' not in columns:
            cursor.execute("ALTER TABLE query_history ADD COLUMN steps TEXT")
        
        conn.commit()
        conn.close()
    
    def _row_to_model(self, row: tuple) -> QueryHistory:
        """Convert SQLite row to QueryHistory model"""
        # Column order (after ALTER TABLE ADD steps):
        # 0:id, 1:question, 2:final_sql, 3:validated_sql, 4:execution_result,
        # 5:row_count, 6:status, 7:error_message, 8:steps_count, 9:execution_time_ms,
        # 10:metadata, 11:created_at, 12:updated_at, 13:steps
        
        steps = None
        created_at = row[11] if len(row) > 11 else None
        updated_at = row[12] if len(row) > 12 else None
        
        # steps는 ALTER TABLE로 추가되어 마지막(인덱스 13)에 있음
        if len(row) > 13 and row[13]:
            try:
                steps = json.loads(row[13])
            except (json.JSONDecodeError, TypeError):
                steps = None
        
        # execution_result와 metadata도 안전하게 파싱
        execution_result = None
        if row[4]:
            try:
                execution_result = json.loads(row[4])
            except (json.JSONDecodeError, TypeError):
                execution_result = None
        
        metadata = None
        if row[10]:
            try:
                metadata = json.loads(row[10])
            except (json.JSONDecodeError, TypeError):
                metadata = None
        
        return QueryHistory(
            id=row[0],
            question=row[1],
            final_sql=row[2],
            validated_sql=row[3],
            execution_result=execution_result,
            row_count=row[5],
            status=row[6],
            error_message=row[7],
            steps_count=row[8],
            execution_time_ms=row[9],
            metadata=metadata,
            steps=steps,
            created_at=created_at,
            updated_at=updated_at
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
             steps, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(entry.steps) if entry.steps else None,
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

