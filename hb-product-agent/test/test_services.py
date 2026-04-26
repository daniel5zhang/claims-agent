"""
服务层单元测试
覆盖: AgentService、ManualGenerator、BaiyanClient
"""
import os
import pytest
import json
from unittest.mock import MagicMock, patch


class TestAgentService:
    """TC-SVC-AGENT: Agent 服务层"""

    @pytest.fixture
    def mock_baiyan(self):
        with patch("services.agent_service.get_baiyan_client") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def agent_service(self, mock_baiyan):
        from services.agent_service import AgentService
        return AgentService()

    def test_get_or_create_conversation_new(self, agent_service, db_session):
        """TC-SVC-001: 新建会话"""
        conv = agent_service._get_or_create_conversation(db_session, None)
        assert conv.session_id is not None
        assert len(conv.session_id) == 32

    def test_get_or_create_conversation_existing(self, agent_service, sample_conversation, db_session):
        """TC-SVC-002: 获取已有会话"""
        conv = agent_service._get_or_create_conversation(db_session, sample_conversation.session_id)
        assert conv.id == sample_conversation.id

    def test_load_messages_empty(self, agent_service):
        """TC-SVC-003: 空消息加载"""
        from database import Conversation
        conv = Conversation(messages_json="")
        msgs = agent_service._load_messages(conv)
        assert msgs == []

    def test_load_messages_invalid_json(self, agent_service):
        """TC-SVC-004: 无效 JSON 返回空列表"""
        from database import Conversation
        conv = Conversation(messages_json="not json")
        msgs = agent_service._load_messages(conv)
        assert msgs == []

    def test_parse_scheme_from_response_with_json_block(self, agent_service):
        """TC-SVC-005: 从 ```json 代码块解析方案"""
        text = '```json\n{"type":"scheme","scheme_name":"测试","services":[]}\n```'
        result = agent_service._parse_scheme_from_response(text)
        assert result is not None
        assert result["scheme_name"] == "测试"

    def test_parse_scheme_from_response_with_plain_block(self, agent_service):
        """TC-SVC-006: 从 ``` 代码块解析"""
        text = '```\n{"services":[{"name":"图文问诊"}]}\n```'
        result = agent_service._parse_scheme_from_response(text)
        assert result is not None

    def test_parse_scheme_from_response_no_block(self, agent_service):
        """TC-SVC-007: 无代码块返回 None"""
        result = agent_service._parse_scheme_from_response("纯文本无 JSON")
        assert result is None

    def test_parse_scheme_from_response_invalid_json(self, agent_service):
        """TC-SVC-008: 无效 JSON 返回 None"""
        text = '```json\n{invalid}\n```'
        result = agent_service._parse_scheme_from_response(text)
        assert result is None

    def test_validate_scheme_empty(self, agent_service, db_session):
        """TC-SVC-009: 空服务列表直接通过"""
        scheme = {"services": []}
        result, out = agent_service._validate_scheme(db_session, scheme)
        assert result["services"] == []
        assert out == []

    def test_validate_scheme_in_scope(self, agent_service, db_session):
        """TC-SVC-010: 素材库范围内的服务通过"""
        from database import Service
        db_session.add(Service(name="图文问诊"))
        db_session.commit()
        scheme = {"services": [{"name": "图文问诊"}]}
        result, out = agent_service._validate_scheme(db_session, scheme)
        assert len(result["services"]) == 1
        assert out == []

    def test_validate_scheme_out_of_scope(self, agent_service, db_session):
        """TC-SVC-011: 超范围服务被过滤"""
        from database import Service
        db_session.add(Service(name="图文问诊"))
        db_session.commit()
        scheme = {"services": [{"name": "图文问诊"}, {"name": "不存在的服务"}]}
        result, out = agent_service._validate_scheme(db_session, scheme)
        assert len(result["services"]) == 1
        assert "不存在的服务" in out

    def test_save_generated_scheme_new(self, agent_service, db_session):
        """TC-SVC-012: 保存新方案"""
        from database import GeneratedScheme
        scheme_data = {"scheme_name": "新方案", "services": [{"cost": 10, "price": 15}]}
        result = agent_service._save_generated_scheme(db_session, 1, scheme_data)
        assert result.scheme_name == "新方案"
        assert result.status == "draft"

    def test_save_generated_scheme_update_existing(self, agent_service, db_session):
        """TC-SVC-013: 更新已有草稿方案"""
        from database import GeneratedScheme
        existing = GeneratedScheme(conversation_id=1, scheme_name="旧名称", service_list_json="[]", status="draft")
        db_session.add(existing)
        db_session.commit()

        scheme_data = {"scheme_name": "新名称", "services": []}
        result = agent_service._save_generated_scheme(db_session, 1, scheme_data)
        assert result.id == existing.id
        assert result.scheme_name == "新名称"

    def test_get_conversation_history_exists(self, agent_service, sample_conversation, db_session):
        """TC-SVC-014: 获取存在的历史"""
        history = agent_service.get_conversation_history(db_session, sample_conversation.session_id)
        assert history is not None
        assert history["session_id"] == sample_conversation.session_id
        assert len(history["messages"]) == 2

    def test_get_conversation_history_not_found(self, agent_service, db_session):
        """TC-SVC-015: 获取不存在的历史"""
        history = agent_service.get_conversation_history(db_session, "notexist")
        assert history is None


