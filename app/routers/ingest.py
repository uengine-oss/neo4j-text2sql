"""Schema ingestion endpoint with streaming progress"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator

from app.deps import get_neo4j_session, get_db_connection, get_openai_client
from app.ingest.ddl_extract import SchemaExtractor
from app.ingest.to_neo4j import Neo4jSchemaLoader
from app.core.embedding import EmbeddingClient


router = APIRouter(prefix="/ingest", tags=["Ingestion"])


class IngestRequest(BaseModel):
    """Request to ingest schema"""
    db_name: str = "postgres"
    schema: Optional[str] = None
    clear_existing: bool = False


class IngestResponse(BaseModel):
    """Response from ingestion"""
    message: str
    status: str
    tables_loaded: int
    columns_loaded: int
    fks_loaded: int


def emit_event(event_type: str, **data) -> str:
    """Emit a streaming event as NDJSON"""
    payload = {"type": event_type, **data}
    return json.dumps(payload, ensure_ascii=False) + "\n"


async def stream_ingestion(
    db_name: str,
    schema: Optional[str],
    clear_existing: bool,
    neo4j_session,
    db_conn,
    openai_client
) -> AsyncGenerator[str, None]:
    """Stream ingestion progress as NDJSON events"""
    
    stats = {"tables": 0, "columns": 0, "fks": 0, "pks": 0}
    
    try:
        yield emit_event("start", message="🚀 스키마 인제스천 시작")
        
        # Initialize clients
        embedding_client = EmbeddingClient(openai_client)
        loader = Neo4jSchemaLoader(neo4j_session, embedding_client)
        extractor = SchemaExtractor(db_conn)
        
        # Phase 1: Setup
        yield emit_event("phase", phase="setup", message="🔧 Neo4j 스키마 설정 중...")
        await loader.setup_constraints_and_indexes()
        yield emit_event("progress", phase="setup", message="✓ 제약조건 및 인덱스 생성 완료")
        
        # Clear existing if requested
        if clear_existing:
            yield emit_event("phase", phase="clear", message="🗑️ 기존 스키마 데이터 삭제 중...")
            await loader.clear_schema(db_name)
            yield emit_event("progress", phase="clear", message="✓ 기존 데이터 삭제 완료")
        
        # Phase 2: Extract schema metadata
        yield emit_event("phase", phase="extract", message="📊 데이터베이스 스키마 추출 중...")
        
        tables = await extractor.extract_tables(schema)
        yield emit_event("progress", phase="extract", message=f"✓ 테이블 {len(tables)}개 발견")
        
        columns = await extractor.extract_columns(schema)
        yield emit_event("progress", phase="extract", message=f"✓ 컬럼 {len(columns)}개 발견")
        
        foreign_keys = await extractor.extract_foreign_keys(schema)
        yield emit_event("progress", phase="extract", message=f"✓ FK {len(foreign_keys)}개 발견")
        
        primary_keys = await extractor.extract_primary_keys(schema)
        yield emit_event("progress", phase="extract", message=f"✓ PK {len(primary_keys)}개 발견")
        
        # Phase 3: Load tables
        yield emit_event("phase", phase="tables", message=f"📋 테이블 {len(tables)}개 로딩 중...")
        
        for idx, table in enumerate(tables, 1):
            # Create table node
            table_name = table["name"]
            schema_name = table["schema"]
            description = table.get("description") or ""
            
            # Generate embedding
            text = embedding_client.format_table_text(table_name=table_name, description=description, columns=[])
            embedding = await embedding_client.embed_text(text)
            
            query = """
            MERGE (t:Table {db: $db, schema: $schema, name: $name})
            SET t.vector = $vector,
                t.description = COALESCE(t.description, $description),
                t.original_name = $original_name,
                t.updated_at = datetime()
            RETURN t
            """
            
            await neo4j_session.run(
                query,
                db=db_name,
                schema=schema_name.lower(),
                name=table_name.lower(),
                vector=embedding,
                description=description,
                original_name=table_name
            )
            
            stats["tables"] = idx
            
            # Emit node created event
            yield emit_event(
                "node_created",
                nodeType="Table",
                name=table_name,
                schema=schema_name,
                progress=f"{idx}/{len(tables)}",
                percent=round((idx / len(tables)) * 100)
            )
        
        yield emit_event("progress", phase="tables", message=f"✓ 테이블 {len(tables)}개 로드 완료")
        
        # Phase 4: Load columns with embeddings
        yield emit_event("phase", phase="columns", message=f"📝 컬럼 {len(columns)}개 로딩 중...")
        
        # Batch embedding generation
        batch_size = 50
        total_batches = (len(columns) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, len(columns))
            batch = columns[start:end]
            
            # Generate embeddings for batch
            texts = [
                embedding_client.format_column_text(
                    column_name=col["name"],
                    table_name=col["table_name"],
                    dtype=col["dtype"],
                    description=col.get("description", "")
                )
                for col in batch
            ]
            
            embeddings = await embedding_client.embed_batch(texts)
            
            yield emit_event(
                "progress",
                phase="columns",
                message=f"🔢 임베딩 생성: {end}/{len(columns)}",
                percent=round((end / len(columns)) * 50)  # 0-50%
            )
            
            # Load columns
            for col, embedding in zip(batch, embeddings):
                fqn = f"{col['schema']}.{col['table_name']}.{col['name']}".lower()
                nullable = loader._normalize_nullable(col.get("nullable"))
                
                query = """
                MATCH (t:Table {db: $db, schema: $schema, name: $table_name})
                MERGE (c:Column {fqn: $fqn})
                SET c.vector = $vector,
                    c.name = $column_name,
                    c.dtype = $dtype,
                    c.description = COALESCE(c.description, $description),
                    c.nullable = $nullable,
                    c.updated_at = datetime()
                MERGE (t)-[:HAS_COLUMN]->(c)
                RETURN c
                """
                
                await neo4j_session.run(
                    query,
                    db=db_name,
                    schema=col["schema"].lower(),
                    table_name=col["table_name"].lower(),
                    fqn=fqn,
                    vector=embedding,
                    column_name=col["name"],
                    dtype=col.get("dtype") or "",
                    description=col.get("description") or "",
                    nullable=nullable
                )
                
                stats["columns"] += 1
            
            # Emit batch progress
            yield emit_event(
                "node_created",
                nodeType="Column",
                count=len(batch),
                total=len(columns),
                progress=f"{end}/{len(columns)}",
                percent=round(50 + (end / len(columns)) * 50)  # 50-100%
            )
        
        yield emit_event("progress", phase="columns", message=f"✓ 컬럼 {len(columns)}개 로드 완료")
        
        # Phase 5: Load foreign keys
        if foreign_keys:
            yield emit_event("phase", phase="fks", message=f"🔗 FK 관계 {len(foreign_keys)}개 생성 중...")
            
            for idx, fk in enumerate(foreign_keys, 1):
                from_fqn = f"{fk['from_schema']}.{fk['from_table']}.{fk['from_column']}".lower()
                to_fqn = f"{fk['to_schema']}.{fk['to_table']}.{fk['to_column']}".lower()
                
                # Column-to-column FK
                query = """
                MATCH (c1:Column {fqn: $from_fqn})
                MATCH (c2:Column {fqn: $to_fqn})
                MERGE (c1)-[fk:FK_TO]->(c2)
                SET fk.constraint = $constraint_name,
                    fk.on_update = $on_update,
                    fk.on_delete = $on_delete
                """
                
                await neo4j_session.run(
                    query,
                    from_fqn=from_fqn,
                    to_fqn=to_fqn,
                    constraint_name=fk["constraint_name"],
                    on_update=fk.get("on_update", "NO ACTION"),
                    on_delete=fk.get("on_delete", "NO ACTION")
                )
                
                # Table-to-table FK
                query2 = """
                MATCH (t1:Table {db: $db, schema: $from_schema, name: $from_table})
                MATCH (t2:Table {db: $db, schema: $to_schema, name: $to_table})
                MERGE (t1)-[:FK_TO_TABLE]->(t2)
                """
                
                await neo4j_session.run(
                    query2,
                    db=db_name,
                    from_schema=fk["from_schema"].lower(),
                    from_table=fk["from_table"].lower(),
                    to_schema=fk["to_schema"].lower(),
                    to_table=fk["to_table"].lower()
                )
                
                stats["fks"] = idx
                
                yield emit_event(
                    "relationship_created",
                    relType="FK_TO",
                    from_table=f"{fk['from_schema']}.{fk['from_table']}",
                    from_column=fk["from_column"],
                    to_table=f"{fk['to_schema']}.{fk['to_table']}",
                    to_column=fk["to_column"],
                    progress=f"{idx}/{len(foreign_keys)}"
                )
            
            yield emit_event("progress", phase="fks", message=f"✓ FK {len(foreign_keys)}개 생성 완료")
        
        # Phase 6: Mark primary keys
        if primary_keys:
            yield emit_event("phase", phase="pks", message=f"🔑 PK {len(primary_keys)}개 설정 중...")
            
            for idx, pk in enumerate(primary_keys, 1):
                fqn = f"{pk['schema']}.{pk['table_name']}.{pk['column_name']}".lower()
                
                query = """
                MATCH (c:Column {fqn: $fqn})
                SET c.is_primary_key = true,
                    c.pk_constraint = $constraint_name
                """
                
                await neo4j_session.run(
                    query,
                    fqn=fqn,
                    constraint_name=pk["constraint_name"]
                )
                
                stats["pks"] = idx
            
            yield emit_event("progress", phase="pks", message=f"✓ PK {len(primary_keys)}개 설정 완료")
        
        # Complete
        yield emit_event(
            "complete",
            message="🎉 인제스천 완료!",
            stats={
                "tables": stats["tables"],
                "columns": stats["columns"],
                "fks": stats["fks"],
                "pks": stats["pks"]
            }
        )
        
    except Exception as e:
        yield emit_event("error", message=f"❌ 인제스천 실패: {str(e)}")
        raise


@router.post("/stream")
async def ingest_schema_stream(
    request: IngestRequest,
    neo4j_session=Depends(get_neo4j_session),
    db_conn=Depends(get_db_connection),
    openai_client=Depends(get_openai_client)
):
    """
    Stream schema ingestion progress.
    Returns NDJSON stream with progress events.
    """
    return StreamingResponse(
        stream_ingestion(
            db_name=request.db_name,
            schema=request.schema,
            clear_existing=request.clear_existing,
            neo4j_session=neo4j_session,
            db_conn=db_conn,
            openai_client=openai_client
        ),
        media_type="application/x-ndjson"
    )


@router.post("", response_model=IngestResponse)
async def ingest_schema(
    request: IngestRequest,
    neo4j_session=Depends(get_neo4j_session),
    db_conn=Depends(get_db_connection),
    openai_client=Depends(get_openai_client)
):
    """
    Ingest database schema into Neo4j graph (non-streaming).
    """
    try:
        embedding_client = EmbeddingClient(openai_client)
        loader = Neo4jSchemaLoader(neo4j_session, embedding_client)
        extractor = SchemaExtractor(db_conn)
        
        await loader.setup_constraints_and_indexes()
        
        if request.clear_existing:
            await loader.clear_schema(request.db_name)
        
        tables = await extractor.extract_tables(request.schema)
        columns = await extractor.extract_columns(request.schema)
        foreign_keys = await extractor.extract_foreign_keys(request.schema)
        primary_keys = await extractor.extract_primary_keys(request.schema)
        
        await loader.load_tables(tables, request.db_name)
        await loader.load_columns(columns, request.db_name)
        await loader.load_foreign_keys(foreign_keys, request.db_name)
        await loader.load_primary_keys(primary_keys, request.db_name)
        
        return IngestResponse(
            message="Schema ingestion completed successfully",
            status="success",
            tables_loaded=len(tables),
            columns_loaded=len(columns),
            fks_loaded=len(foreign_keys)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
