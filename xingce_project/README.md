# 行测学习工作台（公开源码）

本目录在原始题库之外新增 **Python 内容流水线 + FastAPI 后端 + React/TypeScript 前端**。原有题库 Markdown、图片、根目录 README 和提交历史均不改动。

**代码已入仓 ≠ clone 后已具备完整刷题内容。** 本目录不包含大型内容 release、50 张参考卡的实际内容、冻结重建输入、个人答题记录、QA 数据库或密封评测答案。既有私人交付的内容包仍单独保存在 ChatGPT Library；没有公开下载链接。不得把来源许可尚未确认的题目、图片或评分密钥再次提交到公共仓库。

## 功能

- 只读版本化题库、题面/材料/图片检索、单题与组题练习、重组模拟。
- 作答即时保存、暂停/恢复、整组提交后复盘、错因与复习计划、曝光及候选迁移题管理。
- 独立个人 SQLite、JSON/SQLite 备份与校验恢复、内容导入和版本切换。
- 独立评测入口与评分包校验。未提供受控评测包时入口为空，普通练习仍可用。
- 内容规范化、清洗、来源追溯、发布完整性校验、队列缓存与重建一致性检查；不自动调用收费 API。

## 首次运行

以下命令从仓库根目录开始。运行环境：Python 3.12；本次前端构建使用 Node 24 / npm 11。Windows 电脑未实测；内容流水线使用 `fcntl`，全量重建需 Linux/macOS 或 WSL，不能据本机启动说明声称整个流水线原生支持 Windows。

### 1. 安装后端依赖

```sh
python -m venv xingce_project/.venv
# macOS/Linux:
source xingce_project/.venv/bin/activate
# Windows PowerShell: xingce_project\.venv\Scripts\Activate.ps1
python -m pip install -r xingce_project/apps/workbench/backend/requirements.txt
```

若 Windows 不允许激活，可直接使用 `xingce_project\.venv\Scripts\python.exe`。依赖首次安装需联网；requirements 固定已测版本，但不是跨平台完整 wheel 锁。

### 2. 构建前端

```sh
cd xingce_project/apps/workbench/frontend
npm ci --no-audit --no-fund
npm run typecheck
npm test
npm run build
cd ../../../..
```

`dist/` 是本地构建产物，不入 Git；构建后由 FastAPI 提供，运行时不需要 Node 服务或外部 CDN。若使用另行交付、已校验的离线源码包，其预构建 dist 可复用；公开 checkout 本身不附 dist。

### 3. 恢复已有内容包

从**此前已交付、可信的内容 ZIP**中仅提取 `xingce_project/releases/`，恢复到本仓库的同名目录；不要再套一层 `xingce_project`。不要覆盖源码或恢复 ZIP 中旧的 DELIVERY_RECEIPT/DELIVERY_ACCEPTANCE 文档，它们只描述原交付而非当前 Git 版本。最终布局：

```text
<仓库>/
  xingce_project/
    start_workbench.py
    apps/workbench/frontend/dist/index.html  # 步骤 2 生成
    releases/current.json
    releases/content-v8-reviewed753/manifest.json
    releases/content-v8-reviewed753/content.sqlite
    releases/content-v8-reviewed753/*.jsonl
    releases/content-v8-reviewed753/assets/...
```

保留内容包完整结构和全部资产；不要只复制 SQLite。具体版本及数量以包内 `current.json`、manifest 和校验结果为准。已有数据版本的“753 个 AI 加工题目身份 / 732 个可练题 / 50 张参考卡”是独立数据交付的记录，不是本 Git checkout 内的数据，更不是全部已获人工审批。参考卡非正式卡。

缺少内容包时，可运行下面的代码测试，但不能开始真实刷题。`--check` 会明确报缺少数据，不会生成演示题或伪造学习成绩。请从已有私人 Library 交付中取回内容包；没有该授权数据时，需要自行准备满足 schema 的可信 release。

