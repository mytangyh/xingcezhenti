# 公开源码提交验证（2026-10-27）

环境：云端 Linux、Python 3.12.14、Node 24.22.1、npm 11.9.0；后端依赖与 requirements.txt 固定版本一致，前端使用 package-lock.json 的 npm ci。

## 本次重新执行

| 检查 | 结果 |
| --- | --- |
| 后端 unittest discovery | 70 次执行通过 |
| 流水线 unittest discovery | 22 次执行通过 |
| 独立安全/对抗 unittest discovery | 56 次执行：53 通过、3 明确跳过 |
| 前端 Node tests | 16 通过 |
| TypeScript typecheck | 通过 |
| Vite production build | 通过，生成本地 dist（Git 忽略） |
| Python compileall | 通过 |
| 启动器 --check | 合成空 release 校验通过；未创建个人目录，不代表真实题库启动验收 |

Python discovery 包含基类/继承测试的重复执行，因此以上数字不是独立业务场景数，更不是经人工审阅的题目数。测试夹具与临时作答均非真实用户学习记录。

3 项跳过来自 tests_acceptance/test_assessment_pack_security.py，分别检查评分包缺失资产哈希、恶意题面与符号链接。它们依赖单独授权的 personal-holdout-80-v1 受控评分包；公开源码不附该包。缺失时明确 skip，绝不计为通过；提供包后自动恢复执行。

## 本次未运行

- 真实 content-v8-reviewed753 内容完整性/全题 API/搜索/图片集成；本次只恢复源码，未下载大型数据包。
- 冻结输入驱动的全库重建、双构建一致性及真实内容 audit 脚本。
- 受控 80 题评测包的真实 API/评分验收。
- 浏览器端到端、实际断网和用户 Windows 电脑测试。
- 人工方法卡审批、真实用户迁移作答和提分验证。

这些边界不因单测、构建或 Git 推送而改变。原始题库内容未修改。CI 状态须在推送后的确切提交上另查；本文件只记录本地执行，不宣称 GitHub CI 已通过。
