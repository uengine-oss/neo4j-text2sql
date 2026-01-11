"""
CEP 통합 테스트

전체 흐름 테스트:
1. PostgreSQL에 테스트 데이터 생성 (타임스탬프 조작으로 10분 시뮬레이션)
2. Text2SQL API로 자연어 → SQL 변환
3. 폴링으로 데이터 조회 후 CEP로 전송
4. CEP 조건 평가 (10분 지속 조건)
5. 알람 트리거 및 콜백 확인

테스트 시나리오:
- "수위가 3m 이상 10분 이상 지속되면 알람"
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any
import uuid

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.simple_cep import (
    SimpleCEPEngine,
    EventRule,
    Event,
    TriggerResult,
    ConditionOperator,
    get_simple_cep_engine,
    create_rule_from_natural_language
)


# ============================================================================
# 테스트 데이터 생성
# ============================================================================

def generate_water_level_events(
    station_id: str,
    start_time: datetime,
    duration_minutes: int,
    water_level: float,
    interval_seconds: int = 60
) -> List[Event]:
    """
    수위 이벤트 시퀀스 생성
    
    Args:
        station_id: 관측소 ID
        start_time: 시작 시간
        duration_minutes: 지속 시간 (분)
        water_level: 수위 (m)
        interval_seconds: 이벤트 간격 (초)
    
    Returns:
        Event 목록
    """
    events = []
    num_events = (duration_minutes * 60) // interval_seconds
    
    for i in range(num_events + 1):
        timestamp = start_time + timedelta(seconds=i * interval_seconds)
        events.append(Event(
            timestamp=timestamp,
            source_id=station_id,
            event_type="water_level",
            data={
                "station_id": station_id,
                "water_level": water_level,
                "measured_at": timestamp.isoformat(),
                "unit": "m"
            }
        ))
    
    return events


def generate_mixed_water_level_events(
    station_id: str,
    start_time: datetime,
    segments: List[tuple]  # [(duration_minutes, water_level), ...]
) -> List[Event]:
    """
    다양한 수위 이벤트 시퀀스 생성
    
    Args:
        station_id: 관측소 ID
        start_time: 시작 시간
        segments: [(지속시간(분), 수위), ...] 세그먼트 목록
    """
    events = []
    current_time = start_time
    
    for duration_minutes, water_level in segments:
        segment_events = generate_water_level_events(
            station_id=station_id,
            start_time=current_time,
            duration_minutes=duration_minutes,
            water_level=water_level
        )
        events.extend(segment_events)
        current_time += timedelta(minutes=duration_minutes)
    
    return events


# ============================================================================
# SimpleCEP 엔진 단위 테스트
# ============================================================================

class TestSimpleCEPEngine:
    """SimpleCEP 엔진 단위 테스트"""
    
    @pytest.fixture
    def cep_engine(self):
        """테스트용 CEP 엔진"""
        engine = SimpleCEPEngine()
        yield engine
        engine.clear()
    
    @pytest.fixture
    def water_level_rule(self) -> EventRule:
        """수위 감지 규칙 (3m 이상, 10분 지속)"""
        return EventRule(
            id="rule-water-level-001",
            name="수위 이상 감지",
            description="수위가 3m 이상 10분 지속 시 알람",
            field_name="water_level",
            operator=ConditionOperator.GTE,
            threshold=3.0,
            window_minutes=30,
            duration_minutes=10,
            action_type="alert",
            action_config={"channels": ["platform"]}
        )
    
    def test_register_rule(self, cep_engine, water_level_rule):
        """규칙 등록 테스트"""
        rule_id = cep_engine.register_rule(water_level_rule)
        
        assert rule_id == water_level_rule.id
        assert water_level_rule.id in cep_engine.rules
    
    def test_unregister_rule(self, cep_engine, water_level_rule):
        """규칙 등록 해제 테스트"""
        cep_engine.register_rule(water_level_rule)
        cep_engine.unregister_rule(water_level_rule.id)
        
        assert water_level_rule.id not in cep_engine.rules
    
    def test_condition_not_met(self, cep_engine, water_level_rule):
        """조건 미충족 테스트 (수위 3m 미만)"""
        cep_engine.register_rule(water_level_rule)
        
        # 수위 2m (조건 미충족)
        events = generate_water_level_events(
            station_id="ST001",
            start_time=datetime.now(),
            duration_minutes=15,
            water_level=2.0
        )
        
        results = cep_engine.send_events_batch(events)
        
        assert len(results) == 0
    
    def test_condition_met_short_duration(self, cep_engine, water_level_rule):
        """조건 충족하지만 지속 시간 부족 (5분)"""
        cep_engine.register_rule(water_level_rule)
        
        # 수위 3.5m, 5분 지속 (지속 시간 부족)
        events = generate_water_level_events(
            station_id="ST001",
            start_time=datetime.now(),
            duration_minutes=5,
            water_level=3.5
        )
        
        results = cep_engine.send_events_batch(events)
        
        assert len(results) == 0
    
    def test_condition_met_sufficient_duration(self, cep_engine, water_level_rule):
        """조건 충족 + 지속 시간 충족 (10분 이상) → 트리거"""
        cep_engine.register_rule(water_level_rule)
        
        # 수위 3.5m, 12분 지속 (조건 충족)
        events = generate_water_level_events(
            station_id="ST001",
            start_time=datetime.now(),
            duration_minutes=12,
            water_level=3.5
        )
        
        results = cep_engine.send_events_batch(events)
        
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == water_level_rule.id
        assert result.action_type == "alert"
        assert result.condition_met_duration >= timedelta(minutes=10)
    
    def test_condition_reset_when_below_threshold(self, cep_engine, water_level_rule):
        """조건 리셋 테스트 (수위가 임계값 아래로 내려갔다가 다시 올라감)"""
        cep_engine.register_rule(water_level_rule)
        
        # 시나리오: 3.5m(5분) → 2m(3분) → 3.5m(12분)
        # 처음 5분은 리셋되고, 마지막 12분에서 트리거
        events = generate_mixed_water_level_events(
            station_id="ST001",
            start_time=datetime.now(),
            segments=[
                (5, 3.5),   # 5분간 3.5m (조건 충족 but 지속 시간 부족)
                (3, 2.0),   # 3분간 2m (조건 미충족 - 리셋)
                (12, 3.5),  # 12분간 3.5m (조건 충족 + 지속 시간 충족)
            ]
        )
        
        results = cep_engine.send_events_batch(events)
        
        assert len(results) == 1
    
    def test_multiple_stations(self, cep_engine, water_level_rule):
        """다중 관측소 테스트"""
        cep_engine.register_rule(water_level_rule)
        
        base_time = datetime.now()
        
        # 관측소 1: 조건 충족 (3.5m, 12분)
        events1 = generate_water_level_events(
            station_id="ST001",
            start_time=base_time,
            duration_minutes=12,
            water_level=3.5
        )
        
        # 관측소 2: 조건 미충족 (2m)
        events2 = generate_water_level_events(
            station_id="ST002",
            start_time=base_time,
            duration_minutes=15,
            water_level=2.0
        )
        
        # 관측소 3: 조건 충족 (4m, 11분)
        events3 = generate_water_level_events(
            station_id="ST003",
            start_time=base_time,
            duration_minutes=11,
            water_level=4.0
        )
        
        # 모든 이벤트 병합 및 전송
        all_events = events1 + events2 + events3
        results = cep_engine.send_events_batch(all_events)
        
        # ST001과 ST003만 트리거
        assert len(results) == 2
        triggered_sources = {r.matching_events[0].source_id for r in results}
        assert "ST001" in triggered_sources
        assert "ST003" in triggered_sources
        assert "ST002" not in triggered_sources
    
    def test_callback_invocation(self, cep_engine, water_level_rule):
        """콜백 호출 테스트"""
        cep_engine.register_rule(water_level_rule)
        
        callback_results = []
        cep_engine.add_trigger_callback(lambda r: callback_results.append(r))
        
        events = generate_water_level_events(
            station_id="ST001",
            start_time=datetime.now(),
            duration_minutes=12,
            water_level=3.5
        )
        
        cep_engine.send_events_batch(events)
        
        assert len(callback_results) == 1
        assert callback_results[0].rule_name == "수위 이상 감지"


# ============================================================================
# 자연어 규칙 생성 테스트
# ============================================================================

class TestNaturalLanguageRuleCreation:
    """자연어에서 규칙 생성 테스트"""
    
    def test_create_water_level_rule(self):
        """수위 규칙 생성"""
        rule = create_rule_from_natural_language(
            rule_id="test-rule-1",
            name="수위 이상 감지",
            description="테스트",
            natural_language="수위가 3m 이상 10분 지속되면 알람"
        )
        
        assert rule.field_name == "water_level"
        assert rule.threshold == 3.0
        assert rule.operator == ConditionOperator.GTE
        assert rule.duration_minutes == 10
    
    def test_create_flow_rate_rule(self):
        """유량 규칙 생성"""
        rule = create_rule_from_natural_language(
            rule_id="test-rule-2",
            name="유량 급증",
            description="테스트",
            natural_language="유량이 100 이상 5분 지속되면"
        )
        
        assert rule.field_name == "flow_rate"
        assert rule.threshold == 100.0
        assert rule.duration_minutes == 5
    
    def test_create_rule_with_hours(self):
        """시간 단위 규칙 생성"""
        rule = create_rule_from_natural_language(
            rule_id="test-rule-3",
            name="장시간 이상",
            description="테스트",
            natural_language="수위가 2m 초과 1시간 이상 지속"
        )
        
        assert rule.threshold == 2.0
        assert rule.operator == ConditionOperator.GT
        assert rule.duration_minutes == 60


# ============================================================================
# 시뮬레이션 테스트 (10분 가상 시간)
# ============================================================================

class TestTimeSimulation:
    """가상 시간 시뮬레이션 테스트"""
    
    def test_simulate_10_minute_alert(self):
        """10분 알람 시뮬레이션 테스트"""
        engine = SimpleCEPEngine()
        
        # 규칙 등록: 수위 3m 이상 10분 지속 시 알람
        rule = EventRule(
            id="sim-rule-001",
            name="수위 이상 10분 지속 알람",
            description="시뮬레이션 테스트",
            field_name="water_level",
            operator=ConditionOperator.GTE,
            threshold=3.0,
            window_minutes=30,
            duration_minutes=10,
            action_type="alert"
        )
        engine.register_rule(rule)
        
        # 알람 수신 기록
        alarms = []
        engine.add_trigger_callback(lambda r: alarms.append(r))
        
        # 시뮬레이션: 현재 시간에서 시작해서 15분간 수위 3.5m
        base_time = datetime(2025, 1, 11, 10, 0, 0)  # 10:00:00
        
        events = generate_water_level_events(
            station_id="한강대교",
            start_time=base_time,
            duration_minutes=15,
            water_level=3.5,
            interval_seconds=60  # 1분 간격
        )
        
        print(f"\n=== 시뮬레이션 시작 ===")
        print(f"관측소: 한강대교")
        print(f"조건: 수위 >= 3m, 10분 이상 지속")
        print(f"시작 시간: {base_time}")
        print(f"총 이벤트 수: {len(events)}")
        
        # 이벤트 순차 전송 (시뮬레이션)
        for event in events:
            engine.send_event(event)
        
        print(f"\n=== 결과 ===")
        print(f"발생한 알람 수: {len(alarms)}")
        
        for alarm in alarms:
            print(f"알람 발생: {alarm.rule_name}")
            print(f"  - 트리거 시간: {alarm.triggered_at}")
            print(f"  - 지속 시간: {alarm.condition_met_duration}")
            print(f"  - 매칭 이벤트 수: {len(alarm.matching_events)}")
        
        # 검증
        assert len(alarms) == 1
        assert alarms[0].condition_met_duration >= timedelta(minutes=10)
        
        engine.clear()
    
    def test_no_alert_when_condition_drops(self):
        """조건 중간 하락 시 알람 없음 테스트"""
        engine = SimpleCEPEngine()
        
        rule = EventRule(
            id="sim-rule-002",
            name="수위 이상 10분 지속 알람",
            description="시뮬레이션 테스트",
            field_name="water_level",
            operator=ConditionOperator.GTE,
            threshold=3.0,
            window_minutes=30,
            duration_minutes=10,
            action_type="alert"
        )
        engine.register_rule(rule)
        
        alarms = []
        engine.add_trigger_callback(lambda r: alarms.append(r))
        
        base_time = datetime(2025, 1, 11, 10, 0, 0)
        
        # 시나리오: 3.5m(8분) → 2m(2분) → 3.5m(8분)
        # 조건이 중간에 끊기므로 알람 없음
        events = generate_mixed_water_level_events(
            station_id="한강대교",
            start_time=base_time,
            segments=[
                (8, 3.5),  # 8분간 조건 충족
                (2, 2.0),  # 2분간 조건 미충족 (리셋)
                (8, 3.5),  # 8분간 조건 충족 (but 10분 미만)
            ]
        )
        
        print(f"\n=== 조건 하락 시뮬레이션 ===")
        print(f"시나리오: 3.5m(8분) → 2m(2분) → 3.5m(8분)")
        
        for event in events:
            engine.send_event(event)
        
        print(f"발생한 알람 수: {len(alarms)} (예상: 0)")
        
        assert len(alarms) == 0
        
        engine.clear()


# ============================================================================
# E2E 테스트 (DB 연결 필요)
# ============================================================================

class TestE2EWithMockDB:
    """E2E 테스트 (Mock DB)"""
    
    @pytest.mark.asyncio
    async def test_full_flow_with_mock(self):
        """전체 흐름 테스트 (Mock)"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # 1. 이벤트 규칙 생성
        rule_data = {
            "name": "수위 이상 감지 테스트",
            "description": "수위 3m 이상 10분 지속 시 알람",
            "natural_language_condition": "수위가 3m 이상 10분 지속되면",
            "sql": "SELECT * FROM water_level WHERE level >= 3.0",
            "check_interval_minutes": 1,
            "condition_threshold": "rows > 0",
            "action_type": "alert",
            "alert_config": {"channels": ["platform"], "message": "수위 이상!"}
        }
        
        response = client.post("/text2sql/events/rules", json=rule_data)
        assert response.status_code == 200
        
        rule = response.json()
        rule_id = rule["id"]
        
        # 2. CEP 엔진에 규칙 등록 (SimpleCEP 사용)
        engine = get_simple_cep_engine()
        
        cep_rule = EventRule(
            id=rule_id,
            name=rule["name"],
            description=rule["description"],
            field_name="water_level",
            operator=ConditionOperator.GTE,
            threshold=3.0,
            window_minutes=30,
            duration_minutes=10,
            action_type="alert"
        )
        engine.register_rule(cep_rule)
        
        # 3. 알람 콜백 설정
        triggered_alarms = []
        engine.add_trigger_callback(lambda r: triggered_alarms.append(r))
        
        # 4. 가짜 이벤트 생성 및 전송 (10분 시뮬레이션)
        events = generate_water_level_events(
            station_id="TEST-ST001",
            start_time=datetime.now(),
            duration_minutes=12,
            water_level=3.5
        )
        
        for event in events:
            engine.send_event(event)
        
        # 5. 알람 확인
        assert len(triggered_alarms) == 1
        assert triggered_alarms[0].rule_id == rule_id
        
        # 6. 알림 확인 (플랫폼 알림)
        notifications_response = client.get("/text2sql/events/notifications")
        # 알림이 CEP 콜백을 통해 추가되었는지 확인하려면 추가 연동 필요
        
        # 정리
        client.delete(f"/text2sql/events/rules/{rule_id}")
        engine.clear()


