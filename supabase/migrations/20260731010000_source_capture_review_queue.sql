-- ============================================================
-- 公开来源采集：来源配置、执行记录与人工审核候选
-- 所有候选与正式证据分离，审核前绝不写入 evidence。
-- ============================================================
create table public.competitor_sources (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  competitor_id uuid not null,
  label text not null check (length(btrim(label)) > 0),
  source_type text not null check (source_type in (
    'product_page', 'changelog', 'help_center', 'pricing', 'blog', 'release_notes'
  )),
  url text not null check (url ~ '^https://'),
  fetch_interval_hours integer not null default 168
    check (fetch_interval_hours between 6 and 720),
  is_enabled boolean not null default true,
  last_fetched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  unique (competitor_id, url),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, competitor_id)
    references public.competitors(workspace_id, tab_id, id) on delete cascade
);

create table public.source_capture_runs (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  trigger_type text not null check (trigger_type in ('scheduled', 'manual')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'failed')),
  started_at timestamptz,
  completed_at timestamptz,
  source_count integer not null default 0 check (source_count >= 0),
  candidate_count integer not null default 0 check (candidate_count >= 0),
  error_message text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade
);

-- 每次成功读取保存不可变快照；同一来源的相同正文只保存一次。
create table public.source_capture_snapshots (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  source_id uuid not null,
  run_id uuid not null,
  canonical_url text not null check (canonical_url ~ '^https://'),
  extracted_text text not null default '',
  content_hash text not null check (length(btrim(content_hash)) >= 16),
  http_status integer not null check (http_status between 200 and 599),
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  unique (source_id, content_hash),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, source_id)
    references public.competitor_sources(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, run_id)
    references public.source_capture_runs(workspace_id, tab_id, id) on delete cascade
);

create table public.source_capture_candidates (
  id uuid primary key,
  workspace_id uuid not null,
  tab_id uuid not null,
  competitor_id uuid not null,
  source_id uuid not null,
  run_id uuid not null,
  snapshot_id uuid not null,
  source_url text not null check (source_url ~ '^https://'),
  title text not null check (length(btrim(title)) > 0),
  summary text not null default '',
  published_at timestamptz,
  content_hash text not null check (length(btrim(content_hash)) >= 16),
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  unique (source_id, content_hash),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, competitor_id)
    references public.competitors(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, source_id)
    references public.competitor_sources(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, run_id)
    references public.source_capture_runs(workspace_id, tab_id, id) on delete cascade,
  foreign key (workspace_id, tab_id, snapshot_id)
    references public.source_capture_snapshots(workspace_id, tab_id, id) on delete cascade
);

-- 采集任务按来源和时间查询，审核队列按 Tab、状态与最新候选查询。
create index competitor_sources_due_for_fetch_idx
on public.competitor_sources (is_enabled, last_fetched_at);
create index source_capture_snapshots_history_idx
on public.source_capture_snapshots (source_id, fetched_at desc);
create index source_capture_candidates_review_queue_idx
on public.source_capture_candidates (workspace_id, tab_id, status, created_at desc);

create trigger set_competitor_sources_updated_at
before update on public.competitor_sources
for each row execute function public.set_updated_at();
create trigger set_source_capture_runs_updated_at
before update on public.source_capture_runs
for each row execute function public.set_updated_at();
create trigger set_source_capture_candidates_updated_at
before update on public.source_capture_candidates
for each row execute function public.set_updated_at();

-- ============================================================
-- RLS：采集来源、运行和候选只向同一工作区成员开放。
-- 后台采集器使用 Supabase service role，不经浏览器暴露。
-- ============================================================
alter table public.competitor_sources enable row level security;
alter table public.source_capture_runs enable row level security;
alter table public.source_capture_snapshots enable row level security;
alter table public.source_capture_candidates enable row level security;

create policy "workspace members manage competitor_sources"
on public.competitor_sources
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage source_capture_runs"
on public.source_capture_runs
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage source_capture_snapshots"
on public.source_capture_snapshots
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members manage source_capture_candidates"
on public.source_capture_candidates
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));
