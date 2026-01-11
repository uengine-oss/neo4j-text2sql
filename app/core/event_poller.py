"""
Event Poller Service

PostgreSQL에서 주기적으로 데이터를 폴링하여 CEP 엔진에 전송합니다.

기능:
1. 이벤트 규칙의 SQL을 주기적으로 실행
2. 결과를 SimpleCEP 엔진에 이벤트로 전송
3. 트리거 시 알람 콜백 처리
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.core.simple_cep import (
    SimpleCEPEngine, 
    EventRule as CEPRule, 
    Event, 
    TriggerResult,
    ConditionOperator,
    get_simple_cep_engine
)
from app.core.sql_exec import SQLExecutor, SQLExecutionError
from app.core.sql_guard import SQLGuard
from app.smart_logger import SmartLogger


class EventPoller:
    """
    이벤트 폴러
    
    등록된 이벤트 규칙을 주기적으로 실행하고
    CEP 엔진에 결과를 전송합니다.
    """
    
    def __init__(self, cep_engine: Optional[SimpleCEPEngine] = None):
        self.cep_engine = cep_engine or get_simple_cep_engine()
        self.polling_rules: Dict[str, Dict[str, Any]] = {}  # rule_id -> {sql, interval, task}
        self.is_running = False
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self.alarm_callbacks: List[Callable[[TriggerResult], None]] = []
        
        # CEP 알람 콜백 등록
        self.cep_engine.add_trigger_callback(self._handle_cep_trigger)
    
    def _handle_cep_trigger(self, result: TriggerResult) -> None:
        """CEP 트리거 결과 처리"""
        SmartLogger.log(
            "INFO",
            f"CEP Trigger: {result.rule_name} - Duration: {result.condition_met_duration}",
            category="poller.trigger"
        )
        
        # 알람 콜백 호출
        for callback in self.alarm_callbacks:
            try:
                callback(result)
            except Exception as e:
                SmartLogger.log("ERROR", f"Alarm callback error: {e}", category="poller.callback.error")
    
    def add_alarm_callback(self, callback: Callable[[TriggerResult], None]) -> None:
        """알람 콜백 추가"""
        self.alarm_callbacks.append(callback)
    
    async def register_polling_rule(
        self,
        rule_id: str,
        name: str,
        sql: str,
        check_interval_minutes: int,
        field_name: str,
        operator: ConditionOperator,
        threshold: float,
        duration_minutes: int,
        action_type: str = "alert"
    ) -> str:
        """
        폴링 규칙 등록
        
        Args:
            rule_id: 규칙 ID
            name: 규칙 이름
            sql: 데이터 조회 SQL
            check_interval_minutes: 폴링 간격 (분)
            field_name: 감시할 필드명
            operator: 비교 연산자
            threshold: 임계값
            duration_minutes: 지속 시간 조건 (분)
            action_type: 조치 유형 ("alert" | "process")
        """
        # CEP 규칙 생성 및 등록
        cep_rule = CEPRule(
            id=rule_id,
            name=name,
            description=f"SQL: {sql[:50]}...",
            field_name=field_name,
            operator=operator,
            threshold=threshold,
            window_minutes=max(30, duration_minutes * 2),
            duration_minutes=duration_minutes,
            action_type=action_type
        )
        self.cep_engine.register_rule(cep_rule)
        
        # 폴링 정보 저장
        self.polling_rules[rule_id] = {
            "sql": sql,
            "interval_minutes": check_interval_minutes,
            "field_name": field_name,
            "last_polled_at": None
        }
        
        # 폴링 시작
        if self.is_running:
            self._start_polling_task(rule_id)
        
        SmartLogger.log("INFO", f"Polling rule registered: {name}", category="poller.register")
        return rule_id
    
    async def unregister_polling_rule(self, rule_id: str) -> None:
        """폴링 규칙 등록 해제"""
        # 폴링 태스크 중지
        if rule_id in self._polling_tasks:
            self._polling_tasks[rule_id].cancel()
            del self._polling_tasks[rule_id]
        
        # CEP 규칙 해제
        self.cep_engine.unregister_rule(rule_id)
        
        # 폴링 정보 삭제
        if rule_id in self.polling_rules:
            del self.polling_rules[rule_id]
        
        SmartLogger.log("INFO", f"Polling rule unregistered: {rule_id}", category="poller.unregister")
    
    async def start(self, db_pool) -> None:
        """폴러 시작"""
        self.is_running = True
        self._db_pool = db_pool
        
        # 등록된 모든 규칙에 대해 폴링 시작
        for rule_id in self.polling_rules:
            self._start_polling_task(rule_id)
        
        SmartLogger.log("INFO", "Event poller started", category="poller.start")
    
    async def stop(self) -> None:
        """폴러 중지"""
        self.is_running = False
        
        # 모든 폴링 태스크 취소
        for task in self._polling_tasks.values():
            task.cancel()
        self._polling_tasks.clear()
        
        SmartLogger.log("INFO", "Event poller stopped", category="poller.stop")
    
    def _start_polling_task(self, rule_id: str) -> None:
        """폴링 태스크 시작"""
        if rule_id in self._polling_tasks:
            return
        
        async def polling_loop():
            rule_info = self.polling_rules.get(rule_id)
            if not rule_info:
                return
            
            interval_seconds = rule_info["interval_minutes"] * 60
            
            while self.is_running:
                try:
                    await self._execute_poll(rule_id)
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    SmartLogger.log(
                        "ERROR",
                        f"Polling error for {rule_id}: {e}",
                        category="poller.error"
                    )
                    await asyncio.sleep(60)  # 오류 시 1분 대기
        
        task = asyncio.create_task(polling_loop())
        self._polling_tasks[rule_id] = task
    
    async def _execute_poll(self, rule_id: str) -> None:
        """폴링 실행 (SQL 실행 및 CEP 전송)"""
        rule_info = self.polling_rules.get(rule_id)
        if not rule_info:
            return
        
        sql = rule_info["sql"]
        field_name = rule_info["field_name"]
        
        try:
            async with self._db_pool.acquire() as conn:
                executor = SQLExecutor()
                guard = SQLGuard()
                validated_sql, _ = guard.validate(sql)
                
                result = await executor.execute_query(conn, validated_sql, timeout=60.0)
                rows = result.get("rows", [])
                columns = result.get("columns", [])
                
                # 각 행을 이벤트로 변환하여 CEP에 전송
                for row in rows:
                    row_dict = dict(zip(columns, row)) if isinstance(row, (list, tuple)) else row
                    
                    event = Event(
                        timestamp=datetime.now(),
                        source_id=str(row_dict.get("station_id", row_dict.get("source_id", "unknown"))),
                        event_type=field_name,
                        data=row_dict
                    )
                    
                    self.cep_engine.send_event(event)
                
                rule_info["last_polled_at"] = datetime.now().isoformat()
                
                SmartLogger.log(
                    "DEBUG",
                    f"Polled {len(rows)} rows for rule {rule_id}",
                    category="poller.execute"
                )
                
        except SQLExecutionError as e:
            SmartLogger.log("ERROR", f"SQL error in polling: {e}", category="poller.sql.error")
        except Exception as e:
            SmartLogger.log("ERROR", f"Polling error: {e}", category="poller.error")
    
    async def poll_with_simulated_events(
        self,
        rule_id: str,
        events: List[Event]
    ) -> List[TriggerResult]:
        """
        시뮬레이션 이벤트로 폴링 (테스트용)
        
        실제 DB 폴링 대신 제공된 이벤트 목록을 사용합니다.
        """
        results = []
        
        for event in events:
            trigger_results = self.cep_engine.send_event(event)
            results.extend(trigger_results)
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """폴러 상태 조회"""
        return {
            "is_running": self.is_running,
            "polling_rules_count": len(self.polling_rules),
            "active_tasks": len(self._polling_tasks),
            "cep_status": self.cep_engine.get_status(),
            "rules": {
                rule_id: {
                    "last_polled_at": info.get("last_polled_at"),
                    "interval_minutes": info.get("interval_minutes")
                }
                for rule_id, info in self.polling_rules.items()
            }
        }


# 싱글톤 인스턴스
_event_poller: Optional[EventPoller] = None


def get_event_poller() -> EventPoller:
    """EventPoller 인스턴스 반환"""
    global _event_poller
    if _event_poller is None:
        _event_poller = EventPoller()
    return _event_poller
