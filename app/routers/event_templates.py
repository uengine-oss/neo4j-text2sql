"""
이벤트 감지 템플릿 정의

정수장 운영에서 자주 발생하는 이벤트 유형을 사전 정의합니다.
사용자는 이 템플릿을 기반으로 빠르게 이벤트 규칙을 생성할 수 있습니다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter

router = APIRouter(prefix="/events/templates", tags=["Event Templates"])


class EventTemplate(BaseModel):
    """이벤트 템플릿"""
    id: str
    category: str  # 구분
    name: str  # 알람명
    description: str  # 운영 의미
    rule_description: str  # 알람 판단 세부 규칙
    sample_sql: str  # 감지 SQL 예시
    default_interval_minutes: int  # 기본 감지 간격
    default_threshold: str  # 기본 트리거 조건
    recommended_action: Literal["alert", "process"]  # 권장 조치
    diagnostic_questions: List[str]  # 사용자 질문 예시 (상세 진단)
    simple_questions: List[str]  # 사용자 질문 예시 (단순 질문)
    action_questions: List[str]  # 사용자 질문 예시 (조치 질문)
    suggested_process: Optional[str] = None  # 연결 가능한 프로세스


# 사전 정의된 이벤트 템플릿
EVENT_TEMPLATES: List[EventTemplate] = [
    # ============================================================================
    # 여과(GAC) 관련 이벤트
    # ============================================================================
    EventTemplate(
        id="gac-turbidity-rise",
        category="여과(GAC)",
        name="여과지 탁도 상승",
        description="여과 효율 저하 또는 역세 시점 도래를 확인",
        rule_description="여과지 탁도가 기준 이동평균 대비 지속적으로 상승하면서 최근 역세 이후에도 개선되지 않은 경우",
        sample_sql="""
SELECT 
    filter_id,
    turbidity,
    AVG(turbidity) OVER (PARTITION BY filter_id ORDER BY measured_at ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING) as avg_turbidity,
    measured_at
FROM filter_readings
WHERE measured_at >= NOW() - INTERVAL '1 hour'
  AND turbidity > (
    SELECT AVG(turbidity) * 1.2 
    FROM filter_readings 
    WHERE measured_at >= NOW() - INTERVAL '24 hours'
  )
GROUP BY filter_id, turbidity, measured_at
HAVING COUNT(*) >= 3
""".strip(),
        default_interval_minutes=10,
        default_threshold="rows > 0",
        recommended_action="alert",
        diagnostic_questions=[
            "현재 탁도 동향은 어떠한가요?",
            "어떤 여과지인가요?",
            "최근 역세 이후 상태는?"
        ],
        simple_questions=["역세해도 탁도가 왜 안 떨어져요?"],
        action_questions=["역세 시점을 앞당겨야 하나요?"],
        suggested_process="역세_스케줄_조정"
    ),
    
    EventTemplate(
        id="gac-backwash-error",
        category="여과(GAC)",
        name="역세 제어오류/역세 불량",
        description="역세 지연 또는 역세 수문 동시 가동 오류 확인",
        rule_description="역세 스케줄이 도래했으나 배수지/상수 수위 제약으로 역세 순서가 지연되거나 10회 이상 지연",
        sample_sql="""
SELECT 
    filter_id,
    scheduled_time,
    actual_time,
    delay_count,
    water_level,
    status
FROM backwash_schedule
WHERE scheduled_time <= NOW()
  AND (actual_time IS NULL OR delay_count >= 10)
  AND status IN ('PENDING', 'DELAYED')
ORDER BY scheduled_time
""".strip(),
        default_interval_minutes=5,
        default_threshold="rows > 0",
        recommended_action="alert",
        diagnostic_questions=[
            "지금 수위 조건 어때요?",
            "역세 순서가 밀린 이유는?"
        ],
        simple_questions=["이건 왜 안 돼요?"],
        action_questions=["어떻게 해야 돼요?"],
        suggested_process="역세_수동_제어"
    ),
    
    # ============================================================================
    # 착수 관련 이벤트
    # ============================================================================
    EventTemplate(
        id="intake-water-level-risk",
        category="착수",
        name="정수지 수위 위험",
        description="Human-in-the-loop 한 통보 및 상태 확인 필요",
        rule_description="정수지 수위가 정상 범위(하한/상한)를 초과하거나 반복적으로 조건 발생 중인 경우",
        sample_sql="""
SELECT 
    tank_id,
    water_level,
    lower_limit,
    upper_limit,
    measured_at,
    CASE 
        WHEN water_level < lower_limit THEN 'LOW'
        WHEN water_level > upper_limit THEN 'HIGH'
        ELSE 'NORMAL'
    END as status
