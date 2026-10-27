# 行测个人离线工作台 · 前端

React + TypeScript + Vite。依赖锁在 package-lock.json，构建后的 `dist/` 由 FastAPI 静态服务；不把 Vite preview 当生产服务。

## 构建

在本目录执行：

```sh
npm ci --cache .npm-cache --no-audit --no-fund
npm run typecheck
npm test
npm run build
```

在项目所在工作区根目录运行后端（内容 release、个人目录参见 backend/README）：

```sh
python -m uvicorn xingce_project.apps.workbench.backend.app:app --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000`。先构建，再启动后端；FastAPI 启动时检测 dist。开发可运行 `npm run dev`，生产不需要 Node 进程。

## 已实现

- 今日任务和可调整专题/题量/练习模式；不承诺分数、不把预算当实测耗时。
- 纯文本题面、材料/小题分栏、组题导航、选项即时保存、标记、刷新恢复。
- 仅本地登记资产路径可显示图片，点击放大；无原始 HTML 注入、无远程图追踪。
- 练习主动暂停；模拟不允许暂停、不因后台自动停表；服务端计时为准。
- 单题提交/整组提交只在用户操作后读取复盘。按钮防双击；服务端 attempt_id 提供幂等性。
- 来源解析、方法草稿及已核验状态区分；错因/备注/复习间隔；候选迁移题。
- 中文方法搜索与状态过滤；到期复习；个人数据 JSON / SQLite 备份、服务端允许目录导入与恢复、版本切换。

## 安全与验收范围

`tests/logic.test.mjs` 只验证纯函数逻辑：URL白名单、计时和状态文案，不等于真实浏览器端到端验收。类型检查和构建记录另附。本次公开源码提交未重跑真实浏览器验收，详见项目 VALIDATION.md。客户端不持有题库答案；安全边界必须以后端接口测试为准。

默认 source_only 题显式提示待核验。练习源答案与已核验答案分开统计。图片映射、原卷完整性未核准的内容只能由后端阻止进入训练，不由前端假称认证。

## 源码打包

公开 Git 保留 `src/`、`tests/`、`package.json`、`package-lock.json`、TypeScript/Vite 配置及 README/QUALITY 文档。排除 `node_modules/`、`.npm-cache/`、`*.tsbuildinfo`；`dist/` 不入 Git，首次使用先构建。另行制作的私有离线交付包可包含 dist，由 FastAPI 提供，不必附带构建缓存。正式启动命令见上文或项目总启动脚本。
