-- ============================================================
-- 工作区启动修复：拆分首次 owner 插入与既有成员访问策略
-- 避免首次登录在成员触发器建立关系前进入 member-only 更新路径。
-- ============================================================
drop policy if exists "workspace members manage workspaces" on public.workspaces;

create policy "authenticated users bootstrap own workspace"
on public.workspaces
for insert
to authenticated
with check (owner_user_id = auth.uid());

create policy "workspace members read workspaces"
on public.workspaces
for select
to authenticated
using (public.is_workspace_member(id));

create policy "workspace members update workspaces"
on public.workspaces
for update
to authenticated
using (public.is_workspace_member(id))
with check (public.is_workspace_member(id));

create policy "workspace owners delete workspaces"
on public.workspaces
for delete
to authenticated
using (public.is_workspace_owner(id));

-- 解析函数显式校验调用者，只插入自己的工作区；唯一冲突改为重新读取，
-- 不再用 ON CONFLICT UPDATE 触发尚未具备成员关系的 RLS 更新检查。
create or replace function public.resolve_user_workspace(workspace_name text default '我的研究空间')
returns public.workspaces
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved public.workspaces;
begin
  if auth.uid() is null then
    raise exception 'authentication required';
  end if;

  select * into resolved
  from public.workspaces
  where owner_user_id = auth.uid();

  if resolved.id is null then
    begin
      insert into public.workspaces (id, owner_user_id, name)
      values (
        gen_random_uuid(),
        auth.uid(),
        coalesce(nullif(btrim(workspace_name), ''), '我的研究空间')
      )
      returning * into resolved;
    exception when unique_violation then
      select * into resolved
      from public.workspaces
      where owner_user_id = auth.uid();
    end;
  end if;

  if resolved.owner_user_id is distinct from auth.uid() then
    raise exception 'workspace ownership mismatch';
  end if;
  return resolved;
end;
$$;

revoke all on function public.resolve_user_workspace(text) from public;
grant execute on function public.resolve_user_workspace(text) to authenticated;
