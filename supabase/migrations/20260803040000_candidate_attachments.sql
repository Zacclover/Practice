-- ============================================================
-- Preview 候选附件：私有对象由 Worker 管理，浏览器仅能按工作区读取元数据。
-- ============================================================
insert into storage.buckets (id, name, public)
values ('candidate-attachments', 'candidate-attachments', false)
on conflict (id) do nothing;

create table public.candidate_attachments (
  id uuid primary key,
  candidate_id uuid not null references public.source_capture_candidates(id) on delete cascade,
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  source_url text not null check (source_url ~ '^https://'),
  object_path text not null unique,
  media_type text not null check (media_type in ('image/jpeg', 'image/png', 'image/webp', 'image/gif')),
  byte_size bigint not null check (byte_size >= 0 and byte_size <= 5242880),
  created_at timestamptz not null default now()
);

create index candidate_attachments_candidate_id_idx on public.candidate_attachments(candidate_id);
create index candidate_attachments_workspace_id_idx on public.candidate_attachments(workspace_id);

alter table public.candidate_attachments enable row level security;
create policy "workspace members read candidate attachments"
on public.candidate_attachments for select to authenticated
using (public.is_workspace_member(workspace_id));

-- 新建表默认不向 authenticated 授权；先授予 SELECT，再由上方 RLS 严格限制为所属 workspace。
grant select on table public.candidate_attachments to authenticated;
grant select, insert, delete on table public.candidate_attachments to service_role;
-- Worker 以 service_role 删除 Candidate，需显式拥有 DELETE；RLS 以用户成员校验在 Worker 之前完成。
grant delete on table public.source_capture_candidates to service_role;
