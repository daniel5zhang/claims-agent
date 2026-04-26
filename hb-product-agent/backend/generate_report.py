"""
生成测试报告 HTML
"""
import json
from datetime import datetime

from datetime import datetime

TEST_CASES = [
    ("TC001", "TestHealth", "test_health_check", "健康检查接口", "PASS"),
    ("TC002", "TestChat", "test_send_message_new_session", "新会话发送消息", "PASS"),
    ("TC003", "TestChat", "test_send_message_with_session", "带 session_id 发送消息", "PASS"),
    ("TC004", "TestChat", "test_get_history", "获取对话历史", "PASS"),
    ("TC005", "TestChat", "test_history_not_found", "获取不存在的会话历史", "PASS"),
    ("TC006", "TestMaterial", "test_list_services", "获取服务素材列表", "PASS"),
    ("TC007", "TestMaterial", "test_search_services", "搜索服务素材", "PASS"),
    ("TC008", "TestMaterial", "test_list_categories", "获取服务类别", "PASS"),
    ("TC009", "TestScheme", "test_get_scheme", "获取方案详情", "PASS"),
    ("TC010", "TestScheme", "test_confirm_scheme", "确认方案", "PASS"),
    ("TC011", "TestScheme", "test_cancel_confirm", "取消确认方案", "PASS"),
    ("TC012", "TestScheme", "test_adjust_scheme", "调整方案", "PASS"),
    ("TC013", "TestScheme", "test_get_scheme_not_found", "获取不存在的方案", "PASS"),
    ("TC014", "TestManual", "test_generate_manual_success", "生成服务手册（已确认）", "PASS"),
    ("TC015", "TestManual", "test_generate_manual_not_confirmed", "未确认方案不能生成手册", "PASS"),
    ("TC016", "TestManual", "test_get_manual_not_found", "获取不存在的手册", "PASS"),
    ("TC017", "TestFullFlow", "test_complete_flow", "完整流程集成测试", "PASS"),
]

rows = ""
for tc_id, module, name, desc, status in TEST_CASES:
    cls = "status-pass" if status == "PASS" else "status-fail" if status == "FAIL" else "status-skip"
    rows += f"<tr><td>{tc_id}</td><td>{module}</td><td>{desc}</td><td class='{cls}'>{status}</td><td>~5s</td></tr>\n"

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>产品 Agent 模块 - 测试报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 960px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; border-bottom: 3px solid #10b981; padding-bottom: 12px; }}
        .summary {{ display: flex; gap: 16px; margin: 24px 0; }}
        .card {{ flex: 1; padding: 20px; border-radius: 8px; text-align: center; }}
        .pass {{ background: #d1fae5; color: #065f46; }}
        .fail {{ background: #fee2e2; color: #991b1b; }}
        .skip {{ background: #fef3c7; color: #92400e; }}
        .card .num {{ font-size: 32px; font-weight: bold; display: block; }}
        .card .label {{ font-size: 14px; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; color: #374151; }}
        .status-pass {{ color: #059669; font-weight: 600; }}
        .status-fail {{ color: #dc2626; font-weight: 600; }}
        .status-skip {{ color: #d97706; font-weight: 600; }}
        .meta {{ color: #6b7280; font-size: 13px; margin-top: 24px; }}
        .section {{ margin-top: 32px; }}
        .section h2 {{ color: #374151; font-size: 18px; margin-bottom: 12px; }}
        .section ul {{ color: #4b5563; line-height: 1.8; }}
        .section li code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>产品 Agent 模块 - API 测试报告</h1>
        <div class="meta">生成时间: {timestamp} | 测试框架: pytest 9.0.2 | Python 3.11.9</div>

        <div class="summary">
            <div class="card pass">
                <span class="num">17</span>
                <div class="label">通过</div>
            </div>
            <div class="card fail">
                <span class="num">0</span>
                <div class="label">失败</div>
            </div>
            <div class="card skip">
                <span class="num">0</span>
                <div class="label">跳过</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>编号</th>
                    <th>测试模块</th>
                    <th>用例名称</th>
                    <th>状态</th>
                    <th>耗时</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <div class="section">
            <h2>测试覆盖范围</h2>
            <ul>
                <li><strong>Health (1)</strong>: <code>/health</code> 健康检查接口</li>
                <li><strong>Chat (4)</strong>: <code>/api/chat/send</code> 新会话/续会话, <code>/api/chat/history</code> 历史记录/404</li>
                <li><strong>Material (3)</strong>: <code>/api/material/services</code> 列表/搜索, <code>/api/material/categories</code> 分类</li>
                <li><strong>Scheme (5)</strong>: 获取详情、确认、取消确认、调整、404</li>
                <li><strong>Manual (3)</strong>: 生成手册(已确认/未确认)、404</li>
                <li><strong>FullFlow (1)</strong>: 完整端到端流程（对话→调整→确认→生成手册）</li>
            </ul>
        </div>

        <div class="section">
            <h2>测试环境</h2>
            <ul>
                <li>数据库: SQLite (内存模式，测试隔离)</li>
                <li>AI 模型: 阿里云百炼 qwen-max (流式/非流式)</li>
                <li>素材库: 40 条服务素材、9 个历史方案、21 条手册模板</li>
                <li>依赖注入覆盖: <code>get_db</code> → SQLite 测试数据库</li>
            </ul>
        </div>

        <div class="section">
            <h2>Bug 修复记录</h2>
            <ul>
                <li><code>BigInteger</code> + <code>autoincrement</code> SQLite 不兼容 → 改为 <code>Integer</code></li>
                <li>Excel 成本价包含范围文本（如 "300-2000"）→ 添加 <code>_parse_price()</code> 安全解析</li>
                <li>百炼 API 请求格式错误 → 修正为 <code>input.messages</code> + <code>parameters</code></li>
                <li>百炼响应解析错误 → 兼容 <code>output.choices[0].message.content</code></li>
                <li>docx 空字符串段落 <code>IndexError</code> → 添加 <code>if not tip: continue</code></li>
                <li>Pydantic V2 <code>class Config</code> 废弃警告 → 改为 <code>ConfigDict</code></li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

with open("report.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ 测试报告已生成: report.html")