FROM water_tank_levels
WHERE measured_at >= NOW() - INTERVAL '30 minutes'
  AND (water_level < lower_limit OR water_level > upper_limit)
ORDER BY measured_at DESC
""".strip(),
        default_interval_minutes=5,
        default_threshold="rows > 0",
        recommended_action="alert",
        diagnostic_questions=[
            "어떤 탱크가 문제인가요?",
            "어떤 여과 가동률로 분리해야 하는가?"
        ],
        simple_questions=["수위가 왜 이래요?"],
        action_questions=["펌프 가동률을 조정해야 하나요?"],
        suggested_process="펌프_가동률_조정"
    ),
    
    EventTemplate(
        id="intake-pump-combination-fail",
        category="착수",
        name="펌프 조합 실패",
        description="Human-in-the-loop 한 통보 및 상태 확인 필요",
        rule_description="AI가 도출한 펌프 조합이 현장 조건을 충족하지 못할 때 (충돌 포함)",
        sample_sql="""
SELECT 
    recommendation_id,
    pump_combination,
    failure_reason,
    constraint_violated,
    created_at
FROM pump_recommendations
WHERE status = 'FAILED'
  AND created_at >= NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
""".strip(),
        default_interval_minutes=10,
        default_threshold="rows > 0",
        recommended_action="alert",
        diagnostic_questions=["왜 실패했어요?", "어떤 제약 조건이 위반됐나요?"],
        simple_questions=["왜?"],
        action_questions=["수동으로 조합을 설정해야 하나요?"],
        suggested_process="펌프_수동_제어"
    ),
    
    # ============================================================================
    # 약품 관련 이벤트
    # ============================================================================
    EventTemplate(
        id="chemical-algorithm-error",
        category="약품",
        name="약품 알고리즘 분석 오류",
        description="제어 제외 및 여과 공정 영향 가능",
        rule_description="약품 제어에 필요한 센서 데이터에 결측 또는 측정값 급등락이 발생한 경우",
        sample_sql="""
SELECT 
    sensor_id,
    sensor_type,
    value,
    prev_value,
    ABS(value - prev_value) / NULLIF(prev_value, 0) * 100 as change_percent,
    measured_at
FROM chemical_sensor_readings
WHERE measured_at >= NOW() - INTERVAL '30 minutes'
  AND (
    value IS NULL 
    OR ABS(value - prev_value) / NULLIF(prev_value, 0) > 0.5  -- 50% 이상 급변
  )
ORDER BY measured_at DESC
""".strip(),
        default_interval_minutes=5,
        default_threshold="rows > 0",
        recommended_action="alert",
        diagnostic_questions=[
            "가동 전진 시간은 얼마인가요?",
            "어떤 센서에서 오류가 발생했나요?"
        ],
        simple_questions=["센서 데이터가 왜 이상해요?"],
        action_questions=["수동 제어로 전환해야 하나요?"],
        suggested_process="약품_수동_제어"
    ),
    
    # ============================================================================
    # 침전 관련 이벤트
    # ============================================================================
    EventTemplate(
        id="sedimentation-sludge-collector",
        category="침전",
        name="슬러지 수집기 가동 이상",
        description="모터 또는 배관 신호로 진단 필요",
        rule_description="슬러지 발생량 동향 또는 플로우 측정 기준에 비해 배수량이 낮아지거나 막힘 의심 시",
        sample_sql="""
SELECT 
    collector_id,
    sludge_flow,
    expected_flow,
    motor_current,
    (expected_flow - sludge_flow) / NULLIF(expected_flow, 0) * 100 as flow_deficit_percent,
    measured_at
FROM sludge_collector_readings
WHERE measured_at >= NOW() - INTERVAL '1 hour'
  AND sludge_flow < expected_flow * 0.7  -- 기대치의 70% 미만
ORDER BY measured_at DESC
""".strip(),
        default_interval_minutes=15,
        default_threshold="rows > 0",
        recommended_action="process",
        diagnostic_questions=[
            "어디가 문제예요?",
            "막힘인가요 아니면 모터 문제인가요?"
        ],
        simple_questions=["왜 배수량이 적어요?"],
        action_questions=["점검을 요청해야 하나요?"],
        suggested_process="설비_점검_요청"
    ),
    
    # ============================================================================
    # EMS (에너지 관리) 관련 이벤트
    # ============================================================================
    EventTemplate(
        id="ems-peak-forecast",
        category="EMS",
        name="향후 피크 정보",
        description="비용 절감을 위한 사전 제어 권고",
        rule_description="AI 전력 예측 결과 계약 전력 또는 내부 기준 초과일 경우",
        sample_sql="""
