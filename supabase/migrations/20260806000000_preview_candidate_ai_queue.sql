-- ============================================================
-- Preview Candidate AI 持久队列：仅处理待审核 Candidate，不触及证据、矩阵或洞察。
-- Worker Durable Object 负责全局串行与 Alarm；数据库保存每条任务、状态和有限重试进度。
-- ============================================================
alter table public.source_capture_candidates
  drop constraint source_capture_candidates_analysis_status_check,
  add constraint source_capture_candidates_analysis_status_check
    check (analysis_status in ('pending', 'rate_limited', 'available', 'unavailable')),
  drop constraint source_capture_candidates_analysis_shape_check,
  add constraint source_capture_candidates_analysis_shape_check check (
    (analysis_status = 'available' and analysis is not null and jsonb_typeof(analysis) = 'object'
      and analysis_model is not null and analyzed_at is not null)
    or (analysis_status in ('pending', 'rate_limited', 'unavailable') and analysis is null)
  );

create table public.source_capture_ai_queue (
  candidate_id uuid primary key references public.source_capture_candidates(id) on delete cascade,
  page_title text not null default '',
  canonical_url text not null check (canonical_url ~ '^https://'),
  input_text text not null check (length(input_text) between 1 and 6000),
  status text not null default 'pending'
    check (status in ('pending', 'rate_limited', 'available', 'unavailable')),
  attempt_count integer not null default 0 check (attempt_count between 0 and 4),
  next_attempt_at timestamptz not null default now(),
  failure_code text check (failure_code is null or failure_code in (
    'missing_model_config', 'budget_unavailable', 'rate_limited', 'provider_unavailable',
    'malformed_response', 'invalid_response'
  )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index source_capture_ai_queue_due_idx
on public.source_capture_ai_queue (status, next_attempt_at, created_at)
where status in ('pending', 'rate_limited');

create trigger set_source_capture_ai_queue_updated_at
before update on public.source_capture_ai_queue
for each row execute function public.set_updated_at();

alter table public.source_capture_ai_queue enable row level security;
grant select, insert, update, delete on table public.source_capture_ai_queue to service_role;