### 4. 校验与启动

```sh
python xingce_project/start_workbench.py --check
python xingce_project/start_workbench.py
```

打开 **http://127.0.0.1:8765**，Ctrl+C 结束。仅回环绑定、单进程；不得直接部署公网。启动前完整校验哈希、数据库和实体关系。可用 `--port`、`--releases`、`--userdata` 指定端口或目录。

个人数据默认在 `xingce_project/userdata/`，与内容分离，Git 忽略。云端也应使用独立空个人目录，仅通过可信的私有访问方式使用，不要复制 QA 数据或公开服务。本轮真实内容完整性、题面/资产集成和合成浏览器回归见 VALIDATION.md；没有新的题图语义核验或用户学习验收。

## 代码测试

从仓库根目录设置 Python 模块路径后执行：

```sh
# macOS/Linux:
export PYTHONPATH="$PWD:$PWD/xingce_project"
# Windows PowerShell:
# $env:PYTHONPATH = "$PWD;$PWD\xingce_project"
python -m unittest discover -s xingce_project/tests_backend -p 'test_*.py'
python -m unittest discover -s xingce_project/tests_pipeline -p 'test_*.py'
python -m unittest discover -s xingce_project/tests_acceptance -p 'test_*.py'
```

`tests_backend/integration_*.py`、`tests_acceptance/audit_*.py` 等不是无数据单测：它们依赖真实 release、冻结输入或受控评测包。3 项评测包安全测试在包缺失时明确 skip，不代表通过。详见 [验证记录](VALIDATION.md)。

## 全量内容重建（可选，运行工作台不需要）

公开源码不是自包含的全库重建镜像。需另行准备已授权的固定版本原题库、分析索引、方法卡原稿、冻结 overlay 及哈希清单。独立重建输入包同样从既有私人交付恢复，不纳入 Git。

`pipeline.build --root <重建根目录>` 当前约定：

```text
<重建根目录>/
  xingce_project/              # 本目录源码及冻结 overlay 的既有相对布局
  xingce_analysis/             # records.jsonl、materials_candidates.jsonl、v2/...
  repos/xingcezhenti/          # 固定原始提交，含完整图片树，只读输入
```

本仓库题库基线为 `278984401124db40da5163a31275b8deb9c282f4`。单个 Git clone 的根目录不等于以上完整布局；在新目录准备输入，不要让构建覆盖原始 Markdown/图片。先核对输入包 README/清单/哈希，再按 [pipeline/README.md](pipeline/README.md) 的冻结批命令使用新版本名和 `--no-activate` 重建。原始全库重建、双构建一致性、真实数据审计在缺少输入时不能宣称通过。

## 边界

- 人工正式审批、正式方法卡、真实用户学习成效不能由 AI 或程序测试代替。
- source_only、已核验和争议记录分开；留出题与密封评分数据不公开。
- manifest 哈希验证完整性，不是发行者数字签名；只导入可信数据包。
- 本次不为来源题目、图片或第三方依赖重新授权。依赖遵循各自许可证；未确认来源许可的内容仅按已有授权私人使用。

## 本轮新增：全库覆盖与预算路线

“全库覆盖”从当前 release 的完整 questions/occurrences/papers/annotations 读取；不是把可练子集当全库。身份按 source-qid，出现次数、来源卷名组与身份×卷名组分别统计。基础标注保持对比分母，AI 深加工按流水线既有独立证据判据另计；未知年份/卷型/考点单列。来源卷名组只是覆盖代理，不能充当独立考试频率或官方考点概率。来源考试名称保留在证据定位中，不额外猜测考试类别。

代表题仅展示已核验可练题面；组练/模拟期间锁定证据入口。打开证据即记曝光，同材料一并记录；提供原始来源链接时保守记录该文件全部身份，含留出题的来源文件不开放原始链接。原始来源可能含解析，不适合当盲测入口。AI核验仍不等于人工批准。