# ============================================================================
# 폴링 서비스 테스트
# ============================================================================

class TestPollingService:
    """폴링 서비스 테스트"""
    
    @pytest.mark.asyncio
    async def test_polling_with_simulated_data(self):
        """폴링 + 시뮬레이션 데이터 테스트"""
        from app.core.simple_cep import SimpleCEPEngine, EventRule, Event, ConditionOperator
        
        engine = SimpleCEPEngine()
        
        # 규칙 등록
        rule = EventRule(
            id="poll-test-001",
            name="폴링 테스트 규칙",
            description="수위 3m 이상 10분 지속",
            field_name="water_level",
            operator=ConditionOperator.GTE,
            threshold=3.0,
            window_minutes=30,
            duration_minutes=10,
            action_type="alert"
        )
        engine.register_rule(rule)
        
        alarms = []
        engine.add_trigger_callback(lambda r: alarms.append(r))
        
        # 시뮬레이션된 DB 응답 (폴링 결과)
        simulated_db_rows = []
        base_time = datetime(2025, 1, 11, 14, 0, 0)
        
        # 15분간의 데이터 생성
        for i in range(15):
            simulated_db_rows.append({
                "station_id": "한강대교관측소",
                "water_level": 3.5,
                "measured_at": (base_time + timedelta(minutes=i)).isoformat()
            })
        
        # 폴링 시뮬레이션 (1분마다 데이터 조회)
        print("\n=== 폴링 시뮬레이션 ===")
        for row in simulated_db_rows:
            event = Event.from_db_row(row, "water_level", "measured_at")
            results = engine.send_event(event)
            
            if results:
                print(f"[{row['measured_at']}] 알람 트리거!")
        
        print(f"총 알람 수: {len(alarms)}")
        
        assert len(alarms) >= 1
        
        engine.clear()