class TestManualGenerator:
    """TC-SVC-MANUAL: 手册生成器"""

    @pytest.fixture
    def generator(self):
        from services.manual_generator import ManualGenerator
        return ManualGenerator()

    def test_replace_placeholders(self, generator):
        """TC-SVC-016: 占位符替换"""
        content = "{{service_name}} - {{times}} - {{price}}"
        result = generator._replace_placeholders(content, {"name": "图文问诊", "times": "不限次", "price": "10"})
        assert result == "图文问诊 - 不限次 - 10"

    def test_find_template_exact_match(self, generator, db_session, sample_manual_template):
        """TC-SVC-017: 精确匹配模板"""
        tmpl = generator._find_template(db_session, "图文问诊")
        assert tmpl is not None
        assert tmpl.service_name == "图文问诊"

    def test_find_template_fuzzy_match(self, generator, db_session, sample_manual_template):
        """TC-SVC-018: 模糊匹配模板"""
        tmpl = generator._find_template(db_session, "图文")
        assert tmpl is not None

    def test_find_template_no_match(self, generator, db_session):
        """TC-SVC-019: 无匹配模板返回 None"""
        tmpl = generator._find_template(db_session, "不存在的服务")
        assert tmpl is None

    def test_generate_manual_not_confirmed(self, generator, sample_scheme, db_session):
        """TC-SVC-020: 未确认方案生成手册抛异常"""
        with pytest.raises(ValueError, match="未确认"):
            generator.generate_manual(db_session, sample_scheme.id)

    def test_generate_manual_no_services(self, generator, db_session):
        """TC-SVC-021: 空服务列表抛异常"""
        from database import GeneratedScheme
        scheme = GeneratedScheme(conversation_id=1, service_list_json="[]", status="confirmed")
        db_session.add(scheme)
        db_session.commit()
        db_session.refresh(scheme)
        with pytest.raises(ValueError, match="无服务项"):
            generator.generate_manual(db_session, scheme.id)

    def test_generate_manual_creates_file(self, generator, confirmed_scheme, db_session, sample_manual_template):
        """TC-SVC-022: 生成手册创建物理文件"""
        result = generator.generate_manual(db_session, confirmed_scheme.id)
        manual, missing = result
        assert manual.docx_path is not None
        assert os.path.exists(manual.docx_path)

    def test_parse_manual_template(self):
        """TC-SVC-023: 解析 docx 模板"""
        # 这里需要实际 docx 文件，跳过或创建临时文件测试
        pass


class TestBaiyanClient:
    """TC-SVC-BAIYAN: 百炼客户端"""

    def test_client_singleton(self):
        """TC-SVC-024: 单例模式"""
        from services.baiyan_client import get_baiyan_client
        c1 = get_baiyan_client()
        c2 = get_baiyan_client()
        assert c1 is c2

    def test_env_loaded(self):
        """TC-SVC-025: 环境变量加载"""
        import os
        assert os.getenv("BAILIAN_API_KEY") is not None
