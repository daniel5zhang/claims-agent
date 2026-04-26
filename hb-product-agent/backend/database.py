"""
数据库连接层
统一使用 seekdb 嵌入式模式（OceanBase），测试和生产环境保持一致。

注意：以下 monkey-patch 是为了修复 seekdb 驱动与 SQLAlchemy 之间的兼容性问题：
  - _SeekdbCursor 缺少 lastrowid 属性（auto_increment 依赖）
  - rowcount 未正确返回（UPDATE/DELETE 校验依赖）
  - 空结果集缺少 description 列元数据（ORM 加载依赖）
这些 patch 依赖于 seekdb 驱动的内部实现，升级 seekdb/pyobvector 时需验证兼容性。
长期方案：推动 seekdb 团队在驱动层面修复这些问题，届时移除此 patch。
"""
import os
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, Text, DateTime, DECIMAL, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from config import SEEKDB_PATH, SEEKDB_DB

# seekdb 嵌入式模式：通过 pyobvector 自动启动本地 seekdb
from pyobvector import ObVecClient
from pyobvector.client.seekdb_engine import _SeekdbCursor, _execute_via_pyseekdb

# 修复: _SeekdbCursor 缺少 lastrowid 属性（SQLAlchemy autoincrement 依赖）
_orig_execute = _SeekdbCursor.execute

import re


def _extract_table_name(sql):
    """从 SELECT/INSERT/UPDATE/DELETE 语句中提取表名"""
    patterns = [
        r'FROM\s+`?(\w+)`?',
        r'INTO\s+`?(\w+)`?',
        r'UPDATE\s+`?(\w+)`?',
    ]
    for pattern in patterns:
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _patched_execute(self, operation, parameters=None):
    _orig_execute(self, operation, parameters)
    op = operation.strip().upper()
    is_insert = op.startswith("INSERT") or "INSERT" in op
    is_update = op.startswith("UPDATE") or "UPDATE" in op
    is_delete = op.startswith("DELETE") or "DELETE" in op
    is_select = op.startswith("SELECT") or "SELECT" in op
    
    # 修复空结果集的 description（seekdb 驱动返回空列表时不提供列元数据，
    # SQLAlchemy 的 ORM 加载依赖 description 构建结果处理器）
    if is_select and self._description is None:
        table = _extract_table_name(operation)
        if table:
            try:
                desc_result = _execute_via_pyseekdb(self._client, f"SHOW COLUMNS FROM {table}", ())
                if desc_result:
                    def make_desc(name):
                        return (name, None, None, None, None, None, None)
                    first = desc_result[0]
                    if isinstance(first, dict):
                        self._description = [make_desc(row.get('Field', list(row.values())[0])) for row in desc_result]
                    else:
                        self._description = [make_desc(row[0]) for row in desc_result]
            except Exception:
                pass
    
    # 修复 rowcount（seekdb 驱动未正确返回，SQLAlchemy 依赖此属性校验 UPDATE/DELETE）
    self.rowcount = -1
    if is_update or is_delete:
        try:
            result = _execute_via_pyseekdb(self._client, "SELECT ROW_COUNT()", ())
            if result:
                row = result[0]
                if isinstance(row, dict):
                    val = list(row.values())[0]
                elif isinstance(row, (list, tuple)):
                    val = row[0]
                else:
                    val = row
                self.rowcount = int(val) if val is not None else -1
        except Exception:
            pass
    
    self.lastrowid = 0
    if is_insert:
        try:
            result = _execute_via_pyseekdb(self._client, "SELECT LAST_INSERT_ID()", ())
            if result:
                row = result[0]
                if isinstance(row, dict):
                    val = list(row.values())[0]
                elif isinstance(row, (list, tuple)):
                    val = row[0]
                else:
                    val = row
                self.lastrowid = int(val) if val else 0
        except Exception:
            pass

_SeekdbCursor.execute = _patched_execute

# 修复: _SeekdbCursor 缺少 executemany（SQLAlchemy 批量 UPDATE/DELETE 依赖）
if not hasattr(_SeekdbCursor, "executemany"):
    def _patched_executemany(self, statement, parameters):
        """回退为逐条执行"""
        total = 0
        for params in parameters:
            self.execute(statement, params)
            total += max(self.rowcount, 0) if hasattr(self, "rowcount") else 0
        self.rowcount = total
        return total
    _SeekdbCursor.executemany = _patched_executemany

