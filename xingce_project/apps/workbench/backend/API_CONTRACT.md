# API v1（单人离线，JSON）
GET /api/catalog → {release,counts,modules,concepts,quality_notice}
GET /api/search?q=&module=&kind=questions|cards|materials&limit=20 → {items,search_mode,release}; question结果仅题面
GET /api/cards → {items}; GET /api/cards/{id} → card
POST /api/sessions {mode:practice|group|mock,question_ids?:[],module?:string,count?:5,allow_source_only?:false,paper_id?:string} → session（含id,release,mode,status,question_ids,attempts）
GET /api/sessions → {items}; GET /api/sessions/{id} → session
GET /api/sessions/{id}/items → {session,items:[{question_id,stem,options:[{option_id,label,text}],material_id,material:{id,text,assets},assets,answer_status}],attempts}
POST /api/sessions/{id}/events {type:pause|resume|heartbeat|interrupt,question_id?,duration_seconds?} → session；mock禁止pause
POST /api/sessions/{id}/submit {} → session; 所有draft一并提交后允许review
POST /api/attempts {session_id,question_id,attempt_id?:string,selected_option_ids:[],action:save|submit|redo,hint_used?:false,guessed?:false} → {attempt_id,status,selected_option_ids,review_available,...}; 创建session已生成attempts，使用其attempt_id；redo生成新ID
GET /api/attempts/{id}/review → {attempt,question,answer,explanation,source_refs,cards,transfer}; 组/模拟未全提交返回409
POST /api/attempts/{id}/review {error_type,notes?,interval_days?:1|3|7,hint_used?,guessed?} → {due_at,...}
GET /api/reviews/due → {items}; GET /api/stats → {total_submitted,verified,source_only,ungraded,first_attempt,mastery,...}
GET /api/exports?format=json|sqlite → 下载个人数据JSON或SQLite一致性备份
POST /api/imports {path:string} → 校验并导入允许目录内release（具体path权限看README）
GET /api/releases → {items,current}; POST /api/releases/{version}/activate → {release}
POST /api/restore {path:string} → 恢复已验证个人SQLite备份（服务器自己exports目录内）
GET /api/assets/{release}/{path} → 只允许manifest登记安全资产
所有错误 {detail:...}；不返回HTML题面，前端纯文本渲染，图片使用assets[].url。

追加：POST /api/sessions/{id}/abandon {} → session(status=abandoned)，保留草稿/历史，冻结计时并标中断；不能再改/提交，需新建会话。活跃组练/模拟阻止全部解析与卡详情（摘要仍可见），提交或放弃后解锁。practice全部题提交后自动结束。action=redo新建单题session并返回新的session_id/attempt_id，不改历史计时。cards列表/search仅摘要；GET card详情才记录显式例题曝光。question.options[].assets包含本选项图片；question.assets[].role/option_id保留定位，不显示analysis_only。
POST /api/imports {kind:"userdata",path:"export.json"}：从userdata/imports导入v1 JSON完整历史（先隔离验证再一致性合并，冲突拒绝）；无该kind按release导入。

P1：GET /api/today 返回到期队列+有核准题的模块任务，含reason；POST /api/today/{task_id} {count,skip} 调整数量或跳过24小时。答错/提示后/猜测提交自动入1天复习队列，可在review改1/3/7天。stats包括提示/猜测/重做分层、每题证据次数、会话总/有效/阅读/分题时间、未中断已完成会话中位耗时；不是个人电脑性能测试、不是掌握概率。

一期导入：POST /api/imports {kind:"attempts_jsonl",path:"attempts.jsonl"}。每行必需attempt_id/question_id/revision/release_id/selected_options/elapsed_ms/mode/hint_used；可选submitted_at(Unix秒)/correct/guessed/seen_before。版本与选项不明确拒绝，缺独立评分快照归imported_unverified（保留reported_correct但不算准确率），不会猜测历史正确性。重复ID拒绝，失败事务回滚。

GET /api/backups → {items:[{filename,modified_at,size_bytes}]}，只列exports安全basename，供恢复下拉选择。组练/模拟单题submit冻结选项但grade=pending，不存答案；结束整组submit或abandon才冻结最终评分，进行中JSON/SQLite导出也不会露当前组答案。

## 结构化题库检索
GET /api/search/filters → {years,paper_types,concepts,release}（来源标签，不是原卷真实性认证）。
GET /api/search?kind=questions|materials&q=关键词或qid&module=&year=&paper_type=&concept_id=&allow_source_only=false&limit=20。
默认仅可练verified，来源答案必须显式true。年度+卷型须同一来源paper匹配；同一题不重复返回。返回total/items，题目仍题面白名单，附source_papers安全来源标签。材料返回text/assets/questions，检索展示即记曝光。holdout及关联候选材料排除。
GET /api/cards?module=... 与kind=cards均执行模块过滤，模块来自显式字段、来源目录或引用题归属。

## 独立个人迁移测验
独立目录 `xingce_project/assessments`（可用XINGCE_ASSESSMENTS指定），不混当前生产release与训练题量。
GET /api/assessments 仅返回包摘要/可评分及未决数量/历史启动次数，不曝光题面。
POST /api/assessments/{pack_id}/start {confirm:true,seen_before:false,hint_used:false} 明确确认本人开始；锁定独立pack版本及manifest/content hash；mode=mock持续计时，记录assessment_started和整包曝光。首次启动不是完全陌生保证；再次启动明确重做。
整卷提交前所有grade pending；放弃评测不揭密钥。未决题grade.correct=null，不计分母。/api/stats.assessment_sessions独立统计，不混日常训练总数；未做真实用户测验不宣称完成学习效果验证。
评测包契约见assessment.py：schema_version=assessment-1、ordered question_ids、scorable_count/unscored_count、完整files hash，题prompt_ready/assessment_ready与密钥证据一致；所有practice_ready=false、holdout_reserved=true。拒绝多余文件/符号链接/不安全标记/未登记资产。测试中所有作答均使用临时QA个人库。

GET /api/releases现只返回版本/计数摘要，不再把完整资产hash大清单传给浏览器；切换验证不降低。
