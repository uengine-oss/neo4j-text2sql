"""
find_similar_query - Neo4j 그래프 기반 유사 쿼리 검색 도구

기능:
1. 그래프 구조 기반 유사 쿼리 검색 (테이블/컬럼 관계 활용)
2. 값 매핑 자동 조회 (예: "청주" → "BPLC001")
3. 캐싱된 SQL 템플릿 재사용
"""
import re
from typing import List, Optional, Dict, Any

from app.react.tools.context import ToolContext


def _extract_keywords(question: str) -> List[str]:
    """질문에서 핵심 키워드 추출"""
    # 불용어 제거
    stopwords = {
        '을', '를', '이', '가', '에', '의', '에서', '으로', '로', '와', '과',
        '은', '는', '좀', '해줘', '보여줘', '알려줘', '조회', '검색', '해주세요',
        'the', 'a', 'an', 'is', 'are', 'in', 'on', 'at', 'for', 'to', 'of',
        'what', 'show', 'get', 'find', 'query', 'select'
    }
    
    words = question.lower().split()
    keywords = [w for w in words if w not in stopwords and len(w) > 1]
    return keywords


def _extract_entity_keywords(question: str) -> Dict[str, List[str]]:
    """질문에서 엔티티별 키워드 추출"""
    entities = {
        'locations': [],  # 지역/장소명
        'measurements': [],  # 측정 항목
        'time_periods': [],  # 시간 관련
        'aggregations': [],  # 집계 함수
        'others': []
    }
    
    # 지역/장소 패턴
    location_patterns = ['정수장', '사업장', '광역', '지역', '시설']
    # 측정 패턴
    measurement_patterns = ['유량', '수량', '압력', '온도', '탁도', '잔류염소', '수질']
    # 집계 패턴
    agg_patterns = ['평균', '합계', '최대', '최소', '개수', '총', '전체']
    # 시간 패턴
    time_patterns = ['일별', '월별', '연도별', '시간별', '오늘', '어제', '이번달', '올해']
    
    words = question.split()
    for word in words:
        if any(p in word for p in location_patterns):
            entities['locations'].append(word)
        elif any(p in word for p in measurement_patterns):
            entities['measurements'].append(word)
        elif any(p in word for p in agg_patterns):
            entities['aggregations'].append(word)
        elif any(p in word for p in time_patterns):
            entities['time_periods'].append(word)
        elif len(word) > 1:
            entities['others'].append(word)
    
    return entities


