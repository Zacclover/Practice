-- ============================================================
-- 云工作区同步：唯一工作区、原子首导入、Tab 变更与候选审批
-- 本迁移只随代码交付，不由客户端执行，也不包含任何服务端密钥。
-- ============================================================

create unique index workspaces_owner_user_id_unique_idx
on public.workspaces (owner_user_id);

-- 登录用户只解析自己的唯一工作区；并发首次登录通过唯一索引收敛为同一行。
create or replace function public.resolve_user_workspace(workspace_name text default '我的研究空间')
returns public.workspaces
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved public.workspaces;
begin
  if auth.uid() is null then raise exception 'authentication required'; end if;
  insert into public.workspaces (id, owner_user_id, name)
  values (gen_random_uuid(), auth.uid(), coalesce(nullif(btrim(workspace_name), ''), '我的研究空间'))
  on conflict (owner_user_id) do update set owner_user_id = excluded.owner_user_id
  returning * into resolved;
  return resolved;
end;
$$;

revoke all on function public.resolve_user_workspace(text) from public;
grant execute on function public.resolve_user_workspace(text) to authenticated;

-- 首次导入只允许成员向完全空白的工作区写入；所有表在一个事务内完成。
create or replace function public.import_initial_workspace_snapshot(
  target_workspace_id uuid,
  snapshot jsonb
) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  item jsonb;
begin
  if auth.uid() is null or not public.is_workspace_member(target_workspace_id) then
    raise exception 'workspace membership required';
  end if;
  perform 1 from public.workspaces where id = target_workspace_id for update;
  if exists (select 1 from public.workspace_tabs where workspace_id = target_workspace_id) then
    raise exception 'workspace is not empty';
  end if;

  for item in select value from jsonb_array_elements(coalesce(snapshot->'workspace_tabs', '[]'::jsonb)) loop
    insert into public.workspace_tabs (id, workspace_id, name, sort_order, created_at, updated_at)
    values ((item->>'id')::uuid, target_workspace_id, item->>'name', (item->>'sort_order')::integer,
      coalesce((item->>'created_at')::timestamptz, now()), coalesce((item->>'updated_at')::timestamptz, now()));
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'competitors', '[]'::jsonb)) loop
    insert into public.competitors (id, workspace_id, tab_id, name, website, positioning, is_sample, created_at, updated_at)
    values ((item->>'id')::uuid, target_workspace_id, (item->>'tab_id')::uuid, item->>'name', coalesce(item->>'website',''),
      coalesce(item->>'positioning',''), coalesce((item->>'is_sample')::boolean,false),
      coalesce((item->>'created_at')::timestamptz,now()), coalesce((item->>'updated_at')::timestamptz,now()));
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'dimensions', '[]'::jsonb)) loop
    insert into public.dimensions (id, workspace_id, tab_id, name, sort_order, is_sample, created_at, updated_at)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,item->>'name',(item->>'sort_order')::integer,
      coalesce((item->>'is_sample')::boolean,false),coalesce((item->>'created_at')::timestamptz,now()),coalesce((item->>'updated_at')::timestamptz,now()));
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'evidence', '[]'::jsonb)) loop
    insert into public.evidence (id,workspace_id,tab_id,competitor_id,title,content_html,images,is_sample,created_at,updated_at)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'competitor_id')::uuid,item->>'title',
      coalesce(item->>'content_html',''),coalesce(item->'images','[]'::jsonb),coalesce((item->>'is_sample')::boolean,false),
      coalesce((item->>'created_at')::timestamptz,now()),coalesce((item->>'updated_at')::timestamptz,now()));
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'evidence_dimensions', '[]'::jsonb)) loop
    insert into public.evidence_dimensions (id,workspace_id,tab_id,evidence_id,dimension_id)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'evidence_id')::uuid,(item->>'dimension_id')::uuid);
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'insights', '[]'::jsonb)) loop
    insert into public.insights (id,workspace_id,tab_id,title,fact_signals,common_pattern,key_difference,opportunity_hypothesis,action_recommendation,is_sample,created_at,updated_at)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,item->>'title',coalesce(item->>'fact_signals',''),
      coalesce(item->>'common_pattern',''),coalesce(item->>'key_difference',''),coalesce(item->>'opportunity_hypothesis',''),
      coalesce(item->>'action_recommendation',''),coalesce((item->>'is_sample')::boolean,false),
      coalesce((item->>'created_at')::timestamptz,now()),coalesce((item->>'updated_at')::timestamptz,now()));
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'insight_competitors', '[]'::jsonb)) loop
    insert into public.insight_competitors (id,workspace_id,tab_id,insight_id,competitor_id)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'insight_id')::uuid,(item->>'competitor_id')::uuid);
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'insight_dimensions', '[]'::jsonb)) loop
    insert into public.insight_dimensions (id,workspace_id,tab_id,insight_id,dimension_id)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'insight_id')::uuid,(item->>'dimension_id')::uuid);
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'insight_evidence', '[]'::jsonb)) loop
    insert into public.insight_evidence (id,workspace_id,tab_id,insight_id,evidence_id)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'insight_id')::uuid,(item->>'evidence_id')::uuid);
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'matrix_cells', '[]'::jsonb)) loop
    insert into public.matrix_cells (id,workspace_id,tab_id,dimension_id,competitor_id,value,is_sample,created_at,updated_at)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'dimension_id')::uuid,(item->>'competitor_id')::uuid,
      coalesce(item->>'value',''),coalesce((item->>'is_sample')::boolean,false),
      coalesce((item->>'created_at')::timestamptz,now()),coalesce((item->>'updated_at')::timestamptz,now()));
  end loop;
  for item in select value from jsonb_array_elements(coalesce(snapshot->'competitor_sources', '[]'::jsonb)) loop
    insert into public.competitor_sources (id,workspace_id,tab_id,competitor_id,label,source_type,url,fetch_interval_hours,is_enabled)
    values ((item->>'id')::uuid,target_workspace_id,(item->>'tab_id')::uuid,(item->>'competitor_id')::uuid,item->>'label',
      item->>'source_type',item->>'url',(item->>'fetch_interval_hours')::integer,coalesce((item->>'is_enabled')::boolean,true));
  end loop;