# 使用集中配置模块中的路径和数据库名
_client = ObVecClient(path=SEEKDB_PATH, db_name="test")
engine = _client.engine
PK_TYPE = BigInteger  # MySQL 支持 BigInteger + autoincrement
# 创建目标数据库（如果不存在）
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {SEEKDB_DB}"))
    conn.commit()
# 重新连接到目标数据库
_client = ObVecClient(path=SEEKDB_PATH, db_name=SEEKDB_DB)
engine = _client.engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 服务素材表
class Service(Base):
    __tablename__ = "services"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=True, comment="服务类别")
    name = Column(String(100), nullable=False, comment="服务项目名称")
    description = Column(Text, nullable=True, comment="服务说明/服务内容")
    process = Column(Text, nullable=True, comment="服务流程")
    condition = Column(String(500), nullable=True, comment="启动条件")
    times = Column(String(100), nullable=True, comment="服务次数")
    service_time = Column(String(200), nullable=True, comment="服务时间")
    service_response_time = Column(String(200), nullable=True, comment="服务时效")
    service_standard = Column(Text, nullable=True, comment="服务标准")
    service_network = Column(Text, nullable=True, comment="服务网络")
    special_notes = Column(Text, nullable=True, comment="特别说明")
    cost_price = Column(DECIMAL(10, 2), nullable=True, comment="成本价")
    usage_rate_small = Column(DECIMAL(10, 4), nullable=True, comment="5万单以下使用率")
    usage_rate_large = Column(DECIMAL(10, 4), nullable=True, comment="5-10万单使用率")
    source_file = Column(String(200), nullable=True, comment="来源文件")
    sheet_source = Column(String(50), nullable=True, comment="来源Sheet: 产品部/交付部/其他")
    is_priced = Column(Integer, default=0, comment="是否有成本价 0/1")
    aliases = Column(String(500), nullable=True, comment="服务别名（逗号分隔）")
    pricing_category = Column(String(50), nullable=True, comment="定价类别: per_use/per_year/per_event/discount")
    embedding = Column(Text, nullable=True, comment="向量嵌入(JSON)")
    create_time = Column(DateTime, default=datetime.now)


# 历史方案表
class Scheme(Base):
    __tablename__ = "schemes"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    scheme_name = Column(String(200), nullable=False, comment="方案名称")
    customer_name = Column(String(100), nullable=True, comment="客户名称")
    version = Column(String(20), nullable=True, comment="版本")
    total_price = Column(DECIMAL(10, 2), nullable=True, comment="总价")
    service_list_json = Column(Text, nullable=True, comment="服务清单JSON")
    source_file = Column(String(200), nullable=True, comment="来源文件")
    create_time = Column(DateTime, default=datetime.now)


# 方案明细表
class SchemeItem(Base):
    __tablename__ = "scheme_items"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    scheme_id = Column(PK_TYPE, nullable=False, comment="方案ID")
    service_name = Column(String(100), nullable=False, comment="服务名称")
    times = Column(String(100), nullable=True, comment="服务次数")
    condition = Column(String(500), nullable=True, comment="启动条件")
    price = Column(DECIMAL(10, 2), nullable=True, comment="报价")
    remark = Column(String(500), nullable=True, comment="备注")


# 用户表
class User(Base):
    __tablename__ = "users"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, unique=True, comment="用户唯一标识UUID")
    nickname = Column(String(100), nullable=True, comment="昵称")
    create_time = Column(DateTime, default=datetime.now)


