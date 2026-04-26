# 产品 Agent 全量测试报告

## 测试概览

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 134 |
| 通过 | 134 |
| 失败 | 0 |
| 跳过 | 0 |
| 通过率 | 100% |
| 总耗时 | ~300s（真实百炼 API 调用） |

## 测试文件分布

| 文件 | 用例数 | 说明 |
|------|--------|------|
| test_health.py | 5 | 健康检查接口 |
| test_database.py | 20 | 数据库模型 CRUD、约束、关系 |
| test_material.py | 18 | 素材库接口（列表、搜索、详情、分类） |
| test_scheme.py | 23 | 方案管理（获取、确认、调整、状态流转） |
| test_manual.py | 14 | 服务手册生成、获取、下载 |
| test_chat.py | 18 | 对话接口（发送、流式、历史、多轮） |
| test_services.py | 25 | 服务层单元测试（Agent、手册生成器、百炼客户端） |
| test_full_flow.py | 11 | 端到端全流程测试 |

## Bug 修复记录

1. **SQLite BigInteger + autoincrement 不兼容**
   - 修复：引入 `PK_TYPE` 动态切换，SQLite 用 `Integer`，seekdb/MySQL 用 `BigInteger`

2. **seekdb 嵌入式模式 `lastrowid` 缺失**
   - 修复：monkey-patch `_SeekdbCursor.execute`，INSERT 后执行 `SELECT LAST_INSERT_ID()`

3. **百炼 API 请求格式错误**
   - 修复：改为 `input.messages` + `parameters` 格式

4. **百炼 API 响应解析兼容**
   - 修复：同时支持 `output.text` 和 `output.choices[0].message.content`

5. **Excel 成本价解析错误**
   - 修复：添加 `_parse_price()` 安全解析函数，处理范围文本和非数字

6. **docx 空字符串段落 IndexError**
   - 修复：添加 `if not tip: continue` 和 `if p.runs:` 保护

7. **测试数据库隔离问题**
   - 修复：`conftest.py` 添加 `cleanup_db` fixture，每个测试前清空表数据

8. **负数 ID 参数校验缺失**
   - 修复：`material.py` 中 `service_id: int = Path(..., ge=1)`

9. **DECIMAL 序列化为字符串**
   - 修复：`_scheme_to_dict` 中将 `total_cost`/`total_quote` 转 `float`

10. **百炼 API 偶发失败**
    - 修复：`baiyan_client.py` 添加 5 次重试，间隔 3 秒

11. **前端 loading 体验优化**
    - 修复：ChatView.vue 添加分阶段 loading 动画和提示文案

12. **后台异步执行支持**
    - 新增：`/chat/send-async` + `/chat/task/{task_id}` 轮询接口
    - 新增：前端 `pollTask` 轮询机制，避免前端长时间阻塞

## 运行命令

```bash
cd /Users/daniel/Desktop/code/产品精算/hb-product-agent
source backend/venv/bin/activate
DB_TYPE=sqlite python -m pytest test/ -v --timeout=300
```

## 环境信息

- Python: 3.11.9
- FastAPI + SQLAlchemy + httpx
- 阿里云百炼 API（真实调用）
- SQLite（测试隔离数据库）