SELECT 
    forecast_time,
    predicted_power_kw,
    contract_limit_kw,
    internal_limit_kw,
    predicted_power_kw - contract_limit_kw as over_contract,
    confidence
FROM power_forecast
WHERE forecast_time BETWEEN NOW() AND NOW() + INTERVAL '2 hours'
  AND predicted_power_kw > contract_limit_kw * 0.9  -- 계약 전력의 90% 초과
ORDER BY forecast_time
""".strip(),
        default_interval_minutes=30,
        default_threshold="rows > 0",
        recommended_action="process",
        diagnostic_questions=[
            "부하 예측도 해줘요?",
            "피크 시간대는 언제인가요?"
        ],
        simple_questions=["얼마 정도 절약해요?"],
        action_questions=["부하를 분산시켜야 하나요?"],
        suggested_process="부하_분산_제어"
    ),
    
    # ============================================================================
    # 통합(HW/SW) 시스템 이벤트
    # ============================================================================
    EventTemplate(
        id="system-ai-failure",
        category="통합(HW/SW)",
        name="AI 분석/데이터 수집 실패",
        description="운영 환경 점검 통보",
        rule_description="AI 서버 Docker, 시각화 서버 또는 데이터 파이프라인 오류 발생 시",
        sample_sql="""
SELECT 
    service_name,
    status,
    error_message,
    last_heartbeat,
    NOW() - last_heartbeat as downtime
FROM system_health
WHERE status != 'HEALTHY'
  OR last_heartbeat < NOW() - INTERVAL '5 minutes'
ORDER BY last_heartbeat DESC
""".strip(),
        default_interval_minutes=1,
        default_threshold="rows > 0",
        recommended_action="alert",
        diagnostic_questions=[
            "어떤 서비스가 문제인가요?",
            "언제부터 문제가 발생했나요?"
        ],
        simple_questions=["시스템이 왜 안 돼요?"],
        action_questions=["재시작해야 하나요?"],
        suggested_process="서비스_재시작"
    ),
]


# 카테고리별 그룹화
def get_templates_by_category() -> Dict[str, List[EventTemplate]]:
    """카테고리별로 템플릿 그룹화"""
    result: Dict[str, List[EventTemplate]] = {}
    for template in EVENT_TEMPLATES:
        if template.category not in result:
            result[template.category] = []
        result[template.category].append(template)
    return result


# ============================================================================
# API 엔드포인트
# ============================================================================

@router.get("", response_model=List[EventTemplate])
async def list_templates(category: Optional[str] = None):
    """
    이벤트 템플릿 목록 조회
    
    Args:
        category: 카테고리 필터 (선택)
    """
    if category:
        return [t for t in EVENT_TEMPLATES if t.category == category]
    return EVENT_TEMPLATES


@router.get("/categories")
async def list_categories():
    """
    사용 가능한 카테고리 목록 조회
    """
    categories = list(set(t.category for t in EVENT_TEMPLATES))
    return {"categories": sorted(categories)}


@router.get("/by-category")
async def get_templates_grouped():
    """
    카테고리별로 그룹화된 템플릿 조회
    """
    return get_templates_by_category()


@router.get("/{template_id}", response_model=EventTemplate)
async def get_template(template_id: str):
    """
    특정 템플릿 상세 조회
    """
    for template in EVENT_TEMPLATES:
        if template.id == template_id:
            return template
    
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Template not found")


@router.post("/{template_id}/create-rule")
async def create_rule_from_template(
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    check_interval_minutes: Optional[int] = None
):
    """
    템플릿을 기반으로 이벤트 규칙 생성
    
    템플릿의 기본값을 사용하되, 필요한 경우 오버라이드 가능
    """
    from fastapi import HTTPException
    
    # 템플릿 찾기
    template = None
    for t in EVENT_TEMPLATES:
        if t.id == template_id:
            template = t
            break
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 이벤트 규칙 생성 데이터
    from app.routers.events import EventRuleCreate, create_event_rule, AlertConfig, ProcessConfig
    
    rule_data = EventRuleCreate(
        name=name or template.name,
        description=description or template.description,
        natural_language_condition=template.rule_description,
        sql=template.sample_sql,
        check_interval_minutes=check_interval_minutes or template.default_interval_minutes,
        condition_threshold=template.default_threshold,
        action_type=template.recommended_action,
        alert_config=AlertConfig(
            channels=["platform"],
            message=f"{template.name}: {template.description}"
        ) if template.recommended_action == "alert" else None,
        process_config=ProcessConfig(
            process_name=template.suggested_process or "",
            process_params={}
        ) if template.recommended_action == "process" else None
    )
    
    return await create_event_rule(rule_data)