# 对话记录表
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True, comment="用户ID")
    session_id = Column(String(64), nullable=False, unique=True, comment="会话ID")
    title = Column(String(200), nullable=True, comment="会话标题")
    messages_json = Column(Text(16777215), nullable=True, comment="消息历史JSON")
    extracted_needs_json = Column(Text(16777215), nullable=True, comment="提取的需求JSON")
    status = Column(String(20), default="active", comment="状态")
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# 生成的方案表
class GeneratedScheme(Base):
    __tablename__ = "generated_schemes"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    conversation_id = Column(PK_TYPE, nullable=False, comment="对话ID")
    scheme_name = Column(String(200), nullable=True, comment="方案名称")
    scene = Column(String(200), nullable=True, comment="适用场景")
    target_group = Column(String(200), nullable=True, comment="目标人群")
    service_list_json = Column(Text, nullable=True, comment="服务清单JSON")
    total_cost = Column(DECIMAL(10, 2), nullable=True, comment="总成本")
    total_quote = Column(DECIMAL(10, 2), nullable=True, comment="总报价")
    pricing_logic_id = Column(PK_TYPE, nullable=True, comment="关联定价逻辑ID")
    pricing_params_id = Column(PK_TYPE, nullable=True, comment="关联定价参数ID")
    engine_total_cost = Column(DECIMAL(12, 2), nullable=True, comment="规则引擎计算总成本")
    engine_total_quote = Column(DECIMAL(12, 2), nullable=True, comment="规则引擎计算总报价")
    llm_total_cost = Column(DECIMAL(12, 2), nullable=True, comment="LLM给出总成本")
    llm_total_quote = Column(DECIMAL(12, 2), nullable=True, comment="LLM给出总报价")
    final_total_cost = Column(DECIMAL(12, 2), nullable=True, comment="最终确认总成本")
    final_total_quote = Column(DECIMAL(12, 2), nullable=True, comment="最终确认总报价")
    pricing_method = Column(String(50), nullable=True, comment="定价方法: cost_plus/market_benchmark/hybrid/tiered")
    status = Column(String(20), default="draft", comment="状态 draft/confirmed")
    create_time = Column(DateTime, default=datetime.now)


# 服务手册模板表
class ServiceManualTemplate(Base):
    __tablename__ = "service_manual_templates"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    template_name = Column(String(100), nullable=False, comment="模板名称")
    service_name = Column(String(100), nullable=True, comment="对应服务名称")
    section_title = Column(String(100), nullable=True, comment="章节标题")
    content_template = Column(Text, nullable=True, comment="内容模板")
    sort_order = Column(Integer, default=0, comment="排序")


# 生成的服务手册表
class GeneratedManual(Base):
    __tablename__ = "generated_manuals"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    scheme_id = Column(PK_TYPE, nullable=False, comment="方案ID")
    version = Column(Integer, default=1, comment="该方案下第几次生成")
    manual_title = Column(String(200), nullable=True, comment="手册标题")
    docx_path = Column(String(500), nullable=True, comment="docx文件路径")
    status = Column(String(20), default="generated", comment="状态")
    create_time = Column(DateTime, default=datetime.now)


# 定价参数表（每个场景/方案的定价配置）
class PricingParams(Base):
    __tablename__ = "pricing_params"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="参数名称")
    scene = Column(String(100), nullable=True, comment="适用场景")
    volume_min = Column(Integer, nullable=True, comment="最小保单规模")
    volume_max = Column(Integer, nullable=True, comment="最大保单规模")
    channel = Column(String(100), nullable=True, comment="适用渠道")
    margin_rate = Column(DECIMAL(6, 4), nullable=True, comment="基础利润率 (e.g. 0.15 = 15%)")
    channel_coeff = Column(DECIMAL(6, 4), nullable=True, comment="渠道系数")
    package_discount = Column(DECIMAL(6, 4), nullable=True, comment="打包折扣")
    usage_rate_column = Column(String(50), nullable=True, comment="发生率列: small/large")
    rounding_rule = Column(String(50), nullable=True, comment="取整规则: round_to_yuan/round_to_half/ceil")
    source_type = Column(String(20), nullable=True, comment="来源: manual/extracted/inherited")
    source_scheme_id = Column(PK_TYPE, nullable=True, comment="来源方案ID")
    params_json = Column(Text, nullable=True, comment="扩展参数JSON")
    create_time = Column(DateTime, default=datetime.now)


