"""
이벤트 템플릿 API 테스트
"""
import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.main import app
from app.routers.events import _event_rules
from app.routers.event_templates import EVENT_TEMPLATES


# 테스트 전 초기화
@pytest.fixture(autouse=True)
def clear_state():
    """각 테스트 전 상태 초기화"""
    _event_rules.clear()
    yield
    _event_rules.clear()


@pytest.fixture
def client():
    """동기 테스트 클라이언트"""
    return TestClient(app)


class TestEventTemplates:
    """이벤트 템플릿 API 테스트"""
    
    def test_list_templates(self, client):
        """템플릿 목록 조회"""
        response = client.get("/text2sql/events/templates")
        assert response.status_code == 200
        
        templates = response.json()
        assert len(templates) == len(EVENT_TEMPLATES)
        assert all("id" in t and "name" in t for t in templates)
    
    def test_list_templates_by_category(self, client):
        """카테고리별 템플릿 조회"""
        response = client.get("/text2sql/events/templates?category=여과(GAC)")
        assert response.status_code == 200
        
        templates = response.json()
        assert len(templates) >= 1
        assert all(t["category"] == "여과(GAC)" for t in templates)
    
    def test_list_categories(self, client):
        """카테고리 목록 조회"""
        response = client.get("/text2sql/events/templates/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) >= 5  # 최소 5개 카테고리
        assert "여과(GAC)" in data["categories"]
        assert "착수" in data["categories"]
    
    def test_get_templates_grouped(self, client):
        """카테고리별 그룹화된 템플릿 조회"""
        response = client.get("/text2sql/events/templates/by-category")
        assert response.status_code == 200
        
        grouped = response.json()
        assert isinstance(grouped, dict)
        assert "여과(GAC)" in grouped
        assert len(grouped["여과(GAC)"]) >= 1
    
    def test_get_template_detail(self, client):
        """템플릿 상세 조회"""
        template_id = "gac-turbidity-rise"
        response = client.get(f"/text2sql/events/templates/{template_id}")
        assert response.status_code == 200
        
        template = response.json()
        assert template["id"] == template_id
        assert template["name"] == "여과지 탁도 상승"
        assert "sample_sql" in template
        assert "diagnostic_questions" in template
    
    def test_get_template_not_found(self, client):
        """존재하지 않는 템플릿 조회"""
        response = client.get("/text2sql/events/templates/nonexistent-id")
        assert response.status_code == 404
    
    def test_create_rule_from_template(self, client):
        """템플릿에서 규칙 생성"""
        template_id = "gac-turbidity-rise"
        response = client.post(f"/text2sql/events/templates/{template_id}/create-rule")
        assert response.status_code == 200
        
        rule = response.json()
        assert rule["name"] == "여과지 탁도 상승"
        assert rule["is_active"] == True
        assert "id" in rule
        
        # 생성된 규칙이 실제로 저장되었는지 확인
        list_response = client.get("/text2sql/events/rules")
        assert list_response.status_code == 200
        rules = list_response.json()
        assert len(rules) == 1
        assert rules[0]["id"] == rule["id"]
    
    def test_create_rule_from_template_with_override(self, client):
        """템플릿에서 규칙 생성 (커스터마이즈)"""
        template_id = "intake-water-level-risk"
        custom_name = "커스텀 수위 감지"
        custom_interval = 3
        
        response = client.post(
            f"/text2sql/events/templates/{template_id}/create-rule",
            params={
                "name": custom_name,
                "check_interval_minutes": custom_interval
            }
        )
        assert response.status_code == 200
        
        rule = response.json()
        assert rule["name"] == custom_name
        assert rule["check_interval_minutes"] == custom_interval
    
    def test_create_rule_from_nonexistent_template(self, client):
        """존재하지 않는 템플릿에서 규칙 생성 시도"""
        response = client.post("/text2sql/events/templates/nonexistent-id/create-rule")
        assert response.status_code == 404


class TestTemplateContent:
    """템플릿 내용 검증 테스트"""
    
    def test_all_templates_have_required_fields(self):
        """모든 템플릿에 필수 필드가 있는지 확인"""
        required_fields = [
            "id", "category", "name", "description", "rule_description",
            "sample_sql", "default_interval_minutes", "default_threshold",
            "recommended_action", "diagnostic_questions", "simple_questions",
            "action_questions"
        ]
        
        for template in EVENT_TEMPLATES:
            for field in required_fields:
                assert hasattr(template, field), f"Template {template.id} missing {field}"
    
    def test_all_templates_have_valid_sql(self):
        """모든 템플릿의 SQL이 유효한지 확인"""
        for template in EVENT_TEMPLATES:
            sql = template.sample_sql.strip()
            assert len(sql) > 0, f"Template {template.id} has empty SQL"
            assert sql.upper().startswith("SELECT"), f"Template {template.id} SQL must start with SELECT"
    
    def test_all_templates_have_valid_action_type(self):
        """모든 템플릿의 action_type이 유효한지 확인"""
        for template in EVENT_TEMPLATES:
            assert template.recommended_action in ["alert", "process"], \
                f"Template {template.id} has invalid action type"
    
    def test_process_templates_have_suggested_process(self):
        """프로세스 타입 템플릿은 suggested_process가 있어야 함"""
        for template in EVENT_TEMPLATES:
            if template.recommended_action == "process":
                assert template.suggested_process, \
                    f"Process template {template.id} should have suggested_process"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
