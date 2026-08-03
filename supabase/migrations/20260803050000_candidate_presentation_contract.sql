-- ============================================================
-- Candidate 展示契约：新候选不再保存来源摘录，AI 仅写入简体中文标题与摘要。
-- 历史 quoted_text 保持可读；新写入允许显式置空，不改变审核队列边界。
-- ============================================================
alter table public.source_capture_candidates
  alter column quoted_text drop not null,
  alter column quoted_text drop default;

alter table public.source_capture_candidates
  alter column analysis_schema_version set default 'preview_candidate_analysis_v2';
