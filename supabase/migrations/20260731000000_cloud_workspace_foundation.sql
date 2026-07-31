-- ============================================================
-- 工作区基础：身份归属、时间戳与成员角色
-- ============================================================
create table public.workspaces (
  id uuid primary key,
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  name text not null check (length(btrim(name)) > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'member')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id)
);

-- ============================================================
-- Tab 范围：保留浏览器版多 Tab 的数据隔离与排序语义
-- ============================================================
create table public.workspace_tabs (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  name text not null check (length(btrim(name)) > 0),
  sort_order integer not null default 0 check (sort_order >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, id),
  unique (workspace_id, sort_order)
);

-- ============================================================
-- 调研实体：竞品、维度、证据与洞察均归属一个工作区 Tab
-- ============================================================
create table public.competitors (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  name text not null check (length(btrim(name)) > 0),
  website text not null default '',
  positioning text not null default '',
  is_sample boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade
);

create table public.dimensions (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  name text not null check (length(btrim(name)) > 0),
  sort_order integer not null default 0 check (sort_order >= 0),
  is_sample boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  unique (tab_id, name),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade
);

create table public.evidence (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  competitor_id uuid not null,
  title text not null check (length(btrim(title)) > 0),
  content_html text not null default '',
  images jsonb not null default '[]'::jsonb
    check (jsonb_typeof(images) = 'array'),
  is_sample boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, competitor_id)
    references public.competitors(workspace_id, tab_id, id) on delete cascade
);

create table public.insights (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  title text not null check (length(btrim(title)) > 0),
  fact_signals text not null default '',
  common_pattern text not null default '',
  key_difference text not null default '',
  opportunity_hypothesis text not null default '',
  action_recommendation text not null default '',
  is_sample boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade
);

-- ============================================================
-- 证据维度关系：以关系表替代数组并阻止跨 Tab 引用
-- ============================================================
create table public.evidence_dimensions (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  evidence_id uuid not null,
  dimension_id uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (evidence_id, dimension_id),
  foreign key (workspace_id, tab_id, evidence_id)
    references public.evidence(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, dimension_id)
    references public.dimensions(workspace_id, tab_id, id) on delete cascade
);

-- ============================================================
-- 洞察引用关系：竞品、维度和证据引用保持规范化且不可悬空
-- ============================================================
create table public.insight_competitors (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  insight_id uuid not null,
  competitor_id uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (insight_id, competitor_id),
  foreign key (workspace_id, tab_id, insight_id)
    references public.insights(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, competitor_id)
    references public.competitors(workspace_id, tab_id, id) on delete cascade
);

create table public.insight_dimensions (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  insight_id uuid not null,
  dimension_id uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (insight_id, dimension_id),
  foreign key (workspace_id, tab_id, insight_id)
    references public.insights(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, dimension_id)
    references public.dimensions(workspace_id, tab_id, id) on delete cascade
);

create table public.insight_evidence (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  insight_id uuid not null,
  evidence_id uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (insight_id, evidence_id),
  foreign key (workspace_id, tab_id, insight_id)
    references public.insights(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, evidence_id)
    references public.evidence(workspace_id, tab_id, id) on delete cascade
);

-- ============================================================
-- 对比矩阵：每个维度和竞品组合仅有一个单元格
-- ============================================================
create table public.matrix_cells (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  dimension_id uuid not null,
  competitor_id uuid not null,
  value text not null default '',
  is_sample boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (dimension_id, competitor_id),
  foreign key (workspace_id, tab_id, dimension_id)
    references public.dimensions(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, competitor_id)
    references public.competitors(workspace_id, tab_id, id) on delete cascade
);

-- ============================================================
-- 自动时间戳：所有可编辑记录统一维护 updated_at
-- ============================================================
create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_workspaces_updated_at before update on public.workspaces
for each row execute function public.set_updated_at();
create trigger set_workspace_members_updated_at before update on public.workspace_members
for each row execute function public.set_updated_at();
create trigger set_workspace_tabs_updated_at before update on public.workspace_tabs
for each row execute function public.set_updated_at();
create trigger set_competitors_updated_at before update on public.competitors
for each row execute function public.set_updated_at();
create trigger set_dimensions_updated_at before update on public.dimensions
for each row execute function public.set_updated_at();
create trigger set_evidence_updated_at before update on public.evidence
for each row execute function public.set_updated_at();
create trigger set_evidence_dimensions_updated_at before update on public.evidence_dimensions
for each row execute function public.set_updated_at();
create trigger set_insights_updated_at before update on public.insights
for each row execute function public.set_updated_at();
create trigger set_insight_competitors_updated_at before update on public.insight_competitors
for each row execute function public.set_updated_at();
create trigger set_insight_dimensions_updated_at before update on public.insight_dimensions
for each row execute function public.set_updated_at();
create trigger set_insight_evidence_updated_at before update on public.insight_evidence
for each row execute function public.set_updated_at();
create trigger set_matrix_cells_updated_at before update on public.matrix_cells
for each row execute function public.set_updated_at();

