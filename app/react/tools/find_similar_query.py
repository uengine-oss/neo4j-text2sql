"""
find_similar_query - Embedding 기반 유사 쿼리 검색 도구 (범용화)

핵심 변경:
- 도메인 하드코딩(정수장/BPLC 등) 제거
- Query.vector 벡터 인덱스(query_vec_index)로 Top-K 검색
- 품질 지표(steps_count/execution_time_ms)로 rerank
- ValueMapping은 Neo4j에 저장된(강한 게이트 통과) 매핑만 재사용
"""

import json
import re
import time
import traceback
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.embedding import EmbeddingClient
from app.react.tools.context import ToolContext
from app.react.utils.log_sanitize import sanitize_for_log
from app.smart_logger import SmartLogger


_GENERIC_TERMS = {
    "정수장",
    "사업장",
    "시설",
    "지역",
    "코드",
    "수압",
    "유량",
    "평균",
    "합계",
    "최대",
    "최소",
    "전체",
    "조회",
    "검색",
    "보여줘",
    "알려줘",
    "해주세요",
    "데이터",
    "값",
}


def _extract_terms(question: str) -> List[str]:
    text = (question or "").strip()
    if not text:
        return []
    # Korean blocks + alphanumerics
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z0-9_]{2,}", text)
    uniq: List[str] = []
    seen = set()
    for t in tokens:
        term = t.strip()
        if not term or term in _GENERIC_TERMS or term.endswith("코드"):
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(term)
    return uniq[:20]


def _score_to_pct(score: float) -> int:
    try:
        s = float(score)
    except Exception:
        return 0
    # Vector cosine similarity typically in [0,1] for semantic neighbors; clamp.
    s = max(0.0, min(1.0, s))
    return int(round(s * 100))


