-- ============================================================
-- 单来源采集运行兼容：为定时与手动管线记录具体来源及结果。
-- 历史聚合运行允许 source_id 为空，新运行始终由 Worker 写入来源。
-- ============================================================
alter table public.source_capture_runs
  add column source_id uuid,
  add column http_status integer check (http_status between 200 and 599),
  add column finished_at timestamptz;

alter table public.source_capture_runs
  add constraint source_capture_runs_source_fk
  foreign key (workspace_id, tab_id, source_id)
  references public.competitor_sources(workspace_id, tab_id, id)
  on delete cascade;

-- Worker 既有管线以 succeeded 表示成功，保留旧 completed 值以兼容历史记录。
alter table public.source_capture_runs
  drop constraint source_capture_runs_status_check;
alter table public.source_capture_runs
  add constraint source_capture_runs_status_check
  check (status in ('queued', 'running', 'completed', 'succeeded', 'failed'));

-- 候选仅属于审核队列；quoted_text 保存用于人工核验的短摘录。
alter table public.source_capture_candidates
  add column quoted_text text not null default '';

-- 手动冷却严格按来源、触发类型与运行创建时间读取，不依赖来源最后抓取时间。
create index source_capture_runs_manual_cooldown_idx
on public.source_capture_runs (source_id, trigger_type, created_at desc)
where trigger_type = 'manual';
