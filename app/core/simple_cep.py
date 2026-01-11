"""
Simple CEP (Complex Event Processing) Engine
Python 기반 간단한 CEP 엔진 - Esper 대신 사용할 수 있는 경량 버전

특징:
- 시간 윈도우 기반 이벤트 집계
- 조건 평가 및 알람 트리거
- 폴링 기반 데이터 수집
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

from app.smart_logger import SmartLogger


class ConditionOperator(Enum):
    """조건 연산자"""
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NE = "!="


@dataclass
class EventRule:
    """이벤트 규칙"""
    id: str
    name: str
    description: str
    # 감지 조건
    field_name: str  # 감시할 필드 (예: water_level)
    operator: ConditionOperator
    threshold: float
    # 시간 윈도우
    window_minutes: int  # 시간 윈도우 (분)
    duration_minutes: int  # 지속 조건 (분) - 이 시간 동안 조건이 유지되어야 트리거
    # 조치
    action_type: str  # "alert" | "process"
    action_config: Dict[str, Any] = field(default_factory=dict)
    # 상태
    is_active: bool = True
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0


@dataclass
class Event:
    """이벤트 데이터"""
    timestamp: datetime
    source_id: str  # 관측소/센서 ID
    event_type: str  # 이벤트 유형 (water_level, flow_rate 등)
    data: Dict[str, Any]
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any], event_type: str, timestamp_field: str = "measured_at") -> "Event":
        """DB 행에서 이벤트 생성"""
        ts = row.get(timestamp_field)
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif not isinstance(ts, datetime):
            ts = datetime.now()
        
        return cls(
            timestamp=ts,
            source_id=str(row.get("station_id", row.get("source_id", "unknown"))),
            event_type=event_type,
            data=row
        )


@dataclass
class TriggerResult:
    """트리거 결과"""
    rule_id: str
    rule_name: str
    triggered_at: datetime
    condition_met_duration: timedelta
    matching_events: List[Event]
    action_type: str
    action_result: Optional[str] = None


class SimpleCEPEngine:
    """
    간단한 CEP 엔진
    
    시간 윈도우 내의 이벤트를 집계하고 조건을 평가하여 알람을 트리거합니다.
    """
    
    def __init__(self):
        self.rules: Dict[str, EventRule] = {}
        self.event_buffer: Dict[str, List[Event]] = defaultdict(list)  # rule_id -> events
        self.trigger_callbacks: List[Callable[[TriggerResult], None]] = []
        self.is_running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 조건 상태 추적: rule_id -> {source_id -> first_condition_met_time}
        self.condition_state: Dict[str, Dict[str, datetime]] = defaultdict(dict)
    
    def register_rule(self, rule: EventRule) -> str:
        """규칙 등록"""
        self.rules[rule.id] = rule
        self.event_buffer[rule.id] = []
        self.condition_state[rule.id] = {}
        SmartLogger.log("INFO", f"CEP rule registered: {rule.name}", category="cep.register")
        return rule.id
    
    def unregister_rule(self, rule_id: str) -> None:
        """규칙 등록 해제"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            del self.event_buffer[rule_id]
            del self.condition_state[rule_id]
            SmartLogger.log("INFO", f"CEP rule unregistered: {rule_id}", category="cep.unregister")
    
    def add_trigger_callback(self, callback: Callable[[TriggerResult], None]) -> None:
        """트리거 콜백 추가"""
        self.trigger_callbacks.append(callback)
    
    def send_event(self, event: Event) -> List[TriggerResult]:
        """
        이벤트 전송 및 처리
        
        Returns:
            트리거된 결과 목록
        """
        results = []
        
        for rule_id, rule in self.rules.items():
            if not rule.is_active:
                continue
            
            # 이벤트 버퍼에 추가
            self.event_buffer[rule_id].append(event)
            
            # 윈도우 밖의 오래된 이벤트 제거
            cutoff_time = event.timestamp - timedelta(minutes=rule.window_minutes)
            self.event_buffer[rule_id] = [
                e for e in self.event_buffer[rule_id]
                if e.timestamp >= cutoff_time
            ]
            
            # 조건 평가
            result = self._evaluate_rule(rule, event)
            if result:
                results.append(result)
                
                # 콜백 호출
                for callback in self.trigger_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        SmartLogger.log("ERROR", f"Trigger callback error: {e}", category="cep.callback.error")
        
        return results
    
    def send_events_batch(self, events: List[Event]) -> List[TriggerResult]:
        """
        배치 이벤트 전송
        
        타임스탬프 순으로 정렬하여 처리합니다.
        """
        # 타임스탬프 순 정렬
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        all_results = []
        for event in sorted_events:
            results = self.send_event(event)
            all_results.extend(results)
        
        return all_results
    
    def _evaluate_rule(self, rule: EventRule, latest_event: Event) -> Optional[TriggerResult]:
        """
        규칙 평가
        
        1. 현재 이벤트가 조건을 충족하는지 확인
        2. 조건 충족 시간이 지속 시간을 넘었는지 확인
        3. 트리거 조건 충족 시 결과 반환
        """
        # 필드 값 추출
        field_value = latest_event.data.get(rule.field_name)
        if field_value is None:
            return None
        
        try:
            field_value = float(field_value)
        except (ValueError, TypeError):
            return None
        
        # 조건 평가
        condition_met = self._check_condition(field_value, rule.operator, rule.threshold)
        source_id = latest_event.source_id
        
        if condition_met:
            # 조건 충족 시작 시간 기록
            if source_id not in self.condition_state[rule.id]:
                self.condition_state[rule.id][source_id] = latest_event.timestamp
                SmartLogger.log(
                    "DEBUG", 
                    f"Condition started: {rule.name} for {source_id} at {latest_event.timestamp}",
                    category="cep.condition.start"
                )
            
            # 지속 시간 확인
            first_met_time = self.condition_state[rule.id][source_id]
            duration = latest_event.timestamp - first_met_time
            required_duration = timedelta(minutes=rule.duration_minutes)
            
            if duration >= required_duration:
                # 트리거!
                matching_events = [
                    e for e in self.event_buffer[rule.id]
                    if e.source_id == source_id and e.timestamp >= first_met_time
                ]
                
                # 상태 초기화 (다시 트리거되려면 조건이 리셋되어야 함)
                del self.condition_state[rule.id][source_id]
                
                # 규칙 상태 업데이트
                rule.last_triggered_at = latest_event.timestamp
                rule.trigger_count += 1
                
                SmartLogger.log(
                    "INFO",
                    f"Rule triggered: {rule.name} - Duration: {duration}, Events: {len(matching_events)}",
                    category="cep.trigger"
                )
                
                return TriggerResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    triggered_at=latest_event.timestamp,
                    condition_met_duration=duration,
                    matching_events=matching_events,
                    action_type=rule.action_type
                )
        else:
            # 조건 미충족 - 상태 리셋
            if source_id in self.condition_state[rule.id]:
                del self.condition_state[rule.id][source_id]
                SmartLogger.log(
                    "DEBUG",
                    f"Condition reset: {rule.name} for {source_id}",
                    category="cep.condition.reset"
                )
        
        return None
    
    def _check_condition(self, value: float, operator: ConditionOperator, threshold: float) -> bool:
        """조건 연산자 평가"""
        if operator == ConditionOperator.GT:
            return value > threshold
        elif operator == ConditionOperator.GTE:
            return value >= threshold
        elif operator == ConditionOperator.LT:
            return value < threshold
        elif operator == ConditionOperator.LTE:
            return value <= threshold
        elif operator == ConditionOperator.EQ:
            return value == threshold
        elif operator == ConditionOperator.NE:
            return value != threshold
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """엔진 상태 조회"""
        return {
            "status": "running" if self.is_running else "stopped",
            "active_rules": len([r for r in self.rules.values() if r.is_active]),
            "total_rules": len(self.rules),
            "buffered_events": sum(len(buf) for buf in self.event_buffer.values()),
            "engine": "SimpleCEP (Python)"
        }
    
    def clear(self) -> None:
        """모든 상태 초기화"""
        self.rules.clear()
        self.event_buffer.clear()
        self.condition_state.clear()


