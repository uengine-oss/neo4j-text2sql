"""
이벤트 감지 및 조치 API 테스트

테스트 항목:
1. 이벤트 규칙 CRUD
2. 이벤트 규칙 활성/비활성
3. 이벤트 실행 (조건 체크)
4. 알림 관리
5. 스케줄러 관리
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.main import app
from app.routers.events import (
    _event_rules,
    _notifications,
    _scheduler_tasks,
    EventRule,
    AlertConfig,
    ProcessConfig,
    _evaluate_condition
)


# 테스트 전 초기화
@pytest.fixture(autouse=True)
def clear_state():
    """각 테스트 전 상태 초기화"""
    _event_rules.clear()
    _notifications.clear()
    _scheduler_tasks.clear()
    yield
    _event_rules.clear()
    _notifications.clear()
    _scheduler_tasks.clear()


@pytest.fixture
def client():
    """동기 테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
def sample_event_data():
    """샘플 이벤트 규칙 데이터"""
    return {
        "name": "수위 이상 감지",
        "description": "수위가 경고 수준 이상 지속 시 알림",
        "natural_language_condition": "수위가 3m 이상인 관측소가 10분 이상 지속되면",
        "sql": "SELECT station_id, water_level FROM water_level_readings WHERE water_level >= 3.0",
        "check_interval_minutes": 10,
        "condition_threshold": "rows > 0",
        "action_type": "alert",
        "alert_config": {
            "channels": ["platform", "email"],
            "message": "수위 이상 경고!"
        }
    }


@pytest.fixture
def sample_process_event_data():
    """프로세스 실행 이벤트 규칙 데이터"""
    return {
        "name": "유량 급증 감지",
        "description": "유량이 급격히 증가하면 유량 관리 프로세스 실행",
        "natural_language_condition": "현재 유량이 평균 유량의 150% 이상이면",
        "sql": "SELECT station_id, flow_rate FROM flow_readings WHERE flow_rate > 100",
        "check_interval_minutes": 5,
        "condition_threshold": "rows > 0",
        "action_type": "process",
        "process_config": {
            "process_name": "유량_관리_프로세스",
            "process_params": {"threshold": 100}
        }
    }


