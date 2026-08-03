-- ============================================================
-- Preview 候选 AI 分析：仅扩展采集运行与候选，不触及证据、矩阵或洞察。
-- 预算函数以 UTC 日为单位原子预留保守额度，调用方必须先预留再请求模型。
-- ============================================================
alter table public.source_capture_runs
  add column detection_window_start timestamptz,
  add column detection_window_end timestamptz,
  add column detection_window_basis text not null default 'initial_observation'
    check (detection_window_basis in ('explicit', 'prior_success', 'initial_observation')),
  add constraint source_capture_runs_detection_window_check
    check (detection_window_start is null or detection_window_end is null or detection_window_start < detection_window_end);

alter table public.source_capture_candidates
  add column analysis_status text not null default 'unavailable'
    check (analysis_status in ('available', 'unavailable')),
  add column analysis jsonb,
  add column analysis_model text,
  add column analysis_schema_version text not null default 'preview_candidate_analysis_v1',
  add column analysis_input_chars integer check (analysis_input_chars between 0 and 6000),
  add column analysis_reserved_tokens integer check (analysis_reserved_tokens >= 0),
  add column analyzed_at timestamptz,
  add column publication_time_status text not null default 'unverified'
    check (publication_time_status in ('verified', 'not_found', 'unverified')),
  add column detection_window_start timestamptz,
  add column detection_window_end timestamptz,
  add column detection_window_basis text not null default 'initial_observation'
    check (detection_window_basis in ('explicit', 'prior_success', 'initial_observation')),
  add constraint source_capture_candidates_analysis_shape_check check (
    (analysis_status = 'available' and analysis is not null and jsonb_typeof(analysis) = 'object'
      and analysis_model is not null and analyzed_at is not null)
    or (analysis_status = 'unavailable' and analysis is null)
  ),
  add constraint source_capture_candidates_detection_window_check
    check (detection_window_start is null or detection_window_end is null or detection_window_start < detection_window_end);

create table public.source_capture_ai_daily_usage (
  usage_date date primary key,
  reserved_requests integer not null default 0 check (reserved_requests >= 0),
  reserved_tokens bigint not null default 0 check (reserved_tokens >= 0),
  updated_at timestamptz not null default now()
);

alter table public.source_capture_ai_daily_usage enable row level security;

-- 单条 SQL 冲突更新保证并发请求不会越过每日硬上限；超限时不写入预留。
create function public.reserve_source_capture_ai_budget(
  requested_tokens integer,
  daily_request_limit integer,
  daily_token_limit bigint
) returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  reserved boolean;
begin
  if requested_tokens <= 0 or daily_request_limit < 1 or daily_token_limit <= 0
      or requested_tokens > daily_token_limit then
    return false;
  end if;

  insert into public.source_capture_ai_daily_usage as usage (
    usage_date, reserved_requests, reserved_tokens, updated_at
  ) values (
    (now() at time zone 'utc')::date, 1, requested_tokens, now()
  )
  on conflict (usage_date) do update
    set reserved_requests = usage.reserved_requests + 1,
        reserved_tokens = usage.reserved_tokens + excluded.reserved_tokens,
        updated_at = now()
    where usage.reserved_requests < daily_request_limit
      and usage.reserved_tokens + excluded.reserved_tokens <= daily_token_limit
  returning true into reserved;

  return coalesce(reserved, false);
end;
$$;

revoke all on function public.reserve_source_capture_ai_budget(integer, integer, bigint) from public;
grant execute on function public.reserve_source_capture_ai_budget(integer, integer, bigint) to service_role;
grant select on table public.source_capture_ai_daily_usage to service_role;
grant update on table public.source_capture_candidates to service_role;
