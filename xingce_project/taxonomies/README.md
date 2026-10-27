# 概念分类 v2-ai-1

115个现有主题概念；ID由名称稳定派生，改名通过aliases而不是静默替换ID。全部AI参考，不等于专家人工验收。父级层次暂null，不能凭空生成精细层级。规则候选不升级为语义核验。

未识别：question.classification_status=unknown、concept_ids=[]。新标签通过label_proposals.jsonl提交，字段见schemas/label_proposal.schema.json；status=proposed不能自动加入正式taxonomy。接受后新taxonomy_version发布并保留旧ID/别名迁移记录，拒绝保留原因和证据。

当前label_proposals为空表示尚未提交提案，不表示全库已经分类。reviewed release中13677个qid仍unknown（以规范库实时统计为准）。
