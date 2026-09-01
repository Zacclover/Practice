-- ============================================================
-- 更新子页候选：保存确定性条目集合与排除统计，便于人工回溯。
-- 现有 (source_id, content_hash) 唯一约束对规范化条目集合实现语义幂等。
-- ============================================================
alter table public.source_capture_candidates
  add column selected_entries jsonb not null default '[]'::jsonb,
  add column excluded_missing_date_count integer not null default 0
    check (excluded_missing_date_count >= 0);
grant update on table public.source_capture_candidates to service_role;
