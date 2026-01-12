"""
Neo4j 기반 쿼리 히스토리 온톨로지 저장소

쿼리와 테이블/컬럼 간의 관계를 그래프로 모델링하여:
- 유사 쿼리 검색 정확도 향상
- 쿼리 패턴 분석
- 값 매핑 자동 활용

그래프 스키마:
  (:Query {question, sql, status, ...})
      ├──[:USES_TABLE]────────► (:Table {name, schema})
      ├──[:SELECTS]───────────► (:Column {fqn})
      ├──[:FILTERS {op, value}]► (:Column)
      ├──[:AGGREGATES {fn}]───► (:Column)
      ├──[:JOINS_ON]──────────► (:Column)
      └──[:GROUPS_BY]─────────► (:Column)
  
  (:ValueMapping {natural_value, code_value})
      └──[:MAPS_TO]───────────► (:Column)
  
  (:QueryPattern {pattern, template_sql})
      └──[:APPLIES_TO]────────► (:Table)
"""

import re
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field


class QueryNode(BaseModel):
    """Neo4j Query 노드 모델"""
    id: Optional[str] = None
    question: str
    sql: Optional[str] = None
    status: str = "completed"  # completed, error
    row_count: Optional[int] = None
    execution_time_ms: Optional[float] = None
    steps_count: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    
    # 추출된 메타데이터
    tables_used: List[str] = []
    columns_used: List[Dict[str, str]] = []
    value_mappings: List[Dict[str, str]] = []


class ValueMappingNode(BaseModel):
    """값 → 코드 매핑 노드"""
    natural_value: str  # 자연어 값 (예: 청주정수장)
    code_value: str     # 코드 값 (예: BPLC001)
    column_fqn: str     # 컬럼 FQN
    usage_count: int = 1


class QueryPatternNode(BaseModel):
    """쿼리 패턴 템플릿 노드"""
    id: Optional[str] = None
    pattern: str        # 질문 패턴 (예: "{정수장}의 {측정값} 조회")
    template_sql: str   # SQL 템플릿
    placeholders: List[str] = []
    tables_used: List[str] = []
    usage_count: int = 1