async def execute(
    context: ToolContext,
    question: str,
    min_similarity: float = 0.3,
) -> str:
    started = time.perf_counter()
    result_parts: List[str] = ["<tool_result>"]

    terms = _extract_terms(question)
    # For logging/correlation only. Cache graph partition key is db TYPE label.
    db_name = settings.react_caching_db_type

    SmartLogger.log(
        "INFO",
        "find_similar_query.start",
        category="react.tool.find_similar_query",
        params=sanitize_for_log(
            {
                "react_run_id": context.react_run_id,
                "question": question,
                "db": db_name,
                "min_similarity": min_similarity,
                "terms": terms,
            }
        ),
        max_inline_chars=0,
    )

    similar_queries: List[Dict[str, Any]] = []
    value_mappings: List[Dict[str, Any]] = []

    try:
        embedder = EmbeddingClient(context.openai_client)
        embedding = await embedder.embed_text((question or "")[:8000])

        # 1) Query vector search
        cypher = """
        CALL db.index.vector.queryNodes('query_vec_index', $k, $embedding)
        YIELD node, score
        WITH node, score
        WHERE node:Query
          AND node.status = 'completed'
          AND node.sql IS NOT NULL
          AND score >= $min_score
        RETURN node.id AS id,
               node.question AS question,
               node.sql AS sql,
               node.steps_count AS steps_count,
               node.execution_time_ms AS execution_time_ms,
               node.tables_used AS tables_used,
               node.columns_used AS columns_used,
               node.best_run_at_ms AS best_run_at_ms,
               score AS similarity_score
        ORDER BY similarity_score DESC, best_run_at_ms DESC
        LIMIT $k
        """
        k = 8
        res = await context.neo4j_session.run(
            cypher,
            k=k,
            embedding=embedding,
            min_score=float(min_similarity),
        )
        similar_queries = await res.data()

        # 2) Fetch relevant value mappings from Neo4j (strong-gated ones)
        if terms:
            vm_cypher = """
            MATCH (v:ValueMapping)-[:MAPS_TO]->(c:Column)
            WHERE any(term IN $terms WHERE toLower($question) CONTAINS toLower(v.natural_value))
            RETURN v.natural_value AS natural_value,
                   v.code_value AS code_value,
                   c.fqn AS column_fqn,
                   c.name AS column_name,
                   v.usage_count AS usage_count
            ORDER BY v.usage_count DESC
            LIMIT 10
            """
            vm_res = await context.neo4j_session.run(
                vm_cypher,
                terms=terms,
                question=question or "",
            )
            value_mappings = await vm_res.data()

    except Exception as exc:
        result_parts.append(f"<warning>find_similar_query_failed: {str(exc)[:120]}</warning>")
        SmartLogger.log(
            "WARNING",
            "find_similar_query.error",
            category="react.tool.find_similar_query",
            params=sanitize_for_log(
                {
                    "react_run_id": context.react_run_id,
                    "exception": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            ),
            max_inline_chars=0,
        )

    # 3) Build tool_result XML
    if not similar_queries and not value_mappings:
        result_parts.append("<message>No similar queries found in history</message>")
        result_parts.append("<hint>Start with search_tables to explore the schema</hint>")
        result_parts.append("</tool_result>")
        tool_result = "\n".join(result_parts)
        SmartLogger.log(
            "INFO",
            "find_similar_query.done",
            category="react.tool.find_similar_query",
            params=sanitize_for_log(
                {
                    "react_run_id": context.react_run_id,
                    "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                    "question": question,
                    "similar_queries_count": 0,
                    "value_mappings_count": 0,
                    "tool_result": tool_result,
                }
            ),
            max_inline_chars=0,
        )
        return tool_result

    if similar_queries:
        result_parts.append(f"<found_count>{len(similar_queries)}</found_count>")
        result_parts.append("<similar_queries>")
        for sq in similar_queries:
            pct = _score_to_pct(sq.get("similarity_score", 0))
            result_parts.append("<query>")
            result_parts.append(f"<similarity>{pct}%</similarity>")
            result_parts.append(f"<original_question>{sq.get('question') or ''}</original_question>")
            result_parts.append(f"<sql><![CDATA[{sq.get('sql') or ''}]]></sql>")
            if sq.get("steps_count") is not None:
                result_parts.append(f"<steps_count>{sq.get('steps_count')}</steps_count>")
            if sq.get("execution_time_ms") is not None:
                try:
                    result_parts.append(f"<execution_time_ms>{float(sq.get('execution_time_ms')):.0f}</execution_time_ms>")
                except Exception:
                    pass
            tables_used = sq.get("tables_used") or []
            if isinstance(tables_used, list) and tables_used:
                result_parts.append(f"<tables_used>{', '.join(str(x) for x in tables_used)}</tables_used>")
            result_parts.append("</query>")
        result_parts.append("</similar_queries>")

        top_score = float(similar_queries[0].get("similarity_score") or 0.0) if similar_queries else 0.0
        if top_score >= 0.87:
            result_parts.append("<action_required>IMMEDIATE_TEMPLATE_REUSE</action_required>")
            result_parts.append("<instruction>")
            result_parts.append("CRITICAL: 매우 유사한 쿼리가 존재합니다. 위 SQL을 기반으로 바로 explain을 진행하세요.")
            result_parts.append("ValueMapping이 있다면 WHERE 값에 우선 적용하세요.")
            result_parts.append("</instruction>")
        elif top_score >= 0.75:
            result_parts.append("<action_required>ADAPT_TEMPLATE</action_required>")
            result_parts.append("<instruction>")
            result_parts.append("유사한 쿼리 템플릿을 발견했습니다. 위 SQL 구조를 참고하여 조건/값을 조정하세요.")
            result_parts.append("</instruction>")

    if value_mappings:
        result_parts.append("<value_mappings>")
        result_parts.append("<critical>아래 매핑은 강한 게이트(DB 존재 확인)를 통과한 값입니다. WHERE 절에 우선 적용하세요.</critical>")
        seen = set()
        for vm in value_mappings:
            natural = str(vm.get("natural_value") or "").strip()
            code = str(vm.get("code_value") or "").strip()
            col = str(vm.get("column_name") or "").strip()
            if not natural or not code or natural in _GENERIC_TERMS or natural.endswith("코드"):
                continue
            key = (natural, code, col)
            if key in seen:
                continue
            seen.add(key)
            result_parts.append("<mapping>")
            result_parts.append(f"<natural_value>{natural}</natural_value>")
            result_parts.append(f"<code_value>{code}</code_value>")
            result_parts.append(f"<column>{col}</column>")
            result_parts.append(f"<usage>WHERE \"{col}\" = '{code}'</usage>")
            result_parts.append("</mapping>")
        result_parts.append("</value_mappings>")

    result_parts.append("</tool_result>")
    tool_result = "\n".join(result_parts)

    SmartLogger.log(
        "INFO",
        "find_similar_query.done",
        category="react.tool.find_similar_query",
        params=sanitize_for_log(
            {
                "react_run_id": context.react_run_id,
                "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                "question": question,
                "similar_queries_count": len(similar_queries),
                "value_mappings_count": len(value_mappings),
                "tool_result": tool_result,
            }
        ),
        max_inline_chars=0,
    )
    return tool_result


# Tool metadata
NAME = "find_similar_query"
DESCRIPTION = """Search query history for similar questions and their SQL using Neo4j graph.
Use this FIRST before exploring schema to check if a similar query already exists.
Returns:
- Similar queries with their SQL and metadata
- Value mappings (natural language → code) for WHERE clauses
If found, adapt the existing SQL template rather than starting from scratch."""

PARAMETERS = {
    "question": {
        "type": "string",
        "description": "The natural language question to find similar queries for"
    },
    "min_similarity": {
        "type": "number",
        "description": "Minimum similarity threshold (0.0-1.0, default 0.3)"
    }
}

REQUIRED = ["question"]
