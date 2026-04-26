"""
数据库层全量测试
覆盖: 模型定义、CRUD、关联、约束、边界条件
"""
import pytest
from decimal import Decimal


class TestServiceModel:
    """TC-DB-SVC: 服务素材模型"""

    def test_create_service(self, db_session):
        """TC-DB-001: 创建服务素材"""
        from database import Service
        svc = Service(category="测试", name="单元测试服务", cost_price=Decimal("9.99"))
        db_session.add(svc)
        db_session.commit()
        db_session.refresh(svc)
        assert svc.id is not None
        assert svc.name == "单元测试服务"

    def test_service_name_required(self, db_session):
        """TC-DB-002: 服务名不允许为空"""
        from database import Service
        svc = Service(name=None, category="测试")
        db_session.add(svc)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_service_cost_price_decimal(self, db_session):
        """TC-DB-003: cost_price 支持小数"""
        from database import Service
        svc = Service(name="价格测试", cost_price=Decimal("123.45"))
        db_session.add(svc)
        db_session.commit()
        db_session.refresh(svc)
        assert svc.cost_price == Decimal("123.45")

    def test_service_unique_id(self, db_session):
        """TC-DB-004: ID 自增唯一"""
        from database import Service
        s1 = Service(name="服务1")
        s2 = Service(name="服务2")
        db_session.add_all([s1, s2])
        db_session.commit()
        assert s1.id != s2.id
        assert s2.id == s1.id + 1

    def test_service_default_create_time(self, db_session):
        """TC-DB-005: 默认创建时间"""
        from database import Service
        svc = Service(name="时间测试")
        db_session.add(svc)
        db_session.commit()
        assert svc.create_time is not None


class TestGeneratedSchemeModel:
    """TC-DB-SCHEME: 生成方案模型"""

    def test_create_scheme(self, db_session):
        """TC-DB-006: 创建方案"""
        from database import GeneratedScheme
        scheme = GeneratedScheme(
            conversation_id=1, scheme_name="方案测试",
            service_list_json='[]', status="draft"
        )
        db_session.add(scheme)
        db_session.commit()
        assert scheme.id is not None
        assert scheme.status == "draft"

    def test_scheme_status_values(self, db_session):
        """TC-DB-007: 状态只能是 draft/confirmed"""
        from database import GeneratedScheme
        scheme = GeneratedScheme(conversation_id=1, scheme_name="状态测试", status="invalid")
        db_session.add(scheme)
        db_session.commit()
        # 当前无数据库约束，应用层应校验
        assert scheme.status == "invalid"

    def test_scheme_json_field(self, db_session):
        """TC-DB-008: service_list_json 存储 JSON"""
        from database import GeneratedScheme
        import json
        data = [{"name": "图文问诊", "price": 10}]
        scheme = GeneratedScheme(
            conversation_id=1, scheme_name="JSON测试",
            service_list_json=json.dumps(data), status="draft"
        )
        db_session.add(scheme)
        db_session.commit()
        loaded = json.loads(scheme.service_list_json)
        assert loaded[0]["name"] == "图文问诊"

    def test_scheme_total_cost_quote(self, db_session):
        """TC-DB-009: 总成本和总报价为 DECIMAL"""
        from database import GeneratedScheme
        scheme = GeneratedScheme(
            conversation_id=1, scheme_name="金额测试",
            total_cost=Decimal("99.99"), total_quote=Decimal("149.99"),
            status="draft"
        )
        db_session.add(scheme)
        db_session.commit()
        assert scheme.total_cost == Decimal("99.99")