class TestEventRuleCRUD:
    """이벤트 규칙 CRUD 테스트"""
    
    def test_list_rules_empty(self, client):
        """빈 규칙 목록 조회"""
        response = client.get("/text2sql/events/rules")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_create_rule(self, client, sample_event_data):
        """이벤트 규칙 생성"""
        response = client.post("/text2sql/events/rules", json=sample_event_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == sample_event_data["name"]
        assert data["sql"] == sample_event_data["sql"]
        assert data["action_type"] == "alert"
        assert data["is_active"] == True
        assert "id" in data
        assert "created_at" in data
    
    def test_create_rule_with_process(self, client, sample_process_event_data):
        """프로세스 실행 이벤트 규칙 생성"""
        response = client.post("/text2sql/events/rules", json=sample_process_event_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["action_type"] == "process"
        assert data["process_config"]["process_name"] == "유량_관리_프로세스"
    
    def test_create_rule_invalid_sql(self, client, sample_event_data):
        """잘못된 SQL로 규칙 생성 시 실패"""
        sample_event_data["sql"] = "DELETE FROM users"  # 위험한 SQL
        response = client.post("/text2sql/events/rules", json=sample_event_data)
        assert response.status_code == 400
    
    def test_list_rules_with_data(self, client, sample_event_data):
        """규칙 목록 조회 (데이터 있음)"""
        # 규칙 생성
        client.post("/text2sql/events/rules", json=sample_event_data)
        
        # 목록 조회
        response = client.get("/text2sql/events/rules")
        assert response.status_code == 200
        
        rules = response.json()
        assert len(rules) == 1
        assert rules[0]["name"] == sample_event_data["name"]
    
    def test_get_rule(self, client, sample_event_data):
        """규칙 상세 조회"""
        # 규칙 생성
        create_response = client.post("/text2sql/events/rules", json=sample_event_data)
        event_id = create_response.json()["id"]
        
        # 상세 조회
        response = client.get(f"/text2sql/events/rules/{event_id}")
        assert response.status_code == 200
        assert response.json()["id"] == event_id
    
    def test_get_rule_not_found(self, client):
        """존재하지 않는 규칙 조회"""
        response = client.get("/text2sql/events/rules/nonexistent-id")
        assert response.status_code == 404
    
    def test_update_rule(self, client, sample_event_data):
        """규칙 수정"""
        # 규칙 생성
        create_response = client.post("/text2sql/events/rules", json=sample_event_data)
        event_id = create_response.json()["id"]
        
        # 수정
        update_data = {
            "name": "수정된 규칙 이름",
            "check_interval_minutes": 15
        }
        response = client.put(f"/text2sql/events/rules/{event_id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "수정된 규칙 이름"
        assert data["check_interval_minutes"] == 15
    
    def test_delete_rule(self, client, sample_event_data):
        """규칙 삭제"""
        # 규칙 생성
        create_response = client.post("/text2sql/events/rules", json=sample_event_data)
        event_id = create_response.json()["id"]
        
        # 삭제
        response = client.delete(f"/text2sql/events/rules/{event_id}")
        assert response.status_code == 200
        
        # 삭제 확인
        get_response = client.get(f"/text2sql/events/rules/{event_id}")
        assert get_response.status_code == 404
    
    def test_toggle_rule(self, client, sample_event_data):
        """규칙 활성/비활성 토글"""
        # 규칙 생성
        create_response = client.post("/text2sql/events/rules", json=sample_event_data)
        event_id = create_response.json()["id"]
        
        # 토글 (활성 → 비활성)
        response = client.post(f"/text2sql/events/rules/{event_id}/toggle")
        assert response.status_code == 200
        assert response.json()["is_active"] == False
        
        # 토글 (비활성 → 활성)
        response = client.post(f"/text2sql/events/rules/{event_id}/toggle")
        assert response.status_code == 200
        assert response.json()["is_active"] == True


class TestConditionEvaluation:
    """조건 평가 테스트"""
    
    def test_rows_greater_than_zero(self):
        """rows > 0 조건"""
        assert _evaluate_condition("rows > 0", 5, {}) == True
        assert _evaluate_condition("rows > 0", 0, {}) == False
    
    def test_rows_greater_equal(self):
        """rows >= N 조건"""
        assert _evaluate_condition("rows >= 5", 5, {}) == True
        assert _evaluate_condition("rows >= 5", 4, {}) == False
    
    def test_rows_equal(self):
        """rows == N 조건"""
        assert _evaluate_condition("rows == 10", 10, {}) == True
        assert _evaluate_condition("rows == 10", 5, {}) == False
    
    def test_rows_not_equal(self):
        """rows != N 조건"""
        assert _evaluate_condition("rows != 0", 5, {}) == True
        assert _evaluate_condition("rows != 0", 0, {}) == False
    
    def test_invalid_condition_fallback(self):
        """잘못된 조건은 기본값으로 폴백"""
        assert _evaluate_condition("invalid condition", 5, {}) == True
        assert _evaluate_condition("invalid condition", 0, {}) == False


class TestNotifications:
    """알림 관리 테스트"""
    
    def test_list_notifications_empty(self, client):
        """빈 알림 목록 조회"""
        response = client.get("/text2sql/events/notifications")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_acknowledge_notification_not_found(self, client):
        """존재하지 않는 알림 확인 처리"""
        response = client.post("/text2sql/events/notifications/nonexistent-id/acknowledge")
        assert response.status_code == 404


class TestScheduler:
    """스케줄러 관리 테스트"""
    
    def test_scheduler_status_initial(self, client):
        """초기 스케줄러 상태"""
        response = client.get("/text2sql/events/scheduler/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["running"] == False
        assert data["active_tasks"] == 0
    
    def test_start_scheduler(self, client):
        """스케줄러 시작"""
        response = client.post("/text2sql/events/scheduler/start")
        assert response.status_code == 200
        assert "Scheduler started" in response.json()["message"]
    
    def test_stop_scheduler(self, client):
        """스케줄러 중지"""
        # 시작
        client.post("/text2sql/events/scheduler/start")
        
        # 중지
        response = client.post("/text2sql/events/scheduler/stop")
        assert response.status_code == 200
        assert "Scheduler stopped" in response.json()["message"]


class TestMCPIntegration:
    """MCP 클라이언트 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_mcp_client_import(self):
        """MCP 클라이언트 모듈 임포트"""
        from app.core.mcp_client import (
            MCPClient,
            MCPServerConfig,
            WorkAssistantClient,
            execute_process_via_mcp
        )
        
        # 클래스가 정상적으로 임포트되는지 확인
        assert MCPClient is not None
        assert WorkAssistantClient is not None
    
    @pytest.mark.asyncio
    async def test_work_assistant_client_init(self):
        """WorkAssistant 클라이언트 초기화"""
        from app.core.mcp_client import WorkAssistantClient
        
        client = WorkAssistantClient(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        assert client.supabase_url == "https://test.supabase.co"
        assert client.supabase_key == "test-key"
    
    @pytest.mark.asyncio
    async def test_execute_process_via_mcp_mock(self):
        """MCP를 통한 프로세스 실행 (Mock)"""
        from app.core.mcp_client import execute_process_via_mcp, get_work_assistant_client
        
        # Mock 설정
        with patch.object(
            get_work_assistant_client(),
            'execute_process',
            new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "process_name": "test_process",
                "result": {"status": "completed"}
            }
            
            result = await execute_process_via_mcp(
                process_name="test_process",
                params={"param1": "value1"},
                event_data={"event_id": "test-event"}
            )
            
            # 결과 검증
            assert result["success"] == True
            assert result["process_name"] == "test_process"


# 실제 이벤트 실행 테스트 (DB 연결 필요)
class TestEventExecution:
    """이벤트 실행 테스트 (Integration)"""
    
    @pytest.mark.skip(reason="DB 연결 필요")
    def test_run_event_check(self, client, sample_event_data):
        """이벤트 규칙 수동 실행"""
        # 규칙 생성
        create_response = client.post("/text2sql/events/rules", json=sample_event_data)
        event_id = create_response.json()["id"]
        
        # 수동 실행
        response = client.post(f"/text2sql/events/rules/{event_id}/run")
        assert response.status_code == 200
        
        data = response.json()
        assert data["event_id"] == event_id
        assert "executed_at" in data
        assert "condition_met" in data


# ============================================================================
# 대화형 이벤트 설정 Chat API 테스트
# ============================================================================

class TestEventChatAPI:
    """대화형 이벤트 설정 API 테스트"""
    
    def test_chat_initial_message(self, client):
        """초기 대화 메시지 테스트"""
        chat_request = {
            "message": "수위가 3m 이상이면 알려줘",
            "history": [],
            "current_config": {},
            "step": "initial"
        }
        
        response = client.post("/text2sql/events/chat", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "extracted_config" in data
        assert "ready_to_confirm" in data
        assert len(data["response"]) > 0
    
    def test_chat_extract_water_level(self, client):
        """수위 조건 추출 테스트"""
        chat_request = {
            "message": "수위가 3m 이상이면 유량관리 프로세스를 실행해줘",
            "history": [],
            "current_config": {},
            "step": "initial"
        }
        
        response = client.post("/text2sql/events/chat", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("extracted_config", {})
        
        # 조건 추출 확인
        assert config is not None
        # 프로세스 실행 타입이어야 함
        assert config.get("action_type") == "process"
    
    def test_chat_extract_interval(self, client):
        """시간 간격 추출 테스트"""
        chat_request = {
            "message": "5분마다 수위를 확인해서 3m 초과면 알려줘",
            "history": [],
            "current_config": {},
            "step": "initial"
        }
        
        response = client.post("/text2sql/events/chat", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("extracted_config", {})
        
        assert config is not None
        assert config.get("interval") == 5
    
    def test_chat_modification_request(self, client):
        """수정 요청 처리 테스트"""
        chat_request = {
            "message": "간격을 10분으로 변경해줘",
            "history": [
                {"role": "user", "content": "수위가 3m 이상이면 알려줘"},
                {"role": "assistant", "content": "설정했습니다."}
            ],
            "current_config": {
                "condition": "수위가 3m 이상",
                "interval": 5,
                "action_type": "alert"
            },
            "step": "confirm"
        }
        
        response = client.post("/text2sql/events/chat", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "10분" in data["response"]
    
    def test_chat_change_action_type(self, client):
        """조치 유형 변경 테스트"""
        chat_request = {
            "message": "알림으로 변경해줘",
            "history": [],
            "current_config": {
                "action_type": "process"
            },
            "step": "confirm"
        }
        
        response = client.post("/text2sql/events/chat", json=chat_request)
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("extracted_config", {})
        
        # 알림 유형으로 변경 확인
        assert "알림" in data["response"]


# ============================================================================
# CEP 콜백 테스트
# ============================================================================

class TestCEPCallbacks:
    """CEP 서비스 콜백 테스트"""
    
    def test_cep_alert_callback(self, client):
        """CEP 알림 콜백 처리 테스트"""
        callback_data = {
            "rule_id": "test-rule-123",
            "rule_name": "수위 이상 감지",
            "description": "수위 3m 초과",
            "condition": "수위 >= 3m",
            "event_count": 5,
            "triggered_at": "2025-01-11T10:00:00"
        }
        
        response = client.post("/text2sql/events/cep-alert", json=callback_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "processed"
        assert "notification_id" in data
        
        # 알림이 생성되었는지 확인
        notifications_response = client.get("/text2sql/events/notifications")
        assert notifications_response.status_code == 200
        notifications = notifications_response.json()
        assert len(notifications) > 0
        assert notifications[0]["event_id"] == "test-rule-123"
    
    def test_cep_process_callback(self, client):
        """CEP 프로세스 콜백 처리 테스트"""
        callback_data = {
            "rule_id": "test-rule-456",
            "rule_name": "유량 급증 감지",
            "process_config": '{"process_name": "flow_management", "process_params": {}}',
            "event_count": 3,
            "triggered_at": "2025-01-11T10:30:00",
            "trigger_event": {"station_id": "ST001", "rate": 150.5}
        }
        
        response = client.post("/text2sql/events/cep-process", json=callback_data)
        assert response.status_code == 200
        
        data = response.json()
        # MCP 클라이언트가 없어도 로깅됨
        assert data["status"] in ["executed", "logged", "error"]
    
    def test_cep_status(self, client):
        """CEP 상태 조회 테스트"""
        response = client.get("/text2sql/events/cep/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "local_scheduler_running" in data
        assert "local_active_tasks" in data


# ============================================================================
# 자연어 정보 추출 테스트
# ============================================================================

class TestEventInfoExtraction:
    """자연어에서 이벤트 정보 추출 테스트"""
    
    def test_extract_water_level_condition(self):
        """수위 조건 추출"""
        from app.routers.events import _extract_event_info
        
        result = _extract_event_info("수위가 3m 이상이면")
        assert result.get("condition") is not None
        assert "수위" in result.get("condition", "") or "3" in result.get("condition", "")
    
    def test_extract_process_action(self):
        """프로세스 실행 조치 추출"""
        from app.routers.events import _extract_event_info
        
        result = _extract_event_info("유량관리 프로세스를 자동 실행해줘")
        assert result.get("action_type") == "process"
    
    def test_extract_alert_action(self):
        """알림 조치 추출"""
        from app.routers.events import _extract_event_info
        
        result = _extract_event_info("이상 징후가 감지되면 알려줘")
        assert result.get("action_type") == "alert"
    
    def test_extract_interval_minutes(self):
        """분 단위 간격 추출"""
        from app.routers.events import _extract_event_info
        
        result = _extract_event_info("10분마다 확인해서")
        assert result.get("interval") == 10
    
    def test_extract_interval_hours(self):
        """시간 단위 간격 추출"""
        from app.routers.events import _extract_event_info
        
        result = _extract_event_info("1시간마다 확인해줘")
        assert result.get("interval") == 60
    
    def test_default_interval(self):
        """기본 간격값 설정"""
        from app.routers.events import _extract_event_info
        
        result = _extract_event_info("수위 이상이면 알려줘")
        assert result.get("interval") == 10  # 기본값


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