# ============================================================================
# SQL 생성 연동 테스트 (Text2SQL)
# ============================================================================

class TestText2SQLIntegration:
    """Text2SQL 연동 테스트"""
    
    def test_chat_generates_event_config(self):
        """Chat API로 이벤트 설정 생성"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        chat_request = {
            "message": "수위가 3m 이상 10분 이상 지속되면 알람을 줘",
            "history": [],
            "current_config": {},
            "step": "initial"
        }
        
        response = client.post("/text2sql/events/chat", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["response"]
        
        # 추출된 설정 확인
        config = data.get("extracted_config", {})
        print(f"\n=== Chat API 응답 ===")
        print(f"응답: {data['response'][:200]}...")
        print(f"추출된 설정: {config}")
        
        # 조건, 간격, 조치 타입이 추출되어야 함
        assert config.get("condition") or config.get("interval") or config.get("action_type")


# ============================================================================
# 시뮬레이션 API 테스트
# ============================================================================

class TestSimulationAPI:
    """시뮬레이션 API 테스트"""
    
    def test_simulation_triggers_alarm(self):
        """시뮬레이션으로 알람 트리거 테스트"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # 조건 충족: 수위 3.5m, 12분 지속 (10분 필요)
        simulation_request = {
            "rule_name": "수위 이상 감지 테스트",
            "natural_language_condition": "수위가 3m 이상 10분 이상 지속되면 알람",
            "field_name": "water_level",
            "threshold": 3.0,
            "duration_minutes": 10,
            "simulated_value": 3.5,
            "simulated_duration_minutes": 12,
            "station_id": "한강대교관측소"
        }
        
        response = client.post("/text2sql/events/simulate", json=simulation_request)
        assert response.status_code == 200
        
        data = response.json()
        print(f"\n=== 시뮬레이션 API 결과 ===")
        print(f"생성된 이벤트: {data['events_generated']}")
        print(f"트리거된 알람: {data['alarms_triggered']}")
        print(f"조건 상세: {data['condition_details']}")
        
        assert data["alarms_triggered"] == 1
        assert len(data["alarms"]) == 1
    
    def test_simulation_no_alarm_short_duration(self):
        """지속 시간 부족으로 알람 없음"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # 조건 미충족: 수위 3.5m, 5분 지속 (10분 필요)
        simulation_request = {
            "rule_name": "수위 이상 감지 테스트",
            "natural_language_condition": "수위가 3m 이상 10분 이상 지속되면",
            "field_name": "water_level",
            "threshold": 3.0,
            "duration_minutes": 10,
            "simulated_value": 3.5,
            "simulated_duration_minutes": 5,
            "station_id": "한강대교관측소"
        }
        
        response = client.post("/text2sql/events/simulate", json=simulation_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["alarms_triggered"] == 0
    
    def test_simulation_no_alarm_below_threshold(self):
        """임계값 미달로 알람 없음"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # 조건 미충족: 수위 2.5m (3m 필요)
        simulation_request = {
            "rule_name": "수위 이상 감지 테스트",
            "natural_language_condition": "수위가 3m 이상이면",
            "field_name": "water_level",
            "threshold": 3.0,
            "duration_minutes": 10,
            "simulated_value": 2.5,
            "simulated_duration_minutes": 15,
            "station_id": "한강대교관측소"
        }
        
        response = client.post("/text2sql/events/simulate", json=simulation_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["alarms_triggered"] == 0


class TestSimpleCEPAPI:
    """SimpleCEP API 테스트"""
    
    def test_simple_cep_status(self):
        """SimpleCEP 상태 조회"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/text2sql/events/simple-cep/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["available"] == True
        assert "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
