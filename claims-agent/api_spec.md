# API 接口规范

Base URL: `/api/v1/`

---

## REST 端点

### 案件

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|:---:|
| GET | `/cases/` | 案件列表（分页+筛选） | Session |
| POST | `/cases/` | 手工录入新案件 | Session |
| GET | `/cases/{id}/` | 案件详情（含保单/进度/规则矩阵） | Session |
| POST | `/cases/{id}/audit/` | 触发单案件审核 | Session |
| POST | `/cases/batch_audit/` | 批量触发，返回队列任务 ID | Session |
| POST | `/cases/{id}/intervene/` | 人工注入意见 | Session |
| POST | `/cases/{id}/supplement/` | 上传补充材料 | Session |
| POST | `/cases/{id}/cancel/` | 软撤销 | Session |
| POST | `/cases/{id}/attachments/` | 上传附件 | Session |
| POST | `/cases/{id}/refresh_policies/` | 刷新保单数据 | Session |

### 规则

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/rules/` | 规则列表（按类型/层级筛选） |
| GET | `/rules/{id}/` | 规则详情（含历史版本） |
| PUT | `/rules/{id}/` | 更新规则 |
| POST | `/rules/{id}/publish/` | 发布新版本 |

### 配置

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/queue/` | 批量队列状态（含并发数/积压量） |
| GET | `/config/` | 系统配置（模型/存储/通知/SLA） |
| PUT | `/config/` | 更新系统配置 |
| GET | `/health/` | 健康检查（公开） |

### 管理端（admin only）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/admin/drugs/` | 药品库管理 |
| GET/POST | `/admin/hospitals/` | 医院库管理 |
| POST | `/admin/sync_old_system/` | 触发旧系统同步 |
| GET | `/admin/audit_logs/` | 系统审计日志 |
| GET | `/admin/model_logs/` | 模型调用日志 |
| POST | `/admin/reports/generate/` | 生成报表（异步） |
| GET | `/admin/reports/` | 已生成报表列表 |

### C 端（无需认证，`/c/` 路由）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/c/cases/` | 所有案件列表 |
| GET | `/c/cases/{id}/` | 案件状态 + 进度时间轴 |
| POST | `/c/cases/{id}/supplement/` | 提交补材 |

---

## WebSocket 端点

### `/ws/cases/{id}/` — Agent 执行进度实时推送

**认证**：内部系统 Session cookie，C 端匿名

**事件类型**：

```json
// phase_start — 阶段开始
{"event": "phase_start", "phase": "ocr_classify", "policy_id": "P001", "ts": "2026-05-16T10:00:00Z"}

// phase_complete — 阶段完成
{"event": "phase_complete", "phase": "ocr_classify", "policy_id": "P001", "duration_ms": 1200, "ts": "..."}

// tool_call — 工具调用（调试用）
{"event": "tool_call", "tool": "match_drug", "policy_id": "P001", "status": "running", "ts": "..."}

// rule_result — 单条规则结论
{"event": "rule_result", "rule_code": "1.3.1", "rule_name": "特药匹配",
 "policy_id": "P001", "result": "pass", "reason": "处方药品与保障药品匹配", "ts": "..."}

// intervention_required — 需要人工介入
{"event": "intervention_required", "phase": "archive", "reason": "既往症存在歧义", "ts": "..."}

// case_complete — 案件审核完成
{"event": "case_complete", "decision": "pass", "total_amount": 12000.00, "ts": "..."}

// error — 执行异常
{"event": "error", "phase": "audit", "policy_id": "P001", "message": "模型调用超时", "ts": "..."}
```

**断线重连**：指数退避（1s/2s/4s/8s/16s），重连后 GET `/api/v1/cases/{id}/` 补全状态。

---

## 通用规范

- **分页**：`?page=1&page_size=20`，默认 20 条/页，最大 100
- **筛选**：`?status=running&project_id=PROJ001&claim_type=SP`
- **排序**：`?ordering=-created_at`
- **认证**：Django Session（8 小时过期），登录页 `/login/`
- **CORS**：开发阶段 `localhost:5173`，生产同域
- **错误格式**：`{"error": "error_code", "detail": "human-readable message"}`
