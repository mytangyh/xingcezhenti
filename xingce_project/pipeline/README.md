# 离线内容生产与发布

Python标准库实现；不调用付费API，不联网自动回退。原始题库与既有分析输入只读，规范JSONL为事实层，SQLite及阅读/练习包为派生产物。用户作答单独存储。

## 内容版本记录

以下数量和历史验收属于单独交付的内容包，不是本次 Git checkout 内的数据，也未在本次源码提交中重跑。公开源码不包含 releases、冻结 inputs/patches 或受控评测包；恢复与输入布局见项目 README。

## 当前状态

以 `releases/current.json` 指向的版本及其 `manifest.json` 为准，运行：

```sh
cd xingce_project
python -m pipeline.report --queue pipeline/runtime/production.sqlite --output pipeline/runtime/current_status.json
python -m unittest discover -s tests_pipeline -v
```

全库27,473个source-qid身份、58,890次出现、515来源卷名组、2,049候选材料。跨qid精确/近似候选不自动合并，因此这些数量不是“全库语义去重且均可训练”的宣称。规范题库80个留出身份仍隔离；另有独立评测80题面、79个可判分key及H49未决，显式评测API18项已过，但尚未用户作答，不能称完成个人盲测。原47参考卡保留；后续仅经显式准入的card-R19/R20/R21可加入为AI参考候选（总50＝40方法＋10知识），人工正式批准数始终另记，不因准入自动变为已批准。

待核材料、未知独立性、答案分歧和留出题不进入默认练习。真实核验数量、可练数量和争议隔离数量必须分别读取，不用总题量替代。

## 构建冻结批

只使用已完成文件清单及SHA校验的冻结目录。最终753题批的复现命令（重复构建换用另一个版本名，并加`--no-activate`）：

```sh
python -m pipeline.build --root .. --version content-v8-reviewed753 \
 --allow-new-card card-R19 --allow-new-card card-R20 --allow-new-card card-R21 \
 --overlay content_review/snapshots/batch-v4-190 \
 --overlay content_review/snapshots/lineage190-final-v2 \
 --overlay content_review/snapshots/extension-final120-v3 \
 --overlay content_review_reasoning/snapshot_0215_v2 \
 --overlay content_review_reasoning/supplement_r17_r18/snapshot_r17_r18_v2 \
 --overlay content_review_language/snapshots/batch-160-v2 \
 --overlay pipeline/inputs/math-blind50-v2 \
 --overlay content_card_review/snapshots/new-methods-v1 \
 --overlay content_card_review/snapshots/cards-review-v2 \
 --overlay acceptance/holdout \
 --overlay pipeline/patches/render-v2 \
 --overlay pipeline/patches/semantic-format-v2 \
 --overlay pipeline/patches/independent-rereview \
 --overlay acceptance/semantic_format_review \
 --overlay pipeline/patches/material-evidence-alias-v1
```

该批真实AI加工753个题目身份，732题可练；21题答案仍有分歧/未决而隔离（另有原库111无答案题）。50张参考卡＝40方法＋10知识，人工批准与真实个人迁移验收均未完成。56题明确为旧公开例重核，168题仅未命中已知公开清单，9题为明确非盲核验，其余题既往曝光状态未作全局认定；不能把753解释成753道用户从未见过的新盲测题。

版本不可原地覆写；复现时使用新的版本名。overlay按实体ID合并字段，不丢已有标注。构建入口读取overlay字节快照并记录实际消费内容哈希；单构建锁避免并发删除暂存目录。默认禁止新card ID。新增R19/R20/R21必须逐项传入`--allow-new-card card-R19 --allow-new-card card-R20 --allow-new-card card-R21`，且只允许AI参考状态；其他ID仍阻断。

构建在`.building-*`完成所有JSONL、SQLite、资产和manifest，检查文件全集哈希、实体schema、引用、JSONL与SQLite逐实体一致性、题面HTML安全、选项ID及修订迁移后才切换当前版本。失败不触碰当前指针。相同题意身份保留ID，题面实质改变须增加revision；不直接改原始source_answer。

## 发布、读取与回滚

```python
from pipeline.store import resolve_current, connect_readonly, load_entity
from pipeline.release import validate_release, activate_release, import_release
release = resolve_current('releases')
manifest = validate_release(release)
connection = connect_readonly(release / 'content.sqlite')
# 回滚到明确的已验证历史版本：
# activate_release('releases', '<版本名>')
# 导入外部目录，默认不激活：
# import_release('<待导入目录>', 'releases', activate=False)
```