今日路线支持20/40分钟：先安排用户设定的到期复习，再以资料→判断→言语→数量为模块先验；模块内优先未记录曝光候选，结合首次错误、提示/猜测、来源覆盖及题目计时排序。别名链、同材料与变式族、已知公开例均影响曝光判断。评分只用于排序，不换算官方分值、能力概率或预计涨分。

首次统计只用当前题目修订可判分的 verified 记录；中断或同一会话内重做的计时不用于首次耗时估计。耗时无记录按每题120秒，已有中位数限制在60–300秒作为计划值，20%时间留给复盘。实际用时可能超出预算，请使用暂停/结束止损。可调题量、跳过任务、手动选模块；今日路线以具体题目进入单题练，启动时校验版本，切换版本后需刷新。冷启动不推断个人薄弱能力，“未记录曝光”也不证明真正未见。

### 更便捷的内容恢复和启动

```sh
python xingce_project/start_workbench.py --diagnose
python xingce_project/start_workbench.py --import-zip /可信私有包.zip --trusted-content --check
./xingce_project/start.sh
# Windows PowerShell（需先按上文建立 .venv 并安装依赖）
# .\xingce_project\start.ps1
```

ZIP导入仅接受 `xingce_project/releases/`，只导入包指针指定的已完整验证版本；不恢复旧源码或个人数据，不覆盖同名历史版本。拒绝路径穿越/符号链接/超过4GiB解压数据。`--trusted-content` 是你对来源的确认，哈希校验不是发行者签名。缺少前端时仍须 npm 构建；不自动下载私有内容或使用付费服务。

### 私有内容缺口与证据清单

```sh
# 从仓库根目录，先按上文设置 PYTHONPATH
python -m pipeline.learning_report --release xingce_project/releases/content-v8-reviewed753
```

默认输出 `xingce_project/pipeline/runtime/learning_gap_report.json`（Git忽略）。包含实际缺口优先级、已有独立方法标注的证据引用及迁移候选；这些是冻结内容的索引复用，不是新审核题目或新批准卡片。未输入真实个人曝光记录的离线清单不能认定真正未见。本轮未新增题目图片语义核验，不把图片可加载称为读图核验。

### 可复现浏览器回归

```sh
# 先完成前端构建和后端依赖安装；仅使用原创合成夹具
python xingce_project/tests_e2e/serve.py
# 另一个终端：
npm install --prefix /tmp/xingce-browser --no-audit --no-fund playwright@1.62.1
/tmp/xingce-browser/node_modules/.bin/playwright install chromium
PLAYWRIGHT_MODULE=/tmp/xingce-browser/node_modules/playwright node xingce_project/tests_e2e/regression.mjs
```

服务绑定127.0.0.1:8766，退出即清理临时个人数据库。浏览器真实切换 offline 模式验证请求失败/重连；这不等于物理断开主机网络。部分版本/备份动作通过浏览器请求API验证，其余页面交互范围见 VALIDATION.md。CI仅运行合成夹具，不取回内容包、不上传题目、截图、个人记录或评分包，不配置 secrets。

Windows尚无授权实机验收：提供 `verify_windows.ps1`（后端与前端 smoke checks）；浏览器可在两个 PowerShell 终端运行上述 Python 服务和 Node 脚本，将 `PLAYWRIGHT_MODULE` 设置为本机安装目录。全流水线因 fcntl 依赖仍需 WSL/Linux，不能据本机Linux测试称为Windows通过。

模块内排序权重可复核：有首次记录时为 `2×首次错误比例 + 提示/猜测比例`，无记录时用1；另加 `min(来源卷组数,100)/100`，有效题目计时中位数超过120秒加0.5。先比较曝光状态再比较该权重，模块顺序优先于权重。参数是透明启发式，不是统计校准模型。来源卷型确认是独立数据优先项：仅依原文件/官方卷名明确证据建立映射候选，经核对再更新，不用NLP猜补。