# 定价逻辑表（文字描述 + 结构化规则）
class PricingLogic(Base):
    __tablename__ = "pricing_logics"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    scheme_id = Column(PK_TYPE, nullable=True, comment="关联方案ID")
    scheme_type = Column(String(20), nullable=True, comment="方案类型: historical/generated")
    pricing_method = Column(String(100), nullable=True, comment="定价方法: cost_plus/market_benchmark/hybrid/tiered")
    extracted_rules_json = Column(Text, nullable=True, comment="结构化定价规则JSON")
    logic_description = Column(Text, nullable=True, comment="定价逻辑完整描述(LLM生成)")
    diff_vs_engine = Column(Text, nullable=True, comment="与规则引擎基准的差异说明")
    diff_vs_previous = Column(Text, nullable=True, comment="与最近同类方案的定价差异说明")
    confidence_score = Column(DECIMAL(3, 2), nullable=True, comment="逻辑提取置信度 0-1")
    extracted_by = Column(String(50), nullable=True, comment="提取方式: llm/manual/hybrid")
    create_time = Column(DateTime, default=datetime.now)


# 定价规则表（细粒度、可组合）
class PricingRule(Base):
    __tablename__ = "pricing_rules"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    logic_id = Column(PK_TYPE, nullable=True, comment="关联定价逻辑ID")
    rule_category = Column(String(50), nullable=True, comment="规则类别: markup/tiering/rounding/selection/discount")
    rule_name = Column(String(200), nullable=True, comment="规则名称")
    rule_expression = Column(String(500), nullable=True, comment="规则表达式/描述")
    rule_params_json = Column(Text, nullable=True, comment="规则参数JSON")
    priority = Column(Integer, default=0, comment="优先级")
    is_active = Column(Integer, default=1, comment="是否启用")
    create_time = Column(DateTime, default=datetime.now)


# 生成的Excel报价单表
class GeneratedExcel(Base):
    __tablename__ = "generated_excels"
    id = Column(PK_TYPE, primary_key=True, autoincrement=True)
    scheme_id = Column(PK_TYPE, nullable=False, comment="方案ID")
    version = Column(Integer, default=1, comment="该方案下第几次生成")
    excel_title = Column(String(200), nullable=True, comment="报价单标题")
    excel_path = Column(String(500), nullable=True, comment="excel文件路径")
    status = Column(String(20), default="generated", comment="状态")
    create_time = Column(DateTime, default=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)
    # 数据迁移：为已有 conversations 表添加新字段
    _migrate_conversations_table()
    # 数据迁移：定价引擎相关新表和字段
    _migrate_pricing_tables()
    # 数据迁移：generated_manuals / generated_excels 添加 version 字段
    _migrate_generated_files()


def _migrate_conversations_table():
    """为已有 conversations 表添加 user_id 和 title 字段（兼容老数据）"""
    import logging
    logger = logging.getLogger("db_migration")
    try:
        with engine.connect() as conn:
            # 检查 user_id 列是否存在
            try:
                result = conn.execute(text("SHOW COLUMNS FROM conversations LIKE 'user_id'"))
                rows = result.fetchall()
                if not rows:
                    conn.execute(text("ALTER TABLE conversations ADD COLUMN user_id VARCHAR(64) DEFAULT ''"))
                    conn.execute(text("CREATE INDEX ix_conversations_user_id ON conversations(user_id)"))
                    conn.commit()
                    logger.info("Migration: added user_id column to conversations")
            except Exception as e:
                logger.debug(f"Migration check user_id skipped: {e}")
            # 检查 title 列是否存在
            try:
                result = conn.execute(text("SHOW COLUMNS FROM conversations LIKE 'title'"))
                rows = result.fetchall()
                if not rows:
                    conn.execute(text("ALTER TABLE conversations ADD COLUMN title VARCHAR(200) DEFAULT ''"))
                    conn.commit()
                    logger.info("Migration: added title column to conversations")
            except Exception as e:
                logger.debug(f"Migration check title skipped: {e}")
            # 扩展 messages_json 和 extracted_needs_json 列容量（TEXT → MEDIUMTEXT）
            try:
                conn.execute(text(
                    "ALTER TABLE conversations MODIFY COLUMN messages_json TEXT(16777215)"
                ))
                conn.execute(text(
                    "ALTER TABLE conversations MODIFY COLUMN extracted_needs_json TEXT(16777215)"
                ))
                conn.commit()
                logger.info("Migration: expanded messages_json and extracted_needs_json to MEDIUMTEXT")
            except Exception as e:
                logger.debug(f"Migration expand columns skipped (may already be MEDIUMTEXT): {e}")
    except Exception as e:
        logger.warning(f"Migration skipped: {e}")


