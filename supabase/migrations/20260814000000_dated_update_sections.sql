-- ============================================================
-- 网页更新板块：保留每条原始发布日期，供本地 AI 审核前追溯。
-- 仅扩展 raw snapshot 与受控 Candidate 创建；不触及正式证据、矩阵或洞察。
-- ============================================================
alter table public.source_capture_snapshots
  add column if not exists published_at timestamptz;

create index if not exists source_capture_snapshots_published_at_idx
  on public.source_capture_snapshots (source_id, published_at desc)
  where published_at is not null;

create or replace function public.create_local_summary_candidate(
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
  existing_candidate_id uuid;
  candidate_id uuid := gen_random_uuid();
begin
  select * into snapshot_row from public.source_capture_snapshots where id = target_snapshot_id for update;
  if snapshot_row.id is null or not public.is_workspace_member(snapshot_row.workspace_id) then raise exception 'snapshot_not_available'; end if;
  select id into existing_candidate_id from public.source_capture_candidates
    where source_id = snapshot_row.source_id and content_hash = snapshot_row.content_hash limit 1;
  if existing_candidate_id is not null then
    update public.source_capture_snapshots set summary_status = 'generated' where id = snapshot_row.id;
    return existing_candidate_id;
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
    source_url, title, summary, quoted_text, published_at, content_hash, status
  ) values (
    candidate_id, snapshot_row.workspace_id, snapshot_row.tab_id, source_row.competitor_id,
    snapshot_row.source_id, snapshot_row.run_id, snapshot_row.id, snapshot_row.canonical_url,
    btrim(feature_title), btrim(feature_summary), left(snapshot_row.extracted_text, 1200),
    snapshot_row.published_at, snapshot_row.content_hash, 'pending'
  );
  insert into public.candidate_attachments (
    id, workspace_id, tab_id, candidate_id, snapshot_image_id, source_url, image_url, alt_text, sort_order
  ) select gen_random_uuid(), workspace_id, tab_id, candidate_id, id, image_url, image_url, alt_text, sort_order
    from public.source_capture_snapshot_images where snapshot_id = snapshot_row.id;
  update public.source_capture_snapshots set summary_status = 'generated' where id = snapshot_row.id;
  return candidate_id;
end;
$$;

revoke all on function public.create_local_summary_candidate(uuid, text, text) from public;
grant execute on function public.create_local_summary_candidate(uuid, text, text) to authenticated;
