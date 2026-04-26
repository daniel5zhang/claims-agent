--
-- hb_core 菜单插入脚本
-- 在 hb_core 的菜单表中添加「产品 Agent」入口
-- 请根据实际菜单表结构调整
--

-- 假设菜单表名为 sys_menu 或类似（请根据实际表名修改）
-- 以下 SQL 为示例，需要适配 hb_core 实际的菜单表结构

-- 1. 先查询父菜单ID（如「产品管理」或「工具」菜单）
-- SELECT id FROM sys_menu WHERE menu_name = '产品管理';

-- 2. 插入「产品 Agent」菜单
-- INSERT INTO sys_menu (
--     parent_id,
--     menu_name,
--     menu_code,
--     menu_url,
--     menu_type,      -- 1:目录 2:菜单 3:按钮
--     icon,
--     sort_order,
--     status,         -- 0:禁用 1:启用
--     create_time
-- ) VALUES (
--     0,              -- 父菜单ID，请根据实际调整
--     '产品 Agent',
--     'product_agent',
--     'http://localhost:5173',  -- Vue 前端地址，生产环境请替换为实际域名
--     2,
--     'robot',
--     100,
--     1,
--     NOW()
-- );

-- 如果 hb_core 使用 set_dict 配置菜单，请使用以下方式：
-- INSERT INTO set_dict (dict_type, dict_code, dict_value, remark, sort) VALUES
-- ('menu', 'product_agent', '产品 Agent', 'AI产品顾问', 100);

-- 注意：
-- 1. 请将菜单 URL 替换为实际部署地址
-- 2. 如果通过 iframe 嵌入，URL 应指向 iframe 承载页面
-- 3. 如需 SSO 鉴权，请在 URL 中携带 token 或通过 Cookie 传递
