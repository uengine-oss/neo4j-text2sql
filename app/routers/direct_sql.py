"""
Direct SQL 실행 라우터
- SQL 직접 입력 및 실행
- AI 결과 포맷팅 (선택적)
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.deps import get_db_connection, get_openai_client
from app.core.sql_exec import SQLExecutor, SQLExecutionError
from app.core.sql_guard import SQLGuard, SQLValidationError
from app.smart_logger import SmartLogger


router = APIRouter(prefix="/direct-sql", tags=["Direct SQL"])


class DirectSqlRequest(BaseModel):
    sql: str = Field(..., description="실행할 SQL 쿼리")
    max_sql_seconds: int = Field(default=60, ge=1, le=3600, description="SQL 실행 최대 허용 시간(초)")
    format_with_ai: bool = Field(default=False, description="AI로 결과 포맷팅 여부")


class DirectSqlResponse(BaseModel):
    status: str  # success, error
    sql: str
    validated_sql: Optional[str] = None
    columns: List[str] = []
    rows: List[List[Any]] = []
    row_count: int = 0
    execution_time_ms: float = 0
    error_message: Optional[str] = None
    formatted_summary: Optional[str] = None  # AI 포맷팅 결과


@router.post("", response_model=DirectSqlResponse)
async def execute_direct_sql(
    request: DirectSqlRequest,
    db_conn=Depends(get_db_connection),
    openai_client=Depends(get_openai_client),
) -> DirectSqlResponse:
    """
    SQL 쿼리를 직접 실행합니다.
    
    - SQL 검증 (읽기 전용)
    - 실행 및 결과 반환
    - 선택적으로 AI가 결과를 요약/포맷팅
    """
    start_time = time.perf_counter()
    
    SmartLogger.log(
        "INFO",
        "direct_sql.request",
        category="direct_sql.request",
        params={"sql": request.sql[:200]},
    )
    
    # 1. SQL 검증
    guard = SQLGuard()
    try:
        validated_sql, _ = guard.validate(request.sql)
    except SQLValidationError as exc:
        SmartLogger.log(
            "WARNING",
            "direct_sql.validation_error",
            category="direct_sql.validation_error",
            params={"error": str(exc)},
        )
        return DirectSqlResponse(
            status="error",
            sql=request.sql,
            error_message=f"SQL 검증 실패: {exc}"
        )
    
    # 2. SQL 실행
    executor = SQLExecutor()
    try:
        raw_result = await executor.execute_query(
            db_conn,
            validated_sql,
            timeout=float(request.max_sql_seconds),
        )
        formatted = executor.format_results_for_json(raw_result)
        
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        columns = formatted.get("columns", [])
        rows = formatted.get("rows", [])
        row_count = formatted.get("row_count", 0)
        
    except SQLExecutionError as exc:
        SmartLogger.log(
            "ERROR",
            "direct_sql.execution_error",
            category="direct_sql.execution_error",
            params={"error": str(exc)},
        )
        return DirectSqlResponse(
            status="error",
            sql=request.sql,
            validated_sql=validated_sql,
            error_message=f"SQL 실행 실패: {exc}"
        )
    
    # 3. AI 포맷팅 (선택적)
    formatted_summary = None
    if request.format_with_ai and rows:
        try:
            formatted_summary = await _format_with_ai(
                openai_client,
                validated_sql,
                columns,
                rows[:20],  # 처음 20행만
                row_count
            )
        except Exception as e:
            SmartLogger.log(
                "WARNING",
                "direct_sql.ai_format_error",
                category="direct_sql.ai_format_error",
                params={"error": str(e)},
            )
    
    SmartLogger.log(
        "INFO",
        "direct_sql.success",
        category="direct_sql.success",
        params={
            "row_count": row_count,
            "execution_time_ms": execution_time_ms,
        },
    )
    
    return DirectSqlResponse(
        status="success",
        sql=request.sql,
        validated_sql=validated_sql,
        columns=columns,
        rows=rows,
        row_count=row_count,
        execution_time_ms=execution_time_ms,
        formatted_summary=formatted_summary,
    )


async def _format_with_ai(
    openai_client,
    sql: str,
    columns: List[str],
    rows: List[List[Any]],
    total_row_count: int
) -> str:
    """AI로 결과 요약/포맷팅"""
    
    # 결과를 간단한 테이블 형태로 변환
    sample_data = []
    for row in rows[:10]:
        row_dict = {columns[i]: row[i] for i in range(len(columns))}
        sample_data.append(row_dict)
    
    prompt = f"""다음 SQL 쿼리 결과를 사용자에게 친절하게 요약해주세요.