class Neo4jQueryRepository:
    """Neo4j 기반 쿼리 히스토리 저장소"""
    
    def __init__(self, session):
        self.session = session
    
    async def setup_constraints(self):
        """Neo4j 제약조건 및 인덱스 설정"""
        constraints = [
            """
            CREATE CONSTRAINT query_id IF NOT EXISTS
            FOR (q:Query) REQUIRE q.id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT value_mapping_key IF NOT EXISTS
            FOR (v:ValueMapping) REQUIRE (v.natural_value, v.column_fqn) IS NODE KEY
            """,
            """
            CREATE INDEX query_question_idx IF NOT EXISTS
            FOR (q:Query) ON (q.question)
            """,
            """
            CREATE INDEX query_created_idx IF NOT EXISTS
            FOR (q:Query) ON (q.created_at)
            """,
            """
            CREATE INDEX value_mapping_natural_idx IF NOT EXISTS
            FOR (v:ValueMapping) ON (v.natural_value)
            """
        ]
        
        for query in constraints:
            try:
                await self.session.run(query)
            except Exception as e:
                # 제약조건이 이미 존재할 수 있음
                print(f"Constraint setup warning: {e}")
    
    def _generate_query_id(self, question: str, sql: str) -> str:
        """쿼리 ID 생성"""
        content = f"{question}:{sql or ''}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _extract_sql_components(self, sql: str) -> Dict[str, Any]:
        """SQL에서 컴포넌트 추출 (테이블, 컬럼, 조건 등)"""
        if not sql:
            return {}
        
        components = {
            'select_columns': [],
            'filter_conditions': [],
            'aggregate_functions': [],
            'join_conditions': [],
            'group_by_columns': [],
            'tables': []
        }
        
        sql_upper = sql.upper()
        
        # 테이블 추출 (FROM, JOIN 절)
        table_pattern = r'(?:FROM|JOIN)\s+"?(\w+)"?\."?(\w+)"?'
        for match in re.finditer(table_pattern, sql, re.IGNORECASE):
            schema, table = match.groups()
            components['tables'].append({
                'schema': schema.lower(),
                'name': table.lower()
            })
        
        # 집계 함수 추출
        agg_pattern = r'(AVG|SUM|COUNT|MAX|MIN)\s*\(\s*"?(\w+)"?\."?"?(\w+)"?\s*\)'
        for match in re.finditer(agg_pattern, sql, re.IGNORECASE):
            fn, alias_or_col, col = match.groups()
            components['aggregate_functions'].append({
                'function': fn.upper(),
                'column': col.lower()
            })
        
        # WHERE 조건 추출
        where_pattern = r'"?(\w+)"?\."?"?(\w+)"?\s*(=|LIKE|>|<|>=|<=|IN)\s*[\'"]?([^\'"\s,\)]+)[\'"]?'
        for match in re.finditer(where_pattern, sql, re.IGNORECASE):
            alias_or_col, col, op, value = match.groups()
            if col.upper() not in ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN']:
                components['filter_conditions'].append({
                    'column': col.lower(),
                    'operator': op.upper(),
                    'value': value
                })
        
        # GROUP BY 추출
        group_pattern = r'GROUP\s+BY\s+(.+?)(?:ORDER|LIMIT|HAVING|$)'
        group_match = re.search(group_pattern, sql, re.IGNORECASE | re.DOTALL)
        if group_match:
            group_cols = group_match.group(1)
            col_pattern = r'"?(\w+)"?\."?"?(\w+)"?'
            for match in re.finditer(col_pattern, group_cols):
                alias, col = match.groups()
                components['group_by_columns'].append(col.lower())
        
        return components
    
    def _extract_value_mappings(self, question: str, sql: str, metadata: Dict) -> List[Dict]:
        """질문과 SQL에서 값 매핑 추출"""
        mappings = []
        
        if not sql:
            return mappings
        
        # SQL에서 조건절 값 추출
        condition_pattern = r'"?(\w+)"?\."?"?(\w+)"?\s*=\s*\'([^\']+)\''
        for match in re.finditer(condition_pattern, sql):
            table_or_alias, column, value = match.groups()
            
            # 질문에서 관련 자연어 값 찾기
            # 예: "청주" in question and "BPLC001" in value
            question_words = question.split()
            for word in question_words:
                if len(word) >= 2 and word not in ['의', '을', '를', '에서', '으로']:
                    # 값이 코드 형태인지 확인 (영문+숫자)
                    if re.match(r'^[A-Z]+\d+$', value, re.IGNORECASE):
                        mappings.append({
                            'natural_value': word,
                            'code_value': value,
                            'column': column.lower()
                        })
        
        # 메타데이터에서 identified_values 활용
        if metadata and 'identified_values' in metadata:
            for val in metadata.get('identified_values', []):
                if val.get('actual_value') and val.get('user_term'):
                    mappings.append({
                        'natural_value': val['user_term'],
                        'code_value': val['actual_value'],
                        'column': val.get('column', '').lower()
                    })
        
        return mappings
    
    async def save_query(
        self,
        question: str,
        sql: Optional[str],
        status: str,
        metadata: Optional[Dict] = None,
        row_count: Optional[int] = None,
        execution_time_ms: Optional[float] = None,
        steps_count: Optional[int] = None,
        error_message: Optional[str] = None,
        steps: Optional[List[Dict]] = None  # 전체 도구 호출 과정
    ) -> str:
        """쿼리와 관련 메타데이터를 Neo4j에 저장"""
        import json as json_module
        
        query_id = self._generate_query_id(question, sql)
        
        # steps를 JSON 문자열로 변환 (Neo4j에 저장하기 위해)
        steps_json = json_module.dumps(steps, ensure_ascii=False) if steps else None
        
        # 1. Query 노드 생성 또는 업데이트
        query_create = """
        MERGE (q:Query {id: $id})
        SET q.question = $question,
            q.sql = $sql,
            q.status = $status,
            q.row_count = $row_count,
            q.execution_time_ms = $execution_time_ms,
            q.steps_count = $steps_count,
            q.error_message = $error_message,
            q.steps = $steps_json,
            q.updated_at = datetime(),
            q.created_at = COALESCE(q.created_at, datetime())
        RETURN q.id
        """
        
        await self.session.run(
            query_create,
            id=query_id,
            question=question,
            sql=sql,
            status=status,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            steps_count=steps_count,
            error_message=error_message,
            steps_json=steps_json
        )
        
        if sql:
            # 2. SQL 컴포넌트 추출
            components = self._extract_sql_components(sql)
            
            # 3. 테이블 관계 생성
            for table in components.get('tables', []):
                await self.session.run("""
                    MATCH (q:Query {id: $query_id})
                    MATCH (t:Table {schema: $schema, name: $table_name})
                    MERGE (q)-[:USES_TABLE]->(t)
                """, 
                    query_id=query_id,
                    schema=table['schema'],
                    table_name=table['name']
                )
            
            # 4. 집계 함수 관계 생성
            for agg in components.get('aggregate_functions', []):
                await self.session.run("""
                    MATCH (q:Query {id: $query_id})
                    MATCH (c:Column) WHERE toLower(c.name) = $column_name
                    MERGE (q)-[r:AGGREGATES]->(c)
                    SET r.function = $function
                """,
                    query_id=query_id,
                    column_name=agg['column'],
                    function=agg['function']
                )
            
            # 5. 필터 조건 관계 생성
            for filter_cond in components.get('filter_conditions', []):
                await self.session.run("""
                    MATCH (q:Query {id: $query_id})
                    MATCH (c:Column) WHERE toLower(c.name) = $column_name
                    MERGE (q)-[r:FILTERS]->(c)
                    SET r.operator = $operator,
                        r.value = $value
                """,
                    query_id=query_id,
                    column_name=filter_cond['column'],
                    operator=filter_cond['operator'],
                    value=filter_cond['value']
                )
            
            # 6. GROUP BY 관계 생성
            for group_col in components.get('group_by_columns', []):
                await self.session.run("""
                    MATCH (q:Query {id: $query_id})
                    MATCH (c:Column) WHERE toLower(c.name) = $column_name
                    MERGE (q)-[:GROUPS_BY]->(c)
                """,
                    query_id=query_id,
                    column_name=group_col
                )
        
        # 7. 값 매핑 저장
        value_mappings = self._extract_value_mappings(question, sql, metadata or {})
        for mapping in value_mappings:
            await self.save_value_mapping(
                natural_value=mapping['natural_value'],
                code_value=mapping['code_value'],
                column_name=mapping['column']
            )
        
        # 8. 메타데이터에서 추가 관계 저장
        if metadata:
            # identified_tables
            for table in metadata.get('identified_tables', []):
                if table.get('schema') and table.get('name'):
                    await self.session.run("""
                        MATCH (q:Query {id: $query_id})
                        MATCH (t:Table {schema: $schema, name: $table_name})
                        MERGE (q)-[:USES_TABLE]->(t)
                    """,
                        query_id=query_id,
                        schema=table['schema'].lower(),
                        table_name=table['name'].lower()
                    )
            
            # identified_columns with purpose
            for col in metadata.get('identified_columns', []):
                purpose = col.get('purpose', 'SELECT').upper()
                if 'FILTER' in purpose or 'WHERE' in purpose:
                    rel_type = 'FILTERS'
                elif 'GROUP' in purpose:
                    rel_type = 'GROUPS_BY'
                elif 'AVG' in purpose or 'SUM' in purpose or 'COUNT' in purpose:
                    rel_type = 'AGGREGATES'
                elif 'JOIN' in purpose:
                    rel_type = 'JOINS_ON'
                else:
                    rel_type = 'SELECTS'
                
                fqn = f"{col.get('schema', 'public')}.{col.get('table', '')}.{col.get('name', '')}".lower()
                
                await self.session.run(f"""
                    MATCH (q:Query {{id: $query_id}})
                    MATCH (c:Column {{fqn: $fqn}})
                    MERGE (q)-[:{rel_type}]->(c)
                """,
                    query_id=query_id,
                    fqn=fqn
                )
        
        return query_id
    
    async def save_value_mapping(
        self,
        natural_value: str,
        code_value: str,
        column_name: str
    ):
        """값 매핑을 Neo4j에 저장"""
        
        # 컬럼 찾기 및 매핑 저장
        await self.session.run("""
            MATCH (c:Column) WHERE toLower(c.name) = $column_name
            WITH c LIMIT 1
            MERGE (v:ValueMapping {natural_value: $natural_value, column_fqn: c.fqn})
            SET v.code_value = $code_value,
                v.usage_count = COALESCE(v.usage_count, 0) + 1,
                v.updated_at = datetime()
            MERGE (v)-[:MAPS_TO]->(c)
        """,
            natural_value=natural_value,
            code_value=code_value,
            column_name=column_name.lower()
        )
    
    async def find_similar_queries_by_graph(
        self,
        tables: List[str] = None,
        columns: List[str] = None,
        question_keywords: List[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """그래프 구조 기반 유사 쿼리 검색"""
        
        # 테이블과 컬럼 기반 검색
        if tables or columns:
            query = """
            WITH $tables AS tables, $columns AS columns
            
            // 동일한 테이블을 사용하는 쿼리
            OPTIONAL MATCH (q:Query)-[:USES_TABLE]->(t:Table)
            WHERE t.name IN tables
            WITH q, COUNT(DISTINCT t) AS table_matches
            
            // 동일한 컬럼을 사용하는 쿼리
            OPTIONAL MATCH (q)-[:SELECTS|FILTERS|AGGREGATES|GROUPS_BY]->(c:Column)
            WHERE c.name IN columns
            WITH q, table_matches, COUNT(DISTINCT c) AS column_matches
            
            WHERE q IS NOT NULL AND q.status = 'completed'
            
            RETURN q.id AS id,
                   q.question AS question,
                   q.sql AS sql,
                   q.row_count AS row_count,
                   q.execution_time_ms AS execution_time_ms,
                   (table_matches * 2 + column_matches) AS similarity_score
            ORDER BY similarity_score DESC, q.created_at DESC
            LIMIT $limit
            """
            
            result = await self.session.run(
                query,
                tables=[t.lower() for t in (tables or [])],
                columns=[c.lower() for c in (columns or [])],
                limit=limit
            )
        
        # 질문 키워드 기반 검색
        elif question_keywords:
            query = """
            MATCH (q:Query)
            WHERE q.status = 'completed'
            WITH q, 
                 REDUCE(score = 0, keyword IN $keywords |
                     CASE WHEN toLower(q.question) CONTAINS toLower(keyword)
                          THEN score + 1 ELSE score END
                 ) AS keyword_score
            WHERE keyword_score > 0
            
            RETURN q.id AS id,
                   q.question AS question,
                   q.sql AS sql,
                   q.row_count AS row_count,
                   q.execution_time_ms AS execution_time_ms,
                   keyword_score AS similarity_score
            ORDER BY keyword_score DESC, q.created_at DESC
            LIMIT $limit
            """
            
            result = await self.session.run(
                query,
                keywords=question_keywords,
                limit=limit
            )
        else:
            # 최근 쿼리 반환
            query = """
            MATCH (q:Query)
            WHERE q.status = 'completed'
            RETURN q.id AS id,
                   q.question AS question,
                   q.sql AS sql,
                   q.row_count AS row_count,
                   q.execution_time_ms AS execution_time_ms,
                   0 AS similarity_score
            ORDER BY q.created_at DESC
            LIMIT $limit
            """
            
            result = await self.session.run(query, limit=limit)
        
        records = await result.data()
        return records
    
    async def find_value_mapping(self, natural_value: str) -> List[Dict]:
        """자연어 값에 대한 코드 매핑 검색"""
        
        query = """
        MATCH (v:ValueMapping)-[:MAPS_TO]->(c:Column)
        WHERE toLower(v.natural_value) CONTAINS toLower($natural_value)
        RETURN v.natural_value AS natural_value,
               v.code_value AS code_value,
               c.fqn AS column_fqn,
               c.name AS column_name,
               v.usage_count AS usage_count
        ORDER BY v.usage_count DESC
        LIMIT 10
        """
        
        result = await self.session.run(query, natural_value=natural_value)
        return await result.data()
    
    async def get_query_history(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Dict:
        """쿼리 히스토리 조회"""
        
        skip = (page - 1) * page_size
        
        # 쿼리 목록 조회
        query = """
        MATCH (q:Query)
        WHERE $status IS NULL OR q.status = $status
        
        // 관련 테이블 수집
        OPTIONAL MATCH (q)-[:USES_TABLE]->(t:Table)
        WITH q, COLLECT(DISTINCT t.name) AS tables
        
        RETURN q.id AS id,
               q.question AS question,
               q.sql AS sql,
               q.status AS status,
               q.row_count AS row_count,
               q.execution_time_ms AS execution_time_ms,
               q.steps_count AS steps_count,
               q.created_at AS created_at,
               tables
        ORDER BY q.created_at DESC
        SKIP $skip
        LIMIT $limit
        """
        
        result = await self.session.run(
            query,
            status=status,
            skip=skip,
            limit=page_size
        )
        items = await result.data()
        
        # 총 개수 조회
        count_query = """
        MATCH (q:Query)
        WHERE $status IS NULL OR q.status = $status
        RETURN COUNT(q) AS total
        """
        count_result = await self.session.run(count_query, status=status)
        count_record = await count_result.single()
        total = count_record['total'] if count_record else 0
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size
        }
    
    async def get_table_usage_stats(self) -> List[Dict]:
        """테이블 사용 통계"""
        
        query = """
        MATCH (q:Query)-[:USES_TABLE]->(t:Table)
        WHERE q.status = 'completed'
        RETURN t.schema AS schema,
               t.name AS table_name,
               COUNT(q) AS usage_count,
               COLLECT(DISTINCT q.question)[0..3] AS sample_questions
        ORDER BY usage_count DESC
        LIMIT 20
        """
        
        result = await self.session.run(query)
        return await result.data()
    
    async def get_column_usage_stats(self) -> List[Dict]:
        """컬럼 사용 통계 (용도별)"""
        
        query = """
        MATCH (q:Query)-[r]->(c:Column)
        WHERE q.status = 'completed' AND type(r) IN ['SELECTS', 'FILTERS', 'AGGREGATES', 'GROUPS_BY', 'JOINS_ON']
        RETURN c.fqn AS column_fqn,
               c.name AS column_name,
               type(r) AS usage_type,
               COUNT(q) AS usage_count
        ORDER BY usage_count DESC
        LIMIT 30
        """
        
        result = await self.session.run(query)
        return await result.data()
    
    async def delete_query(self, query_id: str) -> bool:
        """쿼리 삭제"""
        
        query = """
        MATCH (q:Query {id: $query_id})
        DETACH DELETE q
        RETURN COUNT(*) > 0 AS deleted
        """
        
        result = await self.session.run(query, query_id=query_id)
        record = await result.single()
        return record['deleted'] if record else False


# 싱글톤 인스턴스 (세션 주입 필요)
_neo4j_query_repo: Optional[Neo4jQueryRepository] = None


def get_neo4j_query_repo(session) -> Neo4jQueryRepository:
    """Neo4j 쿼리 저장소 인스턴스 반환"""
    global _neo4j_query_repo
    if _neo4j_query_repo is None:
        _neo4j_query_repo = Neo4jQueryRepository(session)
    return _neo4j_query_repo

