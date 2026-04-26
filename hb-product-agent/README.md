# 产品方案助手（HB-Product-Agent）

基于大语言模型（LLM）的对话式产品方案生成系统。面向圆心惠保区域销售和业务人员，通过自然语言对话收集客户需求，自动生成**健康管理服务方案、Excel 报价单**和**Word 服务手册**。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 (Composition API) + Vite + Element Plus + Vant |
| 后端 | Python 3.11+ / FastAPI + SQLAlchemy + Uvicorn |
| AI 模型 | 阿里云百炼 DashScope `qwen3.6-plus`（OpenAI 兼容端点） |
| 数据库 | OceanBase SeekDB 嵌入式模式（MySQL 兼容） |
| 文档生成 | python-docx（Word）+ openpyxl（Excel） |
| 部署 | Docker Compose（backend + frontend + seekdb） |

## 核心功能

- **对话式需求收集**：AI 引导销售人员逐步明确目标人群、预算、保单规模、场景渠道等关键信息
- **多档位方案推荐**：自动生成引流档/基础档/标准档/高端档 2-4 个价位方案，服务范围严格校验
- **一键导出交付**：方案确认后自动生成 Excel 报价单（多 Sheet）+ Word 服务手册
- **异步对话机制**：send-async 模式 + 前端轮询，避免长连接超时
- **方案灵活调整**：支持自由文本指令对方案进行二次调整、方案档位切换、确认/取消

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

### 1. 克隆项目

```bash
git clone https://github.com/daniel5zhang/product_agent.git
cd product_agent
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env`，填入百炼 API Key：

```env
BAILIAN_API_KEY=your_api_key_here
BAILIAN_APP_ID=your_app_id_here
```

### 3. 安装依赖

```bash
# 后端
pip install -r backend/requirements.txt

# 前端
cd frontend && npm install && cd ..
```

### 4. 导入服务素材

```bash
cd backend
python import_services.py
cd ..
```

### 5. 启动服务

```bash
# 一键启动前后端
bash start.sh
```

启动后访问：
- 前端：`http://localhost:15174`
- 后端 API 文档：`http://localhost:18080/docs`
- 健康检查：`http://localhost:18080/health`

### Docker Compose 部署（生产环境）

```bash
export BAILIAN_API_KEY=your_api_key
export BAILIAN_APP_ID=your_app_id
docker-compose up -d
```

服务端口：
- 前端 Nginx：`80`（反向代理 `/api/` 到后端）
- 后端 Uvicorn：`18080`（容器外映射）
- SeekDB：`2881`

## 项目结构

```
hb-product-agent/
├── backend/
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 中央配置（.env 加载）
│   ├── database.py             # ORM 模型 + 数据库初始化
│   ├── import_services.py      # 服务素材导入脚本
│   ├── models/
│   │   └── schemas.py          # Pydantic 数据模型
│   ├── middleware/             # 用户身份中间件
│   ├── routers/                # API 路由
│   │   ├── chat.py             # 对话管理
│   │   ├── scheme.py           # 方案管理
│   │   ├── material.py         # 素材库查询
│   │   ├── manual.py           # Word 服务手册
│   │   ├── excel.py            # Excel 报价单
│   │   └── pricing.py          # 定价引擎
│   ├── services/               # 业务逻辑层
│   │   ├── agent_service.py    # 对话编排核心
│   │   ├── baiyan_client.py    # 百炼 LLM 客户端
│   │   ├── task_manager.py     # 异步任务队列
│   │   ├── manual_generator.py # Word 手册生成器
│   │   ├── excel_generator.py  # Excel 报价单生成器
│   │   ├── pricing_engine.py   # 定价计算引擎
│   │   └── scheme_generator.py # 方案生成器
│   └── prompts/                # LLM Prompt 模板
│       ├── system_prompt.txt
│       ├── needs_extraction_prompt.txt
│       ├── pricing_extraction_prompt.txt
│       └── scheme_extraction_prompt.txt
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue    # 主聊天界面
│       │   └── SchemeView.vue  # 方案详情页
│       ├── components/
│       │   ├── ChatBubble.vue  # 消息气泡
│       │   ├── SchemeCard.vue  # 方案卡片
│       │   └── ServiceTable.vue# 服务清单表格
│       ├── api/                # 前端 API 封装
│       └── router/             # Vue Router
├── templates/manual/           # 服务手册模板
│   ├── cover.md
│   ├── warm_tips.md
│   └── appendix.md
├── doc/                        # 文档资料
├── docker-compose.yml
├── start.sh
└── README.md
```

## API 概览

| 模块 | 路径前缀 | 说明 |
|------|---------|------|
| 对话 | `/api/chat` | 会话管理、消息异步发送、历史加载 |
| 方案 | `/api/scheme` | 方案 CRUD、确认/调整、多档位切换 |
| 素材库 | `/api/material` | 服务项目查询、分类检索 |
| 服务手册 | `/api/manual` | Word .docx 手册生成、下载 |
| 报价单 | `/api/excel` | Excel .xlsx 报价单生成、下载 |
| 定价引擎 | `/api/pricing` | 精算定价计算 |

详细接口文档请访问运行中的 Swagger UI：`http://localhost:18080/docs`

## 配置说明

所有配置通过 `backend/.env` 文件管理，主要配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BAILIAN_API_KEY` | 百炼 API Key | - |
| `BAILIAN_APP_ID` | 百炼应用 ID | - |
| `LLM_MODEL` | 模型名称 | `qwen3.6-plus` |
| `DB_TYPE` | 数据库类型（sqlite/seekdb） | `sqlite` |
| `DB_URL` | 数据库连接串 | `sqlite:///./hb_agent.db` |
| `CORS_ORIGINS` | 允许的跨域来源 | `*` |

## License

Internal Use — 圆心惠保 产品精算中心