SQLite文件只读权限且连接采用mode=ro。进行中的会话应固定内容版本。manifest哈希提供完整性，不是发行者密码学签名，不接受未知来源包为可信内容。

历史版本保持不变；不满足当时准入门的历史候选不作为最终入口，最终内容包不混入旧release。

## 事实层与练习安全

- question与occurrence分离，保留commit/path/line。source-qid内候选材料多变式单独标记，候选相同不等于语义绑定已核。
- material ID由`source_path#material_number`稳定派生。无材料标题不等于独立题；独立题也需绑定核查证据。
- 只有verified绑定、完整无泄漏题面、无阻断、非留出题才能practice_ready。默认仅verified答案；source_only必须显式选择，成绩分开。
- `stem_markdown`是历史字段名，实际内容为安全HTML/文本子集，与stem_html一致，不是未过滤原文。剔除答案标记、远程图、事件属性及隐藏答案字段。
- 图片采用assets/sha256路径，角色区分stem、option（含option_id）、material、analysis_only。JFIF原图转存JPEG兼容扩展名；仅解析缺图不冒充题干缺图。
- 原解析保留source_analysis；explanation_origin区分source_reference与native_independent_review，不能将保留的源解析标成独立推导。
- 官方日历等外部补充必须在学生材料题面可见，并明确“非原题原文”；raw_text保持原材料不变。
- 阅读、练习、答案分别导出reading/、practice/、answers/。不能把answers或后台原解析混入学生投影。

## 计算及证据

`calculation.evaluate`只允许有理数+-*/和括号，不执行函数、属性、变量、幂或任意代码。算术复算只证明表达式计算一致，不证明原图读数、模型设定和选项选择正确。具名变量须保留统计对象、时期、单位、原图行列或原文位置。

`lineage190-final-v2`为190资料题补充527具名算式及定性证据。独立封存盲审49/50一致：q19283972揭示后原图复核确认原生产答案正确、盲审误读行列，新增assessment保存纠错；封存盲审仍是49/50，不追改成50/50。

## 原生真实产物与生产队列

```sh
python -m pipeline.native_import --release releases/<版本> \
 --queue pipeline/runtime/production.sqlite \
 --report pipeline/runtime/native_import_report.json
```

真实独立AI标注通过发布校验后进入专属生产键，producer=native_assistant_artifact，回执模型标识未提供、token_usage=null，不编造型号或账单。source-only原解析、基础标签、mock和留出题不计入真实完成产物。

队列初期存在700条未配置外部端点的历史请求，但不代表当前700题全部未完成。实际进度以去重题目身份统计；同题不同版本生产记录不累加冒充新题。外部API未配置不妨碍原生助手完成真实核验。

Queue缓存键包含题/材料ID与revision、prompt、taxonomy和模型配置。收到结果后先fsync独立响应收据，再写DB；DB失败由收据恢复，不新调用。收据本身写失败时保留进程内存结果；重启后无法确定结果的请求进入needs_review，不盲重试。已知调用失败指数退避30秒起、上限600秒、最多3次；不声称无条件exactly-once。

MockProvider仅测试且禁止publish。真实结果没有validator不得通过；费用表对模拟标0、对未报告实际费用标unknown，不猜账单。没有付费自动回退。

## 验收与使用边界

流水线22项单测、独立manifest对抗测试、真实响应DB写异常测试分别记录于测试目录。每个新版本仍须重新执行全库、实际API、holdout、卡数、题面和解释来源检查，不能继承“上一版通过”冒充本版通过。

正式卡片人工审批、个人迁移作答、真实提分验证保持未完成，不能由AI自批替代。源题及图片许可未确认，仅供用户私有复习，不据此公开转载内容包。

最终发版需用同一冻结输入独立构建两个版本，运行`pipeline.reproducibility`，报告实际JSONL/资产字节一致性与SQLite逻辑/二进制一致性；源码打包边界见`SOURCE_PACKAGE_POLICY.md`。

格式修订补丁`pipeline/patches/semantic-format-v2`对含u/sub/sup的254题、89材料递增revision。内容层只保留无属性语义标签，学生端转为明确纯文本划线/上下标；空白横线保留占位。旧release不就地修改。

完整再生产还依赖原repo及`xingce_analysis/records.jsonl`、`materials_candidates.jsonl`、`v2/index/canonical_topic_index.jsonl`、方法卡目录和原始方法文档；这些输入的实际哈希见manifest。若仅下载轻量源码包，需要另备这些输入，不能视为自包含全库再生产包。最终release自带全部规范JSONL，可在新目录调用`make_database`独立重建只读内容库，不触及用户数据库。
