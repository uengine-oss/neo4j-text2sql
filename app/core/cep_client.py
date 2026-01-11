"""
Esper CEP 서비스 클라이언트

Esper CEP 마이크로서비스와 통신하여 이벤트 규칙을 동기화하고 
실시간 이벤트 감지를 관리합니다.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.smart_logger import SmartLogger


# CEP 서비스 URL (환경변수 또는 기본값)
CEP_SERVICE_URL = getattr(settings, 'CEP_SERVICE_URL', 'http://localhost:8088')


class CEPClient:
    """Esper CEP 서비스 클라이언트"""
    
    def __init__(self, base_url: str = CEP_SERVICE_URL):
        self.base_url = base_url.rstrip('/')
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
    async def _request(
        self, 
        method: str, 
        path: str, 
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """HTTP 요청 수행"""
        url = f"{self.base_url}{path}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            SmartLogger.log(
                "ERROR",
                f"CEP API error: {e.response.status_code}",
                category="cep.error",
                params={"url": url, "status": e.response.status_code}
            )
            raise
        except httpx.RequestError as e:
            SmartLogger.log(
                "WARNING",
                f"CEP service unavailable: {e}",
                category="cep.unavailable",
                params={"url": url}
            )
            raise ConnectionError(f"CEP service unavailable: {e}")
    
    # =========================================================================
    # 규칙 관리
    # =========================================================================
    
    async def create_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """CEP에 규칙 생성"""
        SmartLogger.log("INFO", f"Creating CEP rule: {rule_data.get('name')}", category="cep.rule.create")
        return await self._request("POST", "/api/rules", json_data=rule_data)
    
    async def update_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """CEP 규칙 업데이트"""
        SmartLogger.log("INFO", f"Updating CEP rule: {rule_id}", category="cep.rule.update")
        return await self._request("PUT", f"/api/rules/{rule_id}", json_data=rule_data)
    
    async def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        """CEP 규칙 삭제"""
        SmartLogger.log("INFO", f"Deleting CEP rule: {rule_id}", category="cep.rule.delete")
        return await self._request("DELETE", f"/api/rules/{rule_id}")
    
    async def toggle_rule(self, rule_id: str) -> Dict[str, Any]:
        """CEP 규칙 활성/비활성 토글"""
        return await self._request("POST", f"/api/rules/{rule_id}/toggle")
    
    async def get_rules(self) -> List[Dict[str, Any]]:
        """모든 CEP 규칙 조회"""
        return await self._request("GET", "/api/rules")
    
    async def get_active_rules(self) -> List[Dict[str, Any]]:
        """활성 CEP 규칙만 조회"""
        return await self._request("GET", "/api/rules/active")
    
    async def sync_rules(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """규칙 일괄 동기화"""
        SmartLogger.log("INFO", f"Syncing {len(rules)} rules to CEP", category="cep.rule.sync")
        return await self._request("POST", "/api/rules/sync", json_data=rules)
    
    # =========================================================================
    # 이벤트 전송
    # =========================================================================
    
    async def send_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """CEP에 이벤트 전송"""
        return await self._request(
            "POST", 
            "/api/events/send", 
            json_data=event_data,
            params={"eventType": event_type}
        )
    
    async def send_bulk_events(self, event_type: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """CEP에 벌크 이벤트 전송"""
        return await self._request(
            "POST", 
            "/api/events/send/bulk", 
            json_data=events,
            params={"eventType": event_type}
        )
    
    # =========================================================================
    # 상태 조회
    # =========================================================================
    
    async def get_status(self) -> Dict[str, Any]:
        """CEP 엔진 상태 조회"""
        try:
            return await self._request("GET", "/api/events/status")
        except Exception:
            return {"status": "unavailable", "activeRules": 0}
    
    async def get_triggers(
        self, 
        rule_id: Optional[str] = None,
        page: int = 0,
        size: int = 20
    ) -> Dict[str, Any]:
        """트리거 기록 조회"""
        params = {"page": page, "size": size}
        if rule_id:
            params["ruleId"] = rule_id
        return await self._request("GET", "/api/events/triggers", params=params)
    
    async def is_available(self) -> bool:
        """CEP 서비스 가용성 확인"""
        try:
            status = await self.get_status()
            return status.get("status") == "running"
        except Exception:
            return False


# 싱글톤 인스턴스
_cep_client: Optional[CEPClient] = None


def get_cep_client() -> CEPClient:
    """CEP 클라이언트 인스턴스 반환"""
    global _cep_client
    if _cep_client is None:
        _cep_client = CEPClient()
    return _cep_client


async def sync_rule_to_cep(rule: Dict[str, Any]) -> bool:
    """
    이벤트 규칙을 CEP 서비스에 동기화
    
    Args:
        rule: 이벤트 규칙 데이터
        
    Returns:
        성공 여부
    """
    client = get_cep_client()
    
    try:
        # 규칙 데이터를 CEP 형식으로 변환
        cep_rule = {
            "id": rule.get("id"),
            "name": rule.get("name"),
            "description": rule.get("description", ""),
            "naturalLanguageCondition": rule.get("natural_language_condition", ""),
            "checkIntervalMinutes": rule.get("check_interval_minutes", 10),
            "actionType": rule.get("action_type", "alert"),
            "alertConfig": json.dumps(rule.get("alert_config")) if rule.get("alert_config") else None,
            "processConfig": json.dumps(rule.get("process_config")) if rule.get("process_config") else None,
            "isActive": rule.get("is_active", True)
        }
        
        # EPL 쿼리는 CEP 서비스에서 자동 생성
        await client.create_rule(cep_rule)
        
        SmartLogger.log(
            "INFO",
            f"Rule synced to CEP: {rule.get('name')}",
            category="cep.sync.success"
        )
        return True
        
    except Exception as e:
        SmartLogger.log(
            "WARNING",
            f"Failed to sync rule to CEP: {e}",
            category="cep.sync.failed"
        )
        return False


async def delete_rule_from_cep(rule_id: str) -> bool:
    """CEP에서 규칙 삭제"""
    client = get_cep_client()
    
    try:
        await client.delete_rule(rule_id)
        return True
    except Exception as e:
        SmartLogger.log(
            "WARNING",
            f"Failed to delete rule from CEP: {e}",
            category="cep.delete.failed"
        )
        return False