SQL:
```sql
{sql}
```

결과 ({total_row_count}개 행):
```json
{json.dumps(sample_data, ensure_ascii=False, indent=2, default=str)[:2000]}
```

요구사항:
1. 결과의 핵심 내용을 2-3문장으로 요약
2. 주요 인사이트나 패턴이 있다면 언급
3. 한국어로 작성
4. 숫자는 읽기 쉽게 포맷팅 (예: 1,234.56)
"""
    
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 데이터 분석 결과를 사용자에게 친절하게 설명하는 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7,
    )
    
    return response.choices[0].message.content


@router.post("/stream")
async def execute_direct_sql_stream(
    request: DirectSqlRequest,
    db_conn=Depends(get_db_connection),
    openai_client=Depends(get_openai_client),
) -> StreamingResponse:
    """
    SQL 쿼리를 실행하고 결과를 스트리밍합니다.
    AI 포맷팅도 스트리밍으로 제공됩니다.
    """
    
    async def event_generator():
        start_time = time.perf_counter()
        
        # 1. SQL 검증
        yield json.dumps({"event": "validating", "message": "SQL 검증 중..."}, ensure_ascii=False) + "\n"
        
        guard = SQLGuard()
        try:
            validated_sql, _ = guard.validate(request.sql)
            yield json.dumps({"event": "validated", "validated_sql": validated_sql}, ensure_ascii=False) + "\n"
        except SQLValidationError as exc:
            yield json.dumps({"event": "error", "message": f"SQL 검증 실패: {exc}"}, ensure_ascii=False) + "\n"
            return
        
        # 2. SQL 실행
        yield json.dumps({"event": "executing", "message": "SQL 실행 중..."}, ensure_ascii=False) + "\n"
        
        executor = SQLExecutor()
        try:
            raw_result = await executor.execute_query(
                db_conn,
                validated_sql,
                timeout=float(request.max_sql_seconds),
            )
            formatted = executor.format_results_for_json(raw_result)
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            result_payload = {
                "event": "result",
                "columns": formatted.get("columns", []),
                "rows": formatted.get("rows", []),
                "row_count": formatted.get("row_count", 0),
                "execution_time_ms": execution_time_ms,
            }
            yield json.dumps(result_payload, ensure_ascii=False, default=str) + "\n"
            
        except SQLExecutionError as exc:
            yield json.dumps({"event": "error", "message": f"SQL 실행 실패: {exc}"}, ensure_ascii=False) + "\n"
            return
        
        # 3. AI 포맷팅 (선택적)
        if request.format_with_ai and formatted.get("rows"):
            yield json.dumps({"event": "formatting", "message": "AI가 결과를 분석 중..."}, ensure_ascii=False) + "\n"
            
            try:
                # AI 응답 스트리밍
                columns = formatted.get("columns", [])
                rows = formatted.get("rows", [])[:10]
                total_row_count = formatted.get("row_count", 0)
                
                sample_data = []
                for row in rows:
                    row_dict = {columns[i]: row[i] for i in range(len(columns))}
                    sample_data.append(row_dict)
                
                prompt = f"""다음 SQL 쿼리 결과를 사용자에게 친절하게 요약해주세요.

SQL:
```sql
{validated_sql}
```

결과 ({total_row_count}개 행):
```json
{json.dumps(sample_data, ensure_ascii=False, indent=2, default=str)[:2000]}
```

요구사항:
1. 결과의 핵심 내용을 2-3문장으로 요약
2. 주요 인사이트나 패턴이 있다면 언급
3. 한국어로 작성
4. 숫자는 읽기 쉽게 포맷팅 (예: 1,234.56)
"""
                
                stream = await openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 데이터 분석 결과를 사용자에게 친절하게 설명하는 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7,
                    stream=True,
                )
                
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield json.dumps({
                            "event": "format_token",
                            "token": chunk.choices[0].delta.content
                        }, ensure_ascii=False) + "\n"
                
                yield json.dumps({"event": "format_done"}, ensure_ascii=False) + "\n"
                
            except Exception as e:
                yield json.dumps({
                    "event": "format_error",
                    "message": f"AI 포맷팅 실패: {str(e)}"
                }, ensure_ascii=False) + "\n"
        
        # 완료
        yield json.dumps({"event": "completed"}, ensure_ascii=False) + "\n"
    
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

