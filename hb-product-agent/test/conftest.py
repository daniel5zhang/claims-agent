"""
Pytest 全局配置和共享 Fixture
统一使用 seekdb 嵌入式模式，测试和生产环境一致
"""
import os
import sys
import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# 测试使用独立的 seekdb 数据库（隔离）
os.environ["SEEKDB_DB"] = "test"
# 注意：测试使用真实百炼 API（从 ../backend/.env 加载）
# 如需强制 mock，请取消下行注释
# os.environ["BAILIAN_API_KEY"] = ""

# 将 backend 加入路径
backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, backend_dir)

# mock dingtalk_stream（测试环境可能未安装该包）
if "dingtalk_stream" not in sys.modules:
    _dsm = type(sys)("dingtalk_stream")
    _dsm.ChatbotHandler = object
    _dsm.ChatbotMessage = type("ChatbotMessage", (), {"TOPIC": "chatbot", "from_dict": lambda cls, d: type("Msg", (), d)()})()
    _dsm.CallbackMessage = type("CallbackMessage", (), {})()
    _dsm.AckMessage = type("AckMessage", (), {"STATUS_OK": "OK"})()
    sys.modules["dingtalk_stream"] = _dsm

from database import Base, get_db, engine
from main import app

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def cleanup_db():
    """每个测试函数前清空数据库表数据，保证测试隔离"""
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.commit()
    yield


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """测试会话开始前创建表，结束后删除"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """每个测试函数独立的 db session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def client():
    """FastAPI TestClient"""
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def sample_services(db_session):
    """预置服务素材数据"""
    from database import Service
    services = [
        Service(category="基础服务", name="图文问诊", description="7x24小时在线图文咨询", cost_price=5.0, times="不限次"),
        Service(category="基础服务", name="视频问诊", description="三甲医院专家视频问诊", cost_price=15.0, times="2次/年"),
        Service(category="基础服务", name="电话心理咨询", description="专业心理咨询师电话服务", cost_price=8.0, times="1次/年"),
        Service(category="增值服务", name="癌症早筛", description="高发癌症风险评估", cost_price=12.0, times="1次/年"),
        Service(category="增值服务", name="重疾门诊绿通", description="协助预约专家门诊", cost_price=20.0, times="1次/年", condition="确诊重疾"),
        Service(category="增值服务", name="就医陪诊", description="全程就医陪同服务", cost_price=18.0, times="1次/年"),
        Service(category="增值服务", name="住院护工", description="专业院内护工服务", cost_price=25.0, times="8天7晚"),
        Service(category="增值服务", name="购药金", description="药品费用抵扣金", cost_price=10.0, times="按面值"),
    ]
    for s in services:
        db_session.add(s)
    db_session.commit()
    return services


@pytest.fixture(scope="function")
def sample_scheme(db_session):
    """预置草稿方案"""
    from database import GeneratedScheme
    scheme = GeneratedScheme(
        conversation_id=1,
        scheme_name="测试方案A",
        service_list_json='[{"name":"图文问诊","times":"不限次","price":10},{"name":"视频问诊","times":"2次","price":30}]',
        total_cost=40,
        total_quote=55,
        status="draft",
    )
    db_session.add(scheme)
    db_session.commit()
    db_session.refresh(scheme)
    return scheme


@pytest.fixture(scope="function")
def confirmed_scheme(db_session):
    """预置已确认方案"""
    from database import GeneratedScheme
    scheme = GeneratedScheme(
        conversation_id=2,
        scheme_name="测试确认方案B",
        service_list_json='[{"name":"图文问诊","times":"不限次","price":10},{"name":"重疾门诊绿通","times":"1次","price":50}]',
        total_cost=60,
        total_quote=80,
        status="confirmed",
    )
    db_session.add(scheme)
    db_session.commit()
    db_session.refresh(scheme)
    return scheme


@pytest.fixture(scope="function")
def sample_conversation(db_session):
    """预置对话记录"""
    from database import Conversation
    import uuid
    conv = Conversation(
        session_id=str(uuid.uuid4()).replace("-", ""),
        messages_json='[{"role":"user","content":"你好"},{"role":"assistant","content":"您好，有什么可以帮您？"}]',
        extracted_needs_json='{"scene":"测试","budget_range":"50-100元"}',
        status="active",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)
    return conv


@pytest.fixture(scope="function")
def sample_manual_template(db_session):
    """预置手册模板"""
    from database import ServiceManualTemplate
    templates = [
        ServiceManualTemplate(template_name="标准模板", service_name="图文问诊", section_title="图文问诊服务", content_template="服务名称：{{service_name}}\n服务次数：{{times}}\n服务流程：\n（1）登录公众号\n（2）选择图文问诊\n（3）描述症状等待医生回复"),
        ServiceManualTemplate(template_name="标准模板", service_name="重疾门诊绿通", section_title="重疾门诊绿通服务", content_template="服务名称：{{service_name}}\n服务次数：{{times}}\n启动条件：{{condition}}\n服务流程：\n（1）提交病历资料\n（2）管家审核\n（3）预约专家门诊"),
    ]
    for t in templates:
        db_session.add(t)
    db_session.commit()
    return templates