-- ============================================================
-- 成员检查：SECURITY DEFINER 隔离成员表 RLS，避免策略递归
-- ============================================================
create function public.is_workspace_member(target_workspace_id uuid) returns boolean language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.workspace_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()
  );
$$;

create function public.is_workspace_owner(target_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.workspace_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()
      and role = 'owner'
  );
$$;

revoke all on function public.is_workspace_member(uuid) from public;
revoke all on function public.is_workspace_owner(uuid) from public;
grant execute on function public.is_workspace_member(uuid) to authenticated;
grant execute on function public.is_workspace_owner(uuid) to authenticated;

-- ============================================================
-- 所有者建档：创建工作区后由数据库写入唯一 owner 成员
-- ============================================================
create function public.add_workspace_owner() returns trigger language plpgsql security definer set search_path = '' as $$ begin insert into public.workspace_members (
    workspace_id,
    user_id,
    role
  ) values (
    new.id,
    new.owner_user_id,
    'owner'
  );
  return new;
end;
$$;

revoke all on function public.add_workspace_owner() from public;

create trigger on_workspace_created
after insert on public.workspaces
for each row execute function public.add_workspace_owner();

-- ============================================================
-- 所有者保护：工作区归属与 owner 成员身份均不可被普通更新篡改
-- ============================================================
create function public.protect_workspace_ownership()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.owner_user_id <> old.owner_user_id then
    raise exception 'workspace owner cannot be changed';
  end if;
  return new;
end;
$$;

create trigger protect_workspace_ownership
before update on public.workspaces
for each row execute function public.protect_workspace_ownership();

-- ============================================================
-- RLS：工作区仅允许本人创建，数据由成员管理，成员授权仅限 owner
-- ============================================================
alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.workspace_tabs enable row level security;
alter table public.competitors enable row level security;
alter table public.dimensions enable row level security;
alter table public.evidence enable row level security;
alter table public.evidence_dimensions enable row level security;
alter table public.insights enable row level security;
alter table public.insight_competitors enable row level security;
alter table public.insight_dimensions enable row level security;
alter table public.insight_evidence enable row level security;
alter table public.matrix_cells enable row level security;

create policy "workspace members manage workspaces"
on public.workspaces
for all
to authenticated
using (public.is_workspace_member(id))
with check (
  public.is_workspace_member(id)
  or owner_user_id = auth.uid()
);

create policy "workspace members manage workspace_members"
on public.workspace_members
for all
to authenticated
using (
  public.is_workspace_owner(workspace_id)
  and role = 'member'
)
with check (
  public.is_workspace_owner(workspace_id)
  and role = 'member'
);

create policy "workspace members read own membership"
on public.workspace_members
for select
to authenticated
using (user_id = auth.uid());

create policy "workspace members manage workspace_tabs"
on public.workspace_tabs
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage competitors"
on public.competitors
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage dimensions"
on public.dimensions
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage evidence"
on public.evidence
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage evidence_dimensions"
on public.evidence_dimensions
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage insights"
on public.insights
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage insight_competitors"
on public.insight_competitors
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage insight_dimensions"
on public.insight_dimensions
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage insight_evidence"
on public.insight_evidence
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage matrix_cells"
on public.matrix_cells
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

-- ============================================================
-- 查询索引：支持按工作区、Tab 和常用引用键加载研究数据
-- ============================================================
create index workspace_members_user_id_idx
  on public.workspace_members(user_id);
create index workspace_tabs_workspace_id_idx
  on public.workspace_tabs(workspace_id);
create index competitors_tab_id_idx on public.competitors(tab_id);
create index dimensions_tab_id_idx on public.dimensions(tab_id);
create index evidence_tab_id_idx on public.evidence(tab_id);
create index evidence_competitor_id_idx on public.evidence(competitor_id);
create index evidence_dimensions_dimension_id_idx
  on public.evidence_dimensions(dimension_id);
create index insights_tab_id_idx on public.insights(tab_id);
create index insight_competitors_competitor_id_idx
  on public.insight_competitors(competitor_id);
create index insight_dimensions_dimension_id_idx
  on public.insight_dimensions(dimension_id);
create index insight_evidence_evidence_id_idx
  on public.insight_evidence(evidence_id);
create index matrix_cells_competitor_id_idx
  on public.matrix_cells(competitor_id);
