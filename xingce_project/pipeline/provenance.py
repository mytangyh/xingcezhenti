"""Shared discriminator for actual independent native review artifacts."""
def is_independent_annotation(annotation):
 if annotation.get('status')=='reference_not_human_approved':return False
 reasoning=any(annotation.get(k) for k in ('steps','expressions','review_scope','independent_reasoning','minimal_exam_route','blind_reasoning','reasoning_steps'))
 evidence=any(annotation.get(k) for k in ('evidence_refs','binding_evidence_refs','source_evidence','variable_sources'))
 return bool(reasoning and evidence)