def _migrate_pricing_tables():
    """为已有表添加定价引擎相关字段，创建定价相关新表"""
    import logging
    logger = logging.getLogger("db_migration")
    try:
        with engine.connect() as conn:
            # services 表新增字段
            for col, col_def in [
                ("sheet_source", "VARCHAR(50) DEFAULT NULL COMMENT '来源Sheet'"),
                ("is_priced", "INT DEFAULT 0 COMMENT '是否有成本价'"),
                ("aliases", "VARCHAR(500) DEFAULT NULL COMMENT '服务别名'"),
                ("pricing_category", "VARCHAR(50) DEFAULT NULL COMMENT '定价类别'"),
            ]:
                try:
                    result = conn.execute(text(f"SHOW COLUMNS FROM services LIKE '{col}'"))
                    if not result.fetchall():
                        conn.execute(text(f"ALTER TABLE services ADD COLUMN {col} {col_def}"))
                        conn.commit()
                        logger.info(f"Migration: added {col} column to services")
                except Exception as e:
                    logger.debug(f"Migration check services.{col} skipped: {e}")

            # generated_schemes 表新增字段
            for col, col_def in [
                ("pricing_logic_id", "BIGINT DEFAULT NULL COMMENT '关联定价逻辑ID'"),
                ("pricing_params_id", "BIGINT DEFAULT NULL COMMENT '关联定价参数ID'"),
                ("engine_total_cost", "DECIMAL(12,2) DEFAULT NULL COMMENT '规则引擎计算总成本'"),
                ("engine_total_quote", "DECIMAL(12,2) DEFAULT NULL COMMENT '规则引擎计算总报价'"),
                ("llm_total_cost", "DECIMAL(12,2) DEFAULT NULL COMMENT 'LLM给出总成本'"),
                ("llm_total_quote", "DECIMAL(12,2) DEFAULT NULL COMMENT 'LLM给出总报价'"),
                ("final_total_cost", "DECIMAL(12,2) DEFAULT NULL COMMENT '最终确认总成本'"),
                ("final_total_quote", "DECIMAL(12,2) DEFAULT NULL COMMENT '最终确认总报价'"),
                ("pricing_method", "VARCHAR(50) DEFAULT NULL COMMENT '定价方法'"),
            ]:
                try:
                    result = conn.execute(text(f"SHOW COLUMNS FROM generated_schemes LIKE '{col}'"))
                    if not result.fetchall():
                        conn.execute(text(f"ALTER TABLE generated_schemes ADD COLUMN {col} {col_def}"))
                        conn.commit()
                        logger.info(f"Migration: added {col} column to generated_schemes")
                except Exception as e:
                    logger.debug(f"Migration check generated_schemes.{col} skipped: {e}")

            # 创建新表（Base.metadata.create_all 会处理，这里做幂等兜底）
            for table_name, create_sql in [
                ("pricing_params", """
                    CREATE TABLE IF NOT EXISTS pricing_params (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(200) NOT NULL COMMENT '参数名称',
                        scene VARCHAR(100) DEFAULT NULL COMMENT '适用场景',
                        volume_min INT DEFAULT NULL COMMENT '最小保单规模',
                        volume_max INT DEFAULT NULL COMMENT '最大保单规模',
                        channel VARCHAR(100) DEFAULT NULL COMMENT '适用渠道',
                        margin_rate DECIMAL(6,4) DEFAULT NULL COMMENT '基础利润率',
                        channel_coeff DECIMAL(6,4) DEFAULT NULL COMMENT '渠道系数',
                        package_discount DECIMAL(6,4) DEFAULT NULL COMMENT '打包折扣',
                        usage_rate_column VARCHAR(50) DEFAULT NULL COMMENT '发生率列',
                        rounding_rule VARCHAR(50) DEFAULT NULL COMMENT '取整规则',
                        source_type VARCHAR(20) DEFAULT NULL COMMENT '来源',
                        source_scheme_id BIGINT DEFAULT NULL COMMENT '来源方案ID',
                        params_json TEXT DEFAULT NULL COMMENT '扩展参数JSON',
                        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ("pricing_logics", """
                    CREATE TABLE IF NOT EXISTS pricing_logics (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        scheme_id BIGINT DEFAULT NULL COMMENT '关联方案ID',
                        scheme_type VARCHAR(20) DEFAULT NULL COMMENT '方案类型',
                        pricing_method VARCHAR(100) DEFAULT NULL COMMENT '定价方法',
                        extracted_rules_json TEXT DEFAULT NULL COMMENT '结构化定价规则JSON',
                        logic_description TEXT DEFAULT NULL COMMENT '定价逻辑描述',
                        diff_vs_engine TEXT DEFAULT NULL COMMENT '与引擎基准差异',
                        diff_vs_previous TEXT DEFAULT NULL COMMENT '与同类方案差异',
                        confidence_score DECIMAL(3,2) DEFAULT NULL COMMENT '置信度',
                        extracted_by VARCHAR(50) DEFAULT NULL COMMENT '提取方式',
                        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ("pricing_rules", """
                    CREATE TABLE IF NOT EXISTS pricing_rules (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        logic_id BIGINT DEFAULT NULL COMMENT '关联定价逻辑ID',
                        rule_category VARCHAR(50) DEFAULT NULL COMMENT '规则类别',
                        rule_name VARCHAR(200) DEFAULT NULL COMMENT '规则名称',
                        rule_expression VARCHAR(500) DEFAULT NULL COMMENT '规则表达式',
                        rule_params_json TEXT DEFAULT NULL COMMENT '规则参数JSON',
                        priority INT DEFAULT 0 COMMENT '优先级',
                        is_active INT DEFAULT 1 COMMENT '是否启用',
                        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """),
            ]:
                try:
                    result = conn.execute(text(f"SHOW TABLES LIKE '{table_name}'"))
                    if not result.fetchall():
                        conn.execute(text(create_sql))
                        conn.commit()
                        logger.info(f"Migration: created table {table_name}")
                except Exception as e:
                    logger.debug(f"Migration create table {table_name} skipped: {e}")

    except Exception as e:
        logger.warning(f"Pricing migration skipped: {e}")


def _migrate_generated_files():
    """为 generated_excels 和 generated_manuals 表添加 version 字段"""
    import logging
    logger = logging.getLogger("db_migration")
    try:
        with engine.connect() as conn:
            for table_name in ["generated_excels", "generated_manuals"]:
                try:
                    conn.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN version INT DEFAULT 1 "
                        f"COMMENT '该方案下第几次生成'"
                    ))
                    conn.commit()
                    logger.info(f"Migration: added version column to {table_name}")
                except Exception as e:
                    err_msg = str(e).lower()
                    if "duplicate" in err_msg or "already exists" in err_msg or "exist" in err_msg:
                        logger.debug(f"Migration: version column already exists in {table_name}")
                    else:
                        logger.warning(f"Migration: failed to add version to {table_name}: {e}")

            # services 表新增字段（SeekDB 不支持 SHOW COLUMNS LIKE，直接 ALTER 并忽略重复列错误）
            for col, col_def in [
                ("service_time", "VARCHAR(200) DEFAULT NULL COMMENT '服务时间'"),
                ("service_response_time", "VARCHAR(200) DEFAULT NULL COMMENT '服务时效'"),
                ("special_notes", "TEXT DEFAULT NULL COMMENT '特别说明'"),
            ]:
                try:
                    conn.execute(text(
                        f"ALTER TABLE services ADD COLUMN {col} {col_def}"
                    ))
                    conn.commit()
                    logger.info(f"Migration: added {col} column to services")
                except Exception as e:
                    err_msg = str(e).lower()
                    if "duplicate" in err_msg or "already exists" in err_msg or "exist" in err_msg:
                        logger.debug(f"Migration: {col} column already exists in services")
                    else:
                        logger.warning(f"Migration: failed to add {col} to services: {e}")
    except Exception as e:
        logger.warning(f"Generated files migration skipped: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
