-- ============================================================
-- 来源候选：按工作区 Tab 收纳待审核的外部来源
-- ============================================================
create table public.source_candidates (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  tab_id uuid not null,
  url text not null check (length(btrim(url)) > 0),
  title text not null default '',
  summary text not null default '',
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  submitted_by uuid not null references auth.users(id) on delete restrict,
  reviewed_by uuid references auth.users(id) on delete restrict,
  reviewed_at timestamptz,
  review_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, tab_id, id),
  unique (workspace_id, tab_id, url),
  foreign key (workspace_id, tab_id)
    references public.workspace_tabs(workspace_id, id) on delete cascade,
  check (
    (status = 'pending' and reviewed_by is null and reviewed_at is null)
    or
    (status in ('approved', 'rejected') and reviewed_by is not null and reviewed_at is not null)
  )
);

-- ============================================================
-- 审核流水：保存操作者、状态变化、理由与当时的完整候选快照
-- ============================================================
create table public.source_candidate_audits (
  id bigint generated always as identity primary key,
  source_candidate_id uuid not null,
  workspace_id uuid not null,
  tab_id uuid not null,
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  action text not null check (action in ('created', 'status_changed')),
  old_status text check (old_status is null or old_status in ('pending', 'approved', 'rejected')),
  new_status text not null check (new_status in ('pending', 'approved', 'rejected')),
  reason text,
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (workspace_id, tab_id, source_candidate_id)
    references public.source_candidates(workspace_id, tab_id, id) on delete cascade
);

-- ============================================================
-- 自动审计：候选创建和审核状态变化均由数据库写入只读流水
-- ============================================================
create function public.audit_source_candidate_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  audit_actor_user_id uuid;
begin
  if tg_op = 'INSERT' then
    audit_actor_user_id := coalesce(auth.uid(), new.submitted_by);

    insert into public.source_candidate_audits (
      source_candidate_id,
      workspace_id,
      tab_id,
      actor_user_id,
      action,
      old_status,
      new_status,
      reason,
      snapshot
    ) values (
      new.id,
      new.workspace_id,
      new.tab_id,
      audit_actor_user_id,
      'created',
      null,
      new.status,
      new.review_reason,
      to_jsonb(new)
    );
  elsif new.status is distinct from old.status then
    audit_actor_user_id := coalesce(auth.uid(), new.reviewed_by, new.submitted_by);

    insert into public.source_candidate_audits (
      source_candidate_id,
      workspace_id,
      tab_id,
      actor_user_id,
      action,
      old_status,
      new_status,
      reason,
      snapshot
    ) values (
      new.id,
      new.workspace_id,
      new.tab_id,
      audit_actor_user_id,
      'status_changed',
      old.status,
      new.status,
      new.review_reason,
      to_jsonb(new)
    );
  end if;

  return new;
end;
$$;

revoke all on function public.audit_source_candidate_change() from public;

create trigger audit_source_candidate_change
after insert or update of status on public.source_candidates
for each row execute function public.audit_source_candidate_change();

create trigger set_source_candidates_updated_at
before update on public.source_candidates
for each row execute function public.set_updated_at();

-- ============================================================
-- RLS：成员管理本工作区候选，但审核流水仅允许成员读取
-- ============================================================
alter table public.source_candidates enable row level security;
alter table public.source_candidate_audits enable row level security;

create policy "workspace members manage source_candidates"
on public.source_candidates
for all
to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy "workspace members read source_candidate_audits"
on public.source_candidate_audits
for select
to authenticated
using (public.is_workspace_member(workspace_id));

-- ============================================================
-- 查询索引：支持按 Tab、审核队列和候选历史加载数据
-- ============================================================
create index source_candidates_tab_status_created_at_idx
  on public.source_candidates(tab_id, status, created_at desc);
create index source_candidates_submitted_by_idx
  on public.source_candidates(submitted_by);
create index source_candidate_audits_candidate_created_at_idx
  on public.source_candidate_audits(source_candidate_id, created_at);
create index source_candidate_audits_workspace_id_idx
  on public.source_candidate_audits(workspace_id);