async def execute(
    context: ToolContext,
    question: str,
    min_similarity: float = 0.3,
) -> str:
    """
    Neo4j 그래프 기반으로 유사한 쿼리를 검색합니다.
    
    검색 전략:
    1. 질문 키워드 기반 검색
    2. 테이블/컬럼 관계 기반 검색
    3. 값 매핑 조회
    
    Args:
        question: 현재 질문
        min_similarity: 최소 유사도 임계값 (기본 0.3)
    
    Returns:
        유사한 쿼리 목록 (SQL 포함)
    """
    result_parts = ["<tool_result>"]
    
    keywords = _extract_keywords(question)
    entities = _extract_entity_keywords(question)
    
    # 1. Neo4j에서 유사 쿼리 검색
    try:
        # 키워드 기반 검색 쿼리
        neo4j_query = """
        MATCH (q:Query)
        WHERE q.status = 'completed' AND q.sql IS NOT NULL
        
        // 키워드 매칭 점수 계산
        WITH q, 
             REDUCE(score = 0, keyword IN $keywords |
                 CASE WHEN toLower(q.question) CONTAINS toLower(keyword)
                      THEN score + 1 ELSE score END
             ) AS keyword_score
        WHERE keyword_score > 0
        
        // 관련 테이블/컬럼 정보 수집
        OPTIONAL MATCH (q)-[:USES_TABLE]->(t:Table)
        OPTIONAL MATCH (q)-[:FILTERS]->(fc:Column)
        OPTIONAL MATCH (q)-[:AGGREGATES]->(ac:Column)
        
        WITH q, keyword_score,
             COLLECT(DISTINCT t.name) AS tables,
             COLLECT(DISTINCT {column: fc.name, rel: 'FILTER'}) AS filter_cols,
             COLLECT(DISTINCT {column: ac.name, rel: 'AGGREGATE'}) AS agg_cols
        
        RETURN q.id AS id,
               q.question AS question,
               q.sql AS sql,
               q.row_count AS row_count,
               q.execution_time_ms AS execution_time_ms,
               keyword_score AS similarity_score,
               tables,
               filter_cols,
               agg_cols
        ORDER BY keyword_score DESC, q.created_at DESC
        LIMIT 5
        """
        
        result = await context.neo4j_session.run(neo4j_query, keywords=keywords)
        similar_queries = await result.data()
        
    except Exception as e:
        # Neo4j 검색 실패 시 빈 결과 반환
        similar_queries = []
        result_parts.append(f"<warning>Graph search failed: {str(e)[:100]}</warning>")
    
    # 2. 값 매핑 검색 (지역/장소 키워드) - 정확한 매핑만 선택
    value_mappings = []
    
    # 질문에서 정수장 이름 추출 (예: "강릉정수장" or "강릉")
    location_name = None
    for location in entities.get('locations', []):
        if '정수장' in location or len(location) >= 2:
            location_name = location.replace('정수장', '').replace('의', '').strip()
            break
    
    # 질문 전체에서 정수장 이름 패턴 검색
    import re
    location_pattern = re.search(r'([가-힣]{2,4})(?:정수장)?(?:의|에서)?', question)
    if location_pattern and not location_name:
        location_name = location_pattern.group(1)
    
    if location_name:
        try:
            # BPLC_CODE 매핑을 우선적으로 검색
            mapping_query = """
            MATCH (v:ValueMapping)-[:MAPS_TO]->(c:Column)
            WHERE c.name = 'BPLC_CODE'
              AND (
                  toLower(v.natural_value) CONTAINS toLower($location)
                  OR toLower($location) CONTAINS toLower(v.natural_value)
              )
              AND v.code_value STARTS WITH 'BPLC'
            RETURN DISTINCT v.natural_value AS natural_value,
                   v.code_value AS code_value,
                   c.name AS column_name,
                   c.fqn AS column_fqn,
                   v.usage_count AS usage_count
            ORDER BY 
                CASE WHEN v.natural_value = $full_name THEN 0 
                     WHEN v.natural_value CONTAINS $location THEN 1
                     ELSE 2 END,
                v.usage_count DESC
            LIMIT 1
            """
            
            full_name = location_name + "정수장"
            mapping_result = await context.neo4j_session.run(
                mapping_query, 
                location=location_name,
                full_name=full_name
            )
            mappings = await mapping_result.data()
            value_mappings.extend(mappings)
            
        except Exception as e:
            pass
    
    # 매핑이 없으면 DB에서 직접 조회
    if not value_mappings and location_name:
        try:
            # rdisaup_tb에서 직접 조회
            db_query = """
            MATCH (c:Column {name: 'BPLC_NM'})-[:BELONGS_TO]->(t:Table {name: 'rdisaup_tb'})
            WITH c
            // DB에서 직접 조회 대신 캐시된 enum 값 사용
            MATCH (v:ValueMapping)-[:MAPS_TO]->(bc:Column {name: 'BPLC_CODE'})
            WHERE v.natural_value CONTAINS $location
              AND v.code_value STARTS WITH 'BPLC'
            RETURN v.natural_value AS natural_value,
                   v.code_value AS code_value,
                   'BPLC_CODE' AS column_name,
                   bc.fqn AS column_fqn,
                   v.usage_count AS usage_count
            ORDER BY v.usage_count DESC
            LIMIT 1
            """
            
            db_result = await context.neo4j_session.run(db_query, location=location_name)
            db_mappings = await db_result.data()
            value_mappings.extend(db_mappings)
            
        except Exception:
            pass
    
    # 3. 결과 생성
    if not similar_queries and not value_mappings:
        result_parts.append("<message>No similar queries found in history</message>")
        result_parts.append("<hint>Start with search_tables to explore the schema</hint>")
    else:
        if similar_queries:
            result_parts.append(f"<found_count>{len(similar_queries)}</found_count>")
            result_parts.append("<similar_queries>")
            
            for sq in similar_queries:
                score = sq.get('similarity_score', 0)
                max_keywords = len(keywords) if keywords else 1
                
                # 더 정확한 유사도 계산: 키워드 매칭 + 질문 길이 비교
                original_q = sq.get('question', '').lower()
                current_q = question.lower()
                
                # 핵심 키워드 추출 (정수장, 유량, 평균 등)
                core_terms = ['정수장', '유량', '평균', '압력', '수질', '온도', '탁도']
                core_match = sum(1 for t in core_terms if t in original_q and t in current_q)
                
                # 위치 키워드 (강릉, 청주, 창원 등) 비교 - 다르면 템플릿만 재사용
                location_in_original = [w for w in original_q.split() if '정수장' in w or len(w) <= 4]
                location_in_current = [w for w in current_q.split() if '정수장' in w or len(w) <= 4]
                
                # 구조적 유사도 (핵심 키워드 매칭)
                if core_match >= 2:
                    similarity_pct = min(100, 50 + core_match * 15 + score * 5)
                else:
                    similarity_pct = min(100, int((score / max(max_keywords, 1)) * 100))
                
                # 거의 동일한 질문이면 95%+
                if original_q.replace(' ', '') == current_q.replace(' ', ''):
                    similarity_pct = 100
                
                result_parts.append("<query>")
                result_parts.append(f"<similarity>{similarity_pct}%</similarity>")
                result_parts.append(f"<original_question>{sq['question']}</original_question>")
                result_parts.append(f"<sql><![CDATA[{sq['sql']}]]></sql>")
                
                if sq.get('row_count') is not None:
                    result_parts.append(f"<row_count>{sq['row_count']}</row_count>")
                if sq.get('execution_time_ms') is not None:
                    result_parts.append(f"<execution_time_ms>{sq['execution_time_ms']:.0f}</execution_time_ms>")
                
                # 테이블 정보
                tables = sq.get('tables', [])
                if tables:
                    result_parts.append(f"<tables_used>{', '.join(tables)}</tables_used>")
                
                result_parts.append("</query>")
            
            result_parts.append("</similar_queries>")
            
            # 유사도에 따른 명확한 지시
            top_similarity = 0
            if similar_queries:
                # 첫 번째 쿼리의 유사도 재계산
                sq = similar_queries[0]
                original_q = sq.get('question', '').lower()
                current_q = question.lower()
                core_terms = ['정수장', '유량', '평균', '압력', '수질', '온도', '탁도']
                core_match = sum(1 for t in core_terms if t in original_q and t in current_q)
                if core_match >= 2:
                    top_similarity = min(100, 50 + core_match * 15 + sq.get('similarity_score', 0) * 5)
                if original_q.replace(' ', '') == current_q.replace(' ', ''):
                    top_similarity = 100
            
            if top_similarity >= 80:
                result_parts.append("<action_required>IMMEDIATE_TEMPLATE_REUSE</action_required>")
                
                # 값 매핑을 적용한 수정된 SQL 제공
                if similar_queries and value_mappings:
                    template_sql = similar_queries[0].get('sql', '')
                    adapted_sql = template_sql
                    
                    # 값 매핑 적용
                    for vm in value_mappings:
                        code = vm.get('code_value', '')
                        if code.startswith('BPLC'):
                            # 기존 BPLC 코드를 새 코드로 교체
                            adapted_sql = re.sub(
                                r"BPLC_CODE['\"]?\s*=\s*['\"]?BPLC\d+['\"]?",
                                f"\"BPLC_CODE\" = '{code}'",
                                adapted_sql
                            )
                            # BPLC_NM 조건도 정수장 이름으로 교체
                            location_name = vm.get('natural_value', '')
                            if location_name:
                                adapted_sql = re.sub(
                                    r"BPLC_NM['\"]?\s*=\s*['\"][^'\"]+['\"]",
                                    f"\"BPLC_NM\" = '{location_name}'",
                                    adapted_sql
                                )
                            break
                    
                    result_parts.append("<adapted_sql>")
                    result_parts.append("<critical>아래 SQL을 바로 explain 도구에 사용하세요!</critical>")
                    result_parts.append(f"<![CDATA[{adapted_sql}]]>")
                    result_parts.append("</adapted_sql>")
                
                result_parts.append("<instruction>")
                result_parts.append("CRITICAL: 매우 유사한 쿼리가 존재합니다!")
                result_parts.append("1. <adapted_sql>의 SQL을 그대로 복사하세요")
                result_parts.append("2. 바로 explain 도구를 호출하세요")
                result_parts.append("3. get_table_schema, search_column_values 호출 금지!")
                result_parts.append("</instruction>")
            elif top_similarity >= 50:
                result_parts.append("<action_required>ADAPT_TEMPLATE</action_required>")
                result_parts.append("<instruction>")
                result_parts.append("유사한 쿼리 템플릿을 발견했습니다.")
                result_parts.append("1. 위 SQL 구조를 참고하세요")
                result_parts.append("2. value_mappings의 값으로 WHERE 절을 수정하세요")
                result_parts.append("3. 필요시 get_table_schema로 확인 후 진행하세요")
                result_parts.append("</instruction>")
        
        # 값 매핑 정보 - 더 명확하게 표시
        if value_mappings:
            result_parts.append("<value_mappings>")
            result_parts.append("<critical>아래 매핑을 SQL WHERE 절에 직접 사용하세요!</critical>")
            seen = set()
            for vm in value_mappings:
                key = f"{vm['natural_value']}:{vm['code_value']}"
                if key not in seen:
                    seen.add(key)
                    result_parts.append("<mapping>")
                    result_parts.append(f"<natural_value>{vm['natural_value']}</natural_value>")
                    result_parts.append(f"<code_value>{vm['code_value']}</code_value>")
                    result_parts.append(f"<column>{vm['column_name']}</column>")
                    result_parts.append(f"<usage>WHERE \"{vm['column_name']}\" = '{vm['code_value']}'</usage>")
                    result_parts.append("</mapping>")
            result_parts.append("</value_mappings>")
            result_parts.append("<instruction>")
            result_parts.append("CRITICAL: value_mappings의 code_value를 SQL에 즉시 사용하세요!")
            result_parts.append("search_column_values 호출 없이 위 매핑을 직접 적용하세요.")
            result_parts.append("</instruction>")
    
    result_parts.append("</tool_result>")
    return "\n".join(result_parts)


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