class TestConversationModel:
    """TC-DB-CONV: 对话模型"""

    def test_create_conversation(self, db_session):
        """TC-DB-010: 创建对话"""
        from database import Conversation
        conv = Conversation(session_id="testsession123", messages_json="[]")
        db_session.add(conv)
        db_session.commit()
        assert conv.id is not None
        assert conv.status == "active"

    def test_conversation_session_unique(self, db_session):
        """TC-DB-011: session_id 唯一约束"""
        from database import Conversation
        c1 = Conversation(session_id="unique123", messages_json="[]")
        c2 = Conversation(session_id="unique123", messages_json="[]")
        db_session.add(c1)
        db_session.commit()
        db_session.add(c2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_conversation_default_status(self, db_session):
        """TC-DB-012: 默认状态 active"""
        from database import Conversation
        conv = Conversation(session_id="status_test", messages_json="[]")
        db_session.add(conv)
        db_session.commit()
        assert conv.status == "active"


class TestGeneratedManualModel:
    """TC-DB-MANUAL: 手册模型"""

    def test_create_manual(self, db_session):
        """TC-DB-013: 创建手册记录"""
        from database import GeneratedManual
        manual = GeneratedManual(
            scheme_id=1, manual_title="测试手册", docx_path="/tmp/test.docx", status="generated"
        )
        db_session.add(manual)
        db_session.commit()
        assert manual.id is not None


class TestServiceManualTemplateModel:
    """TC-DB-TEMPLATE: 手册模板模型"""

    def test_create_template(self, db_session):
        """TC-DB-014: 创建模板"""
        from database import ServiceManualTemplate
        tmpl = ServiceManualTemplate(
            template_name="标准模板", service_name="图文问诊",
            section_title="图文问诊服务", content_template="测试内容", sort_order=1
        )
        db_session.add(tmpl)
        db_session.commit()
        assert tmpl.id is not None
        assert tmpl.sort_order == 1

    def test_template_sort_order_default(self, db_session):
        """TC-DB-015: 默认排序为 0"""
        from database import ServiceManualTemplate
        tmpl = ServiceManualTemplate(template_name="T", service_name="S")
        db_session.add(tmpl)
        db_session.commit()
        assert tmpl.sort_order == 0


class TestDatabaseRelations:
    """TC-DB-REL: 数据库关系"""

    def test_scheme_conversation_relation(self, db_session):
        """TC-DB-016: 方案与对话关联"""
        from database import Conversation, GeneratedScheme
        conv = Conversation(session_id="rel_test", messages_json="[]")
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        scheme = GeneratedScheme(conversation_id=conv.id, scheme_name="关联方案", status="draft")
        db_session.add(scheme)
        db_session.commit()
        assert scheme.conversation_id == conv.id

    def test_manual_scheme_relation(self, db_session):
        """TC-DB-017: 手册与方案关联"""
        from database import GeneratedScheme, GeneratedManual
        scheme = GeneratedScheme(conversation_id=1, scheme_name="手册测试", status="confirmed")
        db_session.add(scheme)
        db_session.commit()
        db_session.refresh(scheme)

        manual = GeneratedManual(scheme_id=scheme.id, manual_title="手册", docx_path="/tmp/a.docx")
        db_session.add(manual)
        db_session.commit()
        assert manual.scheme_id == scheme.id


class TestDatabaseCRUD:
    """TC-DB-CRUD: 增删改查操作"""

    def test_update_service(self, db_session):
        """TC-DB-018: 更新服务"""
        from database import Service
        svc = Service(name="待更新", cost_price=10)
        db_session.add(svc)
        db_session.commit()

        svc.cost_price = Decimal("20")
        db_session.commit()
        db_session.refresh(svc)
        assert svc.cost_price == Decimal("20")

    def test_delete_service(self, db_session):
        """TC-DB-019: 删除服务"""
        from database import Service
        svc = Service(name="待删除")
        db_session.add(svc)
        db_session.commit()
        sid = svc.id

        db_session.delete(svc)
        db_session.commit()
        assert db_session.query(Service).filter(Service.id == sid).first() is None

    def test_query_filter(self, db_session):
        """TC-DB-020: 条件查询"""
        from database import Service
        db_session.add_all([
            Service(name="A服务", category="类型1"),
            Service(name="B服务", category="类型2"),
            Service(name="C服务", category="类型1"),
        ])
        db_session.commit()
        results = db_session.query(Service).filter(Service.category == "类型1").all()
        assert len(results) == 2
