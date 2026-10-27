# 离线个人工作台后端

在工程上一级目录运行（Python 3.12）：

```sh
python -m pip install -r xingce_project/apps/workbench/backend/requirements.txt
XINGCE_USERDATA=/path/to/private/userdata python -m uvicorn xingce_project.apps.workbench.backend.app:app --host 127.0.0.1 --port 8765 --workers 1
```

默认内容目录 `xingce_project/releases`，可用 `XINGCE_RELEASES` 覆盖；默认个人库在 `xingce_project/userdata`。请保持个人库私密且不要提交到Git。只绑定本机，不能部署公网。构建frontend/dist后服务自动提供静态首页，修改构建或release后无需修改代码，首次添加dist需重启。

## 数据边界
- 内容SQLite以mode=ro读取；个人库完全独立。会话固定release，更新内容不重算历史成绩。
- verified默认；source_only需明确启用，成绩单列；disputed/unresolved不进入自动训练。
- 题面白名单返回，没有考点/解析/正确项。组练/模拟尚未完成时，卡详情及任何旧复盘暂时锁定，防通过其它入口泄露。卡列表只摘要。可提交或“放弃本轮”结束锁定；放弃不抹除历史、不允许继续作答。
- 原卷顺序未实装恢复，所有mock明确为重组模拟，不谎称原卷。没有可练题时返回422，而不是注入演示题。
- 暂停记录服务器有效时间与总时间；mock不能暂停。每15秒heartbeat建议；90秒无心跳后恢复视为中断，速度统计排除中断。显式reading/question_time事件可保存客户端阅读及分题分摊。
- 卡片曝光仅追踪显式example_qids/boundary_qids/question_ids，未知文字引用不能承诺全部未见。
- 图片只允许内容manifest登记的hash路径，不提供analysis_only图片、不接受SVG脚本。

## 导入、恢复、导出
- GET `/api/exports?format=sqlite|json` 下载。SQLite使用在线backup并核验。
- release先复制至 `userdata/imports/<版本目录>`，POST `/api/imports` JSON `{"path":"版本目录"}`。schema、hash、引用通过才复制/切current；同版本拒绝覆盖。旧会话保持旧库。
- 个人JSON导出放 `userdata/imports/a.json`，POST `/api/imports` `{"kind":"userdata","path":"a.json"}`。严格v1导出格式，隔离内存库校验后合并；同ID冲突拒绝，导入前快照。任意旧版JSONL不猜字段、不默默转换。
- POST `/api/restore` `{"path":"personal-xxx.sqlite"}` 仅接受 `userdata/exports` 内备份文件名。校验schema、integrity、引用及依赖release；先保留恢复前快照再在线恢复。
- POST `/api/releases/{version}/activate` 验证后切换/回滚，旧release不得删除。

## 测试
`python -m unittest discover -s xingce_project/tests_backend -v`
测试数据均为独立临时目录的合成fixture，不是实际真题核验依据。实际release集成报告另外生成。API契约见API_CONTRACT.md。

## 选题与曝光
自动组练先筛完整材料组，排除组内任何不可练/保留题，再优先用户记录中未作答、未曝光、未见同材料及同变体组，按题ID确定性排序；每次一完整组。自动模拟按完整组凑题量。题不足回到复习会在selection_notice明示，不伪称新题。指定question_ids用于自主选题/重做。

搜索题面和材料也算已阅（独立于已作答）；方法卡详情及复盘内的方法卡，记录显式example/evidence qids与正文qid数字引用曝光。卡片在生成迁移推荐之前记曝光。保留题及其候选/已绑定材料不进入搜索、训练和推荐；这里是保护候选盲测，不是宣称完成真实学习验证。

## 本次公开源码验证

见项目 [`VALIDATION.md`](../../../VALIDATION.md)。合成 fixture 单测不代表真实题目已核准或真实用户已作答。本次没有随 Git 携带大型内容 release、历史 QA 报告、个人数据或独立评测评分包，因此没有重跑真实 release 集成或浏览器端到端检查。

## 干净个人入口与独立评测

将 `XINGCE_USERDATA` 指向新的空目录即可创建空个人表；程序不复制 QA 记录、不自动开始测验或作答。独立评测默认从工程 `assessments/` 读取（可用 `XINGCE_ASSESSMENTS` 指定）；仅看摘要不产生曝光，须本人明确确认开始。

公开源码和普通内容包不含密封评分答案或父题映射。无独立受控评分包时，“个人迁移测验”显示尚无通过校验的包；普通练习不因此缺失。迁移该功能需要另行授权的原始、hash 匹配评分包，不能把密钥或 QA 个人数据库提交到公共 Git。
