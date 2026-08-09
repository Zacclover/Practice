-- ============================================================
-- 浏览器本地 AI 证据流：原始快照先审核，本地总结后才创建待审候选。
-- 不保留云端模型、预算或限流状态；正式证据仍只能走既有人工采纳 RPC。
-- ============================================================
drop function if exists public.reserve_source_capture_ai_budget(integer, integer, bigint);
drop table if exists public.source_capture_ai_daily_usage;

alter table public.source_capture_candidates
  drop constraint if exists source_capture_candidates_analysis_shape_check,
  drop constraint if exists source_capture_candidates_detection_window_check,
  drop column if exists analysis_status,
  drop column if exists analysis,
  drop column if exists analysis_model,
  drop column if exists analysis_schema_version,
  drop column if exists analysis_input_chars,
  drop column if exists analysis_reserved_tokens,
  drop column if exists analyzed_at;

alter table public.source_capture_snapshots
  add column page_title text not null default '',
  add column capture_mode text not null default 'scheduled'
    check (capture_mode in ('scheduled', 'manual')),
  add column summary_status text not null default 'pending'
    check (summary_status in ('pending', 'generated'));

-- 原页图片只保存经 Worker 校验后的公开 HTTPS 元数据，不下载、不执行远端内容。
create table public.source_capture_snapshot_images (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  snapshot_id uuid not null,
  source_id uuid not null,
  image_url text not null check (image_url ~ '^https://'),
  alt_text text not null default '',
  sort_order integer not null default 0 check (sort_order between 0 and 11),
  created_at timestamptz not null default now(),
  unique (snapshot_id, image_url),
  foreign key (workspace_id, tab_id, snapshot_id)
    references public.source_capture_snapshots(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, source_id)
    references public.competitor_sources(workspace_id, tab_id, id) on delete cascade
);

-- Candidate 附件是快照图片的不可变关联元数据，随候选删除但不影响原始快照。
create table public.candidate_attachments (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  candidate_id uuid not null,
  snapshot_image_id uuid not null,
  image_url text not null check (image_url ~ '^https://'),
  alt_text text not null default '',
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  unique (candidate_id, snapshot_image_id),
  foreign key (workspace_id, tab_id, candidate_id)
    references public.source_capture_candidates(workspace_id, tab_id, id) on delete cascade,
  foreign key (snapshot_image_id) references public.source_capture_snapshot_images(id) on delete restrict
);

alter table public.source_capture_snapshot_images enable row level security;
alter table public.candidate_attachments enable row level security;
create policy "workspace members read snapshot images" on public.source_capture_snapshot_images
for select to authenticated using (public.is_workspace_member(workspace_id));
create policy "workspace members read candidate attachments" on public.candidate_attachments
for select to authenticated using (public.is_workspace_member(workspace_id));
grant select on public.source_capture_snapshot_images, public.candidate_attachments to authenticated;
grant select, insert on public.source_capture_snapshot_images to service_role;
grant select, insert on public.candidate_attachments to service_role;
grant select, delete on public.source_capture_candidates to service_role;

-- 浏览器提交的只是本机推理结果；函数重新校验成员、归属、中文结构及 pending 状态。
create function public.create_local_summary_candidate(
  target_snapshot_id uuid,
  feature_title text,
  feature_summary text
) returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  snapshot_row public.source_capture_snapshots%rowtype;
  source_row public.competitor_sources%rowtype;
  candidate_id uuid := gen_random_uuid();
begin
  select * into snapshot_row from public.source_capture_snapshots where id = target_snapshot_id;
  if snapshot_row.id is null or not public.is_workspace_member(snapshot_row.workspace_id) then
    raise exception 'snapshot_not_available';
  end if;
  if snapshot_row.summary_status <> 'pending' then raise exception 'snapshot_already_summarized'; end if;
  if length(btrim(feature_title)) not between 2 and 40
      or length(btrim(feature_summary)) not between 10 and 1200
      or feature_title !~ '[一-龥]' or feature_summary !~ '[一-龥]' then
    raise exception 'invalid_chinese_summary';
  end if;
  select * into source_row from public.competitor_sources where id = snapshot_row.source_id;
  insert into public.source_capture_candidates (
    id, workspace_id, tab_id, competitor_id, source_id, run_id, snapshot_id,
    source_url, title, summary, quoted_text, content_hash, status
  ) values (
    candidate_id, snapshot_row.workspace_id, snapshot_row.tab_id, source_row.competitor_id,
    snapshot_row.source_id, snapshot_row.run_id, snapshot_row.id, snapshot_row.canonical_url,
    btrim(feature_title), btrim(feature_summary), left(snapshot_row.extracted_text, 1200),
    snapshot_row.content_hash, 'pending'
  );
  insert into public.candidate_attachments (
    id, workspace_id, tab_id, candidate_id, snapshot_image_id, image_url, alt_text, sort_order
  ) select gen_random_uuid(), workspace_id, tab_id, candidate_id, id, image_url, alt_text, sort_order
    from public.source_capture_snapshot_images where snapshot_id = snapshot_row.id;
  update public.source_capture_snapshots set summary_status = 'generated' where id = snapshot_row.id;
  return candidate_id;
end;
$$;

revoke all on function public.create_local_summary_candidate(uuid, text, text) from public;
grant execute on function public.create_local_summary_candidate(uuid, text, text) to authenticated;