# 싱글톤 인스턴스
_cep_engine: Optional[SimpleCEPEngine] = None


def get_simple_cep_engine() -> SimpleCEPEngine:
    """SimpleCEP 엔진 인스턴스 반환"""
    global _cep_engine
    if _cep_engine is None:
        _cep_engine = SimpleCEPEngine()
    return _cep_engine


def create_rule_from_natural_language(
    rule_id: str,
    name: str,
    description: str,
    natural_language: str,
    action_type: str = "alert",
    action_config: Optional[Dict[str, Any]] = None
) -> EventRule:
    """
    자연어에서 규칙 생성
    
    간단한 패턴 매칭으로 규칙 파라미터 추출
    """
    import re
    
    text = natural_language.lower()
    
    # 필드 추출
    field_name = "value"
    if "수위" in text:
        field_name = "water_level"
    elif "유량" in text:
        field_name = "flow_rate"
    elif "탁도" in text:
        field_name = "turbidity"
    
    # 임계값 추출
    threshold = 0.0
    threshold_match = re.search(r'(\d+(?:\.\d+)?)\s*(m|미터|%|도)?', text)
    if threshold_match:
        threshold = float(threshold_match.group(1))
    
    # 연산자 추출
    operator = ConditionOperator.GTE
    if "초과" in text:
        operator = ConditionOperator.GT
    elif "미만" in text:
        operator = ConditionOperator.LT
    elif "이하" in text:
        operator = ConditionOperator.LTE
    
    # 지속 시간 추출
    duration_minutes = 0
    duration_match = re.search(r'(\d+)\s*(분|시간).{0,5}(지속|이상)', text)
    if duration_match:
        duration_minutes = int(duration_match.group(1))
        if duration_match.group(2) == "시간":
            duration_minutes *= 60
    
    # 윈도우 크기 (지속 시간의 2배 또는 최소 30분)
    window_minutes = max(30, duration_minutes * 2)
    
    return EventRule(
        id=rule_id,
        name=name,
        description=description,
        field_name=field_name,
        operator=operator,
        threshold=threshold,
        window_minutes=window_minutes,
        duration_minutes=duration_minutes,
        action_type=action_type,
        action_config=action_config or {}
    )