end;
$$;

revoke all on function public.import_initial_workspace_snapshot(uuid, jsonb) from public;
grant execute on function public.import_initial_workspace_snapshot(uuid, jsonb) to authenticated;

-- Tab 排序与改名使用单次锁和基线时间；冲突时整批拒绝，不产生半完成顺序。
create or replace function public.apply_workspace_tab_mutations(
  target_workspace_id uuid,
  mutations jsonb
) returns setof public.workspace_tabs
language plpgsql
security definer
set search_path = ''
as $$
declare item jsonb; current_updated_at timestamptz;
begin
  if auth.uid() is null or not public.is_workspace_member(target_workspace_id) then raise exception 'workspace membership required'; end if;
  perform 1 from public.workspaces where id = target_workspace_id for update;
  for item in select value from jsonb_array_elements(coalesce(mutations, '[]'::jsonb)) loop
    select updated_at into current_updated_at from public.workspace_tabs
      where workspace_id=target_workspace_id and id=(item->>'id')::uuid for update;
    if item ? 'baseline_updated_at' and current_updated_at is distinct from (item->>'baseline_updated_at')::timestamptz then
      raise exception 'tab conflict: %', item->>'id';
    end if;
  end loop;
  -- 先移出唯一排序区间，再统一落位，交换相邻 Tab 时不会触发中间态唯一约束。
  update public.workspace_tabs set sort_order = sort_order + 100000
    where workspace_id=target_workspace_id
      and id in (select (value->>'id')::uuid from jsonb_array_elements(coalesce(mutations, '[]'::jsonb)));
  for item in select value from jsonb_array_elements(coalesce(mutations, '[]'::jsonb)) loop
    update public.workspace_tabs set name=coalesce(item->>'name',name), sort_order=coalesce((item->>'sort_order')::integer,sort_order)
      where workspace_id=target_workspace_id and id=(item->>'id')::uuid;
  end loop;
  return query select * from public.workspace_tabs where workspace_id=target_workspace_id order by sort_order;
end;
$$;

revoke all on function public.apply_workspace_tab_mutations(uuid, jsonb) from public;
grant execute on function public.apply_workspace_tab_mutations(uuid, jsonb) to authenticated;

-- 候选只有明确审批 RPC 才能转为证据；拒绝动作不会写入研究产物。
create or replace function public.approve_source_capture_candidate(candidate_id uuid, evidence_title text, evidence_content_html text default '')
returns uuid language plpgsql security definer set search_path = '' as $$
declare candidate public.source_capture_candidates; new_evidence_id uuid := gen_random_uuid();
begin
  select * into candidate from public.source_capture_candidates where id=candidate_id for update;
  if candidate.id is null or candidate.status <> 'pending' or not public.is_workspace_member(candidate.workspace_id) then
    raise exception 'pending candidate membership required';
  end if;
  insert into public.evidence (id,workspace_id,tab_id,competitor_id,title,content_html)
  values (new_evidence_id,candidate.workspace_id,candidate.tab_id,candidate.competitor_id,
    coalesce(nullif(btrim(evidence_title),''),candidate.title),coalesce(evidence_content_html,''));
  update public.source_capture_candidates set status='approved',reviewed_at=now(),reviewed_by=auth.uid() where id=candidate_id;
  return new_evidence_id;
end; $$;

revoke all on function public.approve_source_capture_candidate(uuid, text, text) from public;
grant execute on function public.approve_source_capture_candidate(uuid, text, text) to authenticated;
