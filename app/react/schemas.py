"""
ReAct Agent Structured Output Schemas

OpenAI Structured Output을 사용하여 LLM 응답을 강제합니다.
토큰 사용량을 줄이기 위해 축약 필드명을 사용합니다.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TableInfo(BaseModel):
    """식별된 테이블 정보"""
    s: str = Field(description="schema name")
    n: str = Field(description="table name")
    p: str = Field(default="", description="purpose of this table in the query")
    k: str = Field(default="", description="key columns")
    d: str = Field(default="", description="business description")


class ColumnInfo(BaseModel):
    """식별된 컬럼 정보"""
    s: str = Field(description="schema name")
    t: str = Field(description="table name")
    n: str = Field(description="column name")
    dt: str = Field(default="", description="data type")
    p: str = Field(default="", description="purpose (SELECT, JOIN, WHERE, etc.)")


class ValueInfo(BaseModel):
    """식별된 값 정보"""
    s: str = Field(description="schema name")
    t: str = Field(description="table name")
    c: str = Field(description="column name")
    av: str = Field(description="actual value in database")
    ut: str = Field(default="", description="user's original term")


class RelationshipInfo(BaseModel):
    """식별된 관계 정보"""
    ty: str = Field(description="JOIN type")
    cond: str = Field(description="JOIN condition")
    tbs: str = Field(description="tables involved")


class ConstraintInfo(BaseModel):
    """식별된 제약조건 정보"""
    ty: str = Field(description="constraint type (WHERE, HAVING, etc.)")
    cond: str = Field(description="the actual condition")
    st: str = Field(default="needs_verification", description="confirmed or needs_verification")


class CollectedMetadata(BaseModel):
    """수집된 메타데이터 (축약형)"""
    t: List[TableInfo] = Field(default_factory=list, description="identified tables")
    c: List[ColumnInfo] = Field(default_factory=list, description="identified columns")
    v: List[ValueInfo] = Field(default_factory=list, description="identified values")
    rel: List[RelationshipInfo] = Field(default_factory=list, description="identified relationships")
    con: List[ConstraintInfo] = Field(default_factory=list, description="identified constraints")


class SQLCompleteness(BaseModel):
    """SQL 완성도 체크"""
    done: bool = Field(description="is SQL complete?")
    miss: str = Field(default="", description="what information is still needed")
    conf: Literal["high", "medium", "low"] = Field(default="low", description="confidence level")


class ToolCallInfo(BaseModel):
    """도구 호출 정보"""
    n: str = Field(description="tool name")
    p: str = Field(description="parameters (JSON string or plain text depending on tool)")


class ReactOutput(BaseModel):
    """ReAct Agent 출력 스키마 (Structured Output)"""
    r: str = Field(description="reasoning: your thought process")
    m: CollectedMetadata = Field(default_factory=CollectedMetadata, description="collected metadata (only NEW info)")
    sql: str = Field(default="", description="partial SQL with placeholders")
    chk: SQLCompleteness = Field(description="SQL completeness check")
    tool: ToolCallInfo = Field(description="tool call to execute")


# XML 형식과의 호환성을 위한 변환 함수
def react_output_to_xml_like_dict(output: ReactOutput) -> dict:
    """
    ReactOutput을 기존 XML 파싱 결과와 호환되는 dict로 변환
    """
    # 테이블 정보를 XML 형식으로 변환
    tables_xml = ""
    for t in output.m.t:
        tables_xml += f"""<table>
<schema>{t.s}</schema>
<name>{t.n}</name>
<purpose>{t.p}</purpose>
<key_columns>{t.k}</key_columns>
<description>{t.d}</description>
</table>"""
    
    # 컬럼 정보
    columns_xml = ""
    for c in output.m.c:
        columns_xml += f"""<column>
<schema>{c.s}</schema>
<table>{c.t}</table>
<name>{c.n}</name>
<data_type>{c.dt}</data_type>
<purpose>{c.p}</purpose>
</column>"""
    
    # 값 정보
    values_xml = ""
    for v in output.m.v:
        values_xml += f"""<value>
<schema>{v.s}</schema>
<table>{v.t}</table>
<column>{v.c}</column>
<actual_value>{v.av}</actual_value>
<user_term>{v.ut}</user_term>
</value>"""
    
    # 관계 정보
    rels_xml = ""
    for rel in output.m.rel:
        rels_xml += f"""<relationship>
<type>{rel.ty}</type>
<condition>{rel.cond}</condition>
<tables>{rel.tbs}</tables>
</relationship>"""
    
    # 제약조건 정보
    cons_xml = ""
    for con in output.m.con:
        cons_xml += f"""<constraint>
<type>{con.ty}</type>
<condition>{con.cond}</condition>
<status>{con.st}</status>
</constraint>"""
    
    metadata_xml = f"""<collected_metadata>
<identified_tables>{tables_xml}</identified_tables>
<identified_columns>{columns_xml}</identified_columns>
<identified_values>{values_xml}</identified_values>
<identified_relationships>{rels_xml}</identified_relationships>
<identified_constraints>{cons_xml}</identified_constraints>
</collected_metadata>"""
    
    return {
        "reasoning": output.r,
        "metadata_xml": metadata_xml,
        "partial_sql": output.sql,
        "sql_completeness": {
            "is_complete": output.chk.done,
            "missing_info": output.chk.miss,
            "confidence_level": output.chk.conf,
        },
        "tool_call": {
            "name": output.tool.n,
            "parameters": output.tool.p,
        }
    }

