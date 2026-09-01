-- ============================================================
-- 来源抓取图谱同步：用单个受认证事务写入 Tab → 竞品 → 来源。
-- 浏览器仅提交当前本机图谱；函数先验证成员关系和父子归属，
-- 成功后 Worker 才可按 source_id 安全读取来源。
-- ============================================================
create or replace function public.upsert_capture_source_graph(
  target_workspace_id uuid,
  graph jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  tab_payload jsonb := graph -> 'tab';
  competitor_payload jsonb := graph -> 'competitor';
  source_payload jsonb := graph -> 'source';
  graph_tab_id uuid;
  graph_competitor_id uuid;
  graph_source_id uuid;
begin
  if auth.uid() is null or not public.is_workspace_member(target_workspace_id) then
    raise exception '无权同步此研究空间。';
  end if;

  if tab_payload is null or competitor_payload is null or source_payload is null then
    raise exception '研究图谱不完整，无法同步来源。';
  end if;

  graph_tab_id := (tab_payload ->> 'id')::uuid;
  graph_competitor_id := (competitor_payload ->> 'id')::uuid;
  graph_source_id := (source_payload ->> 'id')::uuid;

  if (competitor_payload ->> 'tab_id')::uuid <> graph_tab_id
    or (source_payload ->> 'tab_id')::uuid <> graph_tab_id
    or (source_payload ->> 'competitor_id')::uuid <> graph_competitor_id then
    raise exception '研究图谱关系不一致，无法同步来源。';
  end if;

  insert into public.workspace_tabs (id, workspace_id, name, sort_order)
  values (
    graph_tab_id,
    target_workspace_id,
    left(coalesce(nullif(btrim(tab_payload ->> 'name'), ''), '未命名空间'), 80),
    greatest(coalesce((tab_payload ->> 'sort_order')::integer, 0), 0)
  )
  on conflict (id) do update set
    name = excluded.name,
    sort_order = excluded.sort_order
  where public.workspace_tabs.workspace_id = target_workspace_id;

  if not exists (
    select 1 from public.workspace_tabs
    where id = graph_tab_id and workspace_id = target_workspace_id
  ) then
    raise exception '研究空间页面不可用，无法同步来源。';
  end if;

  insert into public.competitors (id, workspace_id, tab_id, name, website, positioning, is_sample)
  values (
    graph_competitor_id,
    target_workspace_id,
    graph_tab_id,
    left(coalesce(nullif(btrim(competitor_payload ->> 'name'), ''), '未命名竞品'), 120),
    coalesce(competitor_payload ->> 'website', ''),
    coalesce(competitor_payload ->> 'positioning', ''),
    coalesce((competitor_payload ->> 'is_sample')::boolean, false)
  )
  on conflict (id) do update set
    name = excluded.name,
    website = excluded.website,
    positioning = excluded.positioning,
    is_sample = excluded.is_sample
  where public.competitors.workspace_id = target_workspace_id
    and public.competitors.tab_id = graph_tab_id;

  if not exists (
    select 1 from public.competitors
    where id = graph_competitor_id
      and workspace_id = target_workspace_id
      and tab_id = graph_tab_id
  ) then
    raise exception '来源所属竞品不可用，无法同步来源。';
  end if;

  insert into public.competitor_sources (
    id, workspace_id, tab_id, competitor_id, label, source_type, url,
    fetch_interval_hours, is_enabled
  )
  values (
    graph_source_id,
    target_workspace_id,
    graph_tab_id,
    graph_competitor_id,
    left(coalesce(nullif(btrim(source_payload ->> 'label'), ''), '未命名来源'), 120),
    source_payload ->> 'source_type',
    source_payload ->> 'url',
    greatest(least(coalesce((source_payload ->> 'fetch_interval_hours')::integer, 168), 720), 6),
    coalesce((source_payload ->> 'is_enabled')::boolean, true)
  )
  on conflict (id) do update set
    label = excluded.label,
    source_type = excluded.source_type,
    url = excluded.url,
    fetch_interval_hours = excluded.fetch_interval_hours,
    is_enabled = excluded.is_enabled
  where public.competitor_sources.workspace_id = target_workspace_id
    and public.competitor_sources.tab_id = graph_tab_id
    and public.competitor_sources.competitor_id = graph_competitor_id;

  if not exists (
    select 1 from public.competitor_sources
    where id = graph_source_id
      and workspace_id = target_workspace_id
      and tab_id = graph_tab_id
      and competitor_id = graph_competitor_id
  ) then
    raise exception '来源未能同步，请稍后重试。';
  end if;
end;
$$;

revoke all on function public.upsert_capture_source_graph(uuid, jsonb) from public;
grant execute on function public.upsert_capture_source_graph(uuid, jsonb) to authenticated;
